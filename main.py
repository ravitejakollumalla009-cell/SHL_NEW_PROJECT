from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
import requests

app = FastAPI()

CATALOG_URL = "https://tcp-us-prod-rnd.shl.com/voiceRater/shl-ai-hiring/shl_product_catalog.json"

# -----------------------------
# Load Catalog (cached)
# -----------------------------
def load_catalog():
    try:
        response = requests.get(CATALOG_URL, timeout=10)
        data = response.json()
        return data
    except:
        return []

CATALOG = load_catalog()


# -----------------------------
# Request Schema
# -----------------------------
class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[Message]


# -----------------------------
# Context Extraction
# -----------------------------
def extract_context(messages):
    text = " ".join([m.content.lower() for m in messages])

    context = {
        "role": None,
        "level": None,
        "personality": False
    }

    if "java" in text:
        context["role"] = "java"

    if "mid" in text or "4 year" in text:
        context["level"] = "mid"

    if "personality" in text:
        context["personality"] = True

    return context


# -----------------------------
# Intent Detection
# -----------------------------
def is_vague(context):
    return context["role"] is None


def is_comparison(messages):
    last = messages[-1].content.lower()
    return "difference" in last or "compare" in last


def is_out_of_scope(messages):
    last = messages[-1].content.lower()
    return any(x in last for x in ["salary", "legal", "law"])


# -----------------------------
# Filtering Logic
# -----------------------------
def filter_catalog(context):
    results = []

    for item in CATALOG:
        name = str(item).lower()

        if context["role"] and context["role"] not in name:
            continue

        if context["personality"] and "personality" not in name:
            continue

        # Try extracting fields safely
        results.append({
            "name": item.get("name", "Unknown"),
            "url": item.get("url", ""),
            "test_type": item.get("test_type", "Unknown")
        })

    return results[:10]


# -----------------------------
# Comparison Logic
# -----------------------------
def handle_comparison(messages):
    last = messages[-1].content.lower()

    if "opq" in last and "gsa" in last:
        return "OPQ32r measures personality traits, while GSA measures cognitive ability like reasoning."

    return "Please specify two SHL assessments to compare."


# -----------------------------
# Routes
# -----------------------------
@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat")
def chat(request: ChatRequest):
    messages = request.messages
    context = extract_context(messages)

    # OUT OF SCOPE
    if is_out_of_scope(messages):
        return {
            "reply": "I can only help with SHL assessments.",
            "recommendations": [],
            "end_of_conversation": False
        }

    # COMPARISON
    if is_comparison(messages):
        return {
            "reply": handle_comparison(messages),
            "recommendations": [],
            "end_of_conversation": False
        }

    # CLARIFICATION
    if is_vague(context):
        return {
            "reply": "Could you clarify role, experience level, and skills?",
            "recommendations": [],
            "end_of_conversation": False
        }

    # RECOMMENDATION / REFINEMENT
    results = filter_catalog(context)

    if not results:
        return {
            "reply": "No matching SHL assessments found. Please refine your query.",
            "recommendations": [],
            "end_of_conversation": False
        }

    return {
        "reply": f"Here are {len(results)} SHL assessments based on your requirements.",
        "recommendations": results,
        "end_of_conversation": False
    }