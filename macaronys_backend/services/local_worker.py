from __future__ import annotations

import asyncio

import httpx
from fastapi import status

from macaronys_backend.config import settings
from macaronys_backend.logging_config import logger
from macaronys_backend.services.ollama_client import OllamaGemmaClient


async def run_local_ai_worker() -> None:
    worker_count = max(1, settings.ai_worker_concurrency)
    if worker_count == 1:
        await _run_local_ai_worker_loop("local-ollama-gemma")
        return

    logger.info("starting %s local AI workers", worker_count)
    await asyncio.gather(
        *(
            _run_local_ai_worker_loop(f"local-ollama-gemma-{index + 1}")
            for index in range(worker_count)
        )
    )


async def _run_local_ai_worker_loop(worker_id: str) -> None:
    local_client = OllamaGemmaClient(settings)
    headers = {"X-Worker-Token": settings.worker_token}

    async with httpx.AsyncClient(
        base_url=settings.server_base_url,
        timeout=settings.ollama_timeout_seconds + 30,
    ) as api:
        logger.info("%s connected to %s", worker_id, settings.server_base_url)
        while True:
            try:
                claim_response = await api.get(
                    "/api/ai/worker/jobs/next",
                    params={"worker_id": worker_id},
                    headers=headers,
                )
                if claim_response.status_code == status.HTTP_204_NO_CONTENT:
                    await asyncio.sleep(settings.ai_job_poll_seconds)
                    continue
                claim_response.raise_for_status()
            except httpx.HTTPError:
                logger.exception("%s failed to claim an AI job", worker_id)
                await asyncio.sleep(settings.ai_job_poll_seconds)
                continue

            job = claim_response.json()
            job_id = job["id"]
            logger.info("%s claimed AI job %s", worker_id, job_id)

            try:
                result_text = await local_client.generate(job["prompt"])
            except Exception as exc:
                logger.exception("local AI job failed: %s", job_id)
                await api.post(
                    f"/api/ai/jobs/{job_id}/result",
                    headers=headers,
                    json={"success": False, "error_message": str(exc)},
                )
                continue

            try:
                result_response = await api.post(
                    f"/api/ai/jobs/{job_id}/result",
                    headers=headers,
                    json={"success": True, "result_text": result_text},
                )
                result_response.raise_for_status()
            except httpx.HTTPError:
                logger.exception("%s failed to submit AI job result %s", worker_id, job_id)
                await asyncio.sleep(settings.ai_job_poll_seconds)
                continue

            logger.info("%s submitted AI job result %s", worker_id, job_id)
