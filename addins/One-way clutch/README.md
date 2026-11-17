# One-way clutch

A Fusion add-in that rebuilds the decad-gallery model `onewayclutch`: a printed one-way clutch for a D-flat shaft. A hub
pressed on the shaft carries three flexing pawls that engage a ring with 18 internal sawtooth teeth and three bolt ears,
so the ring turns freely one way about the held shaft and is driven the other way. A back plate and a cover hold the ring
on the hub, clamped by three M2 x 16 bolts and nuts. The build has 10 bodies. The dialog takes the `Shaft` preset
(`605ZZ`, `608ZZ` or `608ZZ-gearbox`), the `Freewheel` direction (`Clockwise` or `CounterClockwise`) and the `Bore
clearance`, with the gallery's defaults and input rules, and an `Adapter ring` check box (off by default) that also builds
the gallery's standard adapter ring with its three M2 x 25 bolts and nuts, which makes the build 17 bodies. Bodies are
grouped the way the gallery groups them: the `One-way clutch` component holds the sub-components `Hub`, `Ring`, `Plates`,
`Bolts` and `Nuts` (and `Adapter` with the adapter ring), and each body sits in the sub-component of its container. The
two optional selections `Origin point` and `Axis direction` place the clutch.

## Gallery revision

Gallery revision: a8114921f7302d1c3f862dcc8eca44f2dab108be (`GALLERY_REVISION` in `config.py`)

The add-in translates decad-gallery at this commit: `models/onewayclutch` and the models it builds from,
`models/ballbearing`, `models/m2bolt` and `models/m2nut`.

## Install

See [../../README.md](../../README.md).

## Tests

From the `fusion-addins` root, run `python3 -m unittest discover -s "addins/One-way clutch/tests"`. The tests cover the
pure geometry package `lib/gen/` (the input rules, the derived radii and pawl values, every closed loop, the expected volumes and
bounds, the probes) and, with Fusion mocked, the glue imports, the dialog inputs, the build order, each body's chamfers,
cuts and moves and the build checks. They need no Fusion.

## Build checks

After each build the add-in compares every built body with the expected values from `lib/gen/`: volume, bounding box
and point containment probes. The 605ZZ ring's volume is the gallery's own; the other printed parts' volumes, and the 8 mm
rings', are computed from the sections the add-in draws, and the hub's allows for its chamfer by an estimate. The hub and the ring are probed
on a grid at half their height, with each probe's expectation read from the same sections, so a mirrored or misdrawn curve
shows. It also checks that the component tree has the containers with the right bodies, which stands in for the gallery's
`VerifyContainers`.

Text Commands shows only these lines: `onewayclutch fingerprint <64 hex>` and `onewayclutch gallery <40 hex>` when the
add-in starts, one `summary` line with `bodies`, `expected`, `pass`, `fail` and `seconds` after a build, a `fallback`
line when Fusion rejects the hub's chamfer or the chamfer of a plate's D loop, and an `error` line when a step
fails. A failed check adds one line with `result=FAIL` (`body`, `bounds`, `probes`, `probe`, `containers` or
`container`); a passing check adds nothing. A `cut` line with `result=FAIL` means a cut removed no material, and shows the
tool's bounds. The add-in writes no log file.

## License

See the root [LICENSE](../../LICENSE) of `fusion-addins`. `deploy.py` copies it into the installed folder.
