import sys
import os
import re
import random
import uuid
import subprocess
import logging
import asyncio
from pathlib import Path

import torch
import edge_tts
from faster_whisper import WhisperModel
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from edge_tts.exceptions import NoAudioReceived

current_dir = Path(__file__).resolve().parent
bot_path = current_dir.parent / "Tuesday_bot" / "models"
sys.path.append(str(bot_path))

from tuesday_bot import TuesdayBot

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")

app = FastAPI()
app.mount("/audio", StaticFiles(directory="tmp_audio"), name="audio")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

TMP_DIR = Path("tmp_audio")
TMP_DIR.mkdir(exist_ok=True)

whisper_model = None
bot = None


class ConnectionManager:
    def __init__(self):
        self.connections = {}

    async def connect(self, session_id, websocket):
        await websocket.accept()
        self.connections[session_id] = websocket

    def disconnect(self, session_id):
        self.connections.pop(session_id, None)

    async def send(self, session_id, payload):
        ws = self.connections.get(session_id)
        if ws:
            await ws.send_json(payload)


manager = ConnectionManager()


@app.on_event("startup")
def load_models():
    global whisper_model, bot
    whisper_model = WhisperModel(
        WHISPER_MODEL,
        device=DEVICE,
        compute_type="float16" if DEVICE == "cuda" else "int8"
    )
    bot = TuesdayBot(models_dir=str(bot_path), device=DEVICE)


def convert_to_wav(input_path, output_path):
    subprocess.run(
        ["ffmpeg", "-y", "-i", input_path, "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", output_path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True
    )


def split_text(text):
    return [p.strip() for p in re.split(r'(?<=[.!?])\s+', text) if len(p.strip()) > 6]


async def stream_tts_chunks(text, mode, session_id):
    parts = split_text(text)

    for i, part in enumerate(parts):
        filename = f"{session_id}_chunk_{i}.mp3"
        tmp = TMP_DIR / f"{filename}.tmp"
        final = TMP_DIR / filename

        rate = "-10%" if mode in ["GENTLE_CHECK", "CRISIS_SUPPORT"] else "+10%" if mode == "HYPE_SESSION" else "+0%"
        pitch = "-2Hz" if mode in ["GENTLE_CHECK", "CRISIS_SUPPORT"] else "+2Hz" if mode == "HYPE_SESSION" else "+0Hz"

        try:
            await edge_tts.Communicate(
                part,
                "en-US-JennyNeural",
                rate=rate,
                pitch=pitch
            ).save(str(tmp))

            tmp.replace(final)

            await manager.send(session_id, {
                "event": "audio_chunk",
                "filename": filename
            })

        except NoAudioReceived:
            continue

    await manager.send(session_id, {"event": "audio_done"})


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(session_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(session_id)


@app.post("/talk")
async def talk(background_tasks: BackgroundTasks, file: UploadFile = File(...), session_id: str = None):
    if not session_id:
        session_id = uuid.uuid4().hex

    raw = TMP_DIR / f"{session_id}.webm"
    wav = TMP_DIR / f"{session_id}.wav"

    raw.write_bytes(await file.read())
    convert_to_wav(str(raw), str(wav))

    loop = asyncio.get_running_loop()
    segments, _ = await loop.run_in_executor(None, lambda: whisper_model.transcribe(str(wav)))
    user_text = " ".join(s.text for s in segments).strip()

    if not user_text:
        reply, mode = "i couldn't hear you clearly.", "GENTLE_CHECK"
    else:
        result = bot.generate_response(user_text)
        reply, mode = result["response"], result["mode"]

    background_tasks.add_task(stream_tts_chunks, reply, mode, session_id)

    raw.unlink(missing_ok=True)
    wav.unlink(missing_ok=True)

    return {"user_text": user_text, "ai_text": reply}


@app.post("/reset")
def reset():
    bot.clear_memory()
    return {"status": "ok"}