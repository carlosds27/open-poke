from pydantic import BaseModel
from typing import List, Dict, Any

class PerplexitySearchResponse(BaseModel):
    response: str
    citations: List[str]
    usage_metadata: Dict[str, Any]