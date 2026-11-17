"""One-way clutch inputs, derived dimensions and the placement frame.

Own copy of decad-gallery models/onewayclutch params.go (Params, Shaft, Dimensions) and of the placement rules of the
other add-ins (a point and an axis instead of an r3.Frame).
"""

from __future__ import annotations

import dataclasses
import math

from .constants import (
    ADAPTER_FROM,
    BOLT_ANGLES,
    BOLT_LENGTH,
    COVER_TO,
    EAR_ANGLES,
    FACE_CIRCLE,
    FACE_LENGTH,
    FACE_NUT_DEPTH,
    ADAPTER_THICKNESS,
    MOUNT_LENGTH,
    ADAPTER_TO,
    RING_FROM,
    SEAM,
)
from .fasteners import NUT_CAVITY_HEIGHT, Site

Vec3 = tuple[float, float, float]


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

    # Deviation: the gallery takes an r3.Frame (origin, u, v); the add-in takes a point and an axis direction chosen
    in the dialog (docs/onewayclutch/deviations.md). U is a stable unit vector perpendicular to the axis (Y x axis, or
    Z x axis when the axis is nearly along Y) and V = axis x U, so frame_axes gives back z = axis and +Z gives the
    identity frame. Returns None when both are None. Raises ValueError with a dialog message when the axis is zero
    or not finite.
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
class Shaft:
    """A preset D-flat shaft: its diameter and the depth of its flat below the round."""

    name: str
    diameter: float
    flat_depth: float


# params.go shafts(): the diameters are ballbearing.Lookup(bearing).ShaftDiameter() of the 605ZZ and the 608ZZ.
SHAFTS: tuple[Shaft, ...] = (
    Shaft("605ZZ", 5.0, 0.5),
    Shaft("608ZZ", 8.0, 0.75),
    Shaft("608ZZ-gearbox", 8.0, 0.5),
)

CLOCKWISE = "Clockwise"
COUNTER_CLOCKWISE = "CounterClockwise"
DIRECTIONS: tuple[str, ...] = (CLOCKWISE, COUNTER_CLOCKWISE)


def lookup_shaft(name: str) -> Shaft | None:
    for s in SHAFTS:
        if s.name == name:
            return s
    return None


def direction_sign(direction: str) -> float:
    """-1 for Clockwise, +1 for CounterClockwise, 0 for anything else [Direction.Sign]."""
    return {CLOCKWISE: -1.0, COUNTER_CLOCKWISE: 1.0}.get(direction, 0.0)


@dataclasses.dataclass(frozen=True)
class Params:
    """Clutch inputs. Field order and defaults are the gallery's DefaultParams."""

    shaft: str = "605ZZ"
    freewheel: str = CLOCKWISE  # the direction the ring turns freely, seen from the cover
    bore_clearance: float = 0.05  # ballbearing.PressFitClearance: radial, on the round and on the flat
    placement: Frame | None = None
    # Add-in option, off by default, not a gallery input: also build the standard adapter ring (BuildAdapter) with its
    # three M2 x 25 bolts and nuts (docs/onewayclutch/deviations.md).
    adapter: bool = False
    # Add-in option, off by default, not a gallery input: add the sacrificial bridge layers of the back plate, the
    # cover and the adapter ring (lib/gen/bridge.py; directive in docs/onewayclutch/directives.md).
    sacrificial_bridging: bool = False


def default_params() -> Params:
    return Params()


Vec2 = tuple[float, float]


@dataclasses.dataclass(frozen=True)
class Dimensions:
    """Values derived from Params, in mm, in the local frame [params.go Dimensions].

    The pawl values are in the counter-clockwise layout of pawl 0, before the direction's mirror."""

    shaft: Shaft
    sign: float
    bore_radius: float  # r_b
    bore_flat: float  # f_b: distance from the axis to the bore's flat, on the +Y side
    bore_loop: float  # length of the bore's outline: its arc the long way round plus its flat
    sites: tuple[Site, Site, Site]  # the three clutch bolts
    mount_sites: tuple[Site, Site, Site]  # the three adapter bolts, one per ear
    face_sites: tuple[Site, Site, Site]  # the three face bolts' head pockets in the adapter's rear face
    apex: Vec2  # A: where the head's lock line meets its flank line
    tip_center: Vec2  # centre of the head's tip round
    head_reach: float  # outermost head radius
    head_travel: float  # head_reach - tooth_tip
    flank_end: Vec2  # H_f: flank meets the arm outer arc
    lock_end: Vec2  # H_l: lock line meets the arm inner arc
    ramp_angle: float  # direction of the ring ramp, and of the flank, in degrees
    flank_distance: float  # distance of the flank line from the axis
    ramp_distance: float  # distance of the ring ramp line from the axis
    ramp_normal: Vec2  # unit normal of the ramp, pointing away from the axis
    # Radii, in mm. They grow with the shaft's bore radius (validate.derive_radii).
    core_radius: float  # hub core R_c
    bolt_circle: float  # radius of the bolt holes' centres
    slot_width: float  # slot under each arm s
    arm_inner: float  # core_radius + slot_width
    arm_outer: float  # arm_inner + ARM_THICKNESS
    tooth_tip: float  # ring tooth tip radius R_tip: arm_outer + LOOSE_FIT
    tooth_root: float  # ring tooth root radius R_root
    ring_counter: float  # ring counterbore radius
    ring_outer: float  # ring outside radius
    ear_circle: float  # radius of the ear bores' centres
    ear_reach: float  # radius of the ear tips
    plate_radius: float  # plate radius
    boss_radius: float  # plates' boss reference radius
    adapter_radius: float  # adapter outside radius, equal to ear_reach
    adapter_inner: float  # adapter bore radius
    hub_chamfer: float  # the hub's face chamfer
    growth: float  # tooth_tip minus its value at the least core and slot


def polar(r: float, deg: float) -> Vec2:
    a = math.radians(deg)
    return (r * math.cos(a), r * math.sin(a))


def make_sites(
    bolt_circle: float, ear_circle: float
) -> tuple[tuple[Site, Site, Site], tuple[Site, Site, Site], tuple[Site, Site, Site]]:
    """(bolt sites, mount sites, face sites) in the local frame [params.go Derive], for the derived bolt and ear
    circles."""
    sites: list[Site] = []
    for a in BOLT_ANGLES:
        x, y = polar(bolt_circle, a)
        cx, cy = polar(1.0, a + 30)  # a flat of the nut pocket faces the bore
        sites.append(Site(head=(x, y, COVER_TO), dir=(0.0, 0.0, -1.0), corner=(cx, cy, 0.0), length=BOLT_LENGTH,
                          cavity=COVER_TO - NUT_CAVITY_HEIGHT))
    mounts: list[Site] = []
    for a in EAR_ANGLES:
        x, y = polar(ear_circle, a)
        cx, cy = polar(1.0, a + 30)  # a flat of the nut pocket faces the axis
        mounts.append(Site(head=(x, y, ADAPTER_TO), dir=(0.0, 0.0, -1.0), corner=(cx, cy, 0.0), length=MOUNT_LENGTH,
                           cavity=ADAPTER_TO - RING_FROM - NUT_CAVITY_HEIGHT))
    faces: list[Site] = []
    for a in EAR_ANGLES:
        x, y = polar(FACE_CIRCLE, a)
        cx, cy = polar(1.0, a)
        faces.append(Site(head=(x, y, ADAPTER_FROM), dir=(0.0, 0.0, 1.0), corner=(cx, cy, 0.0), length=FACE_LENGTH,
                          cavity=ADAPTER_THICKNESS + SEAM + FACE_NUT_DEPTH))
    return (sites[0], sites[1], sites[2]), (mounts[0], mounts[1], mounts[2]), (faces[0], faces[1], faces[2])
