import os, requests

k = os.getenv("OPENAI_API_KEY")
print("KEY SET:", bool(k))
if k:
    print("MASK:", k[:4] + "...", "LENGTH:", len(k))

r = requests.get("https://api.openai.com/v1/models", headers={"Authorization": f"Bearer {k}"})
print("STATUS:", r.status_code)
print("BODY START:", r.text[:400])