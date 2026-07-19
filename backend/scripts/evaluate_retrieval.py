import sys
import os
import json
import uuid
import fitz  # PyMuPDF

# Ensure parent directory (backend) is on python path for importing app services
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.models.document import Document
from app.services.pdf_parser_service import parse_pdf_pages
from app.services.chunker_service import chunk_document_pages
from app.services.embedding_service import embedding_service
from app.services.vector_store_service import vector_store_service
from app.services.chat_service import chat_service

def generate_sample_pdf(pdf_path: str):
    doc = fitz.open()
    rect = fitz.Rect(50, 50, 562, 742)  # Standard box layout to wrap lines and prevent clipping
    
    # Page 1
    page1 = doc.new_page()
    page1.insert_textbox(rect, "Section 1: Introduction to Antigravity Cloud\n\n"
                               "Antigravity Cloud is a high-performance serverless database service built specifically for modern cloud applications. "
                               "It provides sub-millisecond query latency and handles horizontal scaling automatically. "
                               "It was officially launched in October 2025 by a dedicated team of former Google systems engineers. "
                               "The primary interface is a REST API that supports JSON payloads.")
    
    # Page 2
    page2 = doc.new_page()
    page2.insert_textbox(rect, "Section 2: Pricing and Subscription Tiers\n\n"
                               "The pricing structure of Antigravity Cloud consists of three clear tiers:\n"
                               "1. Free Tier: Costs $0 per month, supports up to 10,000 read operations per month, and provides 1 GB of storage.\n"
                               "2. Developer Tier: Costs $29 per month, supports up to 1 million read operations, and provides 50 GB of storage.\n"
                               "3. Enterprise Tier: Costs $299 per month, supports unlimited operations, provides 1 TB of storage, and includes a dedicated support engineer.")
    
    # Page 3
    page3 = doc.new_page()
    page3.insert_textbox(rect, "Section 3: Security, Compliance and Replication\n\n"
                               "Security is built-in with end-to-end TLS 1.3 encryption for all queries in transit. "
                               "At rest, data is encrypted using AES-256. Authentication is handled via integration with Firebase Admin SDK, enabling secure token validation.\n"
                               "Antigravity Cloud is currently deployed across three cloud regions: us-east-1 (N. Virginia), eu-west-1 (Ireland), and ap-southeast-1 (Singapore). "
                               "Multi-region replication is fully automated with a maximum replication lag of 150 milliseconds.")
    
    doc.save(pdf_path)
    print(f"Generated sample PDF at: {pdf_path}")

def index_document(db, pdf_path: str, filename: str) -> Document:
    # Check if document already indexed in DB
    existing_doc = db.query(Document).filter(Document.filename == filename, Document.is_deleted == False).first()
    if existing_doc:
        print(f"Document '{filename}' already indexed. Reusing existing document ID: {existing_doc.id}")
        return existing_doc

    doc_id = uuid.uuid4()
    
    # Parse PDF
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()
    pages, _ = parse_pdf_pages(pdf_bytes)
    
    # Chunk PDF
    chunks = chunk_document_pages(pages)
    
    # Generate embeddings
    texts = [c["text"] for c in chunks]
    embeddings = embedding_service.generate_embeddings(texts)
    
    # Store in ChromaDB
    collection_name = vector_store_service.store_document_chunks(doc_id, chunks, embeddings)
    
    # Register in SQL database
    doc = Document(
        id=doc_id,
        user_id=uuid.UUID("00000000-0000-0000-0000-000000000000"), # system / test user
        filename=filename,
        page_count=len(pages),
        chroma_collection_id=collection_name,
        embedding_model=embedding_service.get_embedding_model_info(),
        is_deleted=False
    )
    db.add(doc)
    db.commit()
    print(f"Successfully indexed document '{filename}' with ID: {doc_id}")
    return doc

def run_evaluation():
    db = SessionLocal()
    
    fixtures_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tests", "fixtures")
    os.makedirs(fixtures_dir, exist_ok=True)
    
    # Paths
    pdf_path = os.path.join(fixtures_dir, "eval_sample.pdf")
    questions_json_path = os.path.join(fixtures_dir, "eval_questions.json")
    
    # 1. Generate sample PDF if it doesn't exist
    if not os.path.exists(pdf_path):
        generate_sample_pdf(pdf_path)
        
    # 2. Check if JSON questions exist
    if not os.path.exists(questions_json_path):
        print(f"Error: JSON questions file not found at: {questions_json_path}")
        return
        
    with open(questions_json_path, "r") as f:
        eval_set = json.load(f)
        
    # 3. Index sample PDF
    doc = index_document(db, pdf_path, "eval_sample.pdf")
    
    # 4. Run QA flow
    print("\nRunning RAG QA pipeline on evaluation questions...")
    eval_results = []
    
    for idx, item in enumerate(eval_set):
        question = item["question"]
        expected = item["expected_answer"]
        print(f"[{idx+1}/{len(eval_set)}] Question: {question}")
        
        generator = chat_service.generate_chat_stream(
            db=db,
            document_id=doc.id,
            conversation_id=None,
            question=question,
            request_id=uuid.uuid4(),
            user_id=None,
            session_id="eval-session"
        )
        
        answer_tokens = []
        citations_packet = None
        for chunk in generator:
            try:
                data = json.loads(chunk)
                if "token" in data:
                    answer_tokens.append(data["token"])
                elif "citations" in data:
                    citations_packet = data
            except Exception:
                pass
                
        answer = "".join(answer_tokens).strip()
        
        contexts = []
        if citations_packet and "citations" in citations_packet:
            for cit in citations_packet["citations"]:
                snippet = cit.get("snippet", "")
                if snippet:
                    contexts.append(snippet)
                    
        eval_results.append({
            "question": question,
            "answer": answer,
            "contexts": contexts,
            "ground_truth": expected
        })
        
    # 5. Evaluate using RAGAS if API key is present
    openai_key = os.getenv("OPENAI_API_KEY")
    
    try:
        import pandas as pd
        has_pandas = True
    except ImportError:
        has_pandas = False
    
    if not openai_key:
        print("\n" + "="*80)
        print("WARNING: 'OPENAI_API_KEY' environment variable not set.")
        print("Ragas requires an LLM-as-a-judge (standardly OpenAI) to compute faithfulness and relevancy metrics.")
        print("Please export your OpenAI key to compute context and answer metrics.")
        if has_pandas:
            print("Saving raw query responses and contexts to CSV for manual validation...")
        else:
            print("Saving raw query responses and contexts to JSON for manual validation...")
        print("="*80 + "\n")
        
        if has_pandas:
            df = pd.DataFrame(eval_results)
            csv_path = os.path.join(fixtures_dir, "eval_results_raw.csv")
            df.to_csv(csv_path, index=False)
            print(f"\nRaw RAG results saved to: {csv_path}")
        else:
            json_path = os.path.join(fixtures_dir, "eval_results_raw.json")
            with open(json_path, "w") as jf:
                json.dump(eval_results, jf, indent=2)
            print(f"\nRaw RAG results saved to JSON: {json_path}")
        
        # Print a simple summary view
        print("\nPipeline QA Results Preview:")
        for idx, r in enumerate(eval_results[:3]):
            print(f"\nQ: {r['question']}\nA: {r['answer']}\nContext count: {len(r['contexts'])}")
    else:
        try:
            from datasets import Dataset
            from ragas import evaluate
            from ragas.metrics import (
                faithfulness,
                answer_relevancy,
                context_precision,
                context_recall
            )
            
            print("\nFormatting evaluation dataset for RAGAS...")
            data = {
                "question": [r["question"] for r in eval_results],
                "answer": [r["answer"] for r in eval_results],
                "contexts": [r["contexts"] for r in eval_results],
                "ground_truth": [r["ground_truth"] for r in eval_results]
            }
            dataset = Dataset.from_dict(data)
            
            print("\nInvoking RAGAS evaluator...")
            score_result = evaluate(
                dataset,
                metrics=[
                    faithfulness,
                    answer_relevancy,
                    context_precision,
                    context_recall
                ]
            )
            
            if has_pandas:
                df = score_result.to_pandas()
                csv_path = os.path.join(fixtures_dir, "eval_results.csv")
                df.to_csv(csv_path, index=False)
                
                print("\n" + "="*80)
                print("EVALUATION METRICS SUMMARY")
                print("="*80)
                print(df.to_string(index=True))
                print("="*80)
                print(f"\nDetailed evaluation results saved to: {csv_path}")
                
                # Print averaged scores
                averages = df.mean(numeric_only=True)
                print("\nAverage Scores:")
                for metric, val in averages.items():
                    print(f" - {metric.capitalize()}: {val:.4f}")
            else:
                json_path = os.path.join(fixtures_dir, "eval_results.json")
                with open(json_path, "w") as jf:
                    json.dump(score_result, jf, indent=2)
                print(f"\nDetailed evaluation results saved to JSON: {json_path}")
            
        except Exception as eval_err:
            print(f"Error during Ragas evaluation metrics run: {eval_err}")
            print("Saving raw results as fallback...")
            if has_pandas:
                df = pd.DataFrame(eval_results)
                csv_path = os.path.join(fixtures_dir, "eval_results_raw.csv")
                df.to_csv(csv_path, index=False)
                print(f"Fallback raw results saved to: {csv_path}")
            else:
                json_path = os.path.join(fixtures_dir, "eval_results_raw.json")
                with open(json_path, "w") as jf:
                    json.dump(eval_results, jf, indent=2)
                print(f"Fallback raw results saved to JSON: {json_path}")

if __name__ == "__main__":
    run_evaluation()
