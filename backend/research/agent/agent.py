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
    report:      str
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
        ResearchQuery.objects.filter(id=state["query_id"]).update(status="planning")

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
        ResearchQuery.objects.filter(id=state["query_id"]).update(status="searching")

        seen, results = set(), []
        for q in state["sub_searches"]:
            for r in web_search(q, max_results=4):
                url = r.get("url", "")
                if url and url not in seen:
                    seen.add(url)
                    results.append(r)

        self._emit("search_results", {"count": len(results)})
        return {**state, "raw_results": results}

    # ── Node 3: Scrape + Embed ────────────────────────────────────────────────
    def scrape_and_embed(self, state: AgentState) -> AgentState:
        from research.models import ResearchQuery, ResearchSource
        from .tools import scrape_page, embed_and_store

        self._emit("status", {"step": "scraping", "message": "Reading sources…"})
        ResearchQuery.objects.filter(id=state["query_id"]).update(status="scraping")

        query_obj  = ResearchQuery.objects.get(id=state["query_id"])
        source_ids = []
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
            source_ids.append(source.id)

            try:
                ResearchQuery.objects.filter(id=state["query_id"]).update(
                    status="embedding",
                    status_message=f"Embedding {i+1}/{total}",
                )
                n = embed_and_store(source.id, content)
                self._emit("embedded", {"url": url, "chunks": n})
            except Exception as e:
                logger.warning("Embed failed %s: %s", url, e)

        return {**state, "source_ids": source_ids}

    # ── Node 4: Reflect ───────────────────────────────────────────────────────
    def reflect(self, state: AgentState) -> AgentState:
        from research.models import ResearchQuery
        from .tools import retrieve_chunks

        self._emit("status", {"step": "writing", "message": "Analysing evidence…"})
        ResearchQuery.objects.filter(id=state["query_id"]).update(status="writing")

        chunks = retrieve_chunks(state["query"], state["query_id"], top_k=14)
        self._emit("context_ready", {"chunk_count": len(chunks)})
        return {**state, "chunks": chunks}

    # ── Node 5: Write ─────────────────────────────────────────────────────────
    def write(self, state: AgentState) -> AgentState:
        from research.models import ResearchQuery
        from .prompts import WRITE_REPORT_PROMPT
        from .tools import get_gemini
        from research.models import ResearchSource

        self._emit("status", {"step": "writing", "message": "Writing report…"})

        seen_urls, source_list, context_parts = set(), [], []
        for chunk in state["chunks"]:
            url = chunk["url"]
            if url not in seen_urls:
                seen_urls.add(url)
                source_list.append(url)
            idx = source_list.index(url) + 1
            context_parts.append(f"[Source {idx}] {chunk['text']}")

        context = "\n\n".join(context_parts[:12])
        prompt  = WRITE_REPORT_PROMPT.format(query=state["query"], context=context)
        
        response = get_gemini().generate_content(prompt)
        if not response.candidates or not response.candidates[0].content.parts:
            # If generation failed, we'll still proceed with a mock/empty body
            report_text = "(No generated content)"
        else:
            report_text = response.text

        # Remove any existing '## Sources' section from the model output
        main_part = report_text.split('\n## Sources', 1)[0].strip()

        # Build canonical sources list from the collected chunks/source_list
        src_lines = "\n".join(f"[Source {i+1}] {u}" for i, u in enumerate(source_list))
        full_report = f"{main_part}\n\n## Sources\n{src_lines}"

        # Persist the report and emit events
        ResearchQuery.objects.filter(id=state["query_id"]).update(
            status="done", status_message="Complete", report=full_report,
        )
        # Emit the combined report text first
        self._emit("report", {"report": full_report})

        # Emit structured sources for the frontend to display immediately
        src_objs = list(
            ResearchSource.objects.filter(query_id=state["query_id"])\
                .order_by("created_at")\
                .values("id", "url", "title", "snippet")
        )
        # If DB sources are empty, fall back to URL-only objects
        if not src_objs:
            src_objs = [{"id": None, "url": u, "title": "", "snippet": ""} for u in source_list]

        self._emit("sources", {"sources": src_objs})
        return {**state, "report": full_report, "source_ids": state.get("source_ids", [])}

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
