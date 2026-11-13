# Graham escapement

A Fusion add-in that rebuilds the decad-gallery model `escapement`: a desk-clock-size Graham deadbeat escapement
movement. A spiral mainspring turns a great wheel, which turns a 30-tooth escape wheel through a 13-tooth pinion. An
anchor with two pallets lets the escape wheel advance half a tooth at a time, and a crutch on the anchor's arbor pushes
a 180 mm pendulum. The movement sits in a two-plate frame on seven 605ZZ bearings and four M2 bolts and nuts. The
default build has 32 bodies. The dialog takes the gallery's inputs with the gallery's defaults (`Pendulum length`,
`Amplitude`, `Lock angle`, `Lift angle`, `Phase`, `Backlash`) and the gallery's input rules. Bodies are grouped the way
the gallery groups them: the `Graham Escapement` component holds one sub-component per gallery container (`Frame`,
`Bearings`, `Arbors`, `Escapement`, `Pendulum Assembly`, `Drive`, `Bolts`, `Nuts`) with the gallery's nested
containers below them, and each body sits in the sub-component of its container. The two optional selections `Origin
point` and `Axis direction` place the whole movement.

## Gallery revision

Gallery revision: 0067d30583ac04cf259150adc3578793030ec2c3 (`GALLERY_REVISION` in `config.py`)

The add-in translates decad-gallery at this commit: `models/escapement` and the models it builds from,
`models/spurgear`, `models/spiralspring`, `models/ballbearing`, `models/m2bolt` and `models/m2nut`.

## Install

See [../../README.md](../../README.md).

## Tests

From the `fusion-addins` root, run `python3 -m unittest discover -s "addins/Graham escapement/tests"`. The tests cover
the pure geometry package `lib/gen/` and, with Fusion mocked, the glue imports and the build order (body names, copies,
body count, container components and the dialog inputs). They need no Fusion.

## Build checks

After each build the add-in compares every built body with the expected values from `lib/gen/`: volume, z range against
the assembled position, and point containment probes. It also checks that gear and anchor outline points lie outside
the part they touch (`mesh`, `escapement`, `coupling`), that bolt and nut surface points lie outside the plates they pass
through (`fit`), and that the component tree has the gallery's nineteen containers with the right bodies. This stands
in for the gallery's `VerifyContainers`, which Fusion does not have.

Text Commands shows only these lines: `escapement fingerprint <64 hex>` and `escapement gallery <40 hex>` when the
add-in starts, one `summary` line with `bodies`, `expected`, `pass`, `fail` and `seconds` after a build, and an `error`
line when a step fails. A failed check adds one line with `result=FAIL` (`body`, `bounds`, `probes`, `probe`,
`mesh summary`, `mesh`, `escapement summary`, `escapement`, `coupling summary`, `coupling`, `fit summary`, `fit`,
`containers` or `container`); a passing check adds nothing. The add-in writes no log file.

## License

See the root [LICENSE](../../LICENSE) of `fusion-addins`. `deploy.py` copies it into the installed folder.
