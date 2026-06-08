from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from macaronys_backend.enums import JobStatus, SourceStatus
from macaronys_backend.logging_config import logger
from macaronys_backend.models import AiJob, Source
from macaronys_backend.services.ai_result_parser import save_candidates_from_ai_result
from macaronys_backend.services.ollama_client import OllamaGemmaClient
from macaronys_backend.utils.time import utc_now


class ServerParallelAIProcessor:
    """Runs server-side Ollama/Gemma jobs with a bounded async worker pool."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        ollama_client: OllamaGemmaClient,
        worker_count: int = 1,
    ):
        self.session_factory = session_factory
        self.ollama_client = ollama_client
        self.worker_count = max(1, worker_count)
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self.tasks: list[asyncio.Task[None]] = []
        self._stopping = asyncio.Event()

    async def start(self) -> None:
        if self.tasks:
            return
        self._stopping.clear()
        await self._enqueue_existing_jobs()
        self.tasks = [
            asyncio.create_task(
                self._run(worker_index),
                name=f"server-ai-processor-{worker_index + 1}",
            )
            for worker_index in range(self.worker_count)
        ]
        logger.info("server AI processor started with %s workers", self.worker_count)

    async def stop(self) -> None:
        self._stopping.set()
        for task in self.tasks:
            task.cancel()
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks = []

    async def enqueue(self, job_id: str) -> None:
        await self.queue.put(job_id)

    async def _enqueue_existing_jobs(self) -> None:
        async with self.session_factory() as session:
            rows = await session.execute(
                select(AiJob)
                .where(AiJob.status.in_([JobStatus.queued.value, JobStatus.running.value]))
                .order_by(AiJob.created_at.asc())
            )
            for job in rows.scalars().all():
                if job.status == JobStatus.running.value:
                    job.status = JobStatus.queued.value
                    job.error_message = "requeued after server restart"
                await self.queue.put(job.id)
            await session.commit()

    async def _run(self, worker_index: int) -> None:
        while not self._stopping.is_set():
            job_id = await self.queue.get()
            try:
                await self._process_job(job_id)
            except Exception:
                logger.exception(
                    "AI job failed unexpectedly on server worker %s: %s",
                    worker_index + 1,
                    job_id,
                )
            finally:
                self.queue.task_done()

    async def _process_job(self, job_id: str) -> None:
        async with self.session_factory() as session:
            job = await session.get(AiJob, job_id)
            if job is None or job.status != JobStatus.queued.value:
                return
            job.status = JobStatus.running.value
            job.attempts += 1
            job.started_at = utc_now()
            await session.commit()
            prompt = job.prompt
            source_id = job.source_id

        try:
            result_text = await self.ollama_client.generate(prompt)
            async with self.session_factory() as session:
                job = await session.get(AiJob, job_id)
                source = await session.get(Source, source_id)
                if job is None:
                    return

                saved_count = await save_candidates_from_ai_result(
                    session,
                    source_id,
                    result_text,
                )
                job.status = JobStatus.completed.value
                job.result_text = result_text
                job.error_message = None
                job.finished_at = utc_now()
                if source is not None:
                    source.status = SourceStatus.done.value
                await session.commit()
                logger.info("AI job completed: %s candidates=%s", job_id, saved_count)
        except Exception as exc:
            async with self.session_factory() as session:
                job = await session.get(AiJob, job_id)
                source = await session.get(Source, source_id)
                if job is not None:
                    job.status = JobStatus.failed.value
                    job.error_message = str(exc)
                    job.finished_at = utc_now()
                if source is not None:
                    source.status = SourceStatus.failed.value
                    source.error_message = str(exc)
                await session.commit()
            logger.exception("AI job failed: %s", job_id)


ServerSequentialAIProcessor = ServerParallelAIProcessor
