"""Gearbox inputs, defaults and placement frame.

Own copy of decad-gallery models/planetarygearbox params.go (DefaultParams, Ratio, constants) and the validity
and axes rules of r3 NewFrame, and params.go clearance constants (a800069), plus EarCount and EarBoreDiameter (44d180a).
"""

from __future__ import annotations

import dataclasses
import math

from .bearing import PRESS_FIT_CLEARANCE, SEAT_CLEARANCE  # noqa: F401  (re-exported: gallery params.go seatClearance)

Vec3 = tuple[float, float, float]

LIP_WIDTH = 2.0
LIP_THICKNESS = 1.0
COLLAR_CLEARANCE = 0.5
BOLT_RIM_MARGIN = 1.5
ARM_MARGIN = 1.0
COLLAR_MARGIN = 1.2
COVER_SPOKES = 3
RING_MARGIN = 1.0
TOOL_MARGIN = 1.0
GEAR_ROOT_MODULE_CLEARANCE_FACTOR = 0.25
LOOSE_GEAR_CLEARANCE = 0.5
GEAR_ROOT_MEASUREMENT_MARGIN = 0.02
FIT_CLEARANCE = 0.25
PLANET_BEARING_LIFT = FIT_CLEARANCE
# params.go collarBearingGap: the Tight gap between the input shaft's collar and the front bearing's inner face.
COLLAR_BEARING_GAP = FIT_CLEARANCE
PIN_SHOULDER_CLEARANCE = FIT_CLEARANCE  # params.go pinShoulderClearance: pin's thick part above the bearing's race
PIN_SHOULDER_REACH = FIT_CLEARANCE  # params.go pinShoulderReach: shortest thick part below the plate
STEP_OVERLAP = 0.05  # params.go stepOverlap: how far a thin rod reaches into its thick part
MIN_SOCKET_WALL = 1.0  # params.go minSocketWall: plate kept around a pin socket at mid-plate
MIN_SOCKET_FACE_WALL = 0.5  # params.go minSocketFaceWall: plate kept between a socket and the chamfered outline
MIN_EDGE_CHAMFER = 0.5  # [edgefinish.go MinEdgeChamfer]


def gear_root_clearance(module: float) -> float:
    """Root-to-tip clearance c = max(0.25 m, 0.5)."""
    return max(GEAR_ROOT_MODULE_CLEARANCE_FACTOR * module, LOOSE_GEAR_CLEARANCE)


def gear_root_depth(module: float) -> float:
    """Depth of the root below the pitch circle: m + c."""
    return module + gear_root_clearance(module)


@dataclasses.dataclass(frozen=True)
class Frame:
    origin: Vec3 = (0.0, 0.0, 0.0)
    u: Vec3 = (1.0, 0.0, 0.0)
    v: Vec3 = (0.0, 1.0, 0.0)


def _norm(a: Vec3) -> float:
    return math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def frame_is_valid(f: Frame) -> bool:
    """Port of r3 NewFrame validity: finite numbers, nonzero u and v, not collinear."""
    nums = f.origin + f.u + f.v
    if not all(math.isfinite(n) for n in nums):
        return False
    nu, nv = _norm(f.u), _norm(f.v)
    if nu == 0 or nv == 0:
        return False
    return _norm(_cross(f.u, f.v)) > 1e-12 * nu * nv


def frame_axes(f: Frame) -> tuple[Vec3, Vec3, Vec3, Vec3]:
    """Return (origin, x, y, z) of the orthonormalized frame. Raises ValueError when f is invalid."""
    if not frame_is_valid(f):
        raise ValueError("invalid placement frame")
    nu = _norm(f.u)
    x: Vec3 = (f.u[0] / nu, f.u[1] / nu, f.u[2] / nu)
    k = _dot(f.v, x)
    w: Vec3 = (f.v[0] - k * x[0], f.v[1] - k * x[1], f.v[2] - k * x[2])
    nw = _norm(w)
    y: Vec3 = (w[0] / nw, w[1] / nw, w[2] / nw)
    return (f.origin, x, y, _cross(x, y))


def placement_frame(origin: Vec3 | None, axis: Vec3 | None) -> Frame | None:
    """Frame whose origin is `origin` (world origin when None) and whose Z axis is `axis` (+Z when None).

    Deviation from decad-gallery: the gallery takes an r3.Frame (origin, u, v); the add-in takes a point and an axis
    direction chosen in the dialog. U is a stable unit vector perpendicular to the axis (Y x axis, or Z x axis when the
    axis is nearly along Y) and V = axis x U, so frame_axes gives back z = axis and +Z gives the identity frame.
    Returns None when both are None. Raises ValueError with a dialog message when the axis is zero or not finite.
    """
    if origin is None and axis is None:
        return None
    o = origin if origin is not None else (0.0, 0.0, 0.0)
    a = axis if axis is not None else (0.0, 0.0, 1.0)
    if not all(math.isfinite(n) for n in o):
        raise ValueError("placement origin must be a finite point")
    if not all(math.isfinite(n) for n in a) or _norm(a) < 1e-9:
        raise ValueError("placement axis must be a nonzero direction")
    n = _norm(a)
    z: Vec3 = (a[0] / n, a[1] / n, a[2] / n)
    ref: Vec3 = (0.0, 1.0, 0.0) if abs(z[1]) < 0.9 else (0.0, 0.0, 1.0)
    u = _cross(ref, z)
    nu = _norm(u)
    u = (u[0] / nu, u[1] / nu, u[2] / nu)
    return Frame(o, u, _cross(z, u))


@dataclasses.dataclass(frozen=True)
class Params:
    """Gearbox inputs. Field order and defaults are the gallery's DefaultParams. Lengths mm, angles rad."""

    module: float = 1.0
    pressure_angle: float = 20 * math.pi / 180
    sun_teeth: int = 13
    planet_teeth: int = 29
    ring_teeth: int = 71
    planet_count: int = 3
    stages: int = 1
    samples: int = 15
    gear_thickness: float = 8.0
    carrier_thickness: float = 3.0
    stage_gap: float = 1.0
    cover_thickness: float = 3.0
    bolt_hole_diameter: float = 2.6
    flat_depth: float = 0.5
    seat_chamfer: float = 0.5
    edge_chamfer: float = MIN_EDGE_CHAMFER
    input_shaft_length: float = 12.0
    bearing_clearance: float = SEAT_CLEARANCE
    # Catalog names of the planet and shaft bearings [params.go PlanetBearing, ShaftBearing].
    planet_bearing: str = "605ZZ"
    shaft_bearing: str = "605ZZ"
    carrier_wall: float = 3.0
    ring_wall: float = 7.1
    backlash: float = 0.15
    output_shaft_length: float = 12.0
    ear_count: int = 3
    ear_bore_diameter: float = 4.0
    # Add-in option, not a gallery input (docs/planetarygearbox/directives.md): cut every carrier pin and shaft in two along the
    # plane through its axis that is parallel to the D flat.
    split_pins_shafts: bool = False
    # Add-in option, not a gallery input: add the ring's sacrificial bridge layers (lib/gen/bridge.py).
    sacrificial_bridging: bool = False
    placement: Frame | None = None


def default_params() -> Params:
    return Params()


def ratio(p: Params) -> float:
    """Reduction from the first sun to the last carrier with the ring held fixed."""
    return (1 + p.ring_teeth / p.sun_teeth) ** p.stages
