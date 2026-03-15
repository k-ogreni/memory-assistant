import json
import os

import ollama
from dotenv import load_dotenv

from prompts import EXTRACTION_SYSTEM, EXTRACTION_EXAMPLES, INTENT_SYSTEM, INTENT_EXAMPLES

load_dotenv()

MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")

REJECT_VALUES = {"not specified", "not provided", "unknown", "n/a", "none", "null", ""}


def _clean_extracted(data: dict) -> dict:
    """Remove vague, empty, or hallucinated values from LLM output."""
    cleaned = {}
    for key, value in data.items():
        if isinstance(value, dict):
            inner = {k: v for k, v in value.items()
                     if isinstance(v, str) and v.strip().lower() not in REJECT_VALUES}
            if inner:
                cleaned[key] = inner
        elif isinstance(value, str) and value.strip().lower() not in REJECT_VALUES:
            cleaned[key] = value
    return cleaned


def extract_memory_fields(user_message: str) -> dict:
    """
    Ask the LLM to extract allowlisted fields from a user message.
    Returns a dict of candidate fields (still needs policy validation).
    """
    try:
        response = ollama.chat(
            model=MODEL,
            messages=[
                {"role": "system", "content": EXTRACTION_SYSTEM},
                {"role": "user", "content": EXTRACTION_EXAMPLES + user_message},
            ],
            format="json",
        )
        content = response["message"]["content"].strip()
        extracted = json.loads(content)
        if not isinstance(extracted, dict):
            return {}
        cleaned = _clean_extracted(extracted)
        if cleaned:
            print(f"[LLM] Extracted candidate fields: {cleaned}")
        return cleaned
    except Exception as e:
        print(f"[LLM] Extraction failed: {e}")
        return {}


def parse_retrieval_intent(user_message: str) -> dict:
    """
    Ask the LLM to identify who the user is asking about and which fields they want.
    Returns {"target": str | None, "fields": list[str]}.
    """
    try:
        response = ollama.chat(
            model=MODEL,
            messages=[
                {"role": "system", "content": INTENT_SYSTEM},
                {"role": "user", "content": INTENT_EXAMPLES + user_message},
            ],
            format="json",
        )
        content = response["message"]["content"].strip()
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            return {"target": None, "fields": []}
        target = parsed.get("target")
        fields = parsed.get("fields", [])
        if not isinstance(fields, list):
            fields = []
        return {"target": target, "fields": fields}
    except Exception as e:
        print(f"[LLM] Intent parsing failed: {e}")
        return {"target": None, "fields": []}


def build_system_prompt(
    user_name: str,
    relevant_context: dict | None = None,
    is_retrieval: bool = False,
) -> str:
    """
    Build a system prompt with context rendered as a readable bulleted list.
    is_retrieval=True instructs the LLM to answer directly from the profile data.
    """
    prompt = f"You are a helpful workplace assistant speaking with {user_name}.\n\n"

    if relevant_context:
        prompt += "Profile information (factual, use this to answer questions):\n"
        for key, value in relevant_context.items():
            if isinstance(value, dict):
                if not value:
                    continue
                prompt += f"- {key}:\n"
                for sub_key, sub_val in value.items():
                    prompt += f"  - {sub_key}: {sub_val}\n"
            elif isinstance(value, list):
                if not value:
                    continue
                prompt += f"- {key}:\n"
                for item in value:
                    if isinstance(item, dict):
                        item_name = item.get("name", "")
                        sub_items = {k: v for k, v in item.items() if k != "name"}
                        if sub_items:
                            prompt += f"  - {item_name}:\n"
                            for k, v in sub_items.items():
                                prompt += f"    - {k}: {v}\n"
                        else:
                            prompt += f"  - {item_name}\n"
                    else:
                        prompt += f"  - {item}\n"
            else:
                prompt += f"- {key}: {value}\n"
        prompt += "\n"

    if is_retrieval:
        prompt += (
            "Answer the user's question directly using ONLY the profile information above. "
            "List ALL items if multiple are present for the requested field. "
            "Do not hedge or add disclaimers if the answer is in the profile."
        )
    else:
        prompt += (
            "Be helpful and conversational. "
            "The conversation history above is authoritative - trust what you previously said. "
            "Do not make up facts that were not stated in this conversation or in the profile information."
        )
    if relevant_context and "stored" in relevant_context:
        prompt += " Acknowledge what was just stored in the profile."
    return prompt


def generate_response(system_prompt: str, conversation_history: list[dict]) -> str:
    """Generate a conversational response using Ollama."""
    try:
        messages = [{"role": "system", "content": system_prompt}] + conversation_history
        response = ollama.chat(model=MODEL, messages=messages)
        return response["message"]["content"].strip()
    except Exception as e:
        return f"[Error generating response: {e}]"
