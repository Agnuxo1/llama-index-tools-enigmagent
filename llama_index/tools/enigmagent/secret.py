"""SecretStr wrapper that resolves on first access.

Usage:
    from llama_index.llms.openai import OpenAI
    from llama_index.tools.enigmagent import enigma_secret

    api_key = enigma_secret("OPENAI_KEY", origin="https://api.openai.com")
    llm = OpenAI(api_key=api_key.get_secret_value())
"""
from __future__ import annotations

from pydantic import SecretStr

from .client import EnigmAgentClient


def enigma_secret(
    placeholder: str,
    origin: str,
    client: EnigmAgentClient | None = None,
) -> SecretStr:
    """Resolve a placeholder via EnigmAgent and wrap in pydantic SecretStr."""
    client = client or EnigmAgentClient()
    value = client.resolve(placeholder, origin)
    return SecretStr(value)
