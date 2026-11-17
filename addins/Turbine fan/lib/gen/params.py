"""Turbine fan inputs, derived dimensions and the placement frame.

Own copy of decad-gallery models/turbinefan params.go (Params, Dimensions) and of the placement rules of the other
add-ins (a point and an axis instead of an r3.Frame).
"""

from __future__ import annotations

import dataclasses
import math

from .constants import (
    BLADE_COUNT,
    CLUTCH_SEAM,
    CLUTCH_TURN,
    DEFAULT_BLADE_PITCH,
    DEFAULT_ROTOR_DIAMETER,
    EAR_ANGLES_DEGREES,
    FACE_CIRCLE,
    FACE_LENGTH,
    FACE_NUT_DEPTH,
    FIRST_BLADE_ANGLE,
    LEFT_HAND,
    MOUNT_Z,
    RIGHT_HAND,
    SHAFT_MOUNT,
    ADAPTER_THICKNESS,
    CLUTCH_MOUNT,
)
from .clutch.params import COUNTER_CLOCKWISE, Params as ClutchParams, lookup_shaft
from .fasteners import Site
from .size import Size

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
    in the dialog (docs/turbinefan/deviations.md). U is a stable unit vector perpendicular to the axis (Y x axis, or
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
class Params:
    """Fan inputs in mm and radians. Field order and defaults are the gallery's Params605ZZ."""

    shaft_diameter: float = 5.0  # ballbearing.Params605ZZ().BoreDiameter
    flat_depth: float = 0.5
    bore_clearance: float = 0.05  # ballbearing.PressFitClearance
    rotor_diameter: float = DEFAULT_ROTOR_DIAMETER  # across the blade tips, 128 to 224 mm; it sets every size
    blade_pitch: float = DEFAULT_BLADE_PITCH  # the blade angle at 75 % of the tip radius
    hand: int = RIGHT_HAND
    mount: int = SHAFT_MOUNT
    # In a clutch mount the placement is the clutch's: the fan sits on it through mount_frame.
    placement: Frame | None = None
    # The clutch the clutch mount builds beside the fan; None in a shaft mount. Its own placement and adapter fields
    # are not used: the build sets them (placement above, adapter always on). docs/turbinefan/deviations.md.
    clutch: ClutchParams | None = None
    # Directive: add-in option, off by default, not a gallery input: add the sacrificial bridge layers of the hub and,
    # in a clutch mount, of the clutch's back plate, cover and adapter ring (bridge.py, clutch/bridge.py;
    # docs/turbinefan/directives.md). The blades, bolts and nuts get none.
    sacrificial_bridging: bool = False


def default_params() -> Params:
    return Params()


def hand_for_freewheel(freewheel: str) -> int:
    """The hand that the clutch's Freewheel drives forward [ParamsForClutch]: counter-clockwise gives the left hand."""
    return LEFT_HAND if freewheel == COUNTER_CLOCKWISE else RIGHT_HAND


def params_for_clutch(
    c: ClutchParams, blade_pitch: float = DEFAULT_BLADE_PITCH, placement: Frame | None = None,
    rotor_diameter: float = DEFAULT_ROTOR_DIAMETER,
) -> Params:
    """A clutch-mount fan matched to the clutch c [ParamsForClutch]: c's shaft diameter and flat, the hand that c's
    Freewheel drives forward, the press-fit bore clearance, and c as the clutch to build.

    The pitch and the rotor diameter are the dialog's, as with the gallery's WithBladePitch and WithRotorDiameter.
    # Deviation: the placement is the clutch's own frame, not MountFrame(c.Placement) (docs/turbinefan/deviations.md).
    An unknown shaft name keeps the default shaft so the clutch's own validation
    reports it."""
    shaft = lookup_shaft(c.shaft)
    kwargs: dict = {}
    if shaft is not None:
        kwargs = {"shaft_diameter": shaft.diameter, "flat_depth": shaft.flat_depth}
    return Params(rotor_diameter=rotor_diameter, blade_pitch=blade_pitch, hand=hand_for_freewheel(c.freewheel),
                  mount=CLUTCH_MOUNT,
                  placement=placement, clutch=dataclasses.replace(c, placement=None, adapter=True),
                  sacrificial_bridging=c.sacrificial_bridging, **kwargs)


def point_at(frame: Frame | None, back: float) -> Frame:
    """`frame` (None: the world frame) moved `back` mm backwards along its own Z, so the selected point lands on the
    face that lies `back` mm ahead of the returned frame's origin.

    The selected point is the hub's front face in a shaft mount (back = Size.hub_length) and where the clutch cover ends,
    its outer face, in a clutch mount (back = COVER_TO, 18.5): the gallery's placement point (`buildFrame`,
    `ClutchAnchorZ`), here applied to the selected frame (docs/turbinefan/directives.md)."""
    o, _, _, z = frame_axes(frame if frame is not None else Frame())
    return Frame((o[0] - back * z[0], o[1] - back * z[1], o[2] - back * z[2]),
                 (frame or Frame()).u, (frame or Frame()).v)


def mount_frame(clutch: Frame | None) -> Frame:
    """The placement that seats a clutch-mount fan on a clutch placed at `clutch` (None: the clutch's local frame)
    [MountFrame]: the fan frame is the clutch frame moved to z = MOUNT_Z and turned CLUTCH_TURN about Z. The gallery's
    MountFrame returns the placement point (clutch z COVER_TO, same turn) and its buildFrame moves back by
    ClutchAnchorZ = COVER_TO - MOUNT_Z = -7.75, which lands on the same fan frame."""
    s, c = math.sin(CLUTCH_TURN), math.cos(CLUTCH_TURN)
    local = Frame((0.0, 0.0, MOUNT_Z), (c, s, 0.0), (-s, c, 0.0))
    if clutch is None:
        return local
    o, x, y, z = frame_axes(clutch)

    def rot(v: Vec3) -> Vec3:
        return (x[0] * v[0] + y[0] * v[1] + z[0] * v[2], x[1] * v[0] + y[1] * v[1] + z[1] * v[2],
                x[2] * v[0] + y[2] * v[1] + z[2] * v[2])

    r = rot(local.origin)
    return Frame((o[0] + r[0], o[1] + r[1], o[2] + r[2]), rot(local.u), rot(local.v))


def params_605zz() -> Params:
    return Params()


def params_608zz() -> Params:
    """The 8 mm shaft of a 608ZZ bearing with a 0.75 mm flat."""
    return Params(shaft_diameter=8.0, flat_depth=0.75)


def blade_angle(k: int) -> float:
    """Angle about +Z from +X of blade k's radial line, k = 1, 2, 3: 90, 210 and 330 degrees."""
    return FIRST_BLADE_ANGLE + 2 * math.pi * (k - 1) / BLADE_COUNT


def ear_bolt_angle(k: int) -> float:
    """Angle about +Z from +X, in the fan frame, of ear bolt k, k = 1, 2, 3: 270, 30 and 150 degrees.
    The hub's two adapter holes lie at ear bolts 2 and 3; ear bolt 1 (270) has no hole [EarBoltAngle]."""
    return (math.radians(EAR_ANGLES_DEGREES[k - 1]) - CLUTCH_TURN) % (2 * math.pi)


@dataclasses.dataclass(frozen=True)
class Dimensions:
    """Values derived from Params, in the local frame [params.go Dimensions]. rho is a distance from the shaft axis
    along -Y."""

    size: Size  # the hub, blade and blade joint dimensions that follow the rotor diameter
    set_screw_bolt: float  # the set screw's M2 length: the longest whose head stays inside the round face
    bore_radius: float  # r_b
    bore_flat: float  # f_b: the bore's flat lies at y = -f_b
    bore_flat_width: float  # w_b
    bore_loop: float  # length of the bore's outline in the back face
    shaft_flat_width: float  # w_s
    set_screw_tip: float  # rho_t
    set_screw_head: float  # rho_h: the head's top face
    counterbore_floor: float  # rho_f
    set_screw_site: Site
    blade_sites: tuple[Site, Site, Site]  # head flush with the front face at size.blade_bolt_at along blade k's line, -Z
    adapter_sites: tuple[Site, Site]  # the clutch mount's bolts at 30 and 150 degrees, run along +Z


def blade_site(k: int, size: Size) -> Site:
    a = blade_angle(k)
    u = (math.cos(a), math.sin(a), 0.0)
    return Site(head=(size.blade_bolt_at * u[0], size.blade_bolt_at * u[1], size.hub_length), dir=(0.0, 0.0, -1.0),
                corner=u, length=size.blade_bolt_length, cavity=size.blade_bolt_cavity)


def adapter_site(k: int) -> Site:
    """Adapter bolt k (1 or 2): the head's top face lies on the adapter's rear face, one adapter thickness and one
    seam behind the hub's back face.

    The hub holes stay at fan angles 30 and 150: the ear bolts k + 1 (the gallery's AdapterSites[k-1] uses
    EarBoltAngle(k + 1)). With the turn of 180 degrees they lie on the clutch's face holes 2 and 3 (clutch angles 210
    and 330); hole 1 (clutch angle 90) stays empty."""
    a = ear_bolt_angle(k + 1)
    u = (math.cos(a), math.sin(a), 0.0)
    return Site(head=(FACE_CIRCLE * u[0], FACE_CIRCLE * u[1], -(ADAPTER_THICKNESS + CLUTCH_SEAM)),
                dir=(0.0, 0.0, 1.0), corner=u, length=FACE_LENGTH,
                cavity=ADAPTER_THICKNESS + CLUTCH_SEAM + FACE_NUT_DEPTH)


def hand_name(hand: int) -> str:
    return "Left hand" if hand == LEFT_HAND else "Right hand"
