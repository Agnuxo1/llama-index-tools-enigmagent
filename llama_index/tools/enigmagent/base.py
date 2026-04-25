"""LlamaIndex BaseToolSpec exposing EnigmAgent vault operations as tools.

Usage:
    from llama_index.core.agent import ReActAgent
    from llama_index.llms.openai import OpenAI
    from llama_index.tools.enigmagent import EnigmAgentClient, EnigmAgentToolSpec

    spec = EnigmAgentToolSpec(
        client=EnigmAgentClient(),
        default_origin="https://api.github.com",
    )
    agent = ReActAgent.from_tools(spec.to_tool_list(), llm=OpenAI())

    # The agent can now ask the vault to resolve placeholders, but only at
    # invocation time — placeholders flow through prompts and traces unchanged.
"""
from __future__ import annotations

from typing import Any, Callable

from llama_index.core.tools.tool_spec.base import BaseToolSpec

from .client import EnigmAgentClient


class EnigmAgentToolSpec(BaseToolSpec):
    """Expose `resolve`, `substitute`, and `list` as LlamaIndex tools.

    The model never sees resolved values — only the upstream HTTP call (made
    by your tool, on the user's machine) does. Origin binding is enforced by
    the EnigmAgent server: a wrong origin → the resolver refuses.
    """

    spec_functions = ["resolve_placeholder", "substitute_placeholders", "list_placeholders"]

    def __init__(
        self,
        client: EnigmAgentClient | None = None,
        default_origin: str = "http://localhost",
    ) -> None:
        self.client = client or EnigmAgentClient()
        self.default_origin = default_origin

    def resolve_placeholder(self, placeholder: str, origin: str | None = None) -> str:
        """Resolve a single {{PLACEHOLDER}} name against the local EnigmAgent vault.

        Args:
            placeholder: The placeholder name without braces (e.g. "GITHUB_TOKEN").
            origin: The upstream origin requesting this secret (e.g.
                "https://api.github.com"). The vault refuses if it does not
                match the secret's bound domain.

        Returns:
            The decrypted secret value as a string.
        """
        return self.client.resolve(placeholder, origin or self.default_origin)

    def substitute_placeholders(self, text: str, origin: str | None = None) -> str:
        """Walk a string and substitute every {{NAME}} occurrence in place.

        Args:
            text: Any string that may contain {{PLACEHOLDER}} tokens.
            origin: The upstream origin (see `resolve_placeholder`).

        Returns:
            The same string with every placeholder swapped for its value.
        """
        return self.client.substitute(text, origin or self.default_origin)

    def list_placeholders(self, text: str) -> list[str]:
        """Return every placeholder name found in the text without resolving."""
        return self.client.list_placeholders(text)


def enigma_substitute(
    client: EnigmAgentClient | None = None,
    origin: str = "http://localhost",
) -> Callable[[Any], Any]:
    """A function transformer for use in LlamaIndex `QueryPipeline`.

    Returns a callable that walks any value (str / dict / list) and substitutes
    every {{PLACEHOLDER}} string against EnigmAgent. Drop into a QueryPipeline
    as a module so placeholders are resolved before the LLM stage.

    Example:
        from llama_index.core.query_pipeline import QueryPipeline, FnComponent
        from llama_index.llms.openai import OpenAI
        from llama_index.tools.enigmagent import EnigmAgentClient, enigma_substitute

        sub = FnComponent(fn=enigma_substitute(EnigmAgentClient(), "https://api.openai.com"))
        pipe = QueryPipeline(chain=[sub, OpenAI()])
    """
    client = client or EnigmAgentClient()

    def _walk(value: Any) -> Any:
        if isinstance(value, str):
            return client.substitute(value, origin)
        if isinstance(value, dict):
            return {k: _walk(v) for k, v in value.items()}
        if isinstance(value, list):
            return [_walk(v) for v in value]
        return value

    return _walk
