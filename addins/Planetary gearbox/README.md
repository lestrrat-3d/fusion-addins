# Planetary gearbox

A Fusion add-in that rebuilds the decad-gallery model `planetarygearbox`: a fixed internal ring gear housing one or
more stages, each with a sun gear, planet gears on 605ZZ bearings, a carrier and a shaft, closed by two bearing covers
that eight M2 bolts and eight M2 nuts hold to the ring. It takes the gallery's inputs with the gallery's defaults and
uses the gallery's input rules. Bodies are grouped the way the gallery groups them: the `Planetary Gearbox`
component holds one sub-component per gallery container (`Housing`, `Cover Bearings`, `Bolts`, `Nuts`, `Shafts`,
`Sun Gears`, `Planet Gears`, `Planet Bearings`, `Carriers`), and each body sits in the sub-component of its
container. As in the gallery, the ring, the covers and the carriers have a 45° chamfer (`Edge chamfer`, 0.5 mm) on
the edges of their large flat faces. The ring has three mounting ears by default; the `Mounting ears` check box in the
dialog turns them off, and the `Ear count` and `Ear bore diameter` inputs are disabled while it is unchecked.

## Gallery revision

Gallery revision: 4a452cdc74e783b7e8eb5512cec68d196423dbe4 (`GALLERY_REVISION` in `config.py`)

The add-in translates decad-gallery at this commit: `models/planetarygearbox` and the models it builds from,
`models/spurgear`, `models/ballbearing`, `models/m2bolt` and `models/m2nut`.

## Install

See [../../README.md](../../README.md).

## Tests

From the `fusion-addins` root, run `python3 -m unittest discover -s "addins/Planetary gearbox/tests"`. The tests cover the
pure geometry package `lib/gen/` and, with Fusion mocked, the glue imports and the build order
(body names, copies, body count, container components and edge chamfers for one and two stages). They need no
Fusion.

## Build checks

After each build the add-in compares every built body with the expected values from `lib/gen/`:
volume, z range against the assembled position, and point containment probes (the ring's include its ears and their bores). For a placed build it also checks that
gear outline points lie outside the neighbouring gear (meshing), that bolt and nut surface points lie outside the cover
and ring they pass through (fit), and that the component tree has the gallery's nine containers with the right bodies.
This stands in for the gallery's `VerifyContainers`, which Fusion does not have.

Text Commands shows only these lines: `planetarygearbox fingerprint <64 hex>` and `planetarygearbox gallery <40 hex>`
when the add-in starts, one `summary` line with `bodies`, `expected`, `pass`, `fail` and `seconds` after a build, a
`fallback` line when the planet's root fillet had to use a smaller radius, and an `error` line when a step fails. A
failed check adds one line with `result=FAIL` (`body`, `bounds`, `probes`, `probe`, `mesh summary`, `fit summary`,
`containers` or `container`); a passing check adds nothing. The add-in writes no log file.

## License

See the root [LICENSE](../../LICENSE) of `fusion-addins`. `deploy.py` copies it into the installed folder.
