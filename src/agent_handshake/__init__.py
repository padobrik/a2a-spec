"""agent-handshake: check that what your agent is told matches the tools it actually has."""

__version__ = "1.0.0.dev0"

from agent_handshake.config.loader import load_config
from agent_handshake.config.settings import HandshakeConfig
from agent_handshake.exceptions import ConfigError, HandshakeError

__all__ = [
    "__version__",
    # Config
    "HandshakeConfig",
    "load_config",
    # Exceptions
    "HandshakeError",
    "ConfigError",
]
