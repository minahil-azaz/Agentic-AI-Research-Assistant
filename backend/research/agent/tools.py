import json, logging, re
from typing import List, Tuple

import requests
from bs4 import BeautifulSoup
from django.conf import settings
from types import SimpleNamespace

logger = logging.getLogger(__name__)

_embed_model  = None
_gemini_model = None


def get_embed_model():
    global _embed_model
    if _embed_model is None:
        # Allow forcing a mock embedding model for low-memory local testing
        if getattr(settings, "FORCE_MOCK_EMBEDDINGS", False):
            class _MockEmbed:
                def encode(self, texts, show_progress_bar=False):
                    # Return deterministic zero vectors sized to EMBEDDING_DIM
                    dim = getattr(settings, "EMBEDDING_DIM", 384)
                    import numpy as _np
                    return _np.zeros((len(texts), dim)).tolist()

            _embed_model = _MockEmbed()
        else:
            from sentence_transformers import SentenceTransformer
            _embed_model = SentenceTransformer(settings.EMBEDDING_MODEL)
    return _embed_model


def get_gemini():
    global _gemini_model
    if _gemini_model is None:
        # Respect explicit force-mock flag for local testing
        if getattr(settings, "FORCE_MOCK_GEMINI", False) or not getattr(settings, "GEMINI_API_KEY", None):
            class _MockModel:
                def generate_content(self, prompt):
                    # Provide a minimal response object compatible with
                    # the code expectations: .text and .candidates
                    text = "Auto-generated mock report based on prompt."\
                           "\n\n## Sources\n[Source 1] https://example.com"
                    candidate = SimpleNamespace(content=SimpleNamespace(parts=["mock"]), text=text)
                    return SimpleNamespace(candidates=[candidate], text=text)

            _gemini_model = _MockModel()
        else:
            import google.generativeai as genai
            genai.configure(api_key=settings.GEMINI_API_KEY)
            # Use configurable model from settings so projects can switch models
            model_name = getattr(settings, "GEMINI_MODEL", "gemini-2.5-flash")
            _gemini_model = genai.GenerativeModel(model_name)
    return _gemini_model


def plan_searches(query: str) -> List[str]:
    from .prompts import PLAN_PROMPT
    model    = get_gemini()
    try:
        response = model.generate_content(PLAN_PROMPT.format(query=query))
        if not response.candidates or not response.candidates[0].content.parts:
            logger.error("Gemini blocked the prompt or returned no content.")
            return [query]
            
        text = response.text
        # Extract JSON list using regex to find content between brackets
        match = re.search(r"(\[.*\])", text, re.DOTALL)
        if match:
            text = match.group(1)
        
        result = json.loads(text)
        if isinstance(result, list):
            return [str(s) for s in result[:5]]
    except Exception as e:
        logger.warning("Plan extraction failed: %s", e)
    return [query]


def web_search(query: str, max_results: int = 5) -> List[dict]:
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
        title = soup.title.string.strip() if soup.title else ""
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
        ResearchEmbedding(source=source, chunk_text=c, chunk_index=i, embedding=e.tolist())
        for i, (c, e) in enumerate(zip(chunks, embeddings))
    ]
    ResearchEmbedding.objects.bulk_create(objs, ignore_conflicts=True)
    return len(objs)


def retrieve_chunks(query: str, query_id: int, top_k: int = 12) -> List[dict]:
    from pgvector.django import CosineDistance
    from research.models import ResearchEmbedding
    vec     = get_embed_model().encode([query])[0].tolist()
    results = (
        ResearchEmbedding.objects
        .filter(source__query_id=query_id)
        .annotate(distance=CosineDistance("embedding", vec))
        .order_by("distance")[:top_k]
    )
    return [
        {"text": r.chunk_text, "url": r.source.url, "title": r.source.title}
        for r in results
    ]
