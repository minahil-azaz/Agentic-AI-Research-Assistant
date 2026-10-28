PLAN_PROMPT = """You are a research planning assistant.
Given the user query below, produce 3-5 specific search strings that together cover the topic thoroughly.

Return ONLY a valid JSON array of strings. No explanation, no markdown fences.
Example: ["query one", "query two", "query three"]

User query: {query}"""


WRITE_REPORT_PROMPT = """You are an expert research analyst.
Using the source excerpts below, write a comprehensive Markdown research report.

QUERY: {query}

SOURCES:
{context}

RULES:
- Structure: ## Overview, ## Key Findings, ## Analysis, ## Conclusion
- Cite inline as [Source N], using only the source numbers shown above
- Base every claim on the excerpts; if they do not cover part of the query, say so instead of guessing
- Do not write a Sources section; it is appended automatically
- Minimum 600 words
- Be factual and analytical

Write the report now:"""
