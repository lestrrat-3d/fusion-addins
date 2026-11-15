# Crank Handle

A Fusion add-in that rebuilds the decad-gallery model `crankhandle`: a printed hand crank for a D-flat shaft. Its arm
pinches the shaft through a slit in the hub and an M2 x 18 clamp bolt and nut, a pin is clamped into the arm's far end
by an M2 x 10 bolt and nut and held together by two M2 x 6 cross bolts and nuts, and the handle turns freely on the
pin. The build has 11 bodies. The dialog takes the shaft bore diameter (`Shaft bore diameter`, default 5 mm), the
shaft's `Flat depth`, the `Bore clearance` and the `Throw`, with the gallery's defaults and input rules, and a `Split pin` check box (off by default) that cuts the pin in two
along the plane through its axis, which makes the build 12 bodies (`Pin Half 1` on the shaft side, holding the cross
nuts, and `Pin Half 2`, holding the bolt heads). Bodies are
grouped the way the gallery groups them: the `Crank Handle` component holds the sub-components `Arm`, `Pin`, `Handle`,
`Bolts` and `Nuts`, and each body sits in the sub-component of its container. The two optional selections `Origin
point` and `Axis direction` place the crank.

## Gallery revision

Gallery revision: 77eca2ef5bc3a08038d0626e7eaa8546fbf5678f (`GALLERY_REVISION` in `config.py`)

The add-in translates decad-gallery at this commit: `models/crankhandle` and the models it builds from,
`models/ballbearing`, `models/m2bolt` and `models/m2nut`.

## Install

See [../../README.md](../../README.md).

## Tests

From the `fusion-addins` root, run `python3 -m unittest discover -s "addins/Crank Handle/tests"`. The tests cover the
pure geometry package `lib/gen/` and, with Fusion mocked, the glue imports, the dialog inputs, the build order, each
body's cuts and moves, the pin split and the build checks. They need no Fusion.

## Build checks

After each build the add-in compares every built body with the expected values from `lib/gen/`: volume, bounding box
and point containment probes. The arm's volume is checked only at the two bearing presets (5 mm with a 0.5 mm flat and
8 mm with a 0.75 mm flat), because the gallery gives no formula for it. It also checks that the component tree has the
five containers with the right bodies, which stands in for the gallery's `VerifyContainers`. The checks run on the
whole pin, before the split; the split then checks that the two halves' volumes add up to the pin's.

Text Commands shows only these lines: `crankhandle fingerprint <64 hex>` and `crankhandle gallery <40 hex>` when the
add-in starts, one `summary` line with `bodies`, `expected`, `pass`, `fail` and `seconds` after a build, a `fallback`
line when Fusion rejects the round on a nut pocket's floor, and an `error` line when a step fails. A failed check adds
one line with `result=FAIL` (`body`, `bounds`, `probes`, `probe`, `containers`, `container` or `split`); a passing check adds
nothing. A `cut` line with `result=FAIL` means a cut removed no material, and shows the tool's bounds. The add-in writes no log file.

## License

See the root [LICENSE](../../LICENSE) of `fusion-addins`. `deploy.py` copies it into the installed folder.
