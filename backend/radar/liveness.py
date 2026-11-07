"""Check open status before ranking; uncertain URL checks stay out of ranking."""

import asyncio
from datetime import datetime, timezone

import httpx

from radar.providers.base import as_utc


async def check_jobs(jobs: list) -> tuple[list, list[int]]:
    now = datetime.now(timezone.utc)
    semaphore = asyncio.Semaphore(10)
    async with httpx.AsyncClient(timeout=2, follow_redirects=True) as client:
        async def check(job):
            if job.status != "active" or (job.expires_at and as_utc(job.expires_at) <= now):
                return job, False, True
            if job.source in {"nav", "fixture"}:
                return job, True, False
            async with semaphore:
                try:
                    response = await client.get(job.url)
                except httpx.HTTPError:
                    return job, False, False
            closed = response.status_code in {404, 410}
            if response.is_success:
                text = response.text.casefold()
                closed = any(marker in text for marker in (
                    "this job is no longer available", "this position has been filled",
                    "this job has expired", "stillingen er besatt", "annonsen er utløpt",
                ))
            return job, response.is_success and not closed, closed

        tasks = [asyncio.create_task(check(job)) for job in jobs]
        if not tasks:
            return [], []
        try:
            done, _ = await asyncio.wait(tasks, timeout=2.5)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        checks = [task.result() for task in tasks if task in done]
    return (
        [job for job, alive, _ in checks if alive],
        [job.id for job, _, closed in checks if closed],
    )
