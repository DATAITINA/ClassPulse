import json
import os
import re
from typing import Any, Dict, List

from fastapi import HTTPException
from openai import OpenAI

MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def _extract_json(text: str) -> Dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\n", "", cleaned)
        cleaned = re.sub(r"```$", "", cleaned).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}

    return {}


def _normalize_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        parts = [part.strip("- ") for part in value.splitlines()]
        return [p for p in parts if p]
    return []


def analyze_feedback(feedback_text: str) -> Dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not set")

    client = OpenAI(api_key=api_key)

    prompt = (
        "Analyze the following student feedback.\n\n"
        "Return:\n"
        "1. Sentiment (positive, negative, neutral)\n"
        "2. Key issues (bullet points)\n"
        "3. Suggestions for improvement\n\n"
        "Keep it concise and structured.\n\n"
        f"Feedback:\n{feedback_text}"
    )

    response = client.chat.completions.create(
        model=MODEL_NAME,
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "Return only valid JSON with keys: sentiment, key_issues, suggestions. "
                    "key_issues and suggestions must be arrays of short strings."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    )

    content = response.choices[0].message.content or ""
    data = _extract_json(content)
    if not data:
        raise HTTPException(status_code=500, detail="AI response could not be parsed")

    sentiment = str(data.get("sentiment", "neutral")).lower().strip()
    if sentiment not in {"positive", "negative", "neutral"}:
        sentiment = "neutral"

    key_issues = _normalize_list(data.get("key_issues", []))
    suggestions = _normalize_list(data.get("suggestions", []))

    return {
        "sentiment": sentiment,
        "key_issues": key_issues,
        "suggestions": suggestions,
    }
