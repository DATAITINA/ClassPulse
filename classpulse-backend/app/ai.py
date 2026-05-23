import json
import os
import re
from typing import Any, Dict, List

from openai import OpenAI

MOOD_SCORES = {
    "stressed": -2,
    "bored": -1,
    "confused": -1,
    "calm": 0,
    "engaged": 1,
    "excited": 2,
}

SEVERE_ABUSE_TERMS = {
    "idiot",
    "stupid",
    "useless",
    "hate",
    "trash",
    "dumb",
    "nonsense",
}

WARNING_TERMS = {
    "annoying",
    "boring",
    "terrible",
    "awful",
    "lazy",
    "bad",
    "rude",
    "worst",
}

POSITIVE_TERMS = {
    "clear",
    "helpful",
    "engaging",
    "good",
    "great",
    "supportive",
    "interactive",
    "understand",
    "enjoy",
}

NEGATIVE_TERMS = WARNING_TERMS | {
    "confusing",
    "fast",
    "unclear",
    "difficult",
    "hard",
    "overwhelming",
}


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


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_mood(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower()
    if normalized not in MOOD_SCORES:
        return None
    return normalized


def _describe_mood_shift(mood_before: str | None, mood_after: str | None) -> str | None:
    normalized_before = _normalize_mood(mood_before)
    normalized_after = _normalize_mood(mood_after)
    if not normalized_before or not normalized_after:
        return None

    difference = MOOD_SCORES[normalized_after] - MOOD_SCORES[normalized_before]
    if difference > 0:
        return "lifted"
    if difference < 0:
        return "declined"
    return "steady"


def _build_default_response(mood_before: str | None, mood_after: str | None) -> Dict[str, Any]:
    return {
        "accepted": True,
        "moderation_status": "allowed",
        "moderation_message": "Feedback received and analyzed.",
        "respectful_rewrite": "",
        "sentiment": "neutral",
        "key_issues": [],
        "suggestions": [],
        "strengths": [],
        "next_step_ai": "",
        "pulse_check": {
            "mood_before": _normalize_mood(mood_before),
            "mood_after": _normalize_mood(mood_after),
            "mood_shift": _describe_mood_shift(mood_before, mood_after),
        },
    }


def _infer_sentiment(feedback_text: str) -> str:
    lowered = feedback_text.lower()
    positive_hits = sum(1 for term in POSITIVE_TERMS if term in lowered)
    negative_hits = sum(1 for term in NEGATIVE_TERMS if term in lowered)

    if negative_hits > positive_hits:
        return "negative"
    if positive_hits > negative_hits:
        return "positive"
    return "neutral"


def _fallback_lists(feedback_text: str) -> Dict[str, List[str] | str]:
    lowered = feedback_text.lower()
    key_issues: List[str] = []
    strengths: List[str] = []

    if any(term in lowered for term in {"fast", "pace", "rushed"}):
        key_issues.append("The pace may feel too fast during harder concepts.")
    if any(term in lowered for term in {"confusing", "unclear", "understand"}):
        key_issues.append("Students may need clearer explanations or checkpoints.")
    if any(term in lowered for term in {"example", "examples"}):
        strengths.append("Examples are being noticed as part of the teaching approach.")
    if any(term in lowered for term in {"engaging", "interactive", "discussion"}):
        strengths.append("Interactive moments are standing out to students.")
    if any(term in lowered for term in {"boring", "engagement", "participation"}):
        key_issues.append("Classroom engagement may need more energy or participation moments.")

    if not strengths and _infer_sentiment(feedback_text) != "negative":
        strengths.append("There are signs the class has a foundation students can build on.")

    if not key_issues:
        key_issues.append("Students want a clearer, more supportive learning experience.")

    suggestions = []
    if any("pace" in issue.lower() for issue in key_issues):
        suggestions.append("Slow down briefly during difficult concepts and add recap checkpoints.")
    if any("clear" in issue.lower() for issue in key_issues):
        suggestions.append("Use simpler explanations and one extra worked example before moving on.")
    if any("engagement" in issue.lower() for issue in key_issues):
        suggestions.append("Add a short interactive moment or question break during class.")
    if not suggestions:
        suggestions.append("Acknowledge the concern directly and make one visible class improvement next time.")

    next_step_ai = suggestions[0]

    return {
        "key_issues": key_issues[:3],
        "strengths": strengths[:3],
        "suggestions": suggestions[:3],
        "next_step_ai": next_step_ai,
    }


def _fallback_analysis(
    feedback_text: str,
    mood_before: str | None,
    mood_after: str | None,
    heuristic: Dict[str, str],
    reason: str = "",
) -> Dict[str, Any]:
    response_data = _build_default_response(mood_before, mood_after)
    response_data["moderation_status"] = heuristic["status"]
    response_data["respectful_rewrite"] = heuristic["respectful_rewrite"]

    fallback_lists = _fallback_lists(feedback_text)
    response_data.update(
        {
            "accepted": True,
            "sentiment": _infer_sentiment(feedback_text),
            "key_issues": fallback_lists["key_issues"],
            "suggestions": fallback_lists["suggestions"],
            "strengths": fallback_lists["strengths"],
            "next_step_ai": fallback_lists["next_step_ai"],
            "moderation_message": heuristic["message"]
            or (
                "Feedback received. ClassPulse generated a backup structured summary."
                if reason
                else "Feedback received and analyzed."
            ),
        }
    )
    return response_data


def _build_respectful_rewrite(feedback_text: str) -> str:
    cleaned = re.sub(r"\s+", " ", feedback_text).strip()
    if not cleaned:
        return ""
    return (
        "I am struggling with some parts of this class. Please focus on the teaching "
        "issues that made learning harder, such as pace, clarity, examples, or engagement."
    )


def _heuristic_moderation(feedback_text: str) -> Dict[str, str]:
    lowered = feedback_text.lower()
    severe_hits = sorted(term for term in SEVERE_ABUSE_TERMS if term in lowered)
    if severe_hits:
        return {
            "status": "blocked",
            "message": (
                "Please remove insulting language and focus on the classroom experience. "
                "ClassPulse accepts criticism, but not abuse."
            ),
            "respectful_rewrite": _build_respectful_rewrite(feedback_text),
        }

    warning_hits = sorted(term for term in WARNING_TERMS if term in lowered)
    if warning_hits:
        return {
            "status": "warn",
            "message": (
                "Your feedback can still be useful, but it would be stronger if you phrase "
                "it more constructively."
            ),
            "respectful_rewrite": _build_respectful_rewrite(feedback_text),
        }

    return {"status": "allowed", "message": "", "respectful_rewrite": ""}


def analyze_feedback(
    feedback_text: str, mood_before: str | None = None, mood_after: str | None = None
) -> Dict[str, Any]:
    response_data = _build_default_response(mood_before, mood_after)
    heuristic = _heuristic_moderation(feedback_text)
    response_data["moderation_status"] = heuristic["status"]
    response_data["moderation_message"] = (
        heuristic["message"] or response_data["moderation_message"]
    )
    response_data["respectful_rewrite"] = heuristic["respectful_rewrite"]

    if heuristic["status"] == "blocked":
        response_data["accepted"] = False
        response_data["next_step_ai"] = (
            "Ask the student to resubmit the feedback using specific, respectful classroom details."
        )
        return response_data

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return _fallback_analysis(
            feedback_text,
            mood_before,
            mood_after,
            heuristic,
            reason="missing_api_key",
        )

    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    client = OpenAI(api_key=api_key)

    prompt = (
        "You are helping ClassPulse analyze anonymous student feedback.\n\n"
        "Return valid JSON with these keys only:\n"
        "sentiment: one of positive, negative, neutral\n"
        "key_issues: array of short strings\n"
        "suggestions: array of short strings\n"
        "strengths: array of short strings\n"
        "next_step_ai: one practical recommendation for the teacher's next class\n"
        "moderation_status: allowed or warn\n"
        "moderation_message: short sentence\n"
        "respectful_rewrite: short rewrite if the tone should be improved, otherwise an empty string\n\n"
        "Rules:\n"
        "- Keep everything concise and practical.\n"
        "- Mention strengths as well as problems.\n"
        "- If the feedback is emotionally worded but still usable, set moderation_status to warn.\n"
        "- If the feedback is already respectful, set moderation_status to allowed.\n\n"
        f"Feedback:\n{feedback_text}"
    )

    try:
        response = client.chat.completions.create(
            model=model_name,
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Return only valid JSON. Arrays must contain short strings. "
                        "Do not include markdown."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
    except Exception as exc:
        return _fallback_analysis(
            feedback_text,
            mood_before,
            mood_after,
            heuristic,
            reason=f"openai_error:{exc}",
        )

    content = response.choices[0].message.content or ""
    data = _extract_json(content)
    if not data:
        return _fallback_analysis(
            feedback_text,
            mood_before,
            mood_after,
            heuristic,
            reason="parse_error",
        )

    sentiment = _normalize_text(data.get("sentiment", "neutral")).lower()
    if sentiment not in {"positive", "negative", "neutral"}:
        sentiment = "neutral"

    key_issues = _normalize_list(data.get("key_issues", []))
    suggestions = _normalize_list(data.get("suggestions", []))
    strengths = _normalize_list(data.get("strengths", []))
    next_step_ai = _normalize_text(data.get("next_step_ai", ""))

    ai_status = _normalize_text(data.get("moderation_status", "allowed")).lower()
    if ai_status not in {"allowed", "warn"}:
        ai_status = "allowed"

    ai_message = _normalize_text(data.get("moderation_message", ""))
    ai_rewrite = _normalize_text(data.get("respectful_rewrite", ""))

    final_status = "warn" if "warn" in {heuristic["status"], ai_status} else "allowed"
    final_message = heuristic["message"] or ai_message or "Feedback received and analyzed."
    final_rewrite = response_data["respectful_rewrite"] or ai_rewrite

    response_data.update(
        {
            "accepted": True,
            "moderation_status": final_status,
            "moderation_message": final_message,
            "respectful_rewrite": final_rewrite,
            "sentiment": sentiment,
            "key_issues": key_issues,
            "suggestions": suggestions,
            "strengths": strengths,
            "next_step_ai": next_step_ai,
        }
    )
    return response_data
