"""OCX UnitSet → IrUnit registry and SI conversion utilities.

The OCX model stores all physical quantity values with a ``unit`` attribute
that is the **id** of an entry in the ``<UnitSet>`` element (e.g. ``'Umm'``
for millimetres, ``'UNOvermm2'`` for N/mm²).  Each ``<Unit>`` is defined via
UnitsML's ``<RootUnits>/<EnumeratedRootUnit>`` mechanism — a product of SI
base units, each optionally scaled by an SI prefix and raised to an integer
power.

This module computes a single ``to_si_factor`` float per unit so that any
OCX quantity can be normalised to SI with a single multiplication::

    si_value = raw_value * ir_unit.to_si_factor

For compound units the factor is the product of each root-unit contribution::

    factor = ∏  (base_si_factor[U] × prefix_factor[P]) ^ n_i

Examples
--------
- ``Umm``  (millimetre)    : meter × prefix_m  × power 1  → 1e-3
- ``UKg``  (kilogram)      : gram  × prefix_k  × power 1  → 1.0
- ``UNOvermm2`` (N/mm²)   : newton^1 × (meter × prefix_m)^-2 → 1e6  (Pa)
- ``Ut``   (metric ton)    : metric_ton × power 1           → 1000.0 (kg)
"""
from __future__ import annotations

import math

from loguru import logger

from ocx_model_validator.exeptions import GeometryError
from ocx_model_validator.model.ir import IrPoint3D, IrUnit, Quantity

# ---------------------------------------------------------------------------
# SI prefix multipliers — keyed by the *string value* of the
# EnumeratedRootUnitTypePrefix enum (e.g. 'c' → 1e-2).
# ---------------------------------------------------------------------------
_SI_PREFIX_FACTORS: dict[str, float] = {
    "Y":  1e24,   # yotta
    "Z":  1e21,   # zetta
    "E":  1e18,   # exa
    "P":  1e15,   # peta
    "T":  1e12,   # tera
    "G":  1e9,    # giga
    "M":  1e6,    # mega
    "k":  1e3,    # kilo
    "h":  1e2,    # hecto
    "da": 1e1,    # deca
    "d":  1e-1,   # deci
    "c":  1e-2,   # centi
    "m":  1e-3,   # milli
    "mu": 1e-6,   # micro
    "n":  1e-9,   # nano
    "p":  1e-12,  # pico
    "f":  1e-15,  # femto
    "a":  1e-18,  # atto
    "z":  1e-21,  # zepto
    "y":  1e-24,  # yocto
}

# ---------------------------------------------------------------------------
# SI base-unit conversion factors.
# Key   : string value of EnumeratedRootUnitTypeUnit enum (e.g. 'meter').
# Value : factor such that  1 <unit> = factor × SI_base_unit.
#
# Length    → metre   (m)
# Mass      → kilogram (kg)  [OCX uses 'gram' as its base, so 1 g = 1e-3 kg]
# Force     → newton  (N)
# Pressure  → pascal  (Pa)
# Angle     → radian  (rad)
# Time      → second  (s)
# ---------------------------------------------------------------------------
_BASE_UNIT_SI_FACTOR: dict[str, float] = {
    # Length
    "meter":         1.0,
    "nautical_mile": 1852.0,
    "inch":          0.0254,
    "foot":          0.3048,
    "yard":          0.9144,
    "mile":          1609.344,
    "angstrom":      1e-10,
    # Mass  (SI base: kg; UnitsML base for mass is 'gram')
    "gram":          1e-3,
    "metric_ton":    1e3,
    "pound":         0.45359237,
    "slug":          14.593903,
    "long_ton":      1016.0469,
    "short_ton":     907.18474,
    # Force
    "newton":        1.0,
    "pound_force":   4.44822162,
    "kilogram_force": 9.80665,
    "dyne":          1e-5,
    "kip":           4448.22162,
    "ton_force":     9964.016418,
    # Pressure / stress
    "pascal":        1.0,
    "bar":           1e5,
    "standard_atmosphere": 101325.0,
    # Energy
    "joule":         1.0,
    # Power
    "watt":          1.0,
    # Angle
    "radian":        1.0,
    "arc_degree":    math.pi / 180.0,
    "arc_minute":    math.pi / 10800.0,
    "arc_second":    math.pi / 648000.0,
    "gon":           math.pi / 200.0,
    # Time
    "second":        1.0,
    "minute":        60.0,
    "hour":          3600.0,
    "day":           86400.0,
    # Temperature (factor for *range* conversions; offset conversions not handled here)
    "kelvin":        1.0,
    "degree_Celsius": 1.0,
    # Speed
    "knot":          0.514444,
    # Volume
    "liter":         1e-3,
    # Electrical
    "ampere":        1.0,
    "volt":          1.0,
    "ohm":           1.0,
    "farad":         1.0,
    "henry":         1.0,
    "tesla":         1.0,
    "weber":         1.0,
    "siemens":       1.0,
    # Misc
    "hertz":         1.0,
    "coulomb":       1.0,
}

# ---------------------------------------------------------------------------
# Dimension URL → SI base-unit symbol
# ---------------------------------------------------------------------------
_DIM_TO_SI_SYMBOL: dict[str, str] = {
    "D_L":      "m",
    "D_L2":     "m²",
    "D_L3":     "m³",
    "D_L4":     "m⁴",
    "D_Kg":     "kg",
    "D_Kg.M-3": "kg/m³",
    "D_N.MM-2": "Pa",
    "D_L.T-1":  "m/s",
    "D_NM":     "N·m",
    "D_None":   "",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _prefix_factor(prefix_obj) -> float:
    """Return the SI prefix multiplier from an ``EnumeratedRootUnitTypePrefix``."""
    if prefix_obj is None:
        return 1.0
    raw = prefix_obj.value if hasattr(prefix_obj, "value") else str(prefix_obj)
    factor = _SI_PREFIX_FACTORS.get(raw)
    if factor is None:
        logger.warning(f"Unknown SI prefix {raw!r}; defaulting to 1.0")
        return 1.0
    return factor


def _base_factor(unit_obj) -> float:
    """Return the SI conversion factor from an ``EnumeratedRootUnitTypeUnit``."""
    if unit_obj is None:
        return 1.0
    raw = unit_obj.value if hasattr(unit_obj, "value") else str(unit_obj)
    factor = _BASE_UNIT_SI_FACTOR.get(raw)
    if factor is None:
        logger.warning(f"Unknown base unit {raw!r}; defaulting factor to 1.0")
        return 1.0
    return factor


def _compute_to_si_factor(root_units_obj) -> float:
    """Compute the to-SI multiplication factor from an OCX ``RootUnits`` object.

    The factor is the product of each ``EnumeratedRootUnit`` contribution::

        factor = ∏  (base_si_factor[U] × prefix_factor[P]) ^ power_numerator_i
    """
    if root_units_obj is None:
        return 1.0
    factor = 1.0
    for eru in getattr(root_units_obj, "enumerated_root_unit", []):
        base   = _base_factor(getattr(eru, "unit", None))
        prefix = _prefix_factor(getattr(eru, "prefix", None))
        power  = getattr(eru, "power_numerator", 1)
        if power is None:
            power = 1
        factor *= (base * prefix) ** power
    return factor


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_unit_registry(units_ml) -> dict[str, IrUnit]:
    """Build an ``IrUnit`` registry from an OCX ``UnitsMl`` dataclass.

    Parameters
    ----------
    units_ml:
        The ``OcxXml.units_ml`` attribute (may be ``None`` for models that
        omit the UnitSet).

    Returns
    -------
    dict[str, IrUnit]
        Mapping from OCX unit id (e.g. ``'Umm'``) to ``IrUnit``.  Empty dict
        when ``units_ml`` is ``None`` or contains no ``<UnitSet>``.
    """
    registry: dict[str, IrUnit] = {}

    if units_ml is None:
        logger.warning("UnitsMl not present in OCX root; unit registry is empty.")
        return registry

    unit_set = getattr(units_ml, "unit_set", None)
    if unit_set is None:
        return registry

    for raw_unit in getattr(unit_set, "unit", []):
        uid = getattr(raw_unit, "id", None)
        if not uid:
            continue

        # Human-readable name (first UnitName entry)
        names = getattr(raw_unit, "unit_name", [])
        name = names[0].value if names else uid

        # Symbol (type_value of first UnitSymbol entry)
        syms = getattr(raw_unit, "unit_symbol", [])
        symbol = syms[0].type_value if syms else ""

        dimension_url = getattr(raw_unit, "dimension_url", None)
        si_symbol = _DIM_TO_SI_SYMBOL.get(dimension_url or "", "")

        root_units = getattr(raw_unit, "root_units", None)
        to_si_factor = _compute_to_si_factor(root_units)

        registry[uid] = IrUnit(
            id=uid,
            name=name,
            symbol=symbol,
            dimension_url=dimension_url,
            to_si_factor=to_si_factor,
            si_symbol=si_symbol,
        )
        logger.debug(
            f"Unit {uid!r} ({symbol!r}): to_si_factor={to_si_factor:.6g}"
        )

    logger.info(f"Built unit registry with {len(registry)} entries.")
    return registry


class UnitConverter:
    """Converts OCX physical quantities to coherent SI base-unit values.

    Parameters
    ----------
    registry:
        ``IrUnit`` registry produced by :func:`build_unit_registry`.
    """

    def __init__(self, registry: dict[str, IrUnit]) -> None:
        self._reg = registry

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get_unit(self, unit_id: str) -> IrUnit | None:
        """Look up a unit definition by its OCX id."""
        return self._reg.get(unit_id)

    def si_symbol(self, unit_id: str) -> str:
        """Return the SI base-unit symbol for *unit_id*, or empty string."""
        u = self._reg.get(unit_id)
        return u.si_symbol if u else ""

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    def to_si(self, value: float, unit_id: str) -> float:
        """Convert *value* (in the unit identified by *unit_id*) to SI.

        Returns *value* unchanged when *unit_id* is not found in the registry
        so that callers do not crash on missing unit definitions.
        """
        ir_unit = self._reg.get(unit_id)
        if ir_unit is None:
            logger.warning(
                f"Unit id {unit_id!r} not found in registry; value left unchanged."
            )
            return value
        return value * ir_unit.to_si_factor

    def convert_quantity(self, qty: Quantity | None) -> Quantity | None:
        """Return a new :class:`Quantity` normalised to the SI base unit.

        The original ``Quantity`` is returned unchanged when its unit id is not
        in the registry.  ``None`` is passed through as ``None``.
        """
        if qty is None:
            return None
        ir_unit = self._reg.get(qty.unit)
        if ir_unit is None:
            return qty
        return Quantity(value=qty.value * ir_unit.to_si_factor, unit=ir_unit.si_symbol)

    def resolve_quantity(self, qty: Quantity | None) -> Quantity | None:
        """Return a new :class:`Quantity` with the OCX unit id replaced by the
        human-readable unit symbol (value is *not* changed).

        This is distinct from :meth:`convert_quantity`, which also transforms
        the value to the SI base unit.  ``resolve_quantity`` only replaces the
        ``unit`` string so that callers see ``"mm"`` instead of ``"Umm"``.

        The original ``Quantity`` is returned unchanged when its unit id is not
        in the registry.  ``None`` is passed through as ``None``.

        Examples::

            resolve_quantity(Quantity(12.5, "Umm"))       → Quantity(12.5, "mm")
            resolve_quantity(Quantity(235.0, "UNOvermm2")) → Quantity(235.0, "N/mm2")
        """
        if qty is None:
            return None
        ir_unit = self._reg.get(qty.unit)
        if ir_unit is None:
            return qty  # unknown unit id — return as-is
        # Prefer the unit's own symbol; fall back to SI base-unit symbol.
        # Both may be empty for dimensionless quantities — that is intentional.
        symbol = ir_unit.symbol if ir_unit.symbol else ir_unit.si_symbol
        return Quantity(value=qty.value, unit=symbol)

    def convert_between(
        self,
        value: float,
        from_unit_id: str,
        to_unit_id: str,
    ) -> float | None:
        """Convert *value* from one OCX unit to another via the SI intermediary.

        Parameters
        ----------
        value:
            The numeric value expressed in the unit identified by *from_unit_id*.
        from_unit_id:
            OCX unit id of the source unit (e.g. ``"Umm"``).
        to_unit_id:
            OCX unit id of the target unit (e.g. ``"Um"``).

        Returns
        -------
        float | None
            The converted value, or ``None`` when either unit id is not found
            in the registry (no silent guess).

        Examples::

            convert_between(1000.0, "Umm", "Um")           → 1.0
            convert_between(235.0, "UNOvermm2", "UNOverm2") → 235e6
        """
        from_ir = self._reg.get(from_unit_id)
        to_ir = self._reg.get(to_unit_id)
        if from_ir is None:
            logger.warning(f"convert_between: source unit {from_unit_id!r} not in registry.")
            return None
        if to_ir is None:
            logger.warning(f"convert_between: target unit {to_unit_id!r} not in registry.")
            return None
        if to_ir.to_si_factor == 0.0:
            logger.warning(f"convert_between: target unit {to_unit_id!r} has zero to_si_factor.")
            return None
        si_value = value * from_ir.to_si_factor
        return si_value / to_ir.to_si_factor

# ---------------------------------------------------------------------------
# Quantity/point conversion helpers (mm, m3, kPa targets)
#
# The OCX unit_registry (IrUnit.to_si_factor) is authoritative; a small
# fallback table covers models that omit the units section. A blank unit
# string means the value is already SI.
# ---------------------------------------------------------------------------

_FALLBACK_SI = {
    "": 1.0,
    "Um": 1.0,
    "Umm": 1e-3,
    "Ucm": 1e-2,
    "Um3": 1.0,
    "UPa": 1.0,
    "UMPa": 1e6,
    "UKg": 1.0,
    "Ut": 1e3,
}


def to_si(qty: Quantity, registry: dict[str, IrUnit]) -> float:
    """Return the SI value of qty using registry, falling back to _FALLBACK_SI."""
    unit = qty.unit or ""
    entry = registry.get(unit)
    if entry is not None and entry.to_si_factor is not None:
        return qty.value * entry.to_si_factor
    if unit in _FALLBACK_SI:
        return qty.value * _FALLBACK_SI[unit]
    raise GeometryError(f"Unknown unit id {unit!r}; cannot convert to SI")


def qty_mm(qty: Quantity | None, registry: dict[str, IrUnit]) -> float | None:
    return None if qty is None else to_si(qty, registry) * 1000.0


def qty_m3(qty: Quantity | None, registry: dict[str, IrUnit]) -> float | None:
    return None if qty is None else to_si(qty, registry)


def qty_kpa(qty: Quantity | None, registry: dict[str, IrUnit]) -> float | None:
    return None if qty is None else to_si(qty, registry) / 1e3


def point_mm(p: IrPoint3D, registry: dict[str, IrUnit]) -> tuple[float, float, float]:
    """Convert an IrPoint3D to an (x, y, z) tuple in millimetres."""
    unit = getattr(p, "unit", "") or ""
    f = 1000.0 * to_si(Quantity(1.0, unit), registry)
    return (p.x * f, p.y * f, p.z * f)
