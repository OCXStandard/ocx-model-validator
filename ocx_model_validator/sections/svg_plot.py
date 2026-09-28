"""Render an nh-cross-section/4 JSON document as an SVG plot (stdlib only).

Layout: title on top, plot area left (y → right, z → up), legend column right
with the numbered stiffener list and plate-thickness swatches.
"""
from __future__ import annotations

import re
from xml.sax.saxutils import escape

_PALETTE = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b",
    "#e377c2", "#7f7f7f", "#bcbd22", "#17becf", "#aec7e8", "#ffbb78",
]
_UNKNOWN_COLOR = "#999999"

_PLOT_W = 1200.0
_PLOT_H = 900.0
_LEGEND_W = 360.0
_MARGIN = 40.0
_TITLE_H = 60.0
_ROW_H = 18.0
_STUB_DEFAULT_MM = 250.0
_SVG_NS = 'xmlns="http://www.w3.org/2000/svg"'


def _escape_attr(value) -> str:
    return escape(str(value), {'"': "&quot;"})


def render_svg(doc: dict, *, plate_style=None, stiffener_style=None,
               legend_extra=None, thickness_legend: bool = True) -> str:
    """Render the cross-section document as an SVG string."""
    cs = doc["cross_section"]
    plates: list[dict] = cs.get("plates") or []
    stiffeners: list[dict] = cs.get("stiffeners") or []
    source = (doc.get("source") or {}).get("file", "")

    parts: list[str] = []
    title = f"Cross section at x={cs.get('x_mm')} mm"
    if cs.get("frame") is not None:
        title += f" (frame {cs['frame']})"
    parts.append(
        f'<text x="{_MARGIN}" y="28" font-size="18" font-weight="bold" '
        f'font-family="sans-serif">{escape(title)}</text>'
    )
    parts.append(
        f'<text x="{_MARGIN}" y="48" font-size="12" fill="#555" '
        f'font-family="sans-serif">{escape(str(source))}</text>'
    )

    color_of = _thickness_colors(plates)
    to_px = _fit(plates, stiffeners)
    has_unknown = any(p.get("thickness_mm") is None for p in plates)

    if to_px is None:
        parts.append(
            f'<text x="{_MARGIN}" y="{_TITLE_H + 40}" font-size="14" '
            f'font-family="sans-serif">(no geometry to plot)</text>'
        )
    else:
        parts.extend(_plate_lines(plates, color_of, to_px, plate_style))
        parts.extend(_stiffener_stubs(stiffeners, to_px, stiffener_style))

    legend_x = _MARGIN + _PLOT_W + 40.0
    legend_parts, legend_h = _legend(
        stiffeners, color_of, legend_x, has_unknown,
        legend_extra=legend_extra, thickness_legend=thickness_legend)
    parts.extend(legend_parts)

    width = _MARGIN * 2 + _PLOT_W + _LEGEND_W
    height = max(_TITLE_H + _PLOT_H + _MARGIN * 2, _TITLE_H + legend_h + _MARGIN)
    body = "\n".join(parts)
    return (
        f'<svg {_SVG_NS} width="{width:.0f}" height="{height:.0f}" '
        f'viewBox="0 0 {width:.0f} {height:.0f}">\n'
        f'<rect width="100%" height="100%" fill="white"/>\n{body}\n</svg>\n'
    )


def _thickness_colors(plates: list[dict]) -> dict[float, str]:
    values = sorted({p["thickness_mm"] for p in plates
                     if p.get("thickness_mm") is not None})
    return {t: _PALETTE[i % len(_PALETTE)] for i, t in enumerate(values)}


def _fit(plates: list[dict], stiffeners: list[dict]):
    """Return a (y_mm, z_mm) -> (px, py) mapper, or None if no geometry."""
    ys: list[float] = []
    zs: list[float] = []
    for p in plates:
        ys += [p["y1_mm"], p["y2_mm"]]
        zs += [p["z1_mm"], p["z2_mm"]]
    for s in stiffeners:
        ys.append(s["y_mm"])
        zs.append(s["z_mm"])
    if not ys:
        return None
    min_y, max_y = min(ys), max(ys)
    min_z, max_z = min(zs), max(zs)
    span_y = max(max_y - min_y, 1.0)
    span_z = max(max_z - min_z, 1.0)
    pad_y, pad_z = span_y * 0.05, span_z * 0.05
    min_y, max_y = min_y - pad_y, max_y + pad_y
    min_z, max_z = min_z - pad_z, max_z + pad_z
    scale = min(_PLOT_W / (max_y - min_y), _PLOT_H / (max_z - min_z))

    def to_px(y_mm: float, z_mm: float) -> tuple[float, float]:
        return (_MARGIN + (y_mm - min_y) * scale,
                _TITLE_H + (max_z - z_mm) * scale)

    to_px.scale = scale  # px per mm, used for stub lengths
    return to_px


def _plate_lines(plates, color_of, to_px, style_of=None) -> list[str]:
    out = []
    for p in plates:
        x1, y1 = to_px(p["y1_mm"], p["z1_mm"])
        x2, y2 = to_px(p["y2_mm"], p["z2_mm"])
        t = p.get("thickness_mm")
        override = style_of(p) if style_of is not None else None
        if override is not None:
            color = override.get("color")
            if color is None:
                color = _UNKNOWN_COLOR if t is None else color_of[t]
            style = f'stroke="{_escape_attr(color)}"'
            dash = override.get("dash")
            if dash:
                style += f' stroke-dasharray="{_escape_attr(dash)}"'
            elif t is None:
                style += ' stroke-dasharray="6 4"'
            title = override.get("title") or p.get("name") or ""
        else:
            if t is None:
                style = f'stroke="{_UNKNOWN_COLOR}" stroke-dasharray="6 4"'
            else:
                style = f'stroke="{color_of[t]}"'
            title = p.get("name") or ""
        out.append(
            f'<line class="plate" x1="{x1:.1f}" y1="{y1:.1f}" '
            f'x2="{x2:.1f}" y2="{y2:.1f}" {style} stroke-width="3">'
            f'<title>{escape(str(title))}</title></line>'
        )
    return out


def _stub_len_mm(profile_dimensions: str | None) -> float:
    if profile_dimensions:
        m = re.search(r"\d+(?:\.\d+)?", profile_dimensions)
        if m:
            return float(m.group())
    return _STUB_DEFAULT_MM


def _stiffener_stubs(stiffeners, to_px, style_of=None) -> list[str]:
    out = []
    for n, s in enumerate(stiffeners, start=1):
        x0, y0 = to_px(s["y_mm"], s["z_mm"])
        wdy, wdz = s.get("web_dir_y"), s.get("web_dir_z")
        length_px = _stub_len_mm(s.get("profile_dimensions")) * to_px.scale
        length_px = max(length_px, 8.0)
        if wdy is None or wdz is None:
            dx, dy, dash = 0.0, -length_px, ' stroke-dasharray="4 3"'
        else:
            dx, dy, dash = wdy * length_px, -wdz * length_px, ""
        x1, y1 = x0 + dx, y0 + dy
        override = style_of(s) if style_of is not None else None
        title = None
        stroke = "black"
        if override is not None:
            stroke = str(override.get("color", stroke))
            if override.get("dash"):
                dash = f' stroke-dasharray="{_escape_attr(override["dash"])}"'
            title = override.get("title")
        line = (
            f'<line class="stiffener" x1="{x0:.1f}" y1="{y0:.1f}" '
            f'x2="{x1:.1f}" y2="{y1:.1f}" stroke="{_escape_attr(stroke)}" '
            f'stroke-width="1.5"{dash}'
        )
        if title is None:
            out.append(f"{line}/>")
        else:
            out.append(f"{line}><title>{escape(str(title))}</title></line>")
        lx, ly = x1 + dx * 0.15 + 3.0, y1 + dy * 0.15
        out.append(
            f'<text class="stiffener-no" x="{lx:.1f}" y="{ly:.1f}" '
            f'font-size="11" font-family="sans-serif">{n}</text>'
        )
    return out


def _legend(stiffeners, color_of, x: float, has_unknown: bool, *,
            legend_extra=None, thickness_legend: bool = True) -> tuple[list[str], float]:
    out: list[str] = []
    y = _TITLE_H + 20.0
    out.append(f'<text x="{x}" y="{y}" font-size="14" font-weight="bold" '
               f'font-family="sans-serif">Stiffeners</text>')
    y += _ROW_H
    for n, s in enumerate(stiffeners, start=1):
        label = f"{n}  {s.get('name') or '?'}"
        profile = " ".join(str(v) for v in
                           (s.get("profile_type"), s.get("profile_dimensions")) if v)
        if profile:
            label += f" — {profile}"
        out.append(f'<text x="{x}" y="{y:.1f}" font-size="11" '
                   f'font-family="sans-serif">{escape(label)}</text>')
        y += _ROW_H
    if thickness_legend:
        y += _ROW_H
        out.append(f'<text x="{x}" y="{y:.1f}" font-size="14" font-weight="bold" '
                   f'font-family="sans-serif">Plate thickness</text>')
        y += _ROW_H
        for t, color in color_of.items():
            out.append(f'<line x1="{x}" y1="{y - 4:.1f}" x2="{x + 30}" '
                       f'y2="{y - 4:.1f}" stroke="{color}" stroke-width="3"/>')
            out.append(f'<text x="{x + 38}" y="{y:.1f}" font-size="11" '
                       f'font-family="sans-serif">{t} mm</text>')
            y += _ROW_H
        if has_unknown:
            out.append(f'<line x1="{x}" y1="{y - 4:.1f}" x2="{x + 30}" y2="{y - 4:.1f}" '
                       f'stroke="{_UNKNOWN_COLOR}" stroke-width="3" stroke-dasharray="6 4"/>')
            out.append(f'<text x="{x + 38}" y="{y:.1f}" font-size="11" '
                       f'font-family="sans-serif">unknown</text>')
            y += _ROW_H
    if legend_extra:
        y += _ROW_H
        out.append(f'<text x="{x}" y="{y:.1f}" font-size="14" font-weight="bold" '
                   f'font-family="sans-serif">Legend</text>')
        y += _ROW_H
        for color, dash, label in legend_extra:
            dash_attr = ""
            if dash:
                dash_attr = f' stroke-dasharray="{_escape_attr(dash)}"'
            out.append(f'<line x1="{x}" y1="{y - 4:.1f}" x2="{x + 30}" '
                       f'y2="{y - 4:.1f}" stroke="{_escape_attr(color)}" '
                       f'stroke-width="3"{dash_attr}/>')
            out.append(f'<text x="{x + 38}" y="{y:.1f}" font-size="11" '
                       f'font-family="sans-serif">{escape(str(label))}</text>')
            y += _ROW_H
    return out, y - _TITLE_H
