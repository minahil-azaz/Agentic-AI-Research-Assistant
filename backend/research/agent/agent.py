import logging
from typing import Callable, Dict, List, Optional, TypedDict

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    query_id:    int
    query:       str
    sub_searches: List[str]
    raw_results: List[dict]
    source_ids:  List[int]
    chunks:      List[dict]
    sreport:      str
    error:       Optional[str]


class ResearchAgent:
    def __init__(self, on_event: Optional[Callable] = None):
        self.on_event = on_event or (lambda t, d: None)

    def _emit(self, t: str, d: dict):
        self.on_event(t, d)

    # ── Node 1: Plan ──────────────────────────────────────────────────────────
    def plan(self, state: AgentState) -> AgentState:
        from research.models import ResearchQuery
        from .tools import plan_searches

        self._emit("status", {"step": "planning", "message": "Planning search strategy…"})
        ResearchQuery.objects.filter(id=state["query_id"]).update(status="planning", status_message="Planning")

        try:
            searches = plan_searches(state["query"])
        except Exception as e:
            logger.warning("Plan failed, using raw query: %s", e)
            searches = [state["query"]]

        self._emit("plan", {"sub_searches": searches})
        return {**state, "sub_searches": searches}

    # ── Node 2: Search ────────────────────────────────────────────────────────
    def search(self, state: AgentState) -> AgentState:
        from research.models import ResearchQuery
        from .tools import web_search

        self._emit("status", {"step": "searching", "message": "Searching the web…"})
        ResearchQuery.objects.filter(id=state["query_id"]).update(status="searching", status_message="Searching")

        seen, results = set(), []
        for q in state["sub_searches"]:
            for r in web_search(q, max_results=4):
                url = r.get("url", "")
                if url and url not in seen:
                    seen.add(url)
                    results.append(r)

        if not results:
            raise RuntimeError("The web search returned no results. Check TAVILY_API_KEY or try rephrasing the question.")

        self._emit("search_results", {"count": len(results)})
        return {**state, "raw_results": results}

    # ── Node 3: Scrape + Embed ────────────────────────────────────────────────
    def scrape_and_embed(self, state: AgentState) -> AgentState:
        from research.models import ResearchQuery, ResearchSource
        from .tools import scrape_page, embed_and_store

        self._emit("status", {"step": "scraping", "message": "Reading sources…"})
        ResearchQuery.objects.filter(id=state["query_id"]).update(status="scraping", status_message="Reading sources")

        query_obj  = ResearchQuery.objects.get(id=state["query_id"])
        sources    = []
        total      = len(state["raw_results"])

        for i, result in enumerate(state["raw_results"]):
            url = result.get("url", "")
            if not url:
                continue
            self._emit("source_found", {"url": url, "index": i + 1, "total": total})

            fallback_content = result.get("content", "") or result.get("raw_content", "")
            fallback_title   = result.get("title", "")

            title, full_text = scrape_page(url)
            title   = title or fallback_title
            content = full_text if len(full_text) > 200 else fallback_content

            if not content:
                continue

            source, _ = ResearchSource.objects.get_or_create(
                query=query_obj, url=url,
                defaults={"title": title[:500], "content": content, "snippet": content[:300]},
            )
            sources.append(source)

        if not sources:
            raise RuntimeError("None of the search results could be read.")

        self._emit("status", {"step": "embedding", "message": f"Indexing {len(sources)} sources…"})
        for i, source in enumerate(sources):
            ResearchQuery.objects.filter(id=state["query_id"]).update(
                status="embedding",
                status_message=f"Embedding {i+1}/{len(sources)}",
            )
            try:
                n = embed_and_store(source.id, source.content)
                self._emit("embedded", {"url": source.url, "chunks": n})
            except Exception as e:
                logger.warning("Embed failed %s: %s", source.url, e)

        return {**state, "source_ids": [s.id for s in sources]}

    # ── Node 4: Reflect ───────────────────────────────────────────────────────
    def reflect(self, state: AgentState) -> AgentState:
        from research.models import ResearchQuery, ResearchSource
        from .tools import retrieve_chunks

        self._emit("status", {"step": "writing", "message": "Analysing evidence…"})
        ResearchQuery.objects.filter(id=state["query_id"]).update(status="writing", status_message="Analysing evidence")

        try:
            chunks = retrieve_chunks(state["query"], state["query_id"], top_k=14)
        except Exception as e:
            logger.warning("Retrieval failed, falling back to raw source text: %s", e)
            chunks = []

        if not chunks:
            # Embedding/retrieval failed: ground the report on the scraped text directly
            chunks = [
                {"text": s.content[:2500], "url": s.url, "title": s.title}
                for s in ResearchSource.objects.filter(query_id=state["query_id"])
            ]

        self._emit("context_ready", {"chunk_count": len(chunks)})
        return {**state, "chunks": chunks}

    # ── Node 5: Write ─────────────────────────────────────────────────────────
    def write(self, state: AgentState) -> AgentState:
        from research.models import ResearchQuery, ResearchSource
        from .prompts import WRITE_REPORT_PROMPT
        from .tools import generate_text

        self._emit("status", {"step": "writing", "message": "Writing report…"})

        # Number sources in the same order the UI lists them (ResearchSource.Meta.ordering),
        # so "[Source N]" in the report matches source card N.
        src_objs = list(
            ResearchSource.objects.filter(query_id=state["query_id"]).values("id", "url", "title", "snippet")
        )
        number = {s["url"]: i + 1 for i, s in enumerate(src_objs)}

        context_parts = [
            f"[Source {number[c['url']]}] {c['text']}"
            for c in state["chunks"][:12] if c["url"] in number
        ]
        context = "\n\n".join(context_parts)
        prompt  = WRITE_REPORT_PROMPT.format(query=state["query"], context=context)

        report_text = generate_text(prompt)

        # Remove any '## Sources' section the model wrote; we append the canonical one
        main_part = report_text.split("\n## Sources", 1)[0].strip()

        src_lines = "\n".join(
            f"{i+1}. [{s['title'] or s['url']}]({s['url']})" for i, s in enumerate(src_objs)
        )
        full_report = f"{main_part}\n\n## Sources\n{src_lines}"

        ResearchQuery.objects.filter(id=state["query_id"]).update(
            status="done", status_message="Complete", report=full_report,
        )
        self._emit("report", {"report": full_report})
        self._emit("sources", {"sources": src_objs})
        return {**state, "report": full_report}

    # ── Run ───────────────────────────────────────────────────────────────────
    def run(self, query_id: int, query: str) -> str:
        from research.models import ResearchQuery

        state: AgentState = {
            "query_id": query_id, "query": query,
            "sub_searches": [], "raw_results": [], "source_ids": [],
            "chunks": [], "report": "", "error": None,
        }
        try:
            state = self.plan(state)
            state = self.search(state)
            state = self.scrape_and_embed(state)
            state = self.reflect(state)
            state = self.write(state)
        except Exception as e:
            logger.exception("Pipeline error: %s", e)
            ResearchQuery.objects.filter(id=query_id).update(
                status="error", status_message=str(e)[:500],
            )
            self._emit("error", {"message": str(e)})
            raise
        return state["report"]
