"""Verum SDK client — wraps LLM calls with deployment routing."""
from __future__ import annotations

import os
from typing import Any

import httpx

from verum._cache import DeploymentConfigCache
from verum._router import choose_variant

_DEFAULT_CACHE_TTL = 60.0


class Client:
    """Connect an AI service to The Verum Loop.

    Usage:
        client = verum.Client()  # reads VERUM_API_URL / VERUM_API_KEY from env
        chunks = await client.retrieve(query="...", collection_name="arcana-tarot-knowledge")
        routed = await client.chat(messages=[...], deployment_id="...", provider="grok", model="grok-2-1212")
        # then pass routed["messages"] to the actual LLM SDK
    """

    def __init__(
        self,
        api_url: str | None = None,
        api_key: str | None = None,
        cache_ttl: float = _DEFAULT_CACHE_TTL,
    ) -> None:
        self._api_url = (api_url or os.environ.get("VERUM_API_URL", "")).rstrip("/")
        self._api_key = api_key or os.environ.get("VERUM_API_KEY", "")
        self._cache: DeploymentConfigCache = DeploymentConfigCache(ttl=cache_ttl)

    # ── Public API ────────────────────────────────────────────────────────────

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        deployment_id: str | None = None,
        provider: str = "openai",
        model: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Return (possibly modified) messages with routing decision.

        If deployment_id is given, fetches the current traffic split and may
        replace the system prompt with the CoT variant. The caller passes
        the returned messages["messages"] to the actual LLM SDK.

        Args:
            messages: LLM message list (OpenAI-compatible format).
            deployment_id: Verum deployment UUID. If None, passes through unchanged.
            provider: LLM provider hint ("openai", "anthropic", "grok").
            model: Model identifier passed through for caller use.
            **kwargs: Additional keyword arguments passed through in result.

        Returns:
            Dict with "messages" (possibly modified), "routed_to", "deployment_id".
        """
        if not deployment_id:
            return {"messages": messages, "routed_to": "baseline", "deployment_id": None}

        config = await self._get_deployment_config(deployment_id)
        routed_to = choose_variant(config.get("traffic_split", 0.0))

        if routed_to == "variant" and config.get("variant_prompt"):
            messages = list(messages)
            if messages and messages[0].get("role") == "system":
                messages[0] = {**messages[0], "content": config["variant_prompt"]}
            else:
                messages = [{"role": "system", "content": config["variant_prompt"]}, *messages]

        return {"messages": messages, "routed_to": routed_to, "deployment_id": deployment_id}

    async def retrieve(
        self,
        query: str,
        *,
        collection_name: str,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Retrieve knowledge chunks from the Verum RAG index.

        Args:
            query: The search query.
            collection_name: The RAG collection to search.
            top_k: Number of chunks to return.

        Returns:
            List of chunk dicts with at least a "content" key.
        """
        async with httpx.AsyncClient() as http:
            resp = await http.post(
                f"{self._api_url}/api/v1/retrieve-sdk",
                json={"query": query, "collection_name": collection_name, "top_k": top_k},
                headers=self._headers(),
                timeout=10.0,
            )
            resp.raise_for_status()
            return resp.json().get("chunks", [])

    async def feedback(self, trace_id: str, score: int) -> None:
        """Record user feedback for a trace.

        Args:
            trace_id: The trace UUID from the LLM response.
            score: 1 (positive) or -1 (negative).
        """
        async with httpx.AsyncClient() as http:
            resp = await http.post(
                f"{self._api_url}/api/v1/feedback",
                json={"trace_id": trace_id, "score": score},
                headers=self._headers(),
                timeout=5.0,
            )
            resp.raise_for_status()

    async def record(
        self,
        *,
        deployment_id: str,
        variant: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: int,
        error: str | None = None,
    ) -> str:
        """Record an LLM call to Verum. Returns trace_id.

        Call immediately after the LLM SDK returns. Pass the returned
        trace_id to feedback() if the user provides a rating.

        Args:
            deployment_id: From client.chat() response["deployment_id"].
            variant: From client.chat() response["routed_to"].
            model: Exact model string used (e.g. "grok-2-1212").
            input_tokens: From LLM response usage.prompt_tokens.
            output_tokens: From LLM response usage.completion_tokens.
            latency_ms: Wall-clock time from request start to response end.
            error: Error message if the LLM call failed; None on success.

        Returns:
            trace_id string to pass to feedback().
        """
        async with httpx.AsyncClient() as http:
            resp = await http.post(
                f"{self._api_url}/api/v1/traces",
                json={
                    "deployment_id": deployment_id,
                    "variant": variant,
                    "model": model,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "latency_ms": latency_ms,
                    "error": error,
                },
                headers=self._headers(),
                timeout=5.0,
            )
            resp.raise_for_status()
            return resp.json()["trace_id"]

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _get_deployment_config(self, deployment_id: str) -> dict[str, Any]:
        cached = self._cache.get(deployment_id)
        if cached is not None:
            return cached  # type: ignore[return-value]

        async with httpx.AsyncClient() as http:
            resp = await http.get(
                f"{self._api_url}/api/v1/deploy/{deployment_id}/config",
                headers=self._headers(),
                timeout=5.0,
            )
            resp.raise_for_status()
            config: dict[str, Any] = resp.json()

        self._cache.set(deployment_id, config)
        return config

    def _headers(self) -> dict[str, str]:
        return {"x-verum-api-key": self._api_key}
