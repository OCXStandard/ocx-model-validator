"""Schema-neutral Intermediate Representation (IR) dataclasses for OCX models.

This package was split from the former monolithic ``ir.py`` into domain-focused
submodules (``base``, ``sections``, ``geometry``, ``structural``,
``arrangement``, ``catalogues``, ``metadata``, ``connections``).  Every public
type is re-exported here so that ``from ocx_model_validator.model.ir import X``
continues to work unchanged.

Design decisions:
- Every optional field defaults to ``None`` or ``[]`` — no field access ever
  raises AttributeError.
- ``IrVessel`` is the single root.  All structural parts are stored in flat
  dicts keyed by ``id`` so look-up is O(1).
- ``IrPanel`` holds *id references* to its children, not the objects themselves.
- Section types are modelled as typed subtypes of ``IrSection``.
"""
from __future__ import annotations

from ocx_model_validator.model.ir.base import (
    IrCog,
    IrUnit,
    ParentKind,
    ParentRef,
    Quantity,
    Ref,
)
from ocx_model_validator.model.ir.catalogues import (
    IrHole2D,
    IrHoleShapeCatalogue,
    IrMaterial,
)
from ocx_model_validator.model.ir.sections import (
    IrAngleSection,
    IrBulbFlatSection,
    IrFlatBarSection,
    IrGenericSection,
    IrHalfRoundSection,
    IrHexagonSection,
    IrISection,
    IrLSection,
    IrLSectionOvershootFlange,
    IrLSectionOvershootWeb,
    IrOctagonSection,
    IrRectangularTubeSection,
    IrRoundSection,
    IrSection,
    IrSquareSection,
    IrTSection,
    IrTubeSection,
    IrUSection,
    IrZSection,
)
from ocx_model_validator.model.ir.geometry import (
    IrCircle3D,
    IrCircumArc3D,
    IrCompositeCurve3D,
    IrCone3D,
    IrCoordinateSystem,
    IrCurve3D,
    IrCylinder3D,
    IrEllipse3D,
    IrExtrudedSurface,
    IrLine3D,
    IrNurbs3D,
    IrNurbsSurface,
    IrPlane3D,
    IrPoint3D,
    IrPolyLine3D,
    IrRefPlane,
    IrSphere3D,
    IrSurface,
    IrSurface3D,
    IrSurfaceCollection,
    IrVector3D,
)
from ocx_model_validator.model.ir.connections import (
    IrConnectionConfiguration,
    IrPenetration,
)
from ocx_model_validator.model.ir.arrangement import (
    IrBulkCargo,
    IrCompartment,
    IrDesignView,
    IrGaseousCargo,
    IrLiquidCargo,
    IrOccurrence,
    IrOccurrenceGroup,
    IrPhysicalSpace,
    IrUnitCargo,
)
from ocx_model_validator.model.ir.metadata import (
    IrBuilderInformation,
    IrPrincipalParticulars,
    IrShipDesignation,
    IrStatutoryData,
    IrTonnageData,
)
from ocx_model_validator.model.ir.structural import (
    IrBracket,
    IrEdgeReinforcement,
    IrEndCut,
    IrFeatureCope,
    IrInclination,
    IrLimitedByRef,
    IrMember,
    IrPanel,
    IrPillar,
    IrPlate,
    IrSeam,
    IrStiffener,
    IrVessel,
)

__all__ = [
    # base
    "IrCog", "Quantity", "IrUnit", "Ref", "ParentKind", "ParentRef",
    # catalogues
    "IrMaterial", "IrHole2D", "IrHoleShapeCatalogue",
    # sections
    "IrSection", "IrRectangularTubeSection", "IrOctagonSection",
    "IrSquareSection", "IrBulbFlatSection", "IrFlatBarSection", "IrUSection",
    "IrISection", "IrLSectionOvershootFlange", "IrZSection", "IrRoundSection",
    "IrLSection", "IrTSection", "IrLSectionOvershootWeb", "IrHalfRoundSection",
    "IrHexagonSection", "IrAngleSection", "IrTubeSection", "IrGenericSection",
    # geometry
    "IrPoint3D", "IrVector3D", "IrCurve3D", "IrLine3D", "IrCircumArc3D",
    "IrCircle3D", "IrPolyLine3D", "IrCompositeCurve3D", "IrEllipse3D",
    "IrNurbs3D", "IrSurface3D", "IrPlane3D", "IrSphere3D", "IrCone3D",
    "IrCylinder3D", "IrExtrudedSurface", "IrNurbsSurface",
    "IrCoordinateSystem", "IrRefPlane", "IrSurface", "IrSurfaceCollection",
    # connections
    "IrConnectionConfiguration", "IrPenetration",
    # structural
    "IrPlate", "IrBracket", "IrStiffener", "IrPillar", "IrEdgeReinforcement",
    "IrLimitedByRef", "IrPanel", "IrVessel",
    "IrSeam", "IrMember", "IrEndCut", "IrFeatureCope", "IrInclination",
    # arrangement
    "IrCompartment", "IrPhysicalSpace",
    "IrLiquidCargo", "IrGaseousCargo", "IrBulkCargo", "IrUnitCargo",
    "IrDesignView", "IrOccurrenceGroup", "IrOccurrence",
    # metadata
    "IrShipDesignation", "IrTonnageData", "IrPrincipalParticulars",
    "IrStatutoryData", "IrBuilderInformation",
]
