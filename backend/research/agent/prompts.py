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
- Structure: ## Overview, ## Key Findings, ## Analysis, ## Conclusion, ## Sources
- Cite inline as [Source N]
- Minimum 600 words
- Be factual and analytical

Write the report now:"""
