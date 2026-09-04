import os
from functools import lru_cache

import moondream as md
from dotenv import load_dotenv
from PIL import Image


load_dotenv()


ELEMENT_QUESTIONS = {
    "title": (
        "Is the map title present in this map? "
        "Answer only yes or no."
    ),
    "legend": (
        "Is the map legend present in this map? "
        "Answer only yes or no."
    ),
    "scale": (
        "Is the map scale present in this map? "
        "Answer only yes or no."
    ),
    "north_arrow": (
        "Is the north arrow present in this map? "
        "Answer only yes or no."
    ),
}


class VisionModelNotConfiguredError(RuntimeError):
    pass


@lru_cache
def get_vision_model():
    api_key = os.getenv("MOONDREAM_API_KEY")
    model_id = os.getenv("MOONDREAM_MODEL_ID")

    if not api_key or not model_id:
        raise VisionModelNotConfiguredError(
            "MOONDREAM_API_KEY and MOONDREAM_MODEL_ID "
            "must be configured."
        )

    return md.vl(
        api_key=api_key,
        model=model_id,
    )


def normalize_answer(value: str) -> str:
    answer = str(value).strip().lower()

    if answer.startswith("yes"):
        return "yes"

    if answer.startswith("no"):
        return "no"

    return "invalid"


def analyze_image(image: Image.Image) -> dict:
    model = get_vision_model()

    elements = []
    issues = []

    for element, question in ELEMENT_QUESTIONS.items():
        result = model.query(
            image,
            question,
            settings={
                "temperature": 0.0,
                "max_tokens": 4,
            },
        )

        answer = normalize_answer(
            result.get("answer", "")
        )

        present = answer == "yes"

        elements.append({
            "element": element,
            "present": present,
            "confidence": None,
            "location": None,
        })

        if not present:
            issues.append({
                "error_type": f"missing_{element}",
                "severity": "warning",
                "message": (
                    f"The map does not contain "
                    f"a detectable {element.replace('_', ' ')}."
                ),
                "confidence": None,
            })

    return {
        "elements": elements,
        "issues": issues,
    }