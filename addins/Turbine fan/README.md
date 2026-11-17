# Turbine fan

A Fusion add-in that rebuilds the decad-gallery model `turbinefan`: a fan of three replaceable blades on one printed
hub. The hub is a round cylinder with a D bore for a D-flat shaft, an M2 set screw that presses the shaft's flat, and
two blind M2 holes with nut slots for bolting it to the adapter ring of a one-way clutch. Each blade has a round root
stud that slides into a radial socket in the hub and is held by one M2 bolt and nut. The build has 12 bodies (hub,
three blades, four bolts, four nuts), or 14 with the clutch mount, which swaps the set screw and its nut for two
M2 x 10 adapter bolts and nuts. The clutch mount also builds the one-way clutch with its adapter ring, as a second
top-level component named `One-way clutch` beside the fan, and seats the fan on the adapter. The dialog takes the
shaft bore diameter (`Shaft bore diameter`, default 5 mm), the shaft's `Flat depth`, the `Bore clearance`, the
`Rotor diameter` (default 192 mm, from 128 to 224 mm, which sizes the hub, the blades and the blade bolts), the
`Blade pitch` (default 25 degrees), the `Hand` (`Right hand` or `Left hand`) and the `Mount` (`Shaft` or `Clutch`), with the
gallery's defaults and input rules. With `Clutch`, the dialog shows `Clutch shaft`, `Clutch freewheel` and `Clutch bore
clearance` instead of the shaft, hand and bore inputs, and the hand follows the freewheel. Bodies are grouped the way
the gallery groups them: the `Turbine fan` component holds the sub-components `Hub`, `Blades`, `Bolts` and `Nuts`, and
each body sits in the sub-component of its container. The two optional selections `Origin point` and `Axis direction`
place the fan, or the clutch in the clutch mount.

## Gallery revision

Gallery revision: a8114921f7302d1c3f862dcc8eca44f2dab108be (`GALLERY_REVISION` in `config.py`)

The add-in translates decad-gallery at this commit: `models/turbinefan` and the models it builds from,
`models/ballbearing`, `models/m2bolt`, `models/m2nut` and `models/onewayclutch`.

## Install

See [../../README.md](../../README.md).

## Tests

From the `fusion-addins` root, run `python3 -m unittest discover -s "addins/Turbine fan/tests"`. The tests cover the
pure geometry package `lib/gen/` (the derived dimensions and validation rules, the blade's sections against the
gallery's bounds, the expected volumes and bounds, the probes and the container check; the same for the clutch in
`lib/gen/clutch/`, and the clutch mount's frame and hand) and, with Fusion mocked, the glue imports, the dialog inputs,
the build order, each body's cuts and moves, the blade steps and the build checks, for the fan and for the clutch. They
need no Fusion.

## Build checks

After each build the add-in compares every built body with the expected values from `lib/gen/`: volume, bounding box
and point containment probes. The hub's volume is checked only at the two bearing presets (5 mm with a 0.5 mm flat and
8 mm with a 0.75 mm flat, both at 0.05 mm clearance) at the rotor diameters 128, 192 and 224 mm, because the gallery gives
no formula for it. A blade's volume is checked at the same three diameters and held to 3 %, and its bounding box is held
to 0.3 mm at 128 mm and 0.45 mm at 192 mm, because Fusion lofts through the section points with its own spline. It
also checks that the component tree has the four containers with the right bodies, which stands in for the gallery's
`VerifyContainers`. The clutch mount runs the same checks on the clutch and its adapter, with the clutch's own expected
values, before the fan's.

Text Commands shows only these lines: `turbinefan fingerprint <64 hex>` and `turbinefan gallery <40 hex>` when the
add-in starts, one `summary` line with `bodies`, `expected`, `pass`, `fail` and `seconds` after a build (two in the
clutch mount, the clutch's first), a `fallback`
line when Fusion rejects a round on a cutting tool, and an `error` line when a step fails. A failed check adds one line
with `result=FAIL` (`body`, `bounds`, `probes`, `probe`, `containers` or `container`); a passing check adds nothing. A
`cut` line with `result=FAIL` means a cut removed no material, and shows the tool's bounds. The add-in writes no log
file.

## License

See the root [LICENSE](../../LICENSE) of `fusion-addins`. `deploy.py` copies it into the installed folder.
