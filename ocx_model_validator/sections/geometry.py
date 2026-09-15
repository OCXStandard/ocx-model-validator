"""Plane-curve intersection helpers for transverse cross sections."""
from __future__ import annotations

from collections.abc import Callable, Sequence
from math import atan2, cos, pi, sin

import numpy as np

from ocx_model_validator.exeptions import GeometryError
from ocx_model_validator.model.ir.base import Quantity
from ocx_model_validator.model.ir.geometry import (
    IrCircle3D,
    IrCircumArc3D,
    IrCompositeCurve3D,
    IrCurve3D,
    IrLine3D,
    IrNurbs3D,
    IrPoint3D,
    IrPolyLine3D,
)

_PLANE_EPS = 1e-9


PointToMm = Callable[[IrPoint3D], tuple[float, float, float]]


def intersect_curve_plane(
    curve: IrCurve3D | None,
    x_mm: float,
    to_mm: PointToMm,
    tol: float = 0.1,
) -> list[tuple[float, float]]:
    """Return ``(y, z)`` intersections between an IR curve and plane ``X=x_mm``."""
    if curve is None:
        return []
    if isinstance(curve, IrLine3D):
        if curve.start is None or curve.end is None:
            raise GeometryError("IrLine3D is missing start or end point")
        return _dedupe(_segments_hits([curve.start, curve.end], x_mm, to_mm), tol)
    if isinstance(curve, IrPolyLine3D):
        if not curve.vertices or any(point is None for point in curve.vertices):
            raise GeometryError("IrPolyLine3D is missing vertex point data")
        points = list(curve.vertices)
        if curve.is_closed and len(points) > 1:
            points.append(points[0])
        return _dedupe(_segments_hits(points, x_mm, to_mm), tol)
    if isinstance(curve, IrCompositeCurve3D):
        hits: list[tuple[float, float]] = []
        for segment in curve.segments:
            hits.extend(intersect_curve_plane(segment, x_mm, to_mm, tol))
        return _dedupe(hits, tol)
    if isinstance(curve, IrNurbs3D):
        evaluator, t0, t1, count = _nurbs_evaluator(curve, to_mm)
        return _dedupe(
            _sampled_hits(
                evaluator,
                t0,
                t1,
                x_mm,
                tol,
                max(200, 20 * count),
            ),
            tol,
        )
    if isinstance(curve, IrCircumArc3D):
        return _dedupe(_circumarc_hits(curve, x_mm, to_mm), tol)
    if isinstance(curve, IrCircle3D):
        return _dedupe(_circle_hits(curve, x_mm, to_mm), tol)
    raise GeometryError(f"Unsupported curve type {type(curve).__name__}")


def trace_profile(
    curve: IrCurve3D | None,
    x_mm: float,
    to_mm: PointToMm,
    tol: float = 0.1,
) -> list[tuple[float, float]] | None:
    """Return the full ``(y, z)`` section trace of a prismatic closed contour.

    Plate outer contours of prismatic plates carry the transverse profile
    (e.g. a tessellated bilge arc) on their transverse edges. Walking the
    contour between its two crossings of the plane ``X=x_mm`` through the
    nearest transverse edge and dropping the x coordinate recovers the true
    section trace instead of the corner-cutting chord between the crossings.

    Returns ``None`` when the contour is not a single connected closed loop
    crossing the plane exactly twice — callers fall back to the plain
    plane-hit pairing in that case.
    """
    if curve is None:
        return None
    try:
        polyline = _contour_polyline(curve, to_mm, tol)
    except GeometryError:
        return None
    if polyline is None or len(polyline) < 4:
        return None
    if float(np.linalg.norm(polyline[0] - polyline[-1])) > max(tol, 1.0):
        return None

    points = polyline[:-1]
    count = len(points)
    crossings: list[tuple[int, np.ndarray]] = []
    for index in range(count):
        a = points[index]
        b = points[(index + 1) % count]
        da = float(a[0] - x_mm)
        db = float(b[0] - x_mm)
        if abs(da) < _PLANE_EPS and abs(db) < _PLANE_EPS:
            return None
        if abs(da) < _PLANE_EPS:
            crossings.append((index, a.copy()))
        elif abs(db) >= _PLANE_EPS and da * db < 0.0:
            alpha = da / (da - db)
            crossings.append((index, a + alpha * (b - a)))
    if len(crossings) != 2 or crossings[0][0] == crossings[1][0]:
        return None

    (first_edge, first_hit), (second_edge, second_hit) = crossings
    forward = _walk_ring(points, first_edge, first_hit, second_edge, second_hit)
    backward = _walk_ring(points, second_edge, second_hit, first_edge, first_hit)

    def x_reach(path: list[np.ndarray]) -> float:
        return max(abs(float(point[0]) - x_mm) for point in path)

    chosen = forward if x_reach(forward) <= x_reach(backward) else list(reversed(backward))
    trace: list[tuple[float, float]] = []
    for point in chosen:
        yz = (float(point[1]), float(point[2]))
        if not trace or ((yz[0] - trace[-1][0]) ** 2 + (yz[1] - trace[-1][1]) ** 2) ** 0.5 > tol:
            trace.append(yz)
    if len(trace) < 2:
        return None
    trace[-1] = (float(chosen[-1][1]), float(chosen[-1][2]))
    return trace


def _walk_ring(
    points: list[np.ndarray],
    start_edge: int,
    start_hit: np.ndarray,
    stop_edge: int,
    stop_hit: np.ndarray,
) -> list[np.ndarray]:
    count = len(points)
    path = [start_hit]
    index = (start_edge + 1) % count
    while True:
        path.append(points[index])
        if index == stop_edge:
            break
        index = (index + 1) % count
    path.append(stop_hit)
    return path


def _contour_polyline(
    curve: IrCurve3D,
    to_mm: PointToMm,
    tol: float,
) -> list[np.ndarray] | None:
    """Return the contour as a connected 3D polyline, or ``None`` if unsupported."""
    if isinstance(curve, IrLine3D):
        if curve.start is None or curve.end is None:
            return None
        return [_point_array(curve.start, to_mm), _point_array(curve.end, to_mm)]
    if isinstance(curve, IrPolyLine3D):
        if not curve.vertices or any(point is None for point in curve.vertices):
            return None
        points = [_point_array(point, to_mm) for point in curve.vertices]
        if curve.is_closed and len(points) > 1:
            points.append(points[0].copy())
        return points
    if isinstance(curve, IrNurbs3D):
        evaluator, t0, t1, _ = _nurbs_evaluator(curve, to_mm)
        knots = sorted({float(k) for k in curve.knot_vector if t0 <= k <= t1})
        straight_tol = max(tol, 0.25)
        points: list[np.ndarray] = []
        for left, right in zip(knots, knots[1:]):
            samples = [evaluator(left + (right - left) * step / 4.0) for step in range(4)]
            end = evaluator(right)
            # Polygon-encoded NURBS have straight knot spans; interior samples
            # then sit on the chord (off any true circle) and must be dropped
            # so arc decomposition sees only the tessellation vertices.
            if _points_on_chord(samples[1:], samples[0], end, straight_tol):
                points.append(samples[0])
            else:
                points.extend(samples)
        points.append(evaluator(t1))
        return points
    if isinstance(curve, IrCircumArc3D):
        return _circumarc_polyline(curve, to_mm)
    if isinstance(curve, IrCompositeCurve3D):
        join_tol = max(tol, 1.0)
        chain: list[np.ndarray] | None = None
        for segment in curve.segments:
            piece = _contour_polyline(segment, to_mm, tol)
            if piece is None or len(piece) < 2:
                return None
            if chain is None:
                chain = list(piece)
            elif float(np.linalg.norm(chain[-1] - piece[0])) <= join_tol:
                chain.extend(piece[1:])
            elif float(np.linalg.norm(chain[-1] - piece[-1])) <= join_tol:
                chain.extend(reversed(piece[:-1]))
            else:
                return None
        return chain
    return None


def _points_on_chord(
    interior: list[np.ndarray],
    start: np.ndarray,
    end: np.ndarray,
    tol: float,
) -> bool:
    chord = end - start
    length = float(np.linalg.norm(chord))
    if length <= 0.0:
        return True
    return all(
        float(np.linalg.norm(np.cross(point - start, chord))) / length <= tol
        for point in interior
    )


def _circumarc_polyline(
    curve: IrCircumArc3D,
    to_mm: PointToMm,
    samples: int = 16,
) -> list[np.ndarray] | None:
    if curve.start is None or curve.intermediate is None or curve.end is None:
        return None
    start = _point_array(curve.start, to_mm)
    middle = _point_array(curve.intermediate, to_mm)
    end = _point_array(curve.end, to_mm)
    try:
        center, radius, normal = _circle_from_three_points(start, middle, end)
        u = _normalize(start - center, "IrCircumArc3D has zero radius")
    except GeometryError:
        return None
    v = np.cross(normal, u)
    middle_angle = _angle_on_axes(middle - center, u, v)
    end_angle = _angle_on_axes(end - center, u, v)
    sweep = _arc_sweep_containing_middle(middle_angle, end_angle)
    return [
        center + radius * (cos(theta) * u + sin(theta) * v)
        for theta in np.linspace(0.0, sweep, samples)
    ]


def _segments_hits(
    points: Sequence[IrPoint3D],
    x_mm: float,
    to_mm: PointToMm,
) -> list[tuple[float, float]]:
    if len(points) < 2:
        return []
    coords = [_point_array(point, to_mm) for point in points]
    hits: list[tuple[float, float]] = []
    for a, b in zip(coords, coords[1:]):
        da = float(a[0] - x_mm)
        db = float(b[0] - x_mm)
        if abs(da) < _PLANE_EPS and abs(db) < _PLANE_EPS:
            hits.append((float(a[1]), float(a[2])))
            hits.append((float(b[1]), float(b[2])))
        elif abs(da) < _PLANE_EPS:
            hits.append((float(a[1]), float(a[2])))
        elif abs(db) < _PLANE_EPS:
            hits.append((float(b[1]), float(b[2])))
        elif da * db < 0.0:
            alpha = (x_mm - float(a[0])) / float(b[0] - a[0])
            point = a + alpha * (b - a)
            hits.append((float(point[1]), float(point[2])))
    return hits


def _dedupe(pts: Sequence[tuple[float, float]], tol: float) -> list[tuple[float, float]]:
    kept: list[tuple[float, float]] = []
    for point in pts:
        if not any(np.linalg.norm(np.subtract(point, existing)) <= tol for existing in kept):
            kept.append(point)
    return kept


def _nurbs_evaluator(
    curve: IrNurbs3D,
    to_mm: PointToMm,
) -> tuple[Callable[[float], np.ndarray], float, float, int]:
    degree = curve.degree
    control_points = curve.control_points
    knots = curve.knot_vector
    if degree is None or degree < 0:
        raise GeometryError("IrNurbs3D is missing a valid degree")
    if not control_points or any(point is None for point in control_points):
        raise GeometryError("IrNurbs3D is missing control point data")
    if degree >= len(control_points):
        raise GeometryError("IrNurbs3D degree must be less than control point count")
    expected_knot_count = len(control_points) + degree + 1
    if len(knots) != expected_knot_count:
        raise GeometryError(
            f"IrNurbs3D knot vector must contain {expected_knot_count} values"
        )
    if any(right < left for left, right in zip(knots, knots[1:])):
        raise GeometryError("IrNurbs3D knot vector must be nondecreasing")
    weights = curve.weights or [1.0] * len(control_points)
    if len(weights) != len(control_points):
        raise GeometryError("IrNurbs3D weights must match control points")

    homogeneous = []
    for point, weight in zip(control_points, weights):
        xyz = _point_array(point, to_mm)
        homogeneous.append(np.array([xyz[0] * weight, xyz[1] * weight, xyz[2] * weight, weight]))
    ctrl = np.asarray(homogeneous, dtype=float)
    knot_array = np.asarray(knots, dtype=float)
    t0 = float(knot_array[degree])
    t1 = float(knot_array[-degree - 1])
    if not t1 > t0:
        raise GeometryError("IrNurbs3D has an empty parameter domain")

    def evaluate(t: float) -> np.ndarray:
        span = _find_knot_span(float(t), degree, knot_array, len(ctrl) - 1)
        d = [ctrl[span - degree + j].copy() for j in range(degree + 1)]
        for r in range(1, degree + 1):
            for j in range(degree, r - 1, -1):
                i = span - degree + j
                denom = knot_array[i + degree - r + 1] - knot_array[i]
                alpha = 0.0 if abs(denom) < _PLANE_EPS else (t - knot_array[i]) / denom
                d[j] = (1.0 - alpha) * d[j - 1] + alpha * d[j]
        if abs(d[degree][3]) < _PLANE_EPS:
            raise GeometryError("IrNurbs3D evaluated to zero homogeneous weight")
        return d[degree][:3] / d[degree][3]

    return evaluate, t0, t1, len(control_points)


def _find_knot_span(t: float, degree: int, knots: np.ndarray, n: int) -> int:
    if t >= knots[n + 1]:
        return n
    if t <= knots[degree]:
        return degree
    low = degree
    high = n + 1
    mid = (low + high) // 2
    while t < knots[mid] or t >= knots[mid + 1]:
        if t < knots[mid]:
            high = mid
        else:
            low = mid
        mid = (low + high) // 2
    return mid


def _sampled_hits(
    f: Callable[[float], np.ndarray],
    t0: float,
    t1: float,
    x_mm: float,
    tol: float,
    n: int,
) -> list[tuple[float, float]]:
    params = np.linspace(t0, t1, max(2, n))
    values = [f(float(t)) for t in params]
    residuals = [float(value[0] - x_mm) for value in values]
    hits: list[tuple[float, float]] = []

    for param, value, residual in zip(params, values, residuals):
        if abs(residual) < _PLANE_EPS:
            hits.append((float(value[1]), float(value[2])))

    for index in range(len(params) - 1):
        left_t = float(params[index])
        right_t = float(params[index + 1])
        left_r = residuals[index]
        right_r = residuals[index + 1]
        if abs(left_r) < _PLANE_EPS or abs(right_r) < _PLANE_EPS or left_r * right_r > 0.0:
            continue
        hit = _bisect_hit(f, left_t, right_t, x_mm, tol)
        hits.append((float(hit[1]), float(hit[2])))

    near_hit_threshold = max(tol, 5.0 * tol)
    for index in range(1, len(params) - 1):
        residual = residuals[index]
        left_r = residuals[index - 1]
        right_r = residuals[index + 1]
        if (
            abs(residual) > near_hit_threshold
            or (
                not (residual >= left_r and residual >= right_r)
                and not (residual <= left_r and residual <= right_r)
            )
        ):
            continue
        hit_t, hit, hit_residual = _refine_residual_extremum(
            f,
            float(params[index - 1]),
            float(params[index]),
            float(params[index + 1]),
            x_mm,
            maximize=residual >= left_r and residual >= right_r,
        )
        found_bracketed_hit = False
        if left_r * hit_residual < 0.0:
            hit = _bisect_hit(f, float(params[index - 1]), hit_t, x_mm, tol)
            hits.append((float(hit[1]), float(hit[2])))
            found_bracketed_hit = True
        if hit_residual * right_r < 0.0:
            hit = _bisect_hit(f, hit_t, float(params[index + 1]), x_mm, tol)
            hits.append((float(hit[1]), float(hit[2])))
            found_bracketed_hit = True
        if not found_bracketed_hit and abs(hit_residual) <= tol:
            hits.append((float(hit[1]), float(hit[2])))
    return hits


def _refine_residual_extremum(
    f: Callable[[float], np.ndarray],
    left_t: float,
    center_t: float,
    right_t: float,
    x_mm: float,
    *,
    maximize: bool,
) -> tuple[float, np.ndarray, float]:
    left = left_t
    right = right_t
    center_value = f(center_t)
    center_residual = float(center_value[0] - x_mm)
    best_t = center_t
    best_value = center_value
    best_residual = center_residual
    for _ in range(80):
        left_mid = left + (right - left) / 3.0
        right_mid = right - (right - left) / 3.0
        left_value = f(left_mid)
        right_value = f(right_mid)
        left_residual = float(left_value[0] - x_mm)
        right_residual = float(right_value[0] - x_mm)
        if (maximize and left_residual < right_residual) or (
            not maximize and left_residual > right_residual
        ):
            left = left_mid
        else:
            right = right_mid

        candidate_t = (left + right) / 2.0
        candidate_value = f(candidate_t)
        candidate_residual = float(candidate_value[0] - x_mm)
        if (maximize and candidate_residual > best_residual) or (
            not maximize and candidate_residual < best_residual
        ):
            best_t = candidate_t
            best_value = candidate_value
            best_residual = candidate_residual

    return best_t, best_value, best_residual


def _bisect_hit(
    f: Callable[[float], np.ndarray],
    left_t: float,
    right_t: float,
    x_mm: float,
    tol: float,
) -> np.ndarray:
    left_r = float(f(left_t)[0] - x_mm)
    best = f((left_t + right_t) / 2.0)
    for _ in range(100):
        mid_t = (left_t + right_t) / 2.0
        mid = f(mid_t)
        mid_r = float(mid[0] - x_mm)
        best = mid
        if left_r * mid_r <= 0.0:
            right_t = mid_t
        else:
            left_t = mid_t
            left_r = mid_r
    return best


def _circumarc_hits(
    curve: IrCircumArc3D,
    x_mm: float,
    to_mm: PointToMm,
) -> list[tuple[float, float]]:
    if curve.start is None or curve.intermediate is None or curve.end is None:
        raise GeometryError("IrCircumArc3D is missing defining points")
    start = _point_array(curve.start, to_mm)
    middle = _point_array(curve.intermediate, to_mm)
    end = _point_array(curve.end, to_mm)
    center, radius, normal = _circle_from_three_points(start, middle, end)
    u = _normalize(start - center, "IrCircumArc3D has zero radius")
    v = np.cross(normal, u)

    middle_angle = _angle_on_axes(middle - center, u, v)
    end_angle = _angle_on_axes(end - center, u, v)
    sweep = _arc_sweep_containing_middle(middle_angle, end_angle)

    hits = []
    for theta in _circle_plane_angles(center, radius, u, v, x_mm):
        theta_on_sweep = _equivalent_angle_on_sweep(theta, sweep)
        if theta_on_sweep is not None:
            point = center + radius * (cos(theta_on_sweep) * u + sin(theta_on_sweep) * v)
            hits.append((float(point[1]), float(point[2])))
    return hits


def _circle_hits(
    curve: IrCircle3D,
    x_mm: float,
    to_mm: PointToMm,
) -> list[tuple[float, float]]:
    if curve.center is None or curve.diameter is None or curve.normal is None:
        raise GeometryError("IrCircle3D is missing center, diameter, or normal")
    center = _point_array(curve.center, to_mm)
    diameter = _quantity_length_mm(curve.diameter, to_mm)
    if diameter <= 0.0:
        raise GeometryError("IrCircle3D diameter must be positive")
    normal = _normalize(
        np.array([curve.normal.x, curve.normal.y, curve.normal.z], dtype=float),
        "IrCircle3D normal has zero length",
    )
    ref = np.array([1.0, 0.0, 0.0]) if abs(normal[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    u = _normalize(np.cross(normal, ref), "IrCircle3D normal cannot define a plane")
    v = np.cross(normal, u)
    radius = diameter / 2.0

    hits = []
    for theta in _circle_plane_angles(center, radius, u, v, x_mm):
        point = center + radius * (cos(theta) * u + sin(theta) * v)
        hits.append((float(point[1]), float(point[2])))
    return hits


def _circle_plane_angles(
    center: np.ndarray,
    radius: float,
    u: np.ndarray,
    v: np.ndarray,
    x_mm: float,
) -> list[float]:
    a = float(radius * u[0])
    b = float(radius * v[0])
    c = float(center[0] - x_mm)
    amplitude = (a * a + b * b) ** 0.5
    if amplitude < _PLANE_EPS:
        return []
    value = -c / amplitude
    if value < -1.0 - _PLANE_EPS or value > 1.0 + _PLANE_EPS:
        return []
    value = max(-1.0, min(1.0, value))
    phase = atan2(b, a)
    delta = float(np.arccos(value))
    angles = [(phase + delta) % (2.0 * pi)]
    if delta > _PLANE_EPS and abs(delta - pi) > _PLANE_EPS:
        angles.append((phase - delta) % (2.0 * pi))
    return angles


def _circle_from_three_points(
    a: np.ndarray,
    b: np.ndarray,
    c: np.ndarray,
) -> tuple[np.ndarray, float, np.ndarray]:
    ab = b - a
    ac = c - a
    normal_raw = np.cross(ab, ac)
    normal_norm_sq = float(np.dot(normal_raw, normal_raw))
    if normal_norm_sq < _PLANE_EPS:
        raise GeometryError("Circle defining points are collinear")
    center = a + (
        float(np.dot(ac, ac)) * np.cross(normal_raw, ab)
        + float(np.dot(ab, ab)) * np.cross(ac, normal_raw)
    ) / (2.0 * normal_norm_sq)
    radius = float(np.linalg.norm(a - center))
    if radius < _PLANE_EPS:
        raise GeometryError("Circle radius is zero")
    return center, radius, normal_raw / np.sqrt(normal_norm_sq)


def _arc_sweep_containing_middle(middle_angle: float, end_angle: float) -> float:
    middle = middle_angle % (2.0 * pi)
    end = end_angle % (2.0 * pi)
    if middle <= end:
        return end
    return end - 2.0 * pi


def _equivalent_angle_on_sweep(theta: float, sweep: float) -> float | None:
    candidates = [theta - 2.0 * pi, theta, theta + 2.0 * pi]
    if sweep >= 0.0:
        matches = [candidate for candidate in candidates if -_PLANE_EPS <= candidate <= sweep + _PLANE_EPS]
    else:
        matches = [candidate for candidate in candidates if sweep - _PLANE_EPS <= candidate <= _PLANE_EPS]
    if not matches:
        return None
    return min(matches, key=abs)


def _angle_on_axes(vector: np.ndarray, u: np.ndarray, v: np.ndarray) -> float:
    return atan2(float(np.dot(vector, v)), float(np.dot(vector, u)))


def _quantity_length_mm(qty: Quantity, to_mm: PointToMm) -> float:
    origin = IrPoint3D(0.0, 0.0, 0.0, qty.unit)
    unit_x = IrPoint3D(1.0, 0.0, 0.0, qty.unit)
    scale = _point_array(unit_x, to_mm)[0] - _point_array(origin, to_mm)[0]
    return float(qty.value * scale)


def _point_array(point: IrPoint3D, to_mm: PointToMm) -> np.ndarray:
    return np.asarray(to_mm(point), dtype=float)


def _normalize(vector: np.ndarray, error_message: str) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if norm < _PLANE_EPS:
        raise GeometryError(error_message)
    return vector / norm
