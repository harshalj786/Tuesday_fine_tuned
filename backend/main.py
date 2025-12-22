import sys
import os
import time
import re
import random
from pathlib import Path

# --- SETUP PATHS ---
current_dir = Path(__file__).resolve().parent
# Point to Tuesday_bot/models where tuesday_bot.py lives
bot_path = current_dir.parent / "Tuesday_bot" / "models"
sys.path.append(str(bot_path))

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uuid
import subprocess
import torch
from faster_whisper import WhisperModel
import edge_tts 

from tuesday_bot import TuesdayBot

app = FastAPI()

# Mount the tmp directory so frontend can play audio files
app.mount("/audio", StaticFiles(directory="tmp_audio"), name="audio")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

TMP_DIR = Path("tmp_audio")
TMP_DIR.mkdir(exist_ok=True)

# -------- LOAD MODELS --------
print("Loading Faster-Whisper (CUDA)...")
whisper_model = WhisperModel("small", device="cuda", compute_type="float16")

print("Loading Tuesday Bot...")
bot = TuesdayBot(models_dir=str(bot_path), device="cuda")
print("✅ Tuesday Bot Loaded: Active Listener + Human Voice Mode") 

# -------- UTILS --------
def convert_to_wav(input_path: str, output_path: str):
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-ar", "16000", "-ac", "1",
        "-c:a", "pcm_s16le",
        output_path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

def remove_emojis(text: str) -> str:
    """Removes emojis so TTS doesn't read them out loud."""
    return re.sub(r'[^\x00-\x7F]+', '', text)

def expand_slang(text: str) -> str:
    """
    Converts GenZ slang abbreviations into full spoken words for the voice engine.
    Screen: "ngl that's tough"
    Voice: "not gonna lie that's tough"
    """
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
    
    # Replace all occurrences (case-insensitive)
    for pattern, replacement in slang_map.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    
    return text

def add_human_fillers(text: str, mode: str) -> str:
    """Adds small 'um' or 'like' fillers to sound less robotic in casual modes."""
    # Only add fillers sometimes (30% chance) and only for casual modes
    if mode in ["VIBE_CHECK", "GENTLE_CHECK"] and random.random() < 0.3:
        fillers = ["You know, ", "Honestly, ", "I feel like ", "Hmm, "]
        return random.choice(fillers) + text
    return text

async def text_to_speech(text: str, mode: str, output_filename: str):
    """
    Edge TTS with Dynamic Prosody and Slang Expansion.
    """
    voice = "en-US-JennyNeural" 
    
    # 1. Pipeline: Clean Emojis -> Expand Slang -> Add Fillers
    clean_text = remove_emojis(text)
    clean_text = expand_slang(clean_text)  # <--- NEW STEP
    clean_text = add_human_fillers(clean_text, mode)

    # 2. Dynamic Prosody Settings
    rate = "+0%"
    pitch = "+0Hz"

    if mode == "GENTLE_CHECK" or mode == "CRISIS_SUPPORT":
        # Slow down and lower pitch for comfort/sadness
        rate = "-10%"
        pitch = "-2Hz"
    elif mode == "HYPE_SESSION":
        # Speed up and raise pitch for excitement
        rate = "+10%"
        pitch = "+2Hz"
    
    # 3. Generate Audio
    communicate = edge_tts.Communicate(clean_text, voice, rate=rate, pitch=pitch)
    save_path = TMP_DIR / output_filename
    await communicate.save(str(save_path))
    return str(save_path)

# -------- API --------
@app.post("/talk")
async def talk(file: UploadFile = File(...)):
    session_id = uuid.uuid4().hex
    start_total = time.time()
    
    # 1. SAVE USER AUDIO
    raw_path = TMP_DIR / f"{session_id}_input{Path(file.filename).suffix}"
    wav_path = TMP_DIR / f"{session_id}.wav"
    raw_path.write_bytes(await file.read())
    
    # 2. CONVERT TO WAV
    convert_to_wav(str(raw_path), str(wav_path))

    # 3. TRANSCRIBE
    print(f"\n--- Processing Request {session_id} ---")
    t1 = time.time()
    segments, info = whisper_model.transcribe(str(wav_path), beam_size=5)
    user_text = " ".join([segment.text for segment in segments]).strip()
    print(f"👂 Listening: {time.time() - t1:.2f}s | Text: {user_text}")

    # 4. GET AI RESPONSE
    t2 = time.time()
    if not user_text:
        ai_response_text = "I couldn't hear you clearly."
        mode = "neutral"
    else:
        result = bot.generate_response(user_text)
        ai_response_text = result['response']
        mode = result['mode']
    print(f"🧠 Thinking:  {time.time() - t2:.2f}s | Mode: {mode}")

    # 5. GENERATE AI VOICE (Pass 'mode' for dynamic voice)
    t3 = time.time()
    output_audio_filename = f"{session_id}_response.mp3"
    await text_to_speech(ai_response_text, mode, output_audio_filename)
    print(f"🗣️ Speaking:  {time.time() - t3:.2f}s")

    # Cleanup
    raw_path.unlink(missing_ok=True)
    wav_path.unlink(missing_ok=True)

    total_time = time.time() - start_total
    print(f"⏱️ TOTAL TIME: {total_time:.2f}s")
    print("--------------------------------------\n")

    return {
        "user_text": user_text,
        "ai_text": ai_response_text,
        "mode": mode,
        "audio_url": f"http://localhost:8000/audio/{output_audio_filename}",
        "processing_time": total_time
    }

@app.post("/reset")
def reset_memory():
    bot.clear_memory()
    return {"status": "Memory wiped."}

@app.get("/")
def root():
    return {"status": "Tuesday Bot is Online"}