"""Escapement layout: every derived value and point of the design.

Own copy of decad-gallery models/escapement layout.go (Layout, layoutEscapement) at e11a188. Anchor and crutch points
are relative to the pallet arbor, pendulum points relative to the suspension, the others in the model frame.
"""

from __future__ import annotations

import dataclasses
import math

from .constants import (
    ARM_WIDTH, BACK_ANGLE, BUILD_BACKOFF, CRUTCH_LENGTH, DEG, DRUM_OFFSET, GEAR_ROOT_MARGIN, GEAR_TIP_MARGIN,
    GREAT_TEETH, HUB_RADIUS, MODULE, OVERLAP, PALLET_LENGTH, PALLET_SPAN, PALLET_WIDTH, PINION_TEETH, RAKE,
    ROOT_RADIUS, SPRING_FULL_TURNS, SPRING_MIN_TORQUE, SPRING_YOUNG, SUSPENSION_OFFSET, TEETH, TIP_RADIUS,
)
from .params import Params, default_params
from .spring import SpringDims, derive, spring_params
from .validate import validate

Pt = tuple[float, float]


def angle_of(p: Pt) -> float:
    return math.atan2(p[1], p[0])


def sub(p: Pt, q: Pt) -> Pt:
    return (p[0] - q[0], p[1] - q[1])


def add(p: Pt, q: Pt) -> Pt:
    return (p[0] + q[0], p[1] + q[1])


def rot(p: Pt, a: float) -> Pt:
    s, c = math.sin(a), math.cos(a)
    return (c * p[0] - s * p[1], s * p[0] + c * p[1])


def polar(r: float, a: float) -> Pt:
    return (r * math.cos(a), r * math.sin(a))


def _scale(p: Pt, k: float) -> Pt:
    return (p[0] * k, p[1] * k)


@dataclasses.dataclass(frozen=True)
class Geometry:
    params: Params
    # pitch = tau, half_span = theta, centre_distance = d, tangent_radius = rm.
    pitch: float
    half_span: float
    centre_distance: float
    tangent_radius: float
    r_in: float
    r_out: float
    axis_o: Pt
    axis_p: Pt
    axis_s: Pt
    axis_g: Pt
    il: Pt
    fl: Pt
    ir: Pt
    fr: Pt
    psi_eu: float
    psi_ef: float
    psi_xu: float
    psi_xf: float
    ce: Pt
    fe: Pt
    cx: Pt
    fx: Pt
    top_e: float
    top_x: float
    ge: Pt
    he: Pt
    ke: Pt
    me: Pt
    ne: Pt
    gx: Pt
    hx: Pt
    kx: Pt
    mx: Pt
    nx: Pt
    s0: float
    tooth_tip: Pt
    tooth_l: Pt
    tooth_b: Pt
    crutch_ar: Pt
    crutch_al: Pt
    crutch_bl: Pt
    crutch_br: Pt
    pend_er: Pt
    pend_el: Pt
    pend_ql: Pt
    pend_qr: Pt
    pinion_pitch_r: float
    great_pitch_r: float
    pinion_root: float
    pinion_tip: float
    great_root: float
    great_tip: float
    gear_centre: float
    pinion_phase: float
    great_phase: float
    wheel_phase_e: float
    wheel_phase_x: float
    drop: float
    tip_to_root_a: float
    tip_to_root_b: float
    pendulum_period: float
    spring: SpringDims
    spring_turn: float
    carrier_offset: float
    spring_anchor: Pt
    spring_rate: float
    full_wind_torque: float
    full_wind_strain: float
    run_turns: float


def _tip(centre_distance: float, r: float, left: bool) -> Pt:
    """Where the tip circle meets the circle of radius r about P, on the left (entry) or right side."""
    d = centre_distance
    y = (TIP_RADIUS * TIP_RADIUS - r * r + d * d) / (2 * d)
    x = math.sqrt(TIP_RADIUS * TIP_RADIUS - y * y)
    return (-x if left else x, y)


def _tooth_foot(angle: float) -> Pt:
    """Foot of the tooth face that leans by angle from the inward radial at the tip (0, R), on r = Rr - Overlap."""
    dx, dy = -math.sin(angle), -math.cos(angle)
    rf = ROOT_RADIUS - OVERLAP
    b = TIP_RADIUS * dy
    s = -b - math.sqrt(b * b - (TIP_RADIUS * TIP_RADIUS - rf * rf))
    return (s * dx, TIP_RADIUS + s * dy)


def _escapement(p: Params) -> dict:
    """Everything but the mainspring (layoutEscapement). Raises ValidationError."""
    validate(p)
    v: dict = {"params": p}
    v["pitch"] = pitch = 2 * math.pi / TEETH
    v["half_span"] = half = PALLET_SPAN * pitch / 2
    v["centre_distance"] = d = TIP_RADIUS / math.cos(half)
    v["tangent_radius"] = rm = TIP_RADIUS * math.tan(half)
    v["r_in"] = r_in = rm - PALLET_WIDTH / 2
    v["r_out"] = r_out = rm + PALLET_WIDTH / 2
    v["axis_o"] = (0.0, 0.0)
    v["axis_p"] = pp = (0.0, d)
    v["axis_s"] = (0.0, d + SUSPENSION_OFFSET)
    v["axis_g"] = polar(MODULE * (PINION_TEETH + GREAT_TEETH) / 2, -90 * DEG)

    v["il"] = il = _tip(d, r_out, True)
    v["fl"] = fl = _tip(d, r_in, True)
    v["ir"] = ir = _tip(d, r_in, False)
    v["fr"] = fr = _tip(d, r_out, False)

    lam, kap = p.lift_angle, p.lock_angle
    v["psi_eu"], v["psi_ef"] = -(lam - kap) / 2, (lam + kap) / 2
    v["psi_xu"], v["psi_xf"] = (lam - kap) / 2, -(lam + kap) / 2

    v["ce"] = ce = rot(sub(il, pp), v["psi_eu"])
    v["fe"] = rot(sub(fl, pp), v["psi_ef"])
    v["cx"] = cx = rot(sub(ir, pp), v["psi_xu"])
    v["fx"] = rot(sub(fr, pp), v["psi_xf"])
    v["top_e"] = top_e = angle_of(ce) - PALLET_LENGTH
    v["top_x"] = top_x = angle_of(cx) + PALLET_LENGTH

    v["s0"] = s0 = math.sqrt(HUB_RADIUS * HUB_RADIUS - ARM_WIDTH * ARM_WIDTH)
    ue, ne_ = polar(1, top_e), polar(1, top_e - 90 * DEG)
    ux, nx_ = polar(1, top_x), polar(1, top_x + 90 * DEG)
    v["ge"], v["he"], v["ke"] = _scale(ue, r_in), _scale(ue, HUB_RADIUS), _scale(ue, r_out)
    v["me"] = add(v["ke"], _scale(ne_, ARM_WIDTH))
    v["ne"] = add(_scale(ue, s0), _scale(ne_, ARM_WIDTH))
    v["gx"], v["hx"], v["kx"] = _scale(ux, r_in), _scale(ux, HUB_RADIUS), _scale(ux, r_out)
    v["mx"] = add(v["kx"], _scale(nx_, ARM_WIDTH))
    v["nx"] = add(_scale(ux, s0), _scale(nx_, ARM_WIDTH))

    v["tooth_tip"] = (0.0, TIP_RADIUS)
    v["tooth_l"] = _tooth_foot(RAKE)
    v["tooth_b"] = _tooth_foot(BACK_ANGLE)

    # Crutch (origin P): hub r 6, arm half width 2.5, end circle r 4 at (0, -45).
    v["crutch_ar"] = ar = (2.5, -math.sqrt(36 - 2.5 * 2.5))
    v["crutch_al"] = (-2.5, ar[1])
    v["crutch_bl"] = bl = (-2.5, -CRUTCH_LENGTH + math.sqrt(16 - 2.5 * 2.5))
    v["crutch_br"] = (2.5, bl[1])
    # Pendulum (origin S): eye r 10, rod half width 4, bob r 25 at (0, -Lp).
    v["pend_er"] = er = (4.0, -math.sqrt(100 - 16))
    v["pend_el"] = (-4.0, er[1])
    v["pend_ql"] = ql = (-4.0, -p.pendulum_length + math.sqrt(625 - 16))
    v["pend_qr"] = (4.0, ql[1])

    v["pinion_pitch_r"] = pr = MODULE * PINION_TEETH / 2
    v["great_pitch_r"] = gr = MODULE * GREAT_TEETH / 2
    v["gear_centre"] = gc = pr + gr
    clearance = max(0.25 * MODULE, 0.5)
    v["pinion_root"] = pr - MODULE - clearance - GEAR_ROOT_MARGIN
    v["pinion_tip"] = pr + MODULE - GEAR_TIP_MARGIN
    v["great_root"] = gr - MODULE - clearance - GEAR_ROOT_MARGIN
    v["great_tip"] = gr + MODULE - GEAR_TIP_MARGIN
    v["tip_to_root_a"] = gc - v["pinion_tip"] - v["great_root"]
    v["tip_to_root_b"] = gc - v["great_tip"] - v["pinion_root"]
    v["pinion_phase"] = -90 * DEG
    v["great_phase"] = 90 * DEG + math.pi / GREAT_TEETH

    v["wheel_phase_e"] = pe = math.fmod(math.fmod(90 * DEG - angle_of(il), pitch) + pitch, pitch)
    v["wheel_phase_x"] = pe + pitch / 2
    v["drop"] = pitch / 2 - (angle_of(il) - angle_of(fl))
    v["pendulum_period"] = 2 * math.pi * math.sqrt(p.pendulum_length / 9810)
    if math.isnan(v["ce"][0]):
        raise ValueError("layout produced a nonfinite corner")
    return v


def layout(p: Params) -> Geometry:
    """Compute the geometry of the movement for p. Raises ValidationError."""
    from .motion import state_at  # motion needs Geometry, so import here to avoid a cycle

    v = _escapement(p)
    sp = spring_params()
    dims = derive(sp)
    v["spring"] = dims
    eye = math.atan2(dims.eye_center_y, dims.eye_center_x)
    v["spring_turn"] = turn = -math.pi / 2 - eye
    gx, gy = v["axis_g"]
    v["spring_anchor"] = (gx, gy - math.hypot(dims.eye_center_x, dims.eye_center_y))
    # The arbor's flat meets the spring's bore flat at the default phase. There the old drum pose is the great wheel's
    # angle plus DRUM_OFFSET, and the carrier's bore flat is turned from it by carrier_offset.
    dp = default_params()
    gd = Geometry(**_escapement(dp), spring=dims, spring_turn=turn, carrier_offset=0.0, spring_anchor=(0.0, 0.0),
                  spring_rate=0.0, full_wind_torque=0.0, full_wind_strain=0.0, run_turns=0.0)
    sd = state_at(gd, dp.phase)
    old = gd.great_phase + (sd.wheel_angle - BUILD_BACKOFF) * PINION_TEETH / GREAT_TEETH + DRUM_OFFSET
    v["carrier_offset"] = math.fmod(turn + math.pi / 2 - old, 2 * math.pi)
    # A uniform-curvature spiral: k = E h t^3 / (12 L) and strain = (t / 2) theta / L.
    rate = SPRING_YOUNG * sp.height * sp.thickness ** 3 / (12 * dims.active_length)
    full = SPRING_FULL_TURNS * 2 * math.pi
    v["spring_rate"] = rate
    v["full_wind_torque"] = rate * full
    v["full_wind_strain"] = sp.thickness / 2 * full / dims.active_length
    v["run_turns"] = SPRING_FULL_TURNS - SPRING_MIN_TORQUE / (rate * 2 * math.pi)
    return Geometry(**v)
