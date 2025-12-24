import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import torch
import pandas as pd
from sklearn.metrics import classification_report
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
pred_top3 = []

for text in texts:
    enc = bot.classifier_tokenizer(
        text.lower().strip(),
        padding="max_length",
        truncation=True,
        max_length=128,
        return_tensors="pt"
    ).to(bot.device)

    with torch.no_grad():
        out = bot.classifier(enc["input_ids"], enc["attention_mask"])

    logits = out["emotion"][0]
    top3_ids = logits.topk(3).indices.tolist()
    top3_labels = [bot.id2label[i] for i in top3_ids]

    pred_top3.append(top3_labels)
    pred_emotions.append(top3_labels[0])

POSITIVE = {
    "joyful", "excited", "content", "grateful", "hopeful",
    "proud", "confident", "caring", "trusting", "faithful",
    "impressed", "nostalgic", "prepared"
}

NEGATIVE = {
    "sad", "lonely", "afraid", "anxious", "terrified",
    "angry", "furious", "disgusted", "ashamed", "guilty",
    "jealous", "embarrassed", "devastated", "disappointed",
    "sentimental", "annoyed", "apprehensive"
}

HIGH_AROUSAL = {
    "angry", "furious", "excited", "terrified", "anxious",
    "afraid", "jealous", "embarrassed", "surprised"
}

LOW_AROUSAL = {
    "sad", "lonely", "content", "nostalgic", "sentimental",
    "disappointed", "guilty", "ashamed", "trusting"
}

def map_valence(e):
    if e in POSITIVE:
        return "positive"
    if e in NEGATIVE:
        return "negative"
    return "neutral"

def map_arousal(e):
    if e in HIGH_AROUSAL:
        return "high"
    if e in LOW_AROUSAL:
        return "low"
    return "medium"

true_valence = [map_valence(e) for e in true_emotions]
pred_valence = [map_valence(e) for e in pred_emotions]

true_arousal = [map_arousal(e) for e in true_emotions]
pred_arousal = [map_arousal(e) for e in pred_emotions]

print("\n=== VALENCE LEVEL REPORT ===")
print(classification_report(true_valence, pred_valence, digits=3))

print("\n=== AROUSAL LEVEL REPORT ===")
print(classification_report(true_arousal, pred_arousal, digits=3))

top3_correct = sum(t in p for t, p in zip(true_emotions, pred_top3))
top3_accuracy = top3_correct / len(true_emotions)

print("\n=== TOP-3 EMOTION ACCURACY ===")
print(round(top3_accuracy, 3))
