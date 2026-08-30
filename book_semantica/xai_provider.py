"""Register xAI as a Semantica LLM provider."""

from __future__ import annotations

import os

from semantica.semantic_extract.providers import OpenAIProvider
from semantica.semantic_extract.registry import provider_registry

XAI_BASE_URL = "https://api.x.ai/v1"
XAI_DEFAULT_MODEL = "grok-4.6"


class XAIProvider(OpenAIProvider):
    """OpenAI-compatible client pointed at xAI."""

    def __init__(
        self,
        api_key=None,
        model=XAI_DEFAULT_MODEL,
        base_url=XAI_BASE_URL,
        **kwargs,
    ):
        api_key = api_key or os.environ.get("XAI_API_KEY")
        if not api_key:
            raise ValueError(
                "XAI_API_KEY is not set; refusing to fall back to OPENAI_API_KEY"
            )
        super().__init__(
            api_key=api_key,
            model=model or XAI_DEFAULT_MODEL,
            base_url=base_url or XAI_BASE_URL,
            **kwargs,
        )


def register_xai_provider() -> None:
    provider_registry.register("xai", XAIProvider)
