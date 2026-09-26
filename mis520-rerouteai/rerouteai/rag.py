"""Layer 3 - retrieval-augmented explanation.

Policy documents are split into sections, indexed with TF-IDF and retrieved by
similarity to the question. The LLM (Google Gemini, if GEMINI_API_KEY is set)
may only use the retrieved sections and the optimizer's numbers, and must cite
section IDs. Without a key, a deterministic template answers instead, so the
demo never depends on a network call.
"""

from __future__ import annotations

import os
import pathlib
import re
from dataclasses import dataclass

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

POLICY_DIR = pathlib.Path(__file__).resolve().parents[1] / "policies"


@dataclass
class Chunk:
    id: str
    doc: str
    heading: str
    text: str


def load_chunks(folder: pathlib.Path = POLICY_DIR) -> list[Chunk]:
    chunks = []
    for path in sorted(folder.glob("*.md")):
        parts = re.split(r"^## ", path.read_text(), flags=re.M)
        doc_title = parts[0].strip().splitlines()[0].lstrip("# ").strip()
        for i, part in enumerate(parts[1:], 1):
            heading, _, body = part.partition("\n")
            chunks.append(Chunk(f"{path.stem}#{i}", doc_title, heading.strip(), body.strip()))
    return chunks


class PolicyIndex:
    def __init__(self, chunks: list[Chunk] | None = None):
        self.chunks = chunks or load_chunks()
        self.vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True)
        self.matrix = self.vec.fit_transform([f"{c.heading} {c.heading} {c.text}" for c in self.chunks])

    def search(self, query: str, k: int = 3) -> list[tuple[Chunk, float]]:
        sims = cosine_similarity(self.vec.transform([query]), self.matrix)[0]
        order = sims.argsort()[::-1][:k]
        return [(self.chunks[i], float(sims[i])) for i in order if sims[i] > 0.02]


ANSWER_PROMPT = """You are ReRouteAI, assisting an airline agent and a disrupted traveller.
Answer the question using ONLY (a) the recommendation data and (b) the policy excerpts below.
Cite policy excerpts by their [id]. If the excerpts do not answer something, say so plainly.
Do not invent flights, prices, probabilities or legal rules. Under 180 words.
End with: "Agent approval required before rebooking."

Question: {question}

Recommendation data:
{facts}

Policy excerpts:
{excerpts}
"""


def answer(question: str, facts: str, index: PolicyIndex, k: int = 3) -> tuple[str, list[tuple[Chunk, float]], str]:
    # the question drives retrieval; the situation adds at most one extra section
    hits = index.search(question, k)
    seen = {c.id for c, _ in hits}
    hits += [(c, sc) for c, sc in index.search(facts, 1) if c.id not in seen]
    excerpts = "\n\n".join(f"[{c.id}] {c.heading}: {c.text}" for c, _ in hits)
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if key:
        try:
            from google import genai  # pip install google-genai
            client = genai.Client(api_key=key)
            resp = client.models.generate_content(
                model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
                contents=ANSWER_PROMPT.format(question=question, facts=facts, excerpts=excerpts))
            if resp.text:
                return resp.text, hits, "gemini"
        except Exception as exc:
            facts += f"\n(LLM unavailable: {exc})"
    lines = [facts, "", "Relevant policy:"] + [f"- [{c.id}] {c.heading}: {first_sentences(c.text)}" for c, _ in hits]
    lines.append("\nAgent approval required before rebooking.")
    return "\n".join(lines), hits, "template"


def first_sentences(text: str, n: int = 2) -> str:
    return " ".join(re.split(r"(?<=[.!?])\s+", text)[:n])
