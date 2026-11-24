"""Build a part in its own small design and import it, so the main design's timeline stays short.

The time a Fusion feature takes grows with the length of the timeline (knowledge/performance.md): about 20 ms plus
0.4 to 0.5 ms for each timeline item already there. A part built in a new design sees a timeline of its own few dozen
items. It is exported as a Fusion archive and imported into its container's component, which adds one timeline item to
the main design. The imported component keeps the part's feature history.

All the archives are made first, before anything is built in the main design: making one opens a new document and
returns to the main one, and a Fusion object of the main design held across that was found deleted afterwards
(knowledge/performance.md). `export_all` returns the archives; `import_part` imports one.

# Deviation: the gallery builds every part in one document (docs/sevensegment/deviations.md, "Isolated parts").
"""

from __future__ import annotations

import dataclasses
import os
import typing

import adsk.core
import adsk.fusion

from . import fusion

if typing.TYPE_CHECKING:
    from .build import BuildContext

PART_SUFFIX = " part"  # the name of the component an imported part lands in, after the body's name

# The parts built in their own design: the large ones. The first body of each kind that is copied (the yellow flag body,
# the black bodies, a pivot block, a nut, the bolts of each length; `parts.first_of_each_kind`) is built in its own design
# too. The copies and the bearings are made in the main design.
ISOLATED: frozenset[str] = frozenset({
    "Top Plate", "Cradle Plate", "Guide Plate", "Front Wall", "Rear Wall", "Spring", "Shaft", "Hub", "Rotor", "Housing",
    "Button",
    *(f"Cam {c}" for c in "ABCDEFG"), *(f"Slider {c}" for c in "ABCDEFG"),
})

_IDENTITY = ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


class Unavailable(RuntimeError):
    """The part could not be made in a separate design; nothing was added to the main design."""


def wants(name: str) -> bool:
    return name in ISOLATED


def export_all(ctx: BuildContext, build: typing.Callable[[BuildContext, str], adsk.fusion.BRepBody],
               names: typing.Iterable[str], folder: str) -> dict[str, str]:
    """Build each of `names` with `build(ctx, name)` in a design of its own and export it to `folder`. Returns the
    archive paths by name. A part that could not be exported is left out and logged, and is built in the main design.
    The main design is the active document again when this returns, and no object of it may be used from before the
    call."""
    app = adsk.core.Application.get()
    home = app.activeDocument
    out: dict[str, str] = {}
    for name in names:
        scratch = None
        try:
            try:
                scratch = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
                design = adsk.fusion.Design.cast(app.activeProduct)
                design.designType = adsk.fusion.DesignTypes.ParametricDesignType
            except Exception as e:
                raise Unavailable(f"{name}: no new design: {e}") from e
            # The part is built at the identity, so a move needs no placement conjugation, and nothing is shared.
            root = design.rootComponent
            sctx = dataclasses.replace(ctx, comp=root, top=root, placement_axes=_IDENTITY, container_comps={},
                                       shared={}, part=name)
            body = build(sctx, name)
            body.name = name
            path = os.path.join(folder, f"{len(out)}.f3d")
            try:
                if not design.exportManager.execute(design.exportManager.createFusionArchiveExportOptions(path)):
                    raise RuntimeError("export returned false")
            except Exception as e:
                raise Unavailable(f"{name}: export failed: {e}") from e
            out[name] = path
        except Unavailable as e:
            ctx.log.write("isolate", [("part", name), ("error", str(e)), ("result", "FALLBACK")])
        finally:
            _close(scratch, home)
    return out


def import_part(ctx: BuildContext, name: str, path: str) -> adsk.fusion.BRepBody:
    """Import the archive of `name` into the current component (`ctx.comp`) and return its body there. Raises
    `Unavailable` when the import added nothing usable."""
    try:
        app = adsk.core.Application.get()
        before = ctx.comp.occurrences.count
        res = app.importManager.importToTarget2(app.importManager.createFusionArchiveImportOptions(path), ctx.comp)
        if res is None or ctx.comp.occurrences.count != before + 1:
            raise RuntimeError("the import added no component")
        occ = ctx.comp.occurrences.item(ctx.comp.occurrences.count - 1)
        occ.component.name = name + PART_SUFFIX
        if occ.component.bRepBodies.count != 1:
            raise RuntimeError(f"the imported component has {occ.component.bRepBodies.count} bodies, expected 1")
        return occ.component.bRepBodies.item(0)
    except Exception as e:
        raise Unavailable(f"{name}: import failed: {e}") from e


def _close(scratch: adsk.core.Document | None, home: adsk.core.Document) -> None:
    """Close the scratch document without saving, and make the main design the active one again."""
    try:
        if scratch is not None:
            scratch.close(False)
    finally:
        home.activate()
