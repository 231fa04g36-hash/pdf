from typing import Any, Optional, List

class AppException(Exception):
    """Base exception class for all custom application errors."""
    def __init__(
        self, 
        message: str, 
        status_code: int = 500, 
        errors: Optional[List[Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.errors = errors or []

class NotFoundException(AppException):
    """Raised when a resource is not found."""
    def __init__(self, message: str = "Resource not found", errors: Optional[List[Any]] = None):
        super().__init__(message=message, status_code=404, errors=errors)

class ValidationException(AppException):
    """Raised when request payload or data validation fails."""
    def __init__(self, message: str = "Validation failed", errors: Optional[List[Any]] = None):
        super().__init__(message=message, status_code=422, errors=errors)

class UnauthorizedException(AppException):
    """Raised when authentication credentials fail or are missing."""
    def __init__(self, message: str = "Unauthorized access", errors: Optional[List[Any]] = None):
        super().__init__(message=message, status_code=401, errors=errors)

class ForbiddenException(AppException):
    """Raised when permissions are insufficient."""
    def __init__(self, message: str = "Access forbidden", errors: Optional[List[Any]] = None):
        super().__init__(message=message, status_code=403, errors=errors)

class ExternalServiceException(AppException):
    """Raised when external downstream APIs (OpenAI, Firebase, etc.) fail."""
    def __init__(self, message: str = "Downstream service error", errors: Optional[List[Any]] = None):
        super().__init__(message=message, status_code=502, errors=errors)

class RateLimitException(AppException):
    """Raised when rate limit is exceeded."""
    def __init__(self, message: str = "Too many requests. Please try again later.", errors: Optional[List[Any]] = None):
        super().__init__(message=message, status_code=429, errors=errors)

class InvalidFileTypeException(AppException):
    """Raised when uploaded file is not a valid PDF."""
    def __init__(self, message: str = "Invalid file type. Only PDF documents are supported.", errors: Optional[List[Any]] = None):
        super().__init__(message=message, status_code=400, errors=errors)

class FileTooLargeException(AppException):
    """Raised when file exceeds the maximum size limit."""
    def __init__(self, message: str = "File too large. Maximum size limit is 10MB.", errors: Optional[List[Any]] = None):
        super().__init__(message=message, status_code=413, errors=errors)

class CorruptedFileException(AppException):
    """Raised when the PDF file is corrupted or unreadable."""
    def __init__(self, message: str = "The PDF file appears to be corrupted or unreadable.", errors: Optional[List[Any]] = None):
        super().__init__(message=message, status_code=422, errors=errors)

class PasswordProtectedException(AppException):
    """Raised when the PDF file is password protected."""
    def __init__(self, message: str = "Password protected PDF files are not supported.", errors: Optional[List[Any]] = None):
        super().__init__(message=message, status_code=422, errors=errors)

class PageLimitExceededException(AppException):
    """Raised when the PDF page count exceeds maximum allowable limit."""
    def __init__(self, message: str = "PDF page count exceeds maximum allowable limit of 100 pages.", errors: Optional[List[Any]] = None):
        super().__init__(message=message, status_code=422, errors=errors)

class EmbeddingModelMismatchException(AppException):
    """Raised when query embedding model differs from the model used to index the document."""
    def __init__(self, message: str = "Embedding model mismatch: query model does not match document indexing model.", errors: Optional[List[Any]] = None):
        super().__init__(message=message, status_code=400, errors=errors)

class DocumentNotIndexedException(AppException):
    """Raised when query is made against a missing or deleted vector collection."""
    def __init__(self, message: str = "The document has not been indexed or the vector store collection is missing.", errors: Optional[List[Any]] = None):
        super().__init__(message=message, status_code=404, errors=errors)

class OllamaUnavailableException(AppException):
    """Raised when the local Ollama service is unavailable at runtime."""
    def __init__(self, message: str = "The local AI model (Ollama) is not running. Please start the Ollama application on your machine and try again.", errors: Optional[List[Any]] = None):
        super().__init__(message=message, status_code=503, errors=errors)

class VectorStoreContaminationException(AppException):
    """Raised when the vector store collection contains chunks from a different document."""
    def __init__(self, message: str = "Vector store contamination detected: collection contains chunks from another document.", errors: Optional[List[Any]] = None):
        super().__init__(message=message, status_code=500, errors=errors)





