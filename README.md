# PDF Chatbot

A production-quality PDF RAG (Retrieval-Augmented Generation) Chatbot application, split into a React + Vite frontend and a FastAPI backend.

## Repository Structure

- `frontend/` - React 18 + Vite frontend application (Javascript, Plain CSS Modules, Zustand/Context, Axios).
- `backend/` - FastAPI backend application (to be created).
- `venv/` - Python virtual environment for local backend dependencies.

## Design and Guidelines

This project strictly adheres to 6 core engineering pillars of production quality:
1. **Clean Project Structure**
2. **High Code Quality** (SOLID, DRY, ESLint + Prettier)
3. **Optimized State Management** (Zustand for high-frequency stream state, React Context for static Auth state)
4. **Consistent API Design** (standardized envelope structures)
5. **Robust Error Handling & File Upload Validation**
6. **Polished GitHub & Repository Documentation**

For more details on coding practices, see [.agents/AGENTS.md](file:///.agents/AGENTS.md).

## Getting Started

### Frontend Setup

Refer to the [Frontend README](file:///frontend/README.md) for detailed installation and development instructions.

> For zero-cost local development, set `LLM_PROVIDER=ollama` and `EMBEDDING_PROVIDER=local` — this requires Ollama installed locally with the quantized model pulled once (`ollama pull mistral:7b-instruct-q4_0`) — no API keys or costs incurred during development. Switch to `LLM_PROVIDER=openai` only for final testing/demo, per the original project plan's cost-management guidance.

## RAG Evaluation Framework

To perform objective, metrics-driven evaluation of RAG pipeline changes (instead of relying on "vibe checks"), use the standalone evaluation script. It uses **Ragas** to assess context precision, recall, faithfulness, and relevancy metrics on a set of 15 golden questions.

### Running the Evaluation
1. Configure your environment variables in `.env` (ensure `OPENAI_API_KEY` is set to enable Ragas metrics calculations, as it standardly uses LLM-as-a-judge).
2. Run the evaluation script:
   ```bash
   cd backend
   ..\venv\Scripts\python scripts/evaluate_retrieval.py
   ```
3. The script automatically generates a sample PDF, indexes it, runs 15 evaluation queries through the active retrieval pipeline, calculates metrics, prints a summary table to the console, and writes details to `tests/fixtures/eval_results.csv`.

#   p d f - c h a t b o t  