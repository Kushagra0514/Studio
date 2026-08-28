"""Shared data models for the Studio backend."""

from typing import Any, Dict

from pydantic import BaseModel, Field


class Chunk(BaseModel):
    id: str
    text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
