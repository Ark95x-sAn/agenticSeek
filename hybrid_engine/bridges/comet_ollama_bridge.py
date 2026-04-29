"""
Comet/Perplexity ↔ Ollama Bridge
===================================
Combines Perplexity's real-time web knowledge with Ollama's local reasoning.
Implements the "search → reason → answer" pipeline locally.

Use case: Comet fetches current web data → Ollama reasons over it locally.
"""

from __future__ import annotations

import logging
from typing import Any, AsyncGenerator, Dict, List, Optional

logger = logging.getLogger("hybrid_engine.bridge.comet_ollama")


class CometOllamaBridge:
    """
    Bridge between Comet/Perplexity (web knowledge) and Ollama (local reasoning).
    Enables grounded local inference with real-time web context.
    """

    def __init__(self, comet_client: Any, ollama_client: Any):
        self.comet = comet_client
        self.ollama = ollama_client

    async def search_and_reason(
        self, query: str, model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Step 1: Search the web via Comet/Perplexity.
        Step 2: Reason over the results locally via Ollama.
        Returns a grounded, locally-processed answer.
        """
        # Step 1: Web search
        search_result = await self.comet.search(query)
        if search_result.get("status") != "ok":
            # Fallback: pure Ollama reasoning without web context
            logger.warning("[CometOllama] Search failed, falling back to pure Ollama")
            return await self.ollama.generate(query, model=model)

        web_context = search_result.get("answer", "")
        citations = search_result.get("citations", [])

        # Step 2: Local reasoning with web context injected
        reasoning_prompt = (
            f"Based on the following web search results, answer the question.\n\n"
            f"Question: {query}\n\n"
            f"Web Context:\n{web_context}\n\n"
            f"Sources: {', '.join(citations[:3])}\n\n"
            f"Provide a comprehensive, accurate answer:"
        )

        reasoning_result = await self.ollama.generate(reasoning_prompt, model=model)

        return {
            "status": "ok",
            "bridge": "comet_ollama",
            "query": query,
            "web_context": web_context,
            "citations": citations,
            "local_reasoning": reasoning_result.get("response", ""),
            "model_used": reasoning_result.get("model", model),
        }

    async def stream_grounded_answer(
        self, query: str, model: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        Stream a grounded answer: search first, then stream Ollama reasoning.
        """
        # Fetch web context (non-streaming)
        search_result = await self.comet.search(query)
        web_context = search_result.get("answer", "") if search_result.get("status") == "ok" else ""

        prompt = (
            f"Web context: {web_context}\n\nQuestion: {query}\n\nAnswer:"
            if web_context else query
        )

        async for token in self.ollama.stream_generate(prompt, model=model):
            yield token

    async def embed_and_search(
        self, query: str, candidate_urls: List[str], model: str = "nomic-embed-text"
    ) -> List[Dict[str, Any]]:
        """
        Embed the query and candidate URLs, rank by semantic similarity.
        Uses Ollama embeddings + Comet browser for content extraction.
        """
        query_embedding = await self.ollama.embed(query, model=model)
        ranked = []

        for url in candidate_urls:
            # Extract text from URL via Comet browser
            browse_result = await self.comet.browse_url(url, extract="text")
            if browse_result.get("status") != "ok":
                continue

            content = browse_result.get("content", "")[:500]
            content_embedding = await self.ollama.embed(content, model=model)
            similarity = await self.ollama.cosine_similarity(query_embedding, content_embedding)

            ranked.append({
                "url": url,
                "similarity": similarity,
                "content_preview": content[:200],
            })

        ranked.sort(key=lambda x: x["similarity"], reverse=True)
        return ranked

    async def deep_local_research(
        self, topic: str, model: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        Run Perplexity deep research, then stream Ollama's synthesis locally.
        """
        # Collect deep research from Comet
        research_chunks = []
        async for chunk in self.comet.deep_research(topic, depth=3):
            research_chunks.append(chunk)

        full_research = "".join(research_chunks)

        # Stream local synthesis
        synthesis_prompt = (
            f"You have the following research on '{topic}':\n\n"
            f"{full_research[:4000]}\n\n"
            f"Synthesize the key insights, identify patterns, and provide actionable conclusions:"
        )

        async for token in self.ollama.stream_generate(synthesis_prompt, model=model):
            yield token
