from .base import BaseSchema

class TestSchema(BaseSchema):
    """
    Throwaway test schema to verify camelCase serialization contract.
    """
    document_id: str
    page_count: int
    ocr_triggered: bool
    user_friendly_name: str
