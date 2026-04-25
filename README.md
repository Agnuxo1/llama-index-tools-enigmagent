# llama-index-tools-enigmagent

[![CI](https://github.com/Agnuxo1/llama-index-tools-enigmagent/actions/workflows/ci.yml/badge.svg)](https://github.com/Agnuxo1/llama-index-tools-enigmagent/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/llama-index-tools-enigmagent?label=pypi&color=blue)](https://pypi.org/project/llama-index-tools-enigmagent/)
[![PyPI downloads](https://img.shields.io/pypi/dm/llama-index-tools-enigmagent.svg)](https://pypi.org/project/llama-index-tools-enigmagent/)
[![Python](https://img.shields.io/pypi/pyversions/llama-index-tools-enigmagent.svg)](https://pypi.org/project/llama-index-tools-enigmagent/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![LlamaIndex](https://img.shields.io/badge/LlamaIndex-0.11+-green.svg)](https://github.com/run-llama/llama_index)
[![EnigmAgent](https://img.shields.io/badge/EnigmAgent-MCP-purple.svg)](https://github.com/Agnuxo1/EnigmAgent)
[![GitHub stars](https://img.shields.io/github/stars/Agnuxo1/llama-index-tools-enigmagent?style=social)](https://github.com/Agnuxo1/llama-index-tools-enigmagent)

> **Last week I asked a LlamaIndex agent to push a fix to a private GitHub repo. To do that, the agent needed my personal access token. I had three options, and all three were terrible: paste the token into the prompt (and into the provider's logs forever), give the agent a long-lived token it could reuse on its own at 3 a.m., or give up and do it by hand.**

`llama-index-tools-enigmagent` is option four.

Your LlamaIndex agent emits `{{GITHUB_TOKEN}}`. The placeholder leaves the model and travels through the prompt, the QueryPipeline, the tool inputs, the trace — and only at the moment your tool actually needs the credential does EnigmAgent intercept the call, decrypt the real token locally with AES-256-GCM, and inject it. The plaintext exists for one event-loop tick. The model never sees it. The provider never sees it. Your trace never sees it.

```bash
pip install llama-index-tools-enigmagent
```

In another terminal, next to your app:

```bash
npx enigmagent-mcp --mode rest --port 3737
```

That's the entire install. The Python package talks to the local EnigmAgent REST server over loopback; secrets stay in the encrypted vault on disk.

> Star [the main project](https://github.com/Agnuxo1/EnigmAgent) if you've ever pasted a token you regretted.

---

## The problem (in LlamaIndex terms)

When you build a LlamaIndex agent that needs to authenticate against a real API — GitHub, OpenAI, Stripe, your own backend — you face the same impossible choice every framework faces:

| Option | What happens |
|---|---|
| Put the secret into the prompt | It lands in the trace, in the model's context, possibly in provider logs |
| Bake the token into the tool at construction time | The model can call the tool with arbitrary inputs and exfiltrate the secret indirectly |
| Use a separate HSM / vault per tool | Works but every tool has to be rewritten |

**`llama-index-tools-enigmagent` is option D.** Your prompt, your QueryPipeline, your trace all carry only `{{PLACEHOLDER}}` strings. The real value is resolved at the boundary, by a process the model cannot see, against a vault on the user's machine.

---

## How it works

```
+------------------+  emits {{GITHUB_TOKEN}}  +---------------------+
| LlamaIndex agent | -----------------------> |  Tool input / call  |
|  (any LLM)       |                          |  (github.com / ...) |
+------------------+                          +----------+----------+
                                                         | before invoke (intercepted)
                                                         v
                                          +-------------------------+
                                          |      EnigmAgent         |
                                          |  detects placeholder,   |
                                          |  checks origin match,   |
                                          |  decrypts -> ghp_xxx    |
                                          +----------+--------------+
                                                     | real value
                                                     v
                                          +-------------------------+
                                          |  HTTP request to the    |
                                          |  upstream API           |
                                          +-------------------------+
```

The model emits a placeholder. The placeholder lives in the prompt, the pipeline, and the trace. A `BaseToolSpec` (or `FnComponent`) in your pipeline sees the placeholder right before the request leaves your process and asks the local EnigmAgent REST server to swap it for the real value — but only if the request's `origin` matches the domain that secret was bound to. Wrong domain → the resolver refuses.

---

## Three usage patterns

### 1. `EnigmAgentToolSpec` — agent-callable tools (recommended)

Expose vault operations as first-class LlamaIndex tools the agent can call:

```python
from llama_index.core.agent import ReActAgent
from llama_index.llms.openai import OpenAI
from llama_index.tools.enigmagent import EnigmAgentClient, EnigmAgentToolSpec

spec = EnigmAgentToolSpec(
    client=EnigmAgentClient(),
    default_origin="https://api.github.com",
)

agent = ReActAgent.from_tools(
    spec.to_tool_list(),
    llm=OpenAI(model="gpt-4o-mini"),
    verbose=True,
)

# The agent emits {{GITHUB_TOKEN}}. The tool resolves it at call time.
# The model NEVER sees the value.
agent.chat("Use the GitHub API with header Authorization: Bearer {{GITHUB_TOKEN}} to list my repos")
```

`EnigmAgentToolSpec` exposes three operations:

| Tool | Purpose |
|---|---|
| `resolve_placeholder(name, origin)` | Decrypt one secret |
| `substitute_placeholders(text, origin)` | Walk a string, swap every `{{NAME}}` |
| `list_placeholders(text)` | Extract placeholder names without resolving (useful for dry-runs) |

### 2. `enigma_substitute` — QueryPipeline transformer

Drop into a `QueryPipeline` so every value flowing through gets `{{PLACEHOLDER}}` resolved before the LLM stage:

```python
from llama_index.core.query_pipeline import QueryPipeline, FnComponent
from llama_index.llms.openai import OpenAI
from llama_index.tools.enigmagent import EnigmAgentClient, enigma_substitute

sub = FnComponent(
    fn=enigma_substitute(EnigmAgentClient(), origin="https://api.openai.com"),
)

pipe = QueryPipeline(chain=[sub, OpenAI(model="gpt-4o-mini")])

# {{OPENAI_KEY}} is resolved right before OpenAI is invoked.
pipe.run(input="Bearer {{OPENAI_KEY}}")
```

### 3. `enigma_secret` — drop-in `SecretStr` replacement

For LlamaIndex components that take an API key directly, resolve once at construction time:

```python
from llama_index.llms.openai import OpenAI
from llama_index.tools.enigmagent import enigma_secret

api_key = enigma_secret("OPENAI_KEY", origin="https://api.openai.com")

llm = OpenAI(api_key=api_key.get_secret_value())
```

The plaintext lives only inside the `SecretStr` and only inside the `OpenAI` instance — never in your source, never in your env, never in the prompt.

---

## Configuration

`EnigmAgentClient` defaults to `http://localhost:3737`. Override:

```python
client = EnigmAgentClient(
    base_url="http://127.0.0.1:9999",      # custom port
    timeout=5.0,                            # in seconds
    shared_secret="my-loopback-token",      # sent as X-EnigmAgent-Auth header
)
```

To run the EnigmAgent REST server with a shared secret:

```bash
npx enigmagent-mcp --mode rest --port 3737 --auth my-loopback-token
```

---

## The vault

This package is a thin client. The real work — Argon2id key derivation, AES-256-GCM encryption, origin binding, audit logging — lives in **[EnigmAgent](https://github.com/Agnuxo1/EnigmAgent)**, the npm package that backs it. To create or edit your vault, see the main README. A typical workflow:

```bash
# Create a vault interactively (one-time)
npx enigmagent-mcp --new-vault ./my.vault.json

# Add a secret bound to a domain
npx enigmagent-mcp --vault ./my.vault.json --add GITHUB_TOKEN ghp_xxx --origin https://api.github.com

# Run as REST server next to your LlamaIndex app
npx enigmagent-mcp --mode rest --port 3737 --vault ./my.vault.json
```

---

## Security model

- **Loopback only.** The REST server binds to `127.0.0.1`. Only processes on the same machine can reach it.
- **Origin binding.** Every secret is bound to one or more origins (e.g. `https://api.github.com`). Resolving a secret for a different origin is refused.
- **Argon2id + AES-256-GCM.** The vault file is encrypted at rest with a passphrase-derived key.
- **No plaintext in logs.** Resolved values exist only in the memory of the process making the upstream HTTP call, for the duration of that call.
- **Optional shared secret.** Pass `--auth` to require an `X-EnigmAgent-Auth` header on every REST call, so unauthorised local processes can't query the vault.

Full threat model: [EnigmAgent THREAT_MODEL.md](https://github.com/Agnuxo1/EnigmAgent/blob/main/docs/THREAT_MODEL.md)

---

## Compatibility

- Python: 3.10, 3.11, 3.12, 3.13
- `llama-index-core >= 0.11`
- `pydantic >= 2`
- Any LLM provider (OpenAI, Anthropic, Mistral, local), any tool

---

## Roadmap

- [ ] Auto-rewrite tool inputs in the agent middleware (currently the agent must explicitly call `substitute_placeholders` or wrap calls in `enigma_substitute`)
- [ ] Workflow event helper for the new LlamaIndex `Workflow` API
- [ ] Sister package for LlamaIndex `Settings` (vault-backed default LLM keys)
- [ ] Upstream proposal to LlamaHub once this package has real users

PRs welcome.

---

## See also

- **LangChain integration:** [`langchain-enigmagent`](https://github.com/Agnuxo1/langchain-enigmagent) — same idea, LangChain-native (`Runnable`, `Callback`)

---

## License

MIT (c) 2026 Francisco Angulo de Lafuente

## Links

- Main project: [github.com/Agnuxo1/EnigmAgent](https://github.com/Agnuxo1/EnigmAgent)
- npm package: [enigmagent-mcp](https://www.npmjs.com/package/enigmagent-mcp)
- Issues: [github.com/Agnuxo1/llama-index-tools-enigmagent/issues](https://github.com/Agnuxo1/llama-index-tools-enigmagent/issues)
