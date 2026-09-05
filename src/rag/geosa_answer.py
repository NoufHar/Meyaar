import os

from dotenv import load_dotenv
from groq import Groq

from src.rag.retriever import retrieve_geosa_context


load_dotenv()

client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)


def build_context(passages):
    parts = []

    for index, passage in enumerate(passages, start=1):
        parts.append(
            f"""
Evidence {index}
Source: {passage["source"]}
Page: {passage["page"]}
Category: {passage["category"]}

{passage["text"]}
""".strip()
        )

    return "\n\n".join(parts)


def answer_with_geosa(question):
    results = retrieve_geosa_context(
        question,
        top_k=10
    )

    context = build_context(results)

    prompt = f"""
You are Meyaar's GeoSA evidence assistant.

Answer the user's question using ONLY the supplied evidence.

IMPORTANT RULES:

1. First identify which evidence passage directly answers the question.
2. Do NOT combine information from multiple passages unless it is necessary to answer the question.
3. Do NOT use a passage just because it is related to the topic.
4. If the question asks for a definition, provide only the definition and a short clarification if needed.
5. If the question asks for a requirement, value, code, component, list, or rule, provide only the requested information.
6. Do NOT add unrelated examples, percentages, thresholds, requirements, or background information.
7. Do NOT infer a new requirement from the evidence.
8. Do NOT say something "must be corrected" unless the evidence explicitly states that.
9. Do NOT claim official GeoSA compliance or certification.
10. Meyaar findings are findings or candidate findings, not official GeoSA violations unless explicitly supported by the evidence.
11. Every factual claim must be supported by the selected evidence.
12. Cite the exact source and page that directly support the answer.
13. Prefer the single strongest direct source/page over several loosely related sources.
14. If no supplied passage directly supports the answer, say:
   "The retrieved GeoSA evidence is insufficient to answer this question confidently."
15. Do NOT invent a source, page, number, requirement, or interpretation.
16. Do NOT add a separate "quality concept" section unless the user explicitly asks for one.

Answer concisely.

Use this format:

Answer:
<direct answer>

Source:
<source name>, page <page number>

USER QUESTION:
{question}

EVIDENCE:
{context}
"""

    response = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a strict evidence-grounded assistant. "
                    "You must not add information that is not directly supported "
                    "by the provided evidence."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=0,
        max_completion_tokens=700,
    )

    answer = response.choices[0].message.content.strip()

    return {
        "answer": answer,
        "sources": results,
    }