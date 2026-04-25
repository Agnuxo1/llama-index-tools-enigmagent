"""llama-index-tools-enigmagent — LlamaIndex integration for the EnigmAgent vault."""
from .client import EnigmAgentClient, EnigmAgentResolveError, PLACEHOLDER_RE
from .base import EnigmAgentToolSpec, enigma_substitute
from .secret import enigma_secret

__all__ = [
    "EnigmAgentClient",
    "EnigmAgentResolveError",
    "EnigmAgentToolSpec",
    "enigma_substitute",
    "enigma_secret",
    "PLACEHOLDER_RE",
]
__version__ = "0.1.0"
