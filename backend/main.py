import sys
import os
import time
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
from fastapi import FastAPI, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

current_dir = Path(__file__).resolve().parent
bot_path = current_dir.parent / "Tuesday_bot" / "models"
sys.path.append(str(bot_path))

from tuesday_bot import TuesdayBot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
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

@app.on_event("startup")
def load_models():
    global whisper_model, bot
    logger.info(f"Using device: {DEVICE}")
    whisper_model = WhisperModel(
        WHISPER_MODEL,
        device=DEVICE,
        compute_type="float16" if DEVICE == "cuda" else "int8"
    )
    bot = TuesdayBot(models_dir=str(bot_path), device=DEVICE)
    logger.info("Models loaded successfully")

def convert_to_wav(input_path: str, output_path: str):
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-ar", "16000", "-ac", "1",
        "-c:a", "pcm_s16le",
        output_path
    ]
    try:
        subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            check=True
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(e.stderr.decode())

def remove_emojis(text: str) -> str:
    return re.sub(r'[^\x00-\x7F]+', '', text)

def expand_slang(text: str) -> str:
    slang_map = {
        r"\bngl\b": "not gonna lie",
        r"\bfr\b": "for real",
        r"\btbh\b": "to be honest",
        r"\brn\b": "right now",
        r"\bidk\b": "I don't know",
        r"\bbc\b": "because",
        r"\bimo\b": "in my opinion",
        r"\btbf\b": "to be fair",
        r"\batm\b": "at the moment",
        r"\bjk\b": "just kidding",
        r"\bwdym\b": "what do you mean"
    }
    for pattern, replacement in slang_map.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text

def add_human_fillers(text: str, mode: str) -> str:
    if mode in ["VIBE_CHECK", "GENTLE_CHECK"] and random.random() < 0.3:
        fillers = ["You know, ", "Honestly, ", "I feel like ", "Hmm, "]
        return random.choice(fillers) + text
    return text

async def text_to_speech(text: str, mode: str, output_filename: str):
    voice = "en-US-JennyNeural"
    clean_text = remove_emojis(text)
    clean_text = expand_slang(clean_text)
    clean_text = add_human_fillers(clean_text, mode)

    rate = "+0%"
    pitch = "+0Hz"

    if mode in ["GENTLE_CHECK", "CRISIS_SUPPORT"]:
        rate = "-10%"
        pitch = "-2Hz"
    elif mode == "HYPE_SESSION":
        rate = "+10%"
        pitch = "+2Hz"

    communicate = edge_tts.Communicate(clean_text, voice, rate=rate, pitch=pitch)
    save_path = TMP_DIR / output_filename
    await communicate.save(str(save_path))
    return str(save_path)

@app.post("/talk")
async def talk(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    session_id = uuid.uuid4().hex
    start_total = time.time()
    timings = {}

    raw_path = TMP_DIR / f"{session_id}_input{Path(file.filename).suffix}"
    wav_path = TMP_DIR / f"{session_id}.wav"
    raw_path.write_bytes(await file.read())

    try:
        convert_to_wav(str(raw_path), str(wav_path))
    except RuntimeError as e:
        logger.error(str(e))
        return {"error": "Audio conversion failed"}

    t1 = time.time()
    loop = asyncio.get_running_loop()
    segments, _ = await loop.run_in_executor(
        None,
        lambda: whisper_model.transcribe(str(wav_path), beam_size=5)
    )
    user_text = " ".join([s.text for s in segments]).strip()
    timings["transcription"] = time.time() - t1
    logger.info(f"Transcription ({timings['transcription']:.2f}s): {user_text}")

    t2 = time.time()
    if not user_text:
        ai_response_text = "I couldn't hear you clearly."
        mode = "neutral"
    else:
        result = bot.generate_response(user_text)
        ai_response_text = result["response"]
        mode = result["mode"]
        confidence = result.get("confidence", 1.0)

        if confidence < 0.55:
            mode = "neutral"
        if confidence < 0.4:
            ai_response_text = "I'm here with you. Take your time."

    timings["generation"] = time.time() - t2
    logger.info(f"Generation ({timings['generation']:.2f}s) | Mode: {mode}")

    t3 = time.time()
    output_audio_filename = f"{session_id}_response.mp3"
    background_tasks.add_task(
        text_to_speech,
        ai_response_text,
        mode,
        output_audio_filename
    )
    timings["tts"] = time.time() - t3

    raw_path.unlink(missing_ok=True)
    wav_path.unlink(missing_ok=True)

    total_time = time.time() - start_total
    logger.info(f"Total request time: {total_time:.2f}s")

    return {
        "user_text": user_text,
        "ai_text": ai_response_text,
        "mode": mode,
        "audio_url": f"http://localhost:8000/audio/{output_audio_filename}",
        "processing_time": total_time,
        "timings": timings
    }

@app.post("/reset")
def reset_memory():
    bot.clear_memory()
    return {"status": "Memory wiped."}

@app.get("/")
def root():
    return {"status": "Tuesday Bot is Online"}
