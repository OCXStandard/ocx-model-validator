"""Tests for the self-contained tabbed HTML renderer."""
from ocx_model_validator.reporting.model import (
    Link,
    Report,
    ReportSection,
    ReportTable,
)
from ocx_model_validator.reporting.renderers import get_renderer
from ocx_model_validator.reporting.renderers.html import HtmlRenderer


def _report() -> Report:
    bom = ReportSection(
        title="Bill of material",
        intro="Grouped by material.",
        tables=[ReportTable(
            title="Summary",
            columns=["Material", "Weight (t)"],
            rows=[[Link("NV A36", "material-M1"), 1.5],
                  [Link("Ghost", "material-MISSING"), None]],
            footer_rows=[["Grand total", 1.5]],
        )],
        notes=["1 item missing weight"],
    )
    materials = ReportSection(
        title="Materials",
        tables=[ReportTable(
            title="Materials",
            columns=["Id", "Name"],
            rows=[["M1", "NV A36"]],
            row_anchors=["material-M1"],
        )],
    )
    return Report(title="Model report",
                  metadata={"Vessel": "MV Test", "Schema version": "3.2.0"},
                  sections=[bom, materials])


def test_document_shell():
    out = HtmlRenderer().render(_report())
    assert out.startswith("<!DOCTYPE html>")
    assert "<title>Model report</title>" in out
    assert "<h1>Model report</h1>" in out
    assert "<style>" in out
    assert "<script>" in out


def test_metadata_definition_list():
    out = HtmlRenderer().render(_report())
    assert "<dt>Vessel</dt><dd>MV Test</dd>" in out
    assert "<dt>Schema version</dt><dd>3.2.0</dd>" in out


def test_one_tab_button_and_panel_per_section():
    out = HtmlRenderer().render(_report())
    assert out.count('data-tab="tab-') == 2
    assert '<button type="button" data-tab="tab-0">Bill of material</button>' in out
    assert '<button type="button" data-tab="tab-1">Materials</button>' in out
    assert '<section class="tab-panel" id="tab-0">' in out
    assert '<section class="tab-panel" id="tab-1">' in out


def test_resolved_link_renders_anchor():
    out = HtmlRenderer().render(_report())
    assert '<a href="#material-M1">NV A36</a>' in out


def test_unresolved_link_degrades_to_text():
    out = HtmlRenderer().render(_report())
    assert ">Ghost<" in out
    assert 'href="#material-MISSING"' not in out


def test_orphan_row_anchor_does_not_resolve_link():
    report = Report(title="R", sections=[
        ReportSection(title="Links", tables=[
            ReportTable("Links", ["A"], [[Link("Orphan", "orphan-anchor")]]),
        ]),
        ReportSection(title="Anchors", tables=[
            ReportTable("Anchors", ["A"], [["Real"]], row_anchors=[
                "real-anchor",
                "orphan-anchor",
            ]),
        ]),
    ])
    out = HtmlRenderer().render(report)
    assert ">Orphan<" in out
    assert 'href="#orphan-anchor"' not in out


def test_row_anchor_emitted_as_id():
    out = HtmlRenderer().render(_report())
    assert '<tr id="material-M1">' in out


def test_none_renders_na_and_footer_in_tfoot():
    out = HtmlRenderer().render(_report())
    assert "<td>N/A</td>" in out
    assert "<tfoot>" in out
    assert "<td>Grand total</td>" in out


def test_intro_and_notes():
    out = HtmlRenderer().render(_report())
    assert "<p>Grouped by material.</p>" in out
    assert '<aside class="note">1 item missing weight</aside>' in out


def test_empty_table_placeholder():
    report = Report(title="R", sections=[
        ReportSection(title="S", tables=[ReportTable("T", ["A", "B"], [])])
    ])
    out = HtmlRenderer().render(report)
    assert "<td>(empty)</td><td></td>" in out


def test_html_escaping():
    report = Report(
        title="A <b>& title",
        metadata={"K<": "v&"},
        sections=[ReportSection(title="S <i>", tables=[
            ReportTable("T <x>", ["Col <y>"], [["val <z> & more"]])
        ])],
    )
    out = HtmlRenderer().render(report)
    assert "<b>" not in out
    assert "A &lt;b&gt;&amp; title" in out
    assert "val &lt;z&gt; &amp; more" in out


def test_registry_dispatch():
    assert isinstance(get_renderer("html"), HtmlRenderer)


def _grouped_report() -> Report:
    table = ReportTable(
        title="Summary",
        columns=["Group", "Count"],
        rows=[["G1", 2], ["G2", 1], ["Subtotal", 3]],
        row_children=[[["item-a", None], ["item-b", None]],
                      [["item-c", None]],
                      []],
    )
    return Report(title="Grouped",
                  sections=[ReportSection(title="BOM", tables=[table])])


def test_group_rows_get_class_and_unique_group_ids():
    out = HtmlRenderer().render(_grouped_report())
    assert '<tr class="group" data-group="g0">' in out
    assert '<tr class="group" data-group="g1">' in out
    # Subtotal row has no children → no group class
    assert out.count('class="group"') == 2


def test_child_rows_hidden_and_parented():
    out = HtmlRenderer().render(_grouped_report())
    assert out.count('<tr class="child" data-parent="g0" hidden>') == 2
    assert out.count('<tr class="child" data-parent="g1" hidden>') == 1
    assert "<td>item-a</td>" in out


def test_group_toggle_script_present():
    out = HtmlRenderer().render(_grouped_report())
    assert "tr.group" in out
    assert "toggleAttribute('hidden')" in out


def test_group_rows_styled_bold():
    out = HtmlRenderer().render(_grouped_report())
    assert "tr.group > td { font-weight: 600; }" in out
