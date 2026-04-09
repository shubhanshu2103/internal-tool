import sys
import json
sys.path.append('/Users/apple/Downloads/files/backend')
from evaluation.evaluator import _DraftScoreRaw, JUDGE_SYSTEM
from config import settings
import ollama

prompt = "Draft review: The Lovable tool is amazing. PASS on all aspects."

print("Using format=_DraftScoreRaw.model_json_schema()...")
client = ollama.Client(host=settings.ollama_base_url)
response = client.chat(
    model=settings.ollama_chat_model,
    messages=[
        {"role": "system", "content": JUDGE_SYSTEM},
        {"role": "user", "content": "Please score this tool draft holistically:\n\n" + prompt},
    ],
    format=_DraftScoreRaw.model_json_schema(),
)

print(response.message.content)
