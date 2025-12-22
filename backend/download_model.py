# download_model.py
from huggingface_hub import snapshot_download
import os

print("HF_HOME:", os.getenv("HF_HOME"))
print("Starting snapshot_download of openai/whisper-small ... (this may take several minutes)")

path = snapshot_download(
    repo_id="openai/whisper-small",
    cache_dir=os.getenv("HF_HOME"),
    library_name="faster-whisper"
)

print("Downloaded to:", path)
