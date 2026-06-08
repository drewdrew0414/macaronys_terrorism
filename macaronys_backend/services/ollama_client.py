from __future__ import annotations

import httpx

from macaronys_backend.config import Settings
from macaronys_backend.logging_config import logger


class OllamaGemmaClient:
    """Thin async client for Ollama Gemma chat generation."""

    def __init__(self, config: Settings):
        self.config = config
        self._model_checked = False

    async def ensure_model_ready(self) -> None:
        if self._model_checked:
            return

        async with httpx.AsyncClient(
            base_url=self.config.ollama_host,
            timeout=self.config.ollama_timeout_seconds,
        ) as client:
            tags_response = await client.get("/api/tags")
            tags_response.raise_for_status()
            tags = tags_response.json().get("models", [])
            installed = {model.get("name") for model in tags if isinstance(model, dict)}

            if self.config.ollama_model not in installed:
                if not self.config.ollama_auto_pull:
                    logger.warning(
                        "Ollama model %s is not installed. Pull it manually or set "
                        "OLLAMA_AUTO_PULL=true.",
                        self.config.ollama_model,
                    )
                else:
                    pull_response = await client.post(
                        "/api/pull",
                        json={"name": self.config.ollama_model, "stream": False},
                    )
                    pull_response.raise_for_status()

        self._model_checked = True

    async def generate(self, prompt: str) -> str:
        await self.ensure_model_ready()
        async with httpx.AsyncClient(
            base_url=self.config.ollama_host,
            timeout=self.config.ollama_timeout_seconds,
        ) as client:
            response = await client.post(
                "/api/chat",
                json={
                    "model": self.config.ollama_model,
                    "stream": False,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a strict JSON extraction engine.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "options": {"temperature": 0.1},
                },
            )
            response.raise_for_status()
            payload = response.json()
            content = (payload.get("message") or {}).get("content")
            if not content:
                raise RuntimeError("Ollama returned an empty response")
            return str(content)
