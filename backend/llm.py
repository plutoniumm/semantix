"""LLM client that speaks either the OpenAI v1 API (Ollama's /v1, vLLM,
LM Studio, llama.cpp server, OpenAI, ...) or Ollama's native API.

The endpoint comes from backend.config. With api_style "auto" the style is
detected with a single request (GET {base}/v1/models → OpenAI v1, else
GET {base}/api/tags → Ollama native) and cached until the next probe."""

import httpx
from backend import config

CONNECT_TIMEOUT = 5.0

_detected_style: str | None = None


def _root() -> str:
    base = config.get()["base_url"].rstrip("/")
    return base[: -len("/v1")] if base.endswith("/v1") else base


def _headers() -> dict:
    headers = {"Content-Type": "application/json"}
    api_key = config.get().get("api_key")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


async def detect_style(force: bool = False) -> str:
    global _detected_style
    configured = config.get().get("api_style", "auto")
    if configured in ("openai", "ollama"):
        return configured
    if _detected_style is not None and not force:
        return _detected_style

    async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
        try:
            resp = await client.get(f"{_root()}/v1/models", headers=_headers())
            resp.raise_for_status()
            _detected_style = "openai"
            return _detected_style
        except httpx.HTTPError:
            pass
        resp = await client.get(f"{_root()}/api/tags", headers=_headers())
        resp.raise_for_status()
        _detected_style = "ollama"
        return _detected_style


async def chat(
    model: str,
    system: str,
    user: str,
    json_mode: bool = False,
    read_timeout: float = 30.0,
) -> str:
    style = await detect_style()
    timeout = httpx.Timeout(
        connect=CONNECT_TIMEOUT, read=read_timeout, write=5.0, pool=5.0
    )

    if style == "openai":
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        url = f"{_root()}/v1/chat/completions"
    else:
        payload = {
            "model": model,
            "system": system,
            "prompt": user,
            "stream": False,
        }
        if json_mode:
            payload["format"] = "json"
        url = f"{_root()}/api/generate"

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, json=payload, headers=_headers())
        resp.raise_for_status()
        data = resp.json()

    if style == "openai":
        return data["choices"][0]["message"]["content"]
    return data["response"]


async def list_models() -> list[str]:
    style = await detect_style()
    async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
        if style == "openai":
            resp = await client.get(f"{_root()}/v1/models", headers=_headers())
            resp.raise_for_status()
            return sorted(m["id"] for m in resp.json().get("data", []) if m.get("id"))
        resp = await client.get(f"{_root()}/api/tags", headers=_headers())
        resp.raise_for_status()
        return sorted(m["name"] for m in resp.json().get("models", []) if m.get("name"))


async def probe() -> bool:
    try:
        await detect_style(force=True)
        return True
    except httpx.HTTPError:
        return False
