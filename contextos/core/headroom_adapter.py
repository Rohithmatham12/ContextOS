"""Headroom compression provider.

Headroom is an optional local proxy that compresses context packs without
sending data to any external service. Everything stays on the machine.

Setup
-----
1. Install the client library::

       pip install headroom-ai

2. Start the local proxy (see Headroom docs for your platform)::

       headroom serve          # default: http://127.0.0.1:8787

3. Pass ``--compress headroom`` to ``contextos pack``::

       contextos pack . --task "add auth" --budget 8000 --compress headroom

The proxy URL can be overridden via the ``HEADROOM_BASE_URL`` environment
variable (default: ``http://127.0.0.1:8787``).

ContextOS works fully without Headroom.  Omit ``--compress`` for normal
(uncompressed) output.
"""

from __future__ import annotations

import os

from contextos.core.compression import CompressionProvider, HeadroomUnavailableError

_DEFAULT_URL = "http://127.0.0.1:8787"

_INSTALL_HINT = """\
Headroom is not installed.

  pip install headroom-ai

Then start the local proxy before running ContextOS:

  headroom serve

Or omit --compress to skip compression entirely."""

_PROXY_HINT = """\
Headroom proxy is unreachable at {url}.

Make sure the proxy is running:

  headroom serve

Or omit --compress to skip compression entirely."""


class HeadroomCompressionProvider(CompressionProvider):
    """Compress context packs via a local Headroom proxy.

    Parameters
    ----------
    base_url:
        Base URL of the Headroom proxy.  Defaults to the ``HEADROOM_BASE_URL``
        environment variable or ``http://127.0.0.1:8787``.
    """

    def __init__(self, base_url: str | None = None) -> None:
        self._base_url = base_url or os.environ.get("HEADROOM_BASE_URL", _DEFAULT_URL)

    # ------------------------------------------------------------------
    # CompressionProvider interface
    # ------------------------------------------------------------------

    def name(self) -> str:
        return "headroom"

    def compress(self, text: str, *, budget: int) -> str:
        """Send *text* to the local Headroom proxy and return compressed output.

        Raises
        ------
        HeadroomUnavailableError
            If the ``headroom_ai`` package is not installed, or if the proxy
            is not reachable at :attr:`base_url`.
        """
        hr = self._import_headroom()
        try:
            return hr.compress(text, budget=budget, base_url=self._base_url)
        except HeadroomUnavailableError:
            raise
        except Exception as exc:
            raise HeadroomUnavailableError(
                _PROXY_HINT.format(url=self._base_url) + f"\n\nDetails: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @property
    def base_url(self) -> str:
        return self._base_url

    @staticmethod
    def _import_headroom() -> object:
        """Lazy-import ``headroom_ai``.  Raises :class:`HeadroomUnavailableError` if missing."""
        try:
            import headroom_ai  # type: ignore[import-untyped]

            return headroom_ai
        except ImportError as exc:
            raise HeadroomUnavailableError(_INSTALL_HINT) from exc
