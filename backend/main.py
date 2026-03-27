import asyncio
import json
import socket
import subprocess
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.analyzer import analyze_text, OLLAMA_URL, OLLAMA_MODEL


FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
VITE_PORT = 5173


def _vite_running() -> bool:
    with socket.socket() as s:
        return s.connect_ex(("localhost", VITE_PORT)) == 0


@asynccontextmanager
async def lifespan(app: FastAPI):
    vite = None
    if not _vite_running():
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


@app.post("/warmup")
async def warmup():
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
            await client.post(OLLAMA_URL, json={
                "model": OLLAMA_MODEL,
                "prompt": ".",
                "system": ".",
                "stream": False,
            })
    except Exception:
        pass
    return {"ok": True}


async def _sweep_sessions():
    while True:
        await asyncio.sleep(30)
        now = time.time()
        expired = [sid for sid, s in _sessions.items() if now - s["created_at"] > SESSION_TTL]
        for sid in expired:
            _sessions.pop(sid, None)
