from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.core.exceptions import AppException
import logging

logger = logging.getLogger("app.exceptions")

async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    # Use standard logger configurations
    logger.error(f"Application error on {request.url.path}: {exc.message} (Status: {exc.status_code})")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.message,
            "errors": exc.errors,
        },
    )

async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = []
    for error in exc.errors():
        loc = ".".join(str(l) for l in error.get("loc", []))
        errors.append({
            "field": loc,
            "message": error.get("msg", ""),
            "type": error.get("type", ""),
        })
    
    logger.warning(f"Validation error on {request.url.path}: {errors}")
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "message": "Validation failed",
            "errors": errors,
        },
    )

async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(f"Unhandled system error occurred on {request.url.path}:")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "An unexpected server error occurred.",
            "errors": [{"detail": "Internal server error occurred."}],
        },
    )

"""
Custom Exceptions to HTTP Status Code Mapping:
-------------------------------------------------------------------------
Exception Class                  | Status Code | Description
-------------------------------------------------------------------------
UnauthorizedException            | 401         | Auth token missing/invalid
ForbiddenException               | 403         | Access to resource forbidden
NotFoundException                | 404         | Resource not found
DocumentNotIndexedException      | 404         | ChromaDB collection missing
EmbeddingModelMismatchException  | 400         | Model used != indexing model
InvalidFileTypeException         | 400         | File upload is not PDF
FileTooLargeException            | 413         | Uploaded file size > 10MB
CorruptedFileException           | 422         | PDF cannot be parsed
PasswordProtectedException       | 422         | PDF is password-protected
PageLimitExceededException       | 422         | PDF pages > 100 limit
ValidationException              | 422         | Request validation failed
"""

# OLD: Import list without VectorStoreContaminationException, kept for reference.
# from app.core.exceptions import (
#     InvalidFileTypeException,
#     FileTooLargeException,
#     CorruptedFileException,
#     PasswordProtectedException,
#     EmbeddingModelMismatchException,
#     DocumentNotIndexedException,
#     UnauthorizedException,
#     ForbiddenException,
#     NotFoundException,
#     ValidationException,
#     PageLimitExceededException,
#     OllamaUnavailableException
# )

from app.core.exceptions import (
    InvalidFileTypeException,
    FileTooLargeException,
    CorruptedFileException,
    PasswordProtectedException,
    EmbeddingModelMismatchException,
    DocumentNotIndexedException,
    UnauthorizedException,
    ForbiddenException,
    NotFoundException,
    ValidationException,
    PageLimitExceededException,
    OllamaUnavailableException,
    VectorStoreContaminationException
)

def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)

    # Explicit registrations for individual custom exceptions
    app.add_exception_handler(InvalidFileTypeException, app_exception_handler)
    app.add_exception_handler(FileTooLargeException, app_exception_handler)
    app.add_exception_handler(CorruptedFileException, app_exception_handler)
    app.add_exception_handler(PasswordProtectedException, app_exception_handler)
    app.add_exception_handler(EmbeddingModelMismatchException, app_exception_handler)
    app.add_exception_handler(DocumentNotIndexedException, app_exception_handler)
    app.add_exception_handler(UnauthorizedException, app_exception_handler)
    app.add_exception_handler(ForbiddenException, app_exception_handler)
    app.add_exception_handler(NotFoundException, app_exception_handler)
    app.add_exception_handler(ValidationException, app_exception_handler)
    app.add_exception_handler(PageLimitExceededException, app_exception_handler)
    
    # OLD: OllamaUnavailableException handler registration only, kept for reference
    # app.add_exception_handler(OllamaUnavailableException, app_exception_handler)
    
    app.add_exception_handler(OllamaUnavailableException, app_exception_handler)
    app.add_exception_handler(VectorStoreContaminationException, app_exception_handler)


