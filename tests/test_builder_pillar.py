"""Builder extraction of trace and inclinations onto IrPillar."""
from ocx_model_validator.builders.v3_builder import OcxV3Builder
from ocx_model_validator.model.ir.base import ParentKind, ParentRef


class _Pillar:
    def __init__(self):
        self.id = "PIL1"
        self.name = "Hold pillar"
        self.guidref = None
        self.material_ref = None
        self.section_ref = None
        self.trace_line = None
        self.inclination = None


def _build(raw):
    return OcxV3Builder()._build_pillar(
        raw, ParentRef(kind=ParentKind.VESSEL, id="V1"))


def test_pillar_defaults_have_trace_and_inclinations_fields():
    p = _build(_Pillar())
    assert p.trace is None
    assert p.inclinations == []
    assert p.penetrations == []


def test_pillar_inclinations_built():
    raw = _Pillar()
    raw.inclination = [object(), object()]
    p = _build(raw)
    assert len(p.inclinations) == 2
