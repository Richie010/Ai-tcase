"""
Standalone Gemini API key check — run this directly, no FastAPI/app needed.

Usage:
    python test_api_key.py

Reads GEMINI_API_KEY from backend/.env (or paste it directly below).
"""
import logging
import os
import traceback

# DEBUG MODE: shows every HTTP request/response the Gemini SDK makes under
# the hood (headers, URLs, status codes) — not just the final error.
logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(name)s: %(message)s")
logging.getLogger("urllib3").setLevel(logging.DEBUG)
logging.getLogger("google").setLevel(logging.DEBUG)

# Option 1: reads from your .env file automatically
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # fine if python-dotenv isn't installed — fall back to Option 2 below

API_KEY = "AQ.Ab8RN6K7iTVSOfuIrJjli6QZoIfFrZHVxHZ4JYWgmaHsbuPizw"

# Option 2: if the above doesn't pick it up, just paste your key here directly:
# API_KEY = "paste-your-real-key-here"

print(f"Using API key: {API_KEY[:8]}...{API_KEY[-4:] if len(API_KEY) > 12 else ''}" if API_KEY else "No API key found!")
print("-" * 50)

if not API_KEY:
    print("ERROR: GEMINI_API_KEY is empty. Check your .env file or paste the key directly into this script.")
    exit(1)

try:
    import google.generativeai as genai
except ImportError:
    print("ERROR: google-generativeai is not installed. Run: pip install google-generativeai")
    exit(1)

genai.configure(api_key=API_KEY)

print("Available models for your API key:")
try:
    for m in genai.list_models():
        methods = ", ".join(m.supported_generation_methods)
        print(f"  {m.name}  (supports: {methods})")
except Exception as e:
    print(f"  Could not list models: {e}")
print()

print("Test 1: Embedding call...")
try:
    result = genai.embed_content(
        model="models/text-embedding-004",
        content="hello world",
        task_type="retrieval_document",
    )
    print(f"  SUCCESS — got embedding vector of length {len(result['embedding'])}")
except Exception as e:
    print(f"  FAILED: {type(e).__name__}: {e}")
    print("  --- full traceback ---")
    traceback.print_exc()

print()
print("Test 2: Text generation call...")
try:
    model = genai.GenerativeModel("gemini-2.0-flash")
    response = model.generate_content("Say the word 'pong' and nothing else.")
    print(f"  SUCCESS — response: {response.text.strip()!r}")
except Exception as e:
    print(f"  FAILED: {type(e).__name__}: {e}")
    print("  --- full traceback ---")
    traceback.print_exc()

print()
print("-" * 50)
print("If both tests say SUCCESS, your API key works fine and the app should too.")
print("If either FAILED, the error message above tells you exactly what's wrong")
print("(invalid key, model not found, quota/billing issue, network block, etc.)")