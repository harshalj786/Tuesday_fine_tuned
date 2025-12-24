import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import torch
import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix
from Tuesday_bot.models.tuesday_bot import TuesdayBot

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
print("Using device:", DEVICE)

df = pd.read_csv(ROOT / "Tuesday_bot" / "cleaned.csv")
test_df = df.sample(frac=0.15, random_state=42)

texts = test_df["empathetic_dialogues"].tolist()
true_emotions = test_df["emotion"].tolist()

bot = TuesdayBot(
    models_dir=str(ROOT / "Tuesday_bot" / "models"),
    device=DEVICE
)

pred_emotions = []

for text in texts:
    state = bot.analyze_mental_state(text)
    pred_emotions.append(state["emotion"])

print("\n=== CLASSIFICATION REPORT ===")
print(classification_report(true_emotions, pred_emotions, digits=3))

print("\n=== CONFUSION MATRIX ===")
print(confusion_matrix(true_emotions, pred_emotions))
