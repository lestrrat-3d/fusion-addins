# Seven-segment display

A Fusion add-in that rebuilds the decad-gallery model `sevensegment`: a printed, mechanical digit 0 to 9. Seven rotors
with a yellow face and a black body turn in windows of a top plate, each on two printed pivot blocks, driven by seven
cams on a camshaft that a push-button click indexer steps from digit to digit. The build has 75 bodies. The dialog
takes the `Digit` the display is built showing (0 to 9, default 2) and has the two optional selections `Origin point`
and `Axis direction` that place it. Bodies are grouped the way the gallery groups them: the `Seven-segment display`
component holds the sub-components `Frame`, `Camshaft`, `Click Indexer`, `Segment Sliders`, `Flags` and `Pivot Blocks`,
and each body sits in the sub-component of its container. The sizes are the gallery's, written in mm in
`lib/gen/constants.py` (1.5 times the earlier builds); the dialog has no scale input.

## Gallery revision

Gallery revision: cbbb2ca062d31dfe662fe7963f8a7c536b89a7b2 (`GALLERY_REVISION` in `config.py`)

The add-in translates decad-gallery at this commit: `models/sevensegment` and the models it builds from, which it
reuses as its own copies of their fasteners and bearings (`models/m2bolt`, `models/m2nut` and `models/ballbearing`).

## Install

See [../../README.md](../../README.md).

## Tests

From the `fusion-addins` root, run `python3 -m unittest discover -s "addins/Seven-segment display/tests"`. The tests
cover the pure geometry package `lib/gen/` and, with Fusion mocked, the glue imports, the dialog inputs, the build order,
each body's cuts and moves and the build checks, and they check that the sizes are the gallery's numbers, 1.5 times
the earlier builds, with the fits and the purchased hardware unchanged. They need no Fusion.

## Build checks

After each build the add-in checks that every one of the 75 bodies is a solid, and compares the bounding box of the
frame bodies, the camshaft bodies, the hub and the 14 pivot blocks with the expected values from `lib/gen/`. It also checks that the
component tree has the containers with the right bodies, which stands in for the gallery's `VerifyContainers`.

Text Commands shows only these lines: `sevensegment fingerprint <64 hex>` and `sevensegment gallery <40 hex>` when the
add-in starts, one `timing` line per part (`part`, `seconds`, `items` for the part's timeline items and `timeline` for
the running total) plus one for the containers and one for the checks, one `summary` line with `bodies`, `expected`,
`pass`, `fail` and `seconds` after a build, and an `error` line when a step fails. A flag or pivot block that Fusion
could not copy adds a `copy` line with `result=FALLBACK`, and a large part that could not be built in a design of its
own and imported adds an `isolate` line with `result=FALLBACK`. A failed check adds one line with `result=FAIL` (`body`, `bounds`, `containers` or
`container`); a passing check adds nothing. A `cut` line with `result=FAIL` means a cut removed no material, and shows
the tool's bounds. The add-in writes no log file.

## License

See the root [LICENSE](../../LICENSE) of `fusion-addins`. `deploy.py` copies it into the installed folder.
