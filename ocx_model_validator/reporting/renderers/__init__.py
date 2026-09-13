"""Report renderers — registry and public API."""
from __future__ import annotations

from ocx_model_validator.reporting.renderers.base import ReportRenderer
from ocx_model_validator.reporting.renderers.markdown import MarkdownRenderer
from ocx_model_validator.reporting.renderers.rich import RichRenderer

_RENDERERS: dict[str, type[ReportRenderer]] = {
    "markdown": MarkdownRenderer,
    "rich": RichRenderer,
}


def get_renderer(fmt: str) -> ReportRenderer:
    """Return a renderer instance for ``fmt``; raise ValueError if unknown."""
    try:
        return _RENDERERS[fmt]()
    except KeyError:
        supported = ", ".join(sorted(_RENDERERS))
        raise ValueError(f"Unknown report format {fmt!r}; supported: {supported}") from None


__all__ = ["ReportRenderer", "MarkdownRenderer", "RichRenderer", "get_renderer"]

