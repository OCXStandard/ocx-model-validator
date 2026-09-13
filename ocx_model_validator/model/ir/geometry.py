"""Geometry IR types — points, vectors, curves, surfaces, reference frames.

All geometry types are ``frozen=True`` dataclasses.  ``IrCurve3D.curve_length``
is a required positional field (no default) so builders cannot forget it.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ocx_model_validator.model.ir.base import Quantity


# --- primitive value types ---

@dataclass(frozen=True)
class IrPoint3D:
    """A 3D point in model coordinates."""
    x: float
    y: float
    z: float
    unit: str  # OCX unit id, e.g. 'Um', 'Umm'


@dataclass(frozen=True)
class IrVector3D:
    """A dimensionless 3D direction vector."""
    x: float
    y: float
    z: float


# --- curve hierarchy ---

@dataclass(frozen=True)
class IrCurve3D:
    """Abstract base for all 3D curve types.

    ``curve_length`` has no default — builders MUST pass it (``None`` if the
    length is absent in the model).
    """
    curve_length: Quantity | None  # required positional field
    id: str | None = None


@dataclass(frozen=True)
class IrLine3D(IrCurve3D):
    start: IrPoint3D | None = None
    end: IrPoint3D | None = None


@dataclass(frozen=True)
class IrCircumArc3D(IrCurve3D):
    start: IrPoint3D | None = None
    intermediate: IrPoint3D | None = None
    end: IrPoint3D | None = None


@dataclass(frozen=True)
class IrCircle3D(IrCurve3D):
    center: IrPoint3D | None = None
    diameter: Quantity | None = None
    normal: IrVector3D | None = None


@dataclass(frozen=True)
class IrPolyLine3D(IrCurve3D):
    vertices: list[IrPoint3D] = field(default_factory=list)
    is_closed: bool = False


@dataclass(frozen=True)
class IrCompositeCurve3D(IrCurve3D):
    segments: list[IrCurve3D] = field(default_factory=list)


@dataclass(frozen=True)
class IrEllipse3D(IrCurve3D):
    center: IrPoint3D | None = None
    major_diameter: Quantity | None = None
    minor_diameter: Quantity | None = None
    major_axis: IrVector3D | None = None
    minor_axis: IrVector3D | None = None
    normal: IrVector3D | None = None


@dataclass(frozen=True)
class IrNurbs3D(IrCurve3D):
    degree: int | None = None
    knot_vector: list[float] = field(default_factory=list)
    control_points: list[IrPoint3D] = field(default_factory=list)
    weights: list[float] = field(default_factory=list)
    is_rational: bool = False
    form: str | None = None


# --- surface hierarchy ---

@dataclass(frozen=True)
class IrSurface3D:
    """Abstract base for all 3D surface types."""
    id: str | None = None


@dataclass(frozen=True)
class IrPlane3D(IrSurface3D):
    origin: IrPoint3D | None = None
    normal: IrVector3D | None = None
    udirection: IrVector3D | None = None


@dataclass(frozen=True)
class IrSphere3D(IrSurface3D):
    origin: IrPoint3D | None = None
    radius: Quantity | None = None


@dataclass(frozen=True)
class IrCone3D(IrSurface3D):
    origin: IrPoint3D | None = None
    tip: IrPoint3D | None = None
    base_radius: Quantity | None = None
    tip_radius: Quantity | None = None


@dataclass(frozen=True)
class IrCylinder3D(IrSurface3D):
    origin: IrPoint3D | None = None
    axis: IrVector3D | None = None
    radius: Quantity | None = None
    height: Quantity | None = None


@dataclass(frozen=True)
class IrExtrudedSurface(IrSurface3D):
    base_curve: IrCurve3D | None = None
    sweep: IrVector3D | None = None
    sweep_curve: IrCurve3D | None = None
    face_boundary_curve: IrCurve3D | None = None


@dataclass(frozen=True)
class IrNurbsSurface(IrSurface3D):
    u_degree: int | None = None
    v_degree: int | None = None
    u_knot_vector: list[float] = field(default_factory=list)
    v_knot_vector: list[float] = field(default_factory=list)
    control_points: list[list[IrPoint3D]] = field(default_factory=list)


@dataclass(frozen=True)
class IrUnboundedGeometry:
    """Panel UnboundedGeometry: exactly one of an inline surface, a
    SurfaceRef (local_ref) or a GridRef (ref-plane id) is normally set."""
    surface: IrSurface3D | None = None
    surface_ref: str | None = None
    grid_ref: str | None = None


# --- standalone reference geometry ---

@dataclass(frozen=True)
class IrCoordinateSystem:
    id: str
    name: str | None = None
    is_global: bool = False
    local_origin: IrPoint3D | None = None
    x_ref_plane_ids: list[str] = field(default_factory=list)
    y_ref_plane_ids: list[str] = field(default_factory=list)
    z_ref_plane_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class IrRefPlane:
    id: str
    name: str | None = None
    reference_plane: IrPlane3D | None = None
    location: Quantity | None = None


@dataclass(frozen=True)
class IrSurface:
    id: str
    name: str | None = None
    guidref: str | None = None
    geometry: IrSurface3D | None = None


@dataclass(frozen=True)
class IrSurfaceCollection:
    id: str
    name: str | None = None
    surfaces: list[IrSurface] = field(default_factory=list)
