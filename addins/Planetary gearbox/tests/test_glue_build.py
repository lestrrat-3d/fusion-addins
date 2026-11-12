"""Runs the build order against a mocked Fusion: every part builder, placement, naming and the body-count rule."""

import dataclasses
import importlib
import math
import os
import sys
import unittest
from unittest import mock

import _support  # noqa: F401

from gen import containers, layout
from gen.dims import derive
from gen.params import default_params, placement_frame

_ADDINS = _support.ADDINS


class FakeBody:
    def __init__(self, world, comp, part=""):
        self.comp = comp
        self.part = part
        self.name = ""
        self.isSolid = True
        self.moved = 0
        world.alive.append(self)


class World:
    """Tracks which fake bodies are alive, like the component's body list."""

    def __init__(self):
        self.alive = []
        self.calls = []
        self.chamfers = []

    @property
    def count(self):
        return len(self.alive)


class FakeBodies:
    def __init__(self, items):
        self._items = list(items)

    @property
    def count(self):
        return len(self._items)

    def item(self, i):
        return self._items[i]


class FakeOcc:
    def __init__(self, component):
        self.component = component


class FakeOccurrences:
    def __init__(self, world):
        self._world = world
        self._items = []

    def addNewComponent(self, transform):
        occ = FakeOcc(FakeComponent(self._world))
        self._items.append(occ)
        return occ

    @property
    def count(self):
        return len(self._items)

    def item(self, i):
        return self._items[i]


class FakeComponent:
    def __init__(self, world, name=""):
        self._world = world
        self.name = name
        self.occurrences = FakeOccurrences(world)

    @property
    def bRepBodies(self):
        return FakeBodies([b for b in self._world.alive if b.comp is self])


class FakeLog:
    enabled = False

    def __init__(self):
        self.records = []

    def write(self, event, fields):
        self.records.append((event, dict(fields)))


# Default-input loops as (is_outer, edge_count, start_radius): part -> (bottom face, top face).
FACE_LOOPS = {
    # The default ring has three mounting ears: its outer loop is 3 x (line, arc, line, arc) = 12 edges, and the
    # ear bores are three more single-edge loops that no rule keeps.
    "ring": ([(True, 12, 44.0), (False, 284, 34.5)] + [(False, 1, 39.3)] * 4 + [(False, 1, 49.0)] * 3,
             [(True, 12, 44.0), (False, 284, 34.5)] + [(False, 1, 39.3)] * 4 + [(False, 1, 49.0)] * 3),
    "cover": ([(True, 1, 44.0)] + [(False, 4, 13.25)] * 3 + [(False, 1, 5.0)] + [(False, 1, 39.3)] * 4,
              [(True, 1, 44.0)] + [(False, 4, 13.25)] * 3 + [(False, 1, 38.5)] * 4 + [(False, 1, 10.25)]),
    "carrier": ([(True, 6, 26.25), (False, 12, 2.5)] + [(False, 2, 18.8)] * 3,
                [(True, 6, 26.25), (False, 12, 2.5)]),
}


def install(world, fusion, face_loops=FACE_LOOPS):
    def extrude(ctx, profile, z, length, what):
        world.calls.append(("extrude", what))
        return FakeBody(world, ctx.comp, ctx.part)

    def combine(ctx, target, tools, what):
        world.calls.append(("combine", what))
        for t in tools:
            world.alive.remove(t)
        return target

    def pattern(ctx, body, count, what):
        world.calls.append(("pattern", what))
        return [body] + [FakeBody(world, ctx.comp, ctx.part) for _ in range(count - 1)]

    def copy_body(ctx, body, what):
        world.calls.append(("copy", what))
        return FakeBody(world, ctx.comp, ctx.part)

    def move(ctx, body, pose, what):
        if not pose.is_identity():
            world.calls.append(("move", what))
            body.moved += 1

    def record(kind):
        def f(*args, **kwargs):
            world.calls.append((kind, args[-1] if args and isinstance(args[-1], str) else ""))
            return mock.MagicMock()

        return f

    def split_body(ctx, body, pose, what):
        world.calls.append(("split", what))
        world.alive.remove(body)
        return tuple(FakeBody(world, ctx.comp, ctx.part) for _ in range(2))

    def revolve(ctx, profile, what):
        world.calls.append(("revolve", what))
        return FakeBody(world, ctx.comp, ctx.part)

    def flat_face_loops(body, z, min_area, what, tol=1e-3):
        world.calls.append(("faces", what))
        # Bottom planes are z = 1 for the ring and z = 0 otherwise.
        rows = face_loops[body.part][0 if z <= 1.0 else 1]
        return [(o, [object()] * n, r) for o, n, r in rows]

    def profile_with_loops(sk, loops, what, only=False):
        world.calls.append(("profile", f"{what} {loops}"))
        return mock.MagicMock()

    def chamfer(ctx, edges, distance, what, tangent_chain=True):
        world.calls.append(("chamfer", what))
        world.chamfers.append((what, len(edges), distance, tangent_chain))

    patches = {
        "new_sketch": mock.MagicMock(),
        "draw_loop": mock.MagicMock(),
        "new_sketch_xz": mock.MagicMock(),
        "draw_loop_xz": mock.MagicMock(),
        "revolve": revolve,
        "draw_circle": mock.MagicMock(),
        "draw_rectangle": mock.MagicMock(),
        "profile_with_loops": profile_with_loops,
        "extrude": extrude,
        "join": combine,
        "cut": combine,
        "pattern": pattern,
        "copy_body": copy_body,
        "split_body": split_body,
        "move": move,
        "fillet": record("fillet"),
        "chamfer": chamfer,
        "flat_face_loops": flat_face_loops,
        "axial_edges_at": lambda body, points, tol=1e-3: [object()] * (2 * len(points) // 2),
        "concave_axial_edges": lambda body, tol=1e-3: [],
        "circular_edges_at": lambda body, radius, z, tol=1e-3: [object()],
    }
    return mock.patch.multiple(fusion, **patches)


def build_error(msg):
    # The glue is re-imported inside each run_build, so take BuildError from the module live at call time.
    return sys.modules["Planetary gearbox.commands.gearbox.fusion"].BuildError(msg)


def make_design(adsk, world):
    """A mock design whose gearbox occurrence holds a fake top component. Returns (design, top)."""
    top = FakeComponent(world)
    design = mock.MagicMock()
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    design.rootComponent.occurrences.addNewComponent.return_value.component = top
    return design, top


class GlueBuildTest(unittest.TestCase):
    def run_build(self, fillet=None, log=None, face_loops=None, **changes):
        p = dataclasses.replace(default_params(), **changes)
        adsk = mock.MagicMock()
        fakes = {"adsk": adsk, "adsk.core": adsk.core, "adsk.fusion": adsk.fusion}
        with mock.patch.dict(sys.modules, fakes), mock.patch.object(sys, "path", [_ADDINS] + sys.path):
            fusion = importlib.import_module("Planetary gearbox.commands.gearbox.fusion")
            build = importlib.import_module("Planetary gearbox.commands.gearbox.build")
            self.assertEqual(build.STAGE_PARTS, layout.PARTS)
            self.assertTrue(build.PLACE_INSTANCES)
            world = World()
            design, top = make_design(adsk, world)
            self.top = top
            self.fusion = fusion
            installed = install(world, fusion, face_loops or FACE_LOOPS)
            with installed, mock.patch.object(build.checks, "run_all") as run_all:
                if fillet is not None:
                    mock.patch.object(fusion, "fillet", fillet).start()
                    self.addCleanup(mock.patch.stopall)
                build.build_gearbox(design, p, log or FakeLog())
            self.ctx = run_all.call_args.args[0]
            return world, run_all.call_args.args[1]

    def check_names(self, p_changes, expected_count):
        p = dataclasses.replace(default_params(), **p_changes)
        world, built = self.run_build(**p_changes)

        d = derive(p)
        want = sorted(i.name for i in layout.instances(p, d))
        self.assertEqual(len(want), expected_count)
        self.assertEqual(sorted(name for _, name, _ in built), want)
        self.assertEqual(world.count, expected_count)
        self.assertEqual(sorted(b.name for b in world.alive), want)
        self.assertTrue(all(b.isSolid for b in world.alive))
        self.check_containers(p, derive(p), world)
        copies = [c for c in world.calls if c[0] == "copy" and c[1].endswith(" copy")]
        self.assertEqual(len(copies), expected_count - len({part for part, _, _ in built}))

    def check_containers(self, p, d, world):
        want = containers.expected_bodies(p, d)
        top = self.top
        self.assertEqual(
            [top.occurrences.item(i).component.name for i in range(top.occurrences.count)],
            list(containers.CONTAINER_NAMES),
        )
        self.assertEqual(top.bRepBodies.count, 0)
        by_body = {b.name: b.comp.name for b in world.alive}
        self.assertEqual(by_body, {name: c for c, names in want.items() for name in names})
        root_count, found = self.fusion.component_tree(top)
        self.assertEqual(root_count, 0)
        self.assertTrue(containers.check_root(found, root_count).ok)
        for r in containers.check_containers(found, want):
            self.assertTrue(r.ok, (r.name, r.detail))

    def test_one_stage(self):
        self.check_names({}, 34)

    def test_two_stages(self):
        self.check_names({"stages": 2}, 46)

    def test_pins_shafts_not_split_by_default(self):
        world, _ = self.run_build(stages=2)
        self.assertEqual([c for c in world.calls if c[0] == "split"], [])

    def test_split_pins_shafts(self):
        p = dataclasses.replace(default_params(), stages=2, split_pins_shafts=True)
        world, _ = self.run_build(stages=2, split_pins_shafts=True)
        split = [i.name for i in layout.instances(p, derive(p)) if i.part in layout.SPLIT_PARTS]
        self.assertEqual(len(split), 3 + 6)
        self.assertEqual(sorted(c[1] for c in world.calls if c[0] == "split"), sorted(f"{n} split" for n in split))
        self.assertEqual(world.count, 46 + len(split))
        halves = sorted(b.name for b in world.alive if b.comp.name in (containers.SHAFTS, containers.CARRIER_PINS))
        self.assertEqual(halves, sorted(h for n in split for h in layout.split_names(n)))

    def test_planet_fillet_second_attempt(self):
        attempts = []

        def fillet(ctx, edges, radius, what):
            if what.startswith("planet"):
                attempts.append(radius)
                if len(attempts) == 1:
                    raise build_error(f"{what}: rejected")

        log = FakeLog()
        self.run_build(fillet=fillet, log=log, pressure_angle=math.radians(25))
        self.assertEqual(len(attempts), 2)
        self.assertGreater(attempts[0], attempts[1])
        self.assertAlmostEqual(self.ctx.fillet_radius["planet"], attempts[1])
        fallbacks = [f for e, f in log.records if e == "fallback"]
        self.assertEqual(len(fallbacks), 1)
        self.assertEqual(fallbacks[0]["part"], "Planet Gear 1.3")
        self.assertEqual(fallbacks[0]["step"], "root_fillet")
        self.assertAlmostEqual(fallbacks[0]["radius_mm"], attempts[1])

    def test_planet_fillet_skipped_after_two_failures(self):
        attempts = []

        def fillet(ctx, edges, radius, what):
            if what.startswith("planet"):
                attempts.append(radius)
                raise build_error(f"{what}: rejected")

        log = FakeLog()
        self.run_build(fillet=fillet, log=log, pressure_angle=math.radians(25))
        self.assertEqual(len(attempts), 2)
        self.assertEqual(self.ctx.fillet_radius["planet"], 0.0)
        fallbacks = [f for e, f in log.records if e == "fallback"]
        self.assertEqual([f["radius_mm"] for f in fallbacks], [0.0])

    def test_fastener_calls(self):
        world, _ = self.run_build()
        for call in (
            ("revolve", "bolt revolve"),
            ("revolve", "nut lower_chamfer_revolve"),
            ("revolve", "nut upper_chamfer_revolve"),
            ("fillet", "bolt underhead_fillet"),
        ):
            self.assertIn(call, world.calls)

    def test_housing_feature_calls(self):
        world, _ = self.run_build()
        calls = world.calls
        self.assertEqual(calls.count(("combine", "ring nut_cavity_cut")), 8)
        self.assertEqual(calls.count(("combine", "cover head_pocket_cut")), 4)
        self.assertEqual(calls.count(("copy", "ring nut_cavity_copy")), 7)
        self.assertEqual(calls.count(("copy", "cover head_pocket_copy")), 3)
        first_cavity = calls.index(("combine", "ring nut_cavity_cut"))
        self.assertGreater(first_cavity, calls.index(("extrude", "ring ring_blank_extrude")))
        self.assertLess(first_cavity, calls.index(("combine", "ring ring_cut")))
        # The default build has no bridge layers.
        self.assertEqual(calls.count(("combine", "ring bridge_join")), 0)
        self.assertNotIn(("extrude", "ring bridge_extrude"), calls)
        join = calls.index(("combine", "cover cover_join"))
        for i, c in enumerate(calls):
            if c == ("combine", "cover head_pocket_cut"):
                self.assertGreater(i, join)
        # The carrier has one socket tool, copied for the other two planets and cut in one boolean; no pins stand on it.
        self.assertEqual(calls.count(("extrude", "carrier pin socket_extrude")), 1)
        self.assertEqual(calls.count(("pattern", "carrier socket_pattern")), 1)
        self.assertEqual(calls.count(("combine", "carrier socket_cut")), 1)
        self.assertNotIn(("combine", "carrier carrier_join"), calls)
        # Each pin is its own part: a rod and a D thick part joined once.
        for gap in (1.0, 0.75):
            world, _ = self.run_build(stage_gap=gap)
            for what in ("rod", "thick"):
                self.assertIn(("extrude", f"carrier_pin {what}_extrude"), world.calls)
            self.assertEqual(world.calls.count(("combine", "carrier_pin pin_join")), 1)

    def test_ring_bridging_calls(self):
        world, _ = self.run_build(sacrificial_bridging=True)
        calls = world.calls
        # One bridge layer per nut cavity, joined after the last cavity is cut and before the tooth cut.
        self.assertEqual(calls.count(("combine", "ring bridge_join")), 8)
        self.assertEqual(calls.count(("copy", "ring bridge_copy")), 7)
        last_cavity = len(calls) - 1 - calls[::-1].index(("combine", "ring nut_cavity_cut"))
        first_bridge = calls.index(("combine", "ring bridge_join"))
        self.assertGreater(first_bridge, last_cavity)
        self.assertLess(first_bridge, calls.index(("combine", "ring ring_cut")))

    def test_ring_blank_sketch_has_the_ear_bores(self):
        for changes, loops in (({}, 8), ({"ear_count": 0}, 5), ({"ear_count": 2, "ear_bore_diameter": 6.0}, 7)):
            with self.subTest(changes=changes):
                world, _ = self.run_build(**changes)
                self.assertEqual(
                    [c for c in world.calls if c[0] == "profile" and c[1].startswith("ring ring_blank_sketch")],
                    [("profile", f"ring ring_blank_sketch {loops}")],
                )

    def test_edge_finish_without_ears(self):
        plain = {k: (list(v[0]), list(v[1])) for k, v in FACE_LOOPS.items()}
        plain["ring"] = ([(True, 1, 44.0), (False, 284, 34.5)] + [(False, 1, 39.3)] * 4,) * 2
        world, _ = self.run_build(ear_count=0, face_loops=plain)
        finish = [c for c in world.chamfers if c[0].startswith("ring edge_chamfer")]
        self.assertEqual(finish, [("ring edge_chamfer z=1", 1, 0.5, False), ("ring edge_chamfer z=15", 1, 0.5, False)])

    def test_shaft_flat_calls(self):
        world, _ = self.run_build(stages=2)
        calls = world.calls
        # One flat box per span: input 1, link 1, output none (its thin rod stays round). The flat is not patterned.
        self.assertEqual(len([c for c in calls if c[1].endswith("flat_box_extrude")]), 2)
        self.assertFalse([c for c in calls if "key" in c[1]])
        for part in ("input_shaft", "link_shaft"):
            self.assertIn(("combine", f"{part} flat_cut"), calls)
        self.assertNotIn(("combine", "output_shaft flat_cut"), calls)
        for part in ("link_shaft", "output_shaft"):
            self.assertIn(("combine", f"{part} step_join"), calls)
        self.assertIn(("combine", "sun d_bore_cut"), calls)
        self.assertEqual(calls.count(("extrude", "carrier shaft_hole_extrude")), 1)
        flat_off, _ = self.run_build(flat_depth=0.0)
        self.assertFalse([c for c in flat_off.calls if "flat_box" in c[1] or "flat_cut" in c[1] or "d_bore" in c[1]])

    def test_edge_finishing_calls(self):
        world, _ = self.run_build()
        finish = [c for c in world.chamfers if "edge_chamfer" in c[0]]
        self.assertEqual(
            finish,
            [
                ("ring edge_chamfer z=1", 12, 0.5, False),
                ("ring edge_chamfer z=15", 12, 0.5, False),
                ("cover edge_chamfer z=0", 14, 0.5, False),
                ("cover edge_chamfer z=3", 13, 0.5, False),
                ("carrier edge_chamfer z=0", 6, 0.5, False),
                ("carrier edge_chamfer z=3", 6, 0.5, False),
            ],
        )
        calls = world.calls
        self.assertGreater(calls.index(("chamfer", "ring edge_chamfer z=1")), calls.index(("combine", "ring ring_cut")))
        self.assertGreater(
            calls.index(("chamfer", "cover edge_chamfer z=0")), calls.index(("chamfer", "cover seat_chamfer"))
        )
        self.assertGreater(
            calls.index(("chamfer", "carrier edge_chamfer z=0")), calls.index(("combine", "carrier shaft_hole_cut"))
        )
        self.assertLess(calls.index(("chamfer", "cover edge_chamfer z=3")), calls.index(("copy", "cover copy")))
        world2, _ = self.run_build(stages=2)
        names = [c[0] for c in world2.chamfers if "edge_chamfer" in c[0]]
        self.assertEqual(names.count("ring edge_chamfer z=28"), 1)
        self.assertEqual(names.count("carrier edge_chamfer z=0"), 1)
        self.assertEqual(names.count("carrier edge_chamfer z=3"), 1)

    def test_edge_finishing_loop_guard(self):
        extra = {k: (list(v[0]), list(v[1])) for k, v in FACE_LOOPS.items()}
        extra["cover"][1].append((False, 2, 20.0))
        with self.assertRaises(Exception) as cm:
            self.run_build(face_loops=extra)
        self.assertEqual(type(cm.exception).__name__, "BuildError")
        self.assertEqual(str(cm.exception), "cover edge_chamfer z=3: found 5 loops to chamfer, expected 4")
        none = {k: (list(v[0]), list(v[1])) for k, v in FACE_LOOPS.items()}
        none["ring"] = ([], none["ring"][1])
        with self.assertRaises(Exception) as cm:
            self.run_build(face_loops=none)
        self.assertEqual(str(cm.exception), "ring edge_chamfer z=1: no loop to chamfer")

    def test_default_planet_ladder_has_one_rung(self):
        attempts = []

        def fillet(ctx, edges, radius, what):
            if what.startswith("planet"):
                attempts.append(radius)
                raise build_error(f"{what}: rejected")

        log = FakeLog()
        self.run_build(fillet=fillet, log=log)
        self.assertEqual(len(attempts), 1)
        self.assertEqual(self.ctx.fillet_radius["planet"], 0.0)
        fallbacks = [f for e, f in log.records if e == "fallback"]
        self.assertEqual([f["radius_mm"] for f in fallbacks], [0.0])

    def run_for_placement(self, **changes):
        """Returns (frame_matrix mock, addNewComponent mock) after a K = 1 build."""
        p = dataclasses.replace(default_params(), **changes)
        adsk = mock.MagicMock()
        fakes = {"adsk": adsk, "adsk.core": adsk.core, "adsk.fusion": adsk.fusion}
        with mock.patch.dict(sys.modules, fakes), mock.patch.object(sys, "path", [_ADDINS] + sys.path):
            fusion = importlib.import_module("Planetary gearbox.commands.gearbox.fusion")
            build = importlib.import_module("Planetary gearbox.commands.gearbox.build")
            world = World()
            design, _ = make_design(adsk, world)
            add = design.rootComponent.occurrences.addNewComponent
            frame_matrix = mock.MagicMock(name="frame_matrix")
            with install(world, fusion), mock.patch.object(fusion, "frame_matrix", frame_matrix), \
                    mock.patch.object(build.checks, "run_all"):
                build.build_gearbox(design, p, FakeLog())
            return frame_matrix, add, adsk.core.Matrix3D.create.return_value, add.return_value

    def test_placed_run_uses_frame_as_occurrence_transform(self):
        frame = placement_frame((10.0, -5.0, 7.0), (0.0, 1.0, 1.0))
        frame_matrix, add, _, occ = self.run_for_placement(placement=frame)
        frame_matrix.assert_called_once_with(frame)
        add.assert_called_once_with(frame_matrix.return_value)

    def test_unplaced_run_uses_identity(self):
        frame_matrix, add, identity, _ = self.run_for_placement()
        frame_matrix.assert_not_called()
        add.assert_called_once_with(identity)

    def test_design_radius_logs_no_fallback(self):
        log = FakeLog()
        self.run_build(log=log)
        self.assertEqual([e for e, _ in log.records if e == "fallback"], [])

    def test_non_parametric_design_is_rejected(self):
        adsk = mock.MagicMock()
        fakes = {"adsk": adsk, "adsk.core": adsk.core, "adsk.fusion": adsk.fusion}
        with mock.patch.dict(sys.modules, fakes), mock.patch.object(sys, "path", [_ADDINS] + sys.path):
            fusion = importlib.import_module("Planetary gearbox.commands.gearbox.fusion")
            build = importlib.import_module("Planetary gearbox.commands.gearbox.build")
            design = mock.MagicMock()
            design.designType = "direct"
            with self.assertRaises(fusion.BuildError):
                build.build_gearbox(design, default_params(), FakeLog())


if __name__ == "__main__":
    unittest.main()
