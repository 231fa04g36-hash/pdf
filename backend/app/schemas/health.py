from .base import BaseSchema

class HealthData(BaseSchema):
    """
    Schema for health status info.
    """
    status: str
    database: str
    chroma_db: str
