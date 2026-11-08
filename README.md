# fusion-addins

Autodesk Fusion add-ins generated from [decad-gallery](https://github.com/lestrrat-3d/decad-gallery) models. Each
add-in is one folder under `addins/`. Do not edit the code in those folders by hand, because it is generated and gets
overwritten. `lib/addinkit/` holds runtime code shared by every add-in. Its `general_utils.py` and `event_utils.py`
come from Autodesk's add-in template and keep Autodesk's copyright notice.

## Add-ins

<!-- addins:start -->
<!-- Generated with the add-ins. Do not edit by hand. -->

| Image | Add-in | Description |
|-------|--------|-------------|
| <a href="addins/Planetary%20gearbox"><img src="https://raw.githubusercontent.com/lestrrat-3d/decad-gallery/791aeb255270dfb80a29ed65aa417096997bf30a/models/planetarygearbox/images/hero.png" alt="The default two-stage planetary gearbox, fully assembled, with the ring gear and both end covers cut open to show the planets, carriers, shafts and bearings inside" width="240"></a> | [Planetary gearbox](addins/Planetary%20gearbox) | A compact planetary speed reducer. |

<!-- addins:end -->

## Requirements

- Autodesk Fusion.
- Python 3.12 or newer to run `deploy.py`. It uses only the standard library. On native Windows, run it as
  `py deploy.py ...`.

## Install an add-in

`python3 deploy.py deploy <addin>` copies the add-in's runtime files into Fusion's AddIns folder. It also
adds the shared `lib/addinkit/` (copied to the same path in the installed folder) and `LICENSE`. Fusion does not load
add-ins from `\\wsl.localhost` paths, so the copy is required.

The script picks the destination folder from the first of these that applies:

1. The environment variable `FUSION_ADDIN_DIR`, set to the add-in's own folder (`<AddIns folder>/<addin>`).
2. A `.deploy.conf` file at the repository root. It is untracked, and each add-in deploys to
   `<addins_dir>/<addin>`:

   ```ini
   [deploy]
   addins_dir = /mnt/c/Users/<you>/AppData/Roaming/Autodesk/Autodesk Fusion 360/API/AddIns
   ```

3. The single standard AddIns folder that exists on the machine (WSL, Windows or macOS).

When it finds zero or several standard folders, it exits with code 2 and lists the options above.

Deploy deletes files in the destination that the add-in no longer ships. It keeps bytecode and any debug logs, and it
prints the fingerprint of what it installed.

After deploying, open Fusion's Scripts and Add-Ins dialog, select the add-in, and run it. After redeploying changed
code, stop the add-in and run it again in that dialog, because Fusion keeps the old Python modules loaded until then.

## Check a deployed copy

The fingerprint is a SHA-256 over the installed files: the add-in's files, `lib/addinkit/` and `LICENSE`.
`python3 deploy.py fingerprint <addin>` prints it without installing. Editing `lib/addinkit/` or `LICENSE` changes every
add-in's fingerprint, so redeploy every add-in.

`python3 deploy.py verify <addin>` prints `match` when the deployed
folder has the same fingerprint as this checkout. Otherwise it prints `mismatch` and the files that differ.

Inside Fusion, each command dialog shows a Build line with the first 12 characters of the fingerprint. Compare it
with the first 12 characters printed by `python3 deploy.py fingerprint <addin>`.

## Check an add-in

`python3 deploy.py check <addin>` builds the bundle that `deploy` would install into `.tmp/check/<addin>/` and reports
every problem it finds. It exits with 1 when there are problems and prints each one. It rejects:

- a missing manifest, entry `.py` file or `config.py`;
- an add-in folder that holds `LICENSE` or `lib/addinkit/`, because `deploy.py` adds those;
- files outside the shipped list;
- Python files that do not compile;
- a manifest without a lowercase UUID `id`, or with a non-empty `version`.

On success it prints the file counts and the fingerprint.

## Tests

Run `python3 -m unittest discover` from the repository root. An add-in may carry its own tests in
`addins/<addin>/tests/`. Run them with `python3 -m unittest discover -s "addins/<addin>/tests"`. CI runs both on
Python 3.12 and 3.13, and runs the second command for every add-in that has a `tests/` folder.
Keep the root `lib/` free of an `__init__.py`: `addinkit/__init__.py` imports `adsk`, so discovery must not reach it.

## License

[PolyForm Noncommercial License 1.0.0](LICENSE). The root `LICENSE` covers every add-in. Deploy copies it into each
installed folder.
