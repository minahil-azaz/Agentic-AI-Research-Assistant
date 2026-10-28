import hashlib, json, logging, re
from typing import List, Tuple

import numpy as np
import requests
from bs4 import BeautifulSoup
from django.conf import settings
from types import SimpleNamespace

logger = logging.getLogger(__name__)

_embed_model  = None
_gemini_model = None


class GenerationError(RuntimeError):
    """Raised when the LLM returns no usable text."""


def _to_list(vec) -> List[float]:
    """Embeddings may come back as numpy arrays or plain lists."""
    return vec.tolist() if hasattr(vec, "tolist") else list(vec)


def is_mock_gemini() -> bool:
    return bool(getattr(settings, "FORCE_MOCK_GEMINI", False) or not getattr(settings, "GEMINI_API_KEY", None))


def is_mock_embeddings() -> bool:
    return bool(getattr(settings, "FORCE_MOCK_EMBEDDINGS", False))


def get_embed_model():
    global _embed_model
    if _embed_model is None:
        # Allow forcing a mock embedding model for low-memory local testing
        if is_mock_embeddings():
            class _MockEmbed:
                """
                Hashed bag-of-words vectors. Not semantic, but deterministic and
                non-zero, so cosine retrieval still ranks chunks that share words
                with the query higher (zero vectors make cosine distance NaN).
                """
                def encode(self, texts, show_progress_bar=False):
                    dim = getattr(settings, "EMBEDDING_DIM", 384)
                    out = np.zeros((len(texts), dim), dtype=np.float32)
                    for row, text in enumerate(texts):
                        for word in re.findall(r"\w+", text.lower()):
                            h = int(hashlib.md5(word.encode()).hexdigest(), 16)
                            out[row, h % dim] += 1.0
                        norm = np.linalg.norm(out[row])
                        out[row] = out[row] / norm if norm else 1.0 / np.sqrt(dim)
                    return out

            _embed_model = _MockEmbed()
        else:
            from sentence_transformers import SentenceTransformer
            _embed_model = SentenceTransformer(settings.EMBEDDING_MODEL)
    return _embed_model


class _MockGemini:
    """
    Offline stand-in for Gemini. Returns a JSON plan for planning prompts and
    an extractive report (built only from the supplied source excerpts) for
    report prompts, so the full pipeline can be exercised without an API key.
    """
    def generate_content(self, prompt):
        if "Return ONLY a valid JSON array" in prompt:
            query = prompt.rsplit("User query:", 1)[-1].strip()
            text  = json.dumps([query, f"{query} overview", f"{query} latest research"])
        else:
            text = self._report(prompt)
        candidate = SimpleNamespace(content=SimpleNamespace(parts=[text]), finish_reason=1)
        return SimpleNamespace(candidates=[candidate], text=text)

    @staticmethod
    def _report(prompt):
        query   = re.search(r"QUERY:\s*(.+)", prompt)
        query   = query.group(1).strip() if query else "the query"
        excerpts = re.findall(r"\[Source (\d+)\] (.+?)(?=\n\n\[Source \d+\]|\n\nRULES:)", prompt, re.DOTALL)
        lines = [
            "> **Mock mode:** this report was assembled from source excerpts without an LLM. "
            "Set `GEMINI_API_KEY` and `FORCE_MOCK_GEMINI=False` for a generated report.",
            "", "## Overview", f"Research summary for: **{query}**.", "", "## Key Findings",
        ]
        for n, text in excerpts[:8]:
            sentence = re.split(r"(?<=[.!?])\s", text.strip(), 1)[0][:300]
            lines.append(f"- {sentence} [Source {n}]")
        if not excerpts:
            lines.append("- No source excerpts were available.")
        lines += ["", "## Conclusion", "See the sources below for full details."]
        return "\n".join(lines)


def get_gemini():
    global _gemini_model
    if _gemini_model is None:
        if is_mock_gemini():
            _gemini_model = _MockGemini()
        else:
            import google.generativeai as genai
            genai.configure(api_key=settings.GEMINI_API_KEY)
            # Use configurable model from settings so projects can switch models
            model_name = getattr(settings, "GEMINI_MODEL", "gemini-2.5-flash")
            _gemini_model = genai.GenerativeModel(model_name)
    return _gemini_model


def generate_text(prompt: str) -> str:
    """Call Gemini and return its text, raising GenerationError with a readable reason."""
    try:
        response = get_gemini().generate_content(prompt)
    except Exception as e:
        msg = str(e)
        if "429" in msg or "quota" in msg.lower():
            raise GenerationError("Gemini quota exceeded. Wait a minute or switch GEMINI_MODEL.") from e
        if "API key" in msg or "403" in msg or "401" in msg:
            raise GenerationError("Gemini rejected the API key. Check GEMINI_API_KEY.") from e
        raise GenerationError(f"Gemini request failed: {msg[:300]}") from e

    if not response.candidates or not response.candidates[0].content.parts:
        reason = getattr(getattr(response, "prompt_feedback", None), "block_reason", None)
        raise GenerationError(f"Gemini returned no content{f' (blocked: {reason})' if reason else ''}.")
    try:
        text = response.text
    except ValueError as e:  # raised by the SDK when the candidate was cut off by safety filters
        raise GenerationError(f"Gemini response was blocked: {e}") from e
    if not text or not text.strip():
        raise GenerationError("Gemini returned an empty response.")
    return text


def plan_searches(query: str) -> List[str]:
    from .prompts import PLAN_PROMPT
    try:
        text = generate_text(PLAN_PROMPT.format(query=query))
        # Extract JSON list using regex to find content between brackets
        match = re.search(r"(\[.*\])", text, re.DOTALL)
        if match:
            text = match.group(1)

        result = json.loads(text)
        if isinstance(result, list):
            searches = [str(s).strip() for s in result if str(s).strip()][:5]
            if searches:
                return searches
    except Exception as e:
        logger.warning("Plan extraction failed: %s", e)
    return [query]


def web_search(query: str, max_results: int = 5) -> List[dict]:
    if not settings.TAVILY_API_KEY:
        raise RuntimeError("TAVILY_API_KEY is not set, so the web cannot be searched.")
    from tavily import TavilyClient
    client = TavilyClient(api_key=settings.TAVILY_API_KEY)
    try:
        resp = client.search(query=query, search_depth="basic", max_results=max_results)
        return resp.get("results", [])
    except Exception as e:
        logger.error("Tavily error for '%s': %s", query, e)
        return []


def scrape_page(url: str) -> Tuple[str, str]:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; ResearchBot/1.0)"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        # soup.title.string is None when <title> has nested tags or is empty
        title = soup.title.get_text(strip=True) if soup.title else ""
        paras = soup.find_all(["p", "h1", "h2", "h3", "li"])
        text  = " ".join(p.get_text(" ", strip=True) for p in paras)
        text  = re.sub(r"\s+", " ", text).strip()
        return title, text[:15000]
    except Exception as e:
        logger.warning("Scrape failed %s: %s", url, e)
        return "", ""


def chunk_text(text: str, chunk_size: int = 400, overlap: int = 50) -> List[str]:
    words, chunks, i = text.split(), [], 0
    while i < len(words):
        chunks.append(" ".join(words[i: i + chunk_size]))
        i += chunk_size - overlap
    return chunks


def embed_and_store(source_id: int, text: str) -> int:
    from research.models import ResearchEmbedding, ResearchSource
    source     = ResearchSource.objects.get(id=source_id)
    model      = get_embed_model()
    chunks     = chunk_text(text)
    if not chunks:
        return 0
    embeddings = model.encode(chunks, show_progress_bar=False)
    objs = [
        ResearchEmbedding(source=source, chunk_text=c, chunk_index=i, embedding=_to_list(e))
        for i, (c, e) in enumerate(zip(chunks, embeddings))
    ]
    ResearchEmbedding.objects.bulk_create(objs, ignore_conflicts=True)
    return len(objs)


def retrieve_chunks(query: str, query_id: int, top_k: int = 12) -> List[dict]:
    from pgvector.django import CosineDistance
    from research.models import ResearchEmbedding
    vec     = _to_list(get_embed_model().encode([query])[0])
    results = (
        ResearchEmbedding.objects
        .filter(source__query_id=query_id)
        .select_related("source")
        .annotate(distance=CosineDistance("embedding", vec))
        .order_by("distance")[:top_k]
    )
    return [
        {"text": r.chunk_text, "url": r.source.url, "title": r.source.title}
        for r in results
    ]
