"""Compression provider abstraction for context packs.

The pipeline: select → render → compress → write.
Compression is optional and always falls back gracefully.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import cast


class CompressionError(Exception):
    """Raised when a compression provider fails unrecoverably."""


class HeadroomUnavailableError(CompressionError):
    """Headroom is not installed or its local proxy is unreachable."""


class CompressionProvider(ABC):
    """Abstract base for all compression strategies."""

    @abstractmethod
    def compress(self, text: str, *, budget: int) -> str:
        """Return a compressed version of *text* targeting *budget* tokens.

        Must be idempotent — calling twice on already-compressed text is safe.
        Implementations MUST NOT make network calls to external services.
        """

    @abstractmethod
    def name(self) -> str:
        """Short identifier shown in CLI output (e.g. ``"headroom"``)."""


class NoOpCompressionProvider(CompressionProvider):
    """Passes text through unchanged. Default when --compress is omitted."""

    def compress(self, text: str, *, budget: int) -> str:  # noqa: ARG002
        return text

    def name(self) -> str:
        return "noop"


_PROVIDERS: dict[str, str] = {
    "headroom": "contextos.core.headroom_adapter.HeadroomCompressionProvider",
}

AVAILABLE_PROVIDERS: tuple[str, ...] = tuple(_PROVIDERS)


def get_provider(name: str, **kwargs: object) -> CompressionProvider:
    """Return a :class:`CompressionProvider` by name.

    Raises :class:`ValueError` for unknown names.
    Raises :class:`HeadroomUnavailableError` if the provider's dependency
    is missing or its local service is unreachable.
    """
    if name not in _PROVIDERS:
        choices = ", ".join(AVAILABLE_PROVIDERS)
        raise ValueError(
            f"Unknown compression provider {name!r}. "
            f"Available: {choices}. "
            f"Omit --compress to skip compression."
        )

    module_path, _, class_name = _PROVIDERS[name].rpartition(".")
    import importlib

    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    return cast(CompressionProvider, cls(**kwargs))
