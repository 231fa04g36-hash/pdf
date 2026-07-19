# PDF Chatbot Backend

FastAPI application for PDF Retrieval-Augmented Generation (RAG) Chatbot, structured with a strict layered architecture pattern.

## Request Flow Layering Contract
Every API endpoint MUST adhere to this request path:
`Router (validation & parsing) -> Service (business logic) -> Repository (query assembly) -> Database (data engine)`

*   **Routers**: Located under `app/routers/`. They are thin controllers, validating schemas and handing tasks directly to services.
*   **Services**: Located under `app/services/`. Contain core business logic, orchestrate repositories, external APIs (OpenAI), etc.
*   **Repositories**: Located under `app/repositories/`. Perform data queries, vector operations, SQL queries.
*   **Database / Vector DB**: ChromaDB and SQL database drivers.

## API camelCase Convention
All schemas returned by the API serialize automatically to camelCase to conform to the frontend contract. Write all response models to inherit from [BaseSchema](file:///app/schemas/base.py).

## Getting Started

### Installation
1. Ensure Python 3.11+ is installed.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set up environment:
   ```bash
   cp .env.example .env
   ```

### Running Server
To start the FastAPI development server:
```bash
python -m uvicorn app.main:app --reload --port 8000
```
API Documentation will be available at: [http://localhost:8000/api/docs](http://localhost:8000/api/docs)
Health checks can be queried at: [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)

> [!NOTE]
> For zero-cost local development, set `LLM_PROVIDER=ollama` and `EMBEDDING_PROVIDER=local` — this requires Ollama installed locally with a model pulled (e.g. `ollama pull mistral`) — no API keys or costs incurred during development. Switch to `LLM_PROVIDER=openai` only for final testing/demo, per the original project plan's cost-management guidance.

### Resetting Vector Store
Whenever switching between different test documents during development, run the reset utility script to wipe the local ChromaDB and BM25 persistent files completely clean. This avoids collection contamination or stale test data:
```bash
python scripts/reset_dev_vectorstore.py
```

### Performance & Hardware Fallbacks
When running the chatbot on CPU-only hardware, response latency can sometimes be higher due to the resource requirements of local 7B models (like Mistral). To address this, the pipeline has been optimized with:
- **Parallelized Hybrid Search**: Vector and keyword (BM25) searches run concurrently to minimize retrieval latency.
- **Dynamic Context Limits**: The context window size (`num_ctx`) is tightly calculated per request, avoiding Ollama's larger default.
- **Top-K Tuning**: Default candidate retrieval counts have been reduced to 10 to speed up reranking.

**Actionable Fallback Options**:
If generation latency remains higher than desired on CPU-only setups, consider the following configuration options:
1. **Use a smaller quantized model**: Switch `OLLAMA_MODEL` in `.env` to a lightweight model, such as `phi3:mini` (3.8B) or `llama3.2:3b-instruct-q4_0` (3B), which execute significantly faster on CPU.
2. **Switch to a Cloud LLM provider**: Change `LLM_PROVIDER` in `.env` to `openai` or `claude`. This shifts the heavy inference computation from local hardware to external APIs, yielding fast (sub-5 second) stream completions regardless of local CPU constraints.



