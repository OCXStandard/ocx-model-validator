"""HTML renderer — single self-contained tabbed document.

One tab per report section. ``Link`` cells render as in-page anchors when
their target row anchor exists anywhere in the report, and degrade to plain
text otherwise. Inline CSS/JS only; the file works offline from file://.
"""
from __future__ import annotations

import html
import itertools
from collections.abc import Iterator

from ocx_model_validator.reporting.model import (
    Cell,
    Link,
    Report,
    ReportSection,
    ReportTable,
)

_NA = "N/A"

_CSS = """
body { font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  margin: 2rem; color: #1f2328; }
h1 { margin-bottom: 0.25rem; }
dl.meta { display: grid; grid-template-columns: max-content auto;
  gap: 0.15rem 0.75rem; margin: 0.5rem 0 1.5rem; }
dl.meta dt { font-weight: 600; }
dl.meta dd { margin: 0; }
.tab-bar { display: flex; flex-wrap: wrap; gap: 0.25rem;
  border-bottom: 2px solid #d0d7de; margin-bottom: 1rem; }
.tab-bar button { border: 1px solid #d0d7de; border-bottom: none;
  background: #f6f8fa; padding: 0.4rem 0.9rem; cursor: pointer;
  border-radius: 6px 6px 0 0; font: inherit; }
.tab-bar button.active { background: #fff; font-weight: 600;
  border-color: #0969da; }
.tab-panel { display: none; }
.tab-panel.active { display: block; }
table { border-collapse: collapse; margin: 0.5rem 0 1.5rem; }
th, td { border: 1px solid #d0d7de; padding: 0.3rem 0.6rem; text-align: left; }
th { background: #f6f8fa; }
tfoot td { font-weight: 700; }
tr.group { cursor: pointer; }
tr.group > td:first-child::before { content: "\\25B8\\00A0"; color: #57606a; }
tr.group.open > td:first-child::before { content: "\\25BE\\00A0"; }
tr.child td { background: #fafbfc; color: #57606a; }
tr.highlight td { background: #fff8c5; }
aside.note { border-left: 4px solid #d4a72c; background: #fff8c5;
  padding: 0.4rem 0.8rem; margin: 0.5rem 0; }
"""

_JS = """
const buttons = document.querySelectorAll('.tab-bar button');
function activate(id) {
  document.querySelectorAll('.tab-panel').forEach(
    (p) => p.classList.toggle('active', p.id === id));
  buttons.forEach((b) => b.classList.toggle('active', b.dataset.tab === id));
}
buttons.forEach((b) => b.addEventListener('click', () => activate(b.dataset.tab)));
if (buttons.length) activate(buttons[0].dataset.tab);
document.querySelectorAll('tr.group').forEach((g) => {
  g.addEventListener('click', (e) => {
    if (e.target.closest('a')) return;
    g.classList.toggle('open');
    document.querySelectorAll(
      'tr.child[data-parent="' + g.dataset.group + '"]'
    ).forEach((c) => c.toggleAttribute('hidden'));
  });
});
document.addEventListener('click', (e) => {
  const a = e.target.closest('a[href^="#"]');
  if (!a) return;
  const target = document.getElementById(
    decodeURIComponent(a.getAttribute('href').slice(1)));
  if (!target) return;
  const panel = target.closest('.tab-panel');
  if (panel) activate(panel.id);
  target.scrollIntoView();
  target.classList.add('highlight');
  setTimeout(() => target.classList.remove('highlight'), 1500);
  e.preventDefault();
});
"""


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def _collect_anchors(report: Report) -> set[str]:
    return {a for s in report.sections for t in s.tables
            for a in t.row_anchors[:len(t.rows)] if a}


def _cell_html(c: Cell, anchors: set[str]) -> str:
    if c is None:
        return _NA
    if isinstance(c, Link):
        if c.target in anchors:
            return f'<a href="#{_esc(c.target)}">{_esc(c.text)}</a>'
        return _esc(c.text)
    return _esc(c)


def _table_html(t: ReportTable, anchors: set[str],
                group_ids: Iterator[int]) -> list[str]:
    out = [f"<h3>{_esc(t.title)}</h3>", "<table>"]
    out.append("<thead><tr>"
               + "".join(f"<th>{_esc(col)}</th>" for col in t.columns)
               + "</tr></thead>")
    out.append("<tbody>")
    if not t.rows and not t.footer_rows:
        out.append("<tr><td>(empty)</td>"
                   + "<td></td>" * (len(t.columns) - 1) + "</tr>")
    for i, row in enumerate(t.rows):
        anchor = t.row_anchors[i] if i < len(t.row_anchors) else None
        id_attr = f' id="{_esc(anchor)}"' if anchor else ""
        children = t.row_children[i] if i < len(t.row_children) else []
        gid = f"g{next(group_ids)}" if children else None
        group_attr = f' class="group" data-group="{gid}"' if gid else ""
        out.append(f"<tr{id_attr}{group_attr}>"
                   + "".join(f"<td>{_cell_html(c, anchors)}</td>" for c in row)
                   + "</tr>")
        for child in children:
            out.append(
                f'<tr class="child" data-parent="{gid}" hidden>'
                + "".join(f"<td>{_cell_html(c, anchors)}</td>" for c in child)
                + "</tr>")
    out.append("</tbody>")
    if t.footer_rows:
        out.append("<tfoot>")
        for row in t.footer_rows:
            out.append("<tr>"
                       + "".join(f"<td>{_cell_html(c, anchors)}</td>"
                                 for c in row)
                       + "</tr>")
        out.append("</tfoot>")
    out.append("</table>")
    return out


def _panel_html(section: ReportSection, index: int, anchors: set[str],
                group_ids: Iterator[int]) -> list[str]:
    out = [f'<section class="tab-panel" id="tab-{index}">']
    if section.intro:
        out.append(f"<p>{_esc(section.intro)}</p>")
    for t in section.tables:
        out.extend(_table_html(t, anchors, group_ids))
    for note in section.notes:
        out.append(f'<aside class="note">{_esc(note)}</aside>')
    out.append("</section>")
    return out


class HtmlRenderer:
    """Renders a Report as a self-contained tabbed HTML document."""

    def render(self, report: Report) -> str:
        anchors = _collect_anchors(report)
        group_ids = itertools.count()
        out = [
            "<!DOCTYPE html>",
            '<html lang="en">',
            "<head>",
            '<meta charset="utf-8">',
            f"<title>{_esc(report.title)}</title>",
            f"<style>{_CSS}</style>",
            "</head>",
            "<body>",
            f"<h1>{_esc(report.title)}</h1>",
        ]
        if report.metadata:
            out.append('<dl class="meta">')
            for key, value in report.metadata.items():
                out.append(f"<dt>{_esc(key)}</dt><dd>{_esc(value)}</dd>")
            out.append("</dl>")
        out.append('<div class="tab-bar">')
        for i, section in enumerate(report.sections):
            out.append(f'<button type="button" data-tab="tab-{i}">'
                       f"{_esc(section.title)}</button>")
        out.append("</div>")
        for i, section in enumerate(report.sections):
            out.extend(_panel_html(section, i, anchors, group_ids))
        out.append(f"<script>{_JS}</script>")
        out.append("</body>")
        out.append("</html>")
        return "\n".join(out) + "\n"
