import pytest
from unittest.mock import patch
from llama_index.tools.enigmagent import (
    EnigmAgentClient,
    EnigmAgentToolSpec,
    PLACEHOLDER_RE,
    enigma_substitute,
)


def test_placeholder_regex():
    assert PLACEHOLDER_RE.findall("Bearer {{TOKEN}} for {{user.id}}") == ["TOKEN", "user.id"]


def test_substitute():
    client = EnigmAgentClient()
    with patch.object(EnigmAgentClient, "resolve", lambda self, p, o: f"<{p}>"):
        out = client.substitute("Authorization: Bearer {{GH_TOKEN}}", origin="https://api.github.com")
    assert out == "Authorization: Bearer <GH_TOKEN>"


def test_list_placeholders():
    client = EnigmAgentClient()
    assert client.list_placeholders("a {{X}} b {{Y}}") == ["X", "Y"]


def test_toolspec_exposes_three_tools():
    spec = EnigmAgentToolSpec(default_origin="https://api.github.com")
    tools = spec.to_tool_list()
    names = {t.metadata.name for t in tools}
    assert names == {"resolve_placeholder", "substitute_placeholders", "list_placeholders"}


def test_toolspec_resolve_uses_default_origin():
    spec = EnigmAgentToolSpec(default_origin="https://api.github.com")
    captured: dict[str, str] = {}

    def fake_resolve(self, p, o):
        captured["placeholder"] = p
        captured["origin"] = o
        return "ghp_xxx"

    with patch.object(EnigmAgentClient, "resolve", fake_resolve):
        out = spec.resolve_placeholder("GITHUB_TOKEN")
    assert out == "ghp_xxx"
    assert captured == {"placeholder": "GITHUB_TOKEN", "origin": "https://api.github.com"}


def test_enigma_substitute_walks_dicts_and_lists():
    fn = enigma_substitute(EnigmAgentClient(), origin="https://api.example.com")
    with patch.object(EnigmAgentClient, "resolve", lambda self, p, o: f"<{p}>"):
        out = fn({"headers": ["Bearer {{X}}", "x-y: {{Y}}"], "ok": True, "n": 1})
    assert out == {"headers": ["Bearer <X>", "x-y: <Y>"], "ok": True, "n": 1}
