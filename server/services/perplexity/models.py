from pydantic import BaseModel
from typing import List, Dict, Any

class PerplexitySearchResponse(BaseModel):
    response: str
    citations: List[Dict[str, Any]]
    usage_metadata: Dict[str, Any]