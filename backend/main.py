import asyncio
import json
import os
import socket
import subprocess
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend import config as app_config
from backend import llm
from backend.analyzer import analyze_text, analyze_sentence, probe_llm
from backend.cache import cache
from backend.translation import translator as get_active_translator

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
VITE_PORT = 5173


def _vite_running() -> bool:
    with socket.socket() as s:
        return s.connect_ex(("localhost", VITE_PORT)) == 0


@asynccontextmanager
async def lifespan(app: FastAPI):
    vite = None
    if os.getenv("SEMANTIX_NO_VITE") != "1" and not _vite_running():
        vite = subprocess.Popen(["npm", "run", "dev"], cwd=FRONTEND_DIR)
    task = asyncio.create_task(_sweep_sessions())
    yield
    task.cancel()
    if vite is not None:
        vite.terminate()
        try:
            vite.wait(timeout=5)
        except subprocess.TimeoutExpired:
            vite.kill()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_sessions: dict[str, dict] = {}
SESSION_TTL = 60


class AnalyzeRequest(BaseModel):
    text: str
    variant: Literal["british", "american"]
    mode: Literal["plain", "latex"] = "plain"


class TranslateRequest(BaseModel):
    text: str
    source_lang: str
    target_lang: str


class SentenceRequest(BaseModel):
    sentence: str
    variant: Literal["british", "american"]
    sentence_index: int = 0


class ModelSelectRequest(BaseModel):
    target: Literal["analyzer", "translator"]
    model: str


@app.post("/analyze")
async def post_analyze(body: AnalyzeRequest):
    session_id = str(uuid.uuid4())
    _sessions[session_id] = {
        "text": body.text,
        "variant": body.variant,
        "mode": body.mode,
        "created_at": time.time(),
    }
    return {"session_id": session_id}


@app.get("/analyze/stream/{session_id}")
async def get_stream(session_id: str):
    session = _sessions.pop(session_id, None)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    text = session["text"]
    variant = session["variant"]
    mode = session["mode"]

    async def event_stream():
        try:
            async for result in analyze_text(text, variant, mode):
                data = json.dumps(result)
                yield f"event: sentence\ndata: {data}\n\n"
        except Exception as exc:
            error_data = json.dumps({"message": str(exc)})
            yield f"event: error\ndata: {error_data}\n\n"
            return
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/analyze/sentence")
async def post_analyze_sentence(body: SentenceRequest):
    return await analyze_sentence(body.sentence, body.variant, body.sentence_index)


@app.get("/health")
async def health():
    return {"ollama": await probe_llm(), "model": app_config.get()["analyzer_model"]}


@app.get("/models")
async def get_models():
    cfg = app_config.get()
    try:
        models = await llm.list_models()
        style = await llm.detect_style()
    except Exception:
        models = []
        style = None
    return {
        "models": models,
        "analyzer_model": cfg["analyzer_model"],
        "translate_model": cfg["translate_model"],
        "base_url": cfg["base_url"],
        "api_style": style,
    }


@app.post("/models/select")
async def select_model(body: ModelSelectRequest):
    cfg = app_config.set_model(body.target, body.model)
    return {
        "ok": True,
        "analyzer_model": cfg["analyzer_model"],
        "translate_model": cfg["translate_model"],
    }


@app.post("/cache/clear")
async def cache_clear():
    cache.clear()
    return {"ok": True}


@app.post("/warmup")
async def warmup():
    try:
        await llm.chat(
            model=app_config.get()["analyzer_model"],
            system=".",
            user=".",
            read_timeout=5.0,
        )
    except Exception:
        pass
    return {"ok": True}


@app.post("/translation")
async def translate(body: TranslateRequest):
    try:
        result = await get_active_translator().translate_text(
            body.text, body.source_lang, body.target_lang
        )
        return {
            "translation": result,
            "source_lang": body.source_lang,
            "target_lang": body.target_lang,
        }
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Translation failed: {e}")


async def _sweep_sessions():
    while True:
        await asyncio.sleep(30)
        now = time.time()
        expired = [
            sid for sid, s in _sessions.items() if now - s["created_at"] > SESSION_TTL
        ]
        for sid in expired:
            _sessions.pop(sid, None)
