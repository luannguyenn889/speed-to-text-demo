import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

api_key = os.environ.get("GEMINI_API_KEY", "")
if not api_key:
    print("Warning: GEMINI_API_KEY is not set. Please set it in .env file.")
else:
    print(f"Testing API Key: {api_key[:10]}...")

try:
    client = genai.Client(api_key=api_key)
    print("Listing available models for this key:")
    count = 0
    for m in client.models.list():
        print(f" - {m.name}")
        count += 1
    if count == 0:
        print("Warning: No models returned for this key.")
except Exception as e:
    print(f"Error testing key: {str(e)}")
