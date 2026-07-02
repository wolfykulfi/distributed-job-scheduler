"""AI-generated failure summaries via Groq's OpenAI-compatible chat completions API.

Optional bonus feature: the scheduler's core reliability guarantees don't depend on this in any
way -- if GROQ_API_KEY isn't configured, the /ai-summary endpoint returns a clear error rather
than the app failing to start or silently degrading elsewhere.
"""

import httpx

from app.config import settings
from app.core.exceptions import AppError

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

_SYSTEM_PROMPT = (
    "You summarize job failures for an on-call engineer looking at a dashboard. Given a job "
    "name, error message, and stack trace, write a 1-2 sentence plain-English summary of what "
    "most likely went wrong and, if obvious, a one-phrase suggestion. Do not restate the raw "
    "error verbatim. Be concise -- this renders in a table cell."
)


class AiSummaryUnavailable(AppError):
    status_code = 503
    code = "ai_summary_unavailable"


async def summarize_failure(job_name: str, error_message: str, error_stacktrace: str | None) -> str:
    if not settings.groq_api_key:
        raise AiSummaryUnavailable("AI summaries aren't configured (no GROQ_API_KEY set)")

    user_content = f"Job: {job_name}\nError: {error_message}"
    if error_stacktrace:
        user_content += f"\nStack trace (last 2000 chars):\n{error_stacktrace[-2000:]}"

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                GROQ_URL,
                headers={"Authorization": f"Bearer {settings.groq_api_key}"},
                json={
                    "model": settings.groq_model,
                    "messages": [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": user_content},
                    ],
                    "max_tokens": 150,
                    "temperature": 0.2,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
    except (httpx.HTTPError, KeyError, IndexError) as exc:
        raise AiSummaryUnavailable(f"AI summary request failed: {exc}") from exc
