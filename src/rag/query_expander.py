from functools import lru_cache

from dotenv import load_dotenv
from groq import Groq

from src.rag.config import QUERY_EXPANSION_MODEL


# Load environment variables from .env
load_dotenv()

client = Groq()


def contains_arabic(text: str) -> bool:
    """
    Check whether the text contains Arabic characters.
    """
    return any(
        "\u0600" <= char <= "\u06FF"
        for char in text
    )


def _generate_expansion(
    query: str,
    stronger: bool = False,
) -> str:
    """
    Generate an English retrieval query from an Arabic query.

    The stronger prompt is used only when the first attempt
    produces an invalid expansion.
    """

    if stronger:
        prompt = f"""
Rewrite the Arabic user query below as ONE complete English search query
for retrieving evidence from official geospatial standards and technical
guidelines.

Rules:
- Preserve the full meaning of the Arabic query.
- Translate all important concepts into English.
- Preserve identifiers and technical terminology.
- Use relevant technical terms such as annotation, map display,
  scale bar, map elements, cartography, GIS, CRS, EPSG, and SANSRS
  only when they are implied by the original query.
- Do NOT answer the question.
- Do NOT invent facts, requirements, numbers, standards, or page numbers.
- Do NOT summarize the query.
- Do NOT return keywords only.
- Do NOT return Arabic.
- Return exactly one complete English search query.
- The result should normally contain at least 6 words.

Example:

Arabic:
ما متطلب الدقة الأفقية للمنتجات الكارتوغرافية؟

Correct:
What is the horizontal accuracy requirement for cartographic products?

Incorrect:
horizontal

Arabic query:
{query}
"""

    else:
        prompt = f"""
Rewrite the following Arabic user query as ONE complete English search query
for retrieving relevant evidence from official geospatial standards.

Rules:
- Preserve the full meaning of the original query.
- Preserve technical terms and identifiers.
- Do NOT answer the question.
- Do NOT invent facts, numbers, requirements, standards, or page numbers.
- Do NOT return keywords only.
- Do NOT return Arabic.
- Return only one complete English search query.

Example:

Arabic:
ما متطلب الدقة الأفقية للمنتجات الكارتوغرافية؟

Correct:
What is the horizontal accuracy requirement for cartographic products?

Incorrect:
horizontal

Arabic query:
{query}
"""

    response = client.chat.completions.create(
        model=QUERY_EXPANSION_MODEL,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        temperature=0,
        max_completion_tokens=300,
    )

    content = response.choices[0].message.content

    if not content:
        return ""

    return content.strip()


def _is_valid_expansion(
    original_query: str,
    expanded_query: str,
) -> bool:
    """
    Validate the generated English retrieval query.
    """

    if not expanded_query:
        return False

    expanded_query = expanded_query.strip()

    # It should not simply return the original Arabic query.
    if expanded_query == original_query.strip():
        return False

    # The expansion must be English/non-Arabic.
    if contains_arabic(expanded_query):
        return False

    # Reject keyword-only or suspiciously short outputs.
    if len(expanded_query.split()) < 4:
        return False

    return True


@lru_cache(maxsize=256)
def expand_query(query: str) -> str:
    """
    Expand an Arabic query into a complete English retrieval query.

    Strategy:
    1. English queries are returned unchanged.
    2. Arabic queries get one normal expansion attempt.
    3. If that result is invalid, retry once with a stronger prompt.
    4. If both attempts fail, safely fall back to the original query.
    """

    query = query.strip()

    if not query:
        return query

    # No expansion is needed for an English query.
    if not contains_arabic(query):
        return query

    try:
        # First attempt
        expanded = _generate_expansion(
            query=query,
            stronger=False,
        )

        if _is_valid_expansion(
            original_query=query,
            expanded_query=expanded,
        ):
            return expanded

        print(
            "First query expansion attempt was invalid. "
            "Retrying with stronger prompt..."
        )

        # Second attempt
        expanded_retry = _generate_expansion(
            query=query,
            stronger=True,
        )

        if _is_valid_expansion(
            original_query=query,
            expanded_query=expanded_retry,
        ):
            return expanded_retry

        print(
            "Query expansion failed after retry. "
            "Using original query."
        )

        return query

    except Exception as exc:
        print(
            f"Query expansion error: {exc}. "
            "Using original query."
        )

        return query