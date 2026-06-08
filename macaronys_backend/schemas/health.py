from __future__ import annotations

from pydantic import BaseModel


class HealthRead(BaseModel):
    status: str
    app: str
    ai_execution_mode: str
    ollama_model: str
    database: str
