# Plaque stand

A Fusion add-in that rebuilds the decad-gallery model `plaquestand`: a desk or shelf stand for a flat, heavy
rectangular plaque, made of two identical printed brackets joined by a printed rail and fixed by two M2 x 6 bolts and
nuts. The plaque leans back in a slot in each bracket, against a back rest and behind a low front lip. The build has 8
bodies: the two brackets, the rail, two bolts, two nuts and the plaque itself as a reference body that is not printed.
The dialog takes the gallery's six inputs with its defaults and input rules: `Plaque width`, `Plaque height`,
`Plaque thickness`, `Recline`, `Lip height` and `Slot clearance`. Bodies are grouped the way the gallery groups them:
the `Plaque stand` component holds the sub-components `Brackets`, `Rail`, `Bolts`, `Nuts` and `Plaque`, and each
body sits in the sub-component of its container.

## Gallery revision

Gallery revision: b2200f3eb988273abd396d94c79a8bf671d2d9c6 (`GALLERY_REVISION` in `config.py`)

The add-in translates decad-gallery at this commit: `models/plaquestand` and the models it builds from,
`models/m2bolt` and `models/m2nut`.

## Install

See [../../README.md](../../README.md).

## Tests

From the `fusion-addins` root, run `python3 -m unittest discover -s "addins/Plaque stand/tests"`. The tests cover the
pure geometry package `lib/gen/` (the derived dimensions and validation rules of the six representative cases, the
outline's 26 segments, area, length and tangent joins, the expected volumes and bounds, the probes) and, with Fusion
mocked, the glue imports, the dialog inputs, the build order, each body's chamfers, cuts and moves and the build
checks. They need no Fusion.

## Build checks

After each build the add-in compares every built body with the expected values from `lib/gen/`: volume, bounding box
and point containment probes. The brackets' and the rail's volumes are computed from the sections the add-in draws and
agree with the gallery's decad builds to 0.1 mm^3. Each bracket is probed on a grid across its profile, with every
probe's expectation read from the same outline, so a misdrawn curve shows. It also checks that the component tree has
the five containers with the right bodies, which stands in for the gallery's `VerifyContainers`.

Text Commands shows only these lines: `plaquestand fingerprint <64 hex>` and `plaquestand gallery <40 hex>` when the
add-in starts, one `summary` line with `bodies`, `expected`, `pass`, `fail` and `seconds` after a build, a `fallback`
line when Fusion rejects the round on a nut pocket's floor, and an `error` line when a step fails. A failed check adds
one line with `result=FAIL` (`body`, `bounds`, `probes`, `probe`, `containers` or `container`); a passing check adds
nothing. A `cut` line with `result=FAIL` means a cut removed no material, and shows the tool's bounds. The add-in
writes no log file.

## License

See the root [LICENSE](../../LICENSE) of `fusion-addins`. `deploy.py` copies it into the installed folder.
