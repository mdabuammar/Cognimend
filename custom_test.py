import os
import time
import requests
import json

UPLOAD_URL = "http://localhost:8001"
QUERY_URL = "http://localhost:8002"

FILES = [
    {"filename": "random1.txt", "title": "Random Topic 1", "content": "The sky is blue because of Rayleigh scattering. Sunlight hits the atmosphere and scatters."},
    {"filename": "random2.txt", "title": "Random Topic 2", "content": "Apples are high in fiber and vitamin C. They grow on trees and are harvested in autumn."},
    {"filename": "random3.txt", "title": "Random Topic 3", "content": "Machine learning is a subset of artificial intelligence where models learn from data."},
    {"filename": "random4.txt", "title": "Random Topic 4", "content": "Water freezes at 0 degrees Celsius and boils at 100 degrees Celsius under standard atmospheric pressure."},
    {"filename": "random5.txt", "title": "Random Topic 5", "content": "The capital of France is Paris. It is known for the Eiffel Tower and the Louvre museum."}
]

QUERIES = [
    "Why is the sky blue?",
    "What causes Rayleigh scattering?",
    "What vitamins are in apples?",
    "When are apples harvested?",
    "What is machine learning?",
    "What do machine learning models learn from?",
    "At what temperature does water boil?",
    "What is the freezing point of water?",
    "What is the capital of France?",
    "What is Paris known for?"
]

print("Uploading 5 random files...")
for f in FILES:
    files = {"file": (f["filename"], f["content"].encode(), "text/plain")}
    try:
        r = requests.post(f"{UPLOAD_URL}/upload", files=files, data={"title": f["title"]})
        print(f"Uploaded {f['filename']}: {r.status_code}")
    except Exception as e:
        print(f"Upload failed for {f['filename']}: {e}")

print("Waiting for indexing to complete (10s)...")
time.sleep(10)

print("Running 10 queries...")
results = []
for q in QUERIES:
    try:
        r = requests.post(f"{QUERY_URL}/query", json={"question": q, "top_k": 3})
        if r.ok:
            d = r.json()
            conf = d.get("confidence", 0)
            ans = d.get("answer", "")
            print(f"Q: {q}")
            print(f"  Confidence: {conf}%")
            print(f"  Answer: {ans[:80]}...")
            results.append({"query": q, "confidence": conf, "answer": ans})
        else:
            print(f"Query failed: {r.status_code} - {r.text}")
    except Exception as e:
        print(f"Query error: {e}")

artifact_path = "artifacts/random_query_results.md"
os.makedirs(os.path.dirname(artifact_path), exist_ok=True)
with open(artifact_path, "w", encoding="utf-8") as f:
    f.write("# 🧪 Random Query Test Results\n\n")
    f.write("Five random files were uploaded and tested with 10 queries. Results and confidence levels are below:\n\n")
    f.write("| Query | Confidence | Answer |\n")
    f.write("|---|---|---|\n")
    for r in results:
        f.write(f"| {r['query']} | **{r['confidence']}%** | {r['answer']} |\n")

print("Done. Saved to artifact.")
