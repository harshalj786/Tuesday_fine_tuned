\# Tuesday Bot: GenZ Empathy in Voice \& Vibe



Spill the chaos; I'll catch it with slang, modes, and a pulse. Tuesday's your unfiltered ear—mood-sniffing classifier, LoRA-tuned replies, TTS that \*feels\* human. GPU-optimized for <3s magic. Late nights? We've got you. 💙



\## Core Sparks

\- \*\*State Scanner\*\*: BERT-derived model flags emotions (sadness? Anxiety?), intents (vent? Advice?), risks—triggers modes like GENTLE\_CHECK ("that sucks, i'm here") or HYPE\_SESSION (🔥 energy match).

\- \*\*Response Ritual\*\*: Phi-3.5 LoRA generates raw, sanitized (no therapy BS), history-aware (6 turns deep).

\- \*\*Audio Arc\*\*: Faster-Whisper (1.2.1) hears raw; Edge-TTS (6.1.x) expands slang ("ngl" → spoken flow), dials prosody (pitch down for calm).

\- \*\*Interface Intimacy\*\*: Glassy HTML/JS—orb pulses (listening red, thinking gold, speaking green); mic blobs to /talk.



\## Local Awakening (gpu\_env Grace)

1\. Clone: `git clone https://github.com/\[yourusername]/tuesday-bot.git \&\& cd tuesday-bot`

2\. Cocoon: `gpu\_env\\Scripts\\Activate.ps1` (PowerShell policy? `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser`).

3\. Nourish: `pip install -r requirements.txt` (Torch 2.5.1+cu121 unleashes GPU; CPU? Edit drop +cu121).

4\. Models: Seed `Tuesday\_bot/models/` with .pth classifier \& phi35 LoRA (HF snapshot for deploys—code tweak below).

5\. Kindle: `uvicorn main:app --reload --host 0.0.0.0 --port 8000`

6\. Commune: http://localhost:8000 – Tap orb, voice your world; hear the echo.



\## Model Mysteries

\- Classifier: `mental\_state\_model\_best.pth` (from `model.ipynb`—multi-task: emotions x8, intents x3, risks x3).

\- Generator: `phi35\_genz\_therapist\_final/`—LoRA on `microsoft/Phi-3.5-mini-instruct` (anti-referral prompt baked).

\- Deploy Ease: In `tuesday\_bot.py` \_\_init\_\_: 

&nbsp; ```python

&nbsp; from huggingface\_hub import snapshot\_download

&nbsp; if not os.path.exists(f"{self.models\_dir}/phi35\_genz\_therapist\_final"): 

&nbsp;     snapshot\_download("microsoft/Phi-3.5-mini-instruct", local\_dir=...) 

