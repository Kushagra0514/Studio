from pydantic import BaseModel, Field
from typing import Dict, Any, List

class Chunk(BaseModel):
    id: str
    text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
