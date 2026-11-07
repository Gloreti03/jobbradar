"""UNICO punto di accesso a DeepSeek (BLUEPRINT sez. 8).

Uso:
    from llm import complete_json, acomplete_json
    profile = complete_json("smart", system=PROMPT, user=cv_text, schema=Profile)
    # in parallelo (es. ranking a gruppi):
    results = await asyncio.gather(*(acomplete_json("fast", ..., schema=X) for ... in gruppi))

DeepSeek garantisce un JSON valido ma NON lo schema: qui si valida con Pydantic e,
se fallisce, si riprova mandando l'errore al modello.
"""

import json
from typing import Literal, TypeVar

from openai import AsyncOpenAI, OpenAI
from pydantic import BaseModel, ValidationError

from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, MODEL_FAST, MODEL_SMART

T = TypeVar("T", bound=BaseModel)
ModelKind = Literal["smart", "fast"]

TIMEOUT_S = 90


class LLMError(RuntimeError):
    """Il modello non ha prodotto un JSON valido per lo schema dopo i tentativi."""


_sync_client: OpenAI | None = None
_async_client: AsyncOpenAI | None = None


def _client() -> OpenAI:
    global _sync_client
    if _sync_client is None:
        _sync_client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL, timeout=TIMEOUT_S)
    return _sync_client


def _aclient() -> AsyncOpenAI:
    global _async_client
    if _async_client is None:
        _async_client = AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL, timeout=TIMEOUT_S)
    return _async_client


def _model(kind: ModelKind) -> str:
    return MODEL_SMART if kind == "smart" else MODEL_FAST


def _messages(system: str, user: str, schema: type[BaseModel]) -> list[dict]:
    schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=False)
    system_full = (
        f"{system}\n\n"
        "Reply ONLY with a single JSON object (no markdown, no comments) that is valid "
        f"against this JSON Schema:\n{schema_json}"
    )
    return [{"role": "system", "content": system_full}, {"role": "user", "content": user}]


def _parse(raw: str | None, schema: type[T]) -> T:
    if not raw:
        raise ValueError("empty response")
    return schema.model_validate_json(raw)


def _retry_messages(messages: list[dict], raw: str | None, err: Exception) -> list[dict]:
    return messages + [
        {"role": "assistant", "content": raw or ""},
        {
            "role": "user",
            "content": f"Your JSON was not valid for the schema. Error:\n{err}\n"
            "Reply again with the corrected full JSON object only.",
        },
    ]


def complete_json(
    kind: ModelKind,
    system: str,
    user: str,
    schema: type[T],
    *,
    temperature: float = 0.3,
    max_tokens: int = 4096,
    retries: int = 2,
) -> T:
    messages = _messages(system, user, schema)
    last_err: Exception | None = None
    for _ in range(retries + 1):
        resp = _client().chat.completions.create(
            model=_model(kind),
            messages=messages,
            response_format={"type": "json_object"},
            temperature=temperature,
            max_tokens=max_tokens,
        )
        raw = resp.choices[0].message.content
        try:
            return _parse(raw, schema)
        except (ValidationError, ValueError) as err:
            last_err = err
            messages = _retry_messages(messages, raw, err)
    raise LLMError(f"Invalid JSON from model for {schema.__name__}: {last_err}")


async def acomplete_json(
    kind: ModelKind,
    system: str,
    user: str,
    schema: type[T],
    *,
    temperature: float = 0.3,
    max_tokens: int = 4096,
    retries: int = 2,
) -> T:
    messages = _messages(system, user, schema)
    last_err: Exception | None = None
    for _ in range(retries + 1):
        resp = await _aclient().chat.completions.create(
            model=_model(kind),
            messages=messages,
            response_format={"type": "json_object"},
            temperature=temperature,
            max_tokens=max_tokens,
        )
        raw = resp.choices[0].message.content
        try:
            return _parse(raw, schema)
        except (ValidationError, ValueError) as err:
            last_err = err
            messages = _retry_messages(messages, raw, err)
    raise LLMError(f"Invalid JSON from model for {schema.__name__}: {last_err}")
