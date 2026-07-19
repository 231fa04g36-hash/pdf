import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logging_config import setup_logging
from app.core.firebase import initialize_firebase
from app.exception_handlers import register_exception_handlers
from app.routers import health_router, auth_router, document_router, chat_router, conversation_router

# Initialize logging system
setup_logging("DEBUG" if settings.ENVIRONMENT == "development" else "INFO")
logger = logging.getLogger("app.main")

# Instantiate FastAPI Application
app = FastAPI(
    title="PDF Chatbot API",
    description="FastAPI Backend for PDF RAG Chatbot",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# Request body size limiting at ASGI/server level (15MB max)
from starlette.types import ASGIApp, Receive, Scope, Send
from fastapi.responses import JSONResponse

class LimitRequestSizeMiddleware:
    def __init__(self, app: ASGIApp, max_content_size: int = 15 * 1024 * 1024):
        self.app = app
        self.max_content_size = max_content_size

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            content_length = 0
            for header_name, header_value in scope.get("headers", []):
                if header_name == b"content-length":
                    try:
                        content_length = int(header_value)
                    except ValueError:
                        pass
                    break
            
            if content_length > self.max_content_size:
                response = JSONResponse(
                    status_code=413,
                    content={
                        "success": False,
                        "message": "Request entity too large",
                        "errors": [{"detail": f"Request size exceeds limit of {self.max_content_size} bytes."}]
                    }
                )
                await response(scope, receive, send)
                return

            bytes_received = 0
            async def wrapped_receive() -> dict:
                nonlocal bytes_received
                message = await receive()
                if message["type"] == "http.request":
                    body_len = len(message.get("body", b""))
                    bytes_received += body_len
                    if bytes_received > self.max_content_size:
                        raise ValueError("Request body size limit exceeded")
                return message

            try:
                await self.app(scope, wrapped_receive, send)
                return
            except ValueError as e:
                if str(e) == "Request body size limit exceeded":
                    response = JSONResponse(
                        status_code=413,
                        content={
                            "success": False,
                            "message": "Request entity too large",
                            "errors": [{"detail": "Streamed request body exceeded limit."}]
                        }
                    )
                    await response(scope, receive, send)
                    return
                raise e
        
        await self.app(scope, receive, send)

# Register request size limiter at server level
app.add_middleware(LimitRequestSizeMiddleware, max_content_size=15 * 1024 * 1024)

# CORS configuration (strictly explicit, no wildcard allowed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register custom exceptions handlers mapping to envelope format
register_exception_handlers(app)

# Include routers (API Version prefix applied globally)
app.include_router(health_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(document_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")
app.include_router(conversation_router, prefix="/api/v1")


def pre_warm_ollama_model() -> None:
    import httpx
    url = f"{settings.OLLAMA_API_URL}/api/generate"
    payload = {
        "model": settings.OLLAMA_MODEL,
        "keep_alive": "30m"
    }
    try:
        logger.info(f"Pre-warming local Ollama model '{settings.OLLAMA_MODEL}' with keep_alive='30m'...")
        resp = httpx.post(url, json=payload, timeout=60.0)
        if resp.status_code == 200:
            logger.info(f"Ollama model '{settings.OLLAMA_MODEL}' pre-warming request successful.")
            
            # Verify loaded models in memory using /api/ps
            try:
                ps_url = f"{settings.OLLAMA_API_URL}/api/ps"
                ps_resp = httpx.get(ps_url, timeout=3.0)
                if ps_resp.status_code == 200:
                    ps_data = ps_resp.json()
                    models = [m.get("name") for m in ps_data.get("models", [])]
                    logger.info(f"[Ollama PS - Startup Pre-warm] Loaded models: {models} | Details: {ps_data}")
                else:
                    logger.warning(f"Ollama /api/ps check failed with status: {ps_resp.status_code}")
            except Exception as ps_err:
                logger.warning(f"Failed to query Ollama /api/ps on startup: {ps_err}")
        else:
            logger.warning(f"Ollama model pre-warming returned status code {resp.status_code}")
    except Exception as err:
        logger.warning(f"Failed to pre-warm Ollama model: {err}")


# OLD: startup event initializing only Firebase SDK — replaced below to add local Ollama server connection check during startup
# @app.on_event("startup")
# async def startup_event() -> None:
#     # Initialize Firebase Admin SDK
#     initialize_firebase()
#     logger.info(f"PDF Chatbot backend started in environment: '{settings.ENVIRONMENT}'")
#     logger.info(f"CORS origins configured: {settings.cors_origins_list}")

@app.on_event("startup")
async def startup_event() -> None:
    # Initialize Firebase Admin SDK
    initialize_firebase()
    
    # Pre-warm local embedding model in the background so it doesn't block startup or health check
    if settings.EMBEDDING_PROVIDER == "local":
        import asyncio
        from app.services.embedding_service import embedding_service
        logger.info("Scheduling local embedding model pre-warming task in the background...")
        asyncio.create_task(asyncio.to_thread(embedding_service.pre_load_local_model))
    else:
        logger.info("Skipping local embedding pre-warming because EMBEDDING_PROVIDER is 'openai'.")
    
    # Fast fail check for Ollama local server
    if settings.LLM_PROVIDER.lower() == "ollama":
        import httpx
        logger.info(f"Performing fast fail startup check for local Ollama server at '{settings.OLLAMA_API_URL}'...")
        try:
            # OLD: simple reachability check without model quantization verification, kept for reference
            # resp = httpx.get(settings.OLLAMA_API_URL, timeout=3.0)
            # if resp.status_code != 200:
            #     raise RuntimeError(f"Ollama server returned status code {resp.status_code}")
            # logger.info("Ollama server is verified reachable.")
            
            resp = httpx.get(settings.OLLAMA_API_URL, timeout=3.0)
            if resp.status_code != 200:
                raise RuntimeError(f"Ollama server returned status code {resp.status_code}")
            logger.info("Ollama server is verified reachable.")
            
            # Start pre-warming local Ollama model in the background
            import asyncio
            logger.info("Scheduling local Ollama model pre-warming task in the background...")
            asyncio.create_task(asyncio.to_thread(pre_warm_ollama_model))
            
            # Query Ollama's /api/tags to confirm model quantization
            try:
                tags_resp = httpx.get(f"{settings.OLLAMA_API_URL}/api/tags", timeout=3.0)
                if tags_resp.status_code == 200:
                    tags_data = tags_resp.json()
                    models_list = tags_data.get("models", [])
                    
                    # Find matching model
                    matching_model = None
                    target_model = settings.OLLAMA_MODEL.lower()
                    
                    for m in models_list:
                        m_name = m.get("name", "").lower()
                        # Match exact name, or name without tag, or name with :latest
                        if m_name == target_model or m_name.split(":")[0] == target_model.split(":")[0]:
                            matching_model = m
                            break
                            
                    if matching_model:
                        q_level = matching_model.get("details", {}).get("quantization_level", "")
                        m_name = matching_model.get("name", "")
                        
                        # Check quantization level or name for markers (e.g. q4, q5, q8, q2, q3, q6, int4, int8)
                        is_quantized = any(q in q_level.lower() or q in m_name.lower() for q in ["q4", "q5", "q8", "q2", "q3", "q6", "int4", "int8"])
                        
                        if not is_quantized:
                            logger.warning(
                                f"WARNING: The configured Ollama model '{settings.OLLAMA_MODEL}' appears to be full-precision "
                                f"(quantization: '{q_level or 'unknown'}'). Running a full-precision model on CPU can "
                                f"be 2-5x slower. Consider using a 4-bit quantized model (e.g., mistral:7b-instruct-q4_0)."
                            )
                        else:
                            logger.info(f"Ollama model '{m_name}' verified as quantized (level: {q_level or 'detected'}).")
                    else:
                        logger.warning(
                            f"WARNING: The configured Ollama model '{settings.OLLAMA_MODEL}' was not found in local models tags list. "
                            f"Please ensure it has been pulled ('ollama pull {settings.OLLAMA_MODEL}')."
                        )
                else:
                    logger.warning(f"Could not retrieve Ollama model tags for verification: HTTP {tags_resp.status_code}")
            except Exception as tags_err:
                logger.warning(f"Failed to check Ollama model quantization details: {tags_err}")

        except Exception as err:
            critical_msg = (
                f"\n================================================================================\n"
                f"CRITICAL ERROR: Local Ollama server is not reachable at '{settings.OLLAMA_API_URL}'.\n"
                f"Please ensure Ollama is installed and running locally, or switch LLM_PROVIDER config.\n"
                f"Error details: {err}\n"
                f"================================================================================"
            )
            logger.critical(critical_msg)
            # OLD: exited the app on failure, kept for reference
            # import sys
            # sys.exit(1)

    logger.info(f"PDF Chatbot backend started in environment: '{settings.ENVIRONMENT}'")
    logger.info(f"CORS origins configured: {settings.cors_origins_list}")

@app.on_event("shutdown")
async def shutdown_event() -> None:
    logger.info("PDF Chatbot backend shutting down...")

