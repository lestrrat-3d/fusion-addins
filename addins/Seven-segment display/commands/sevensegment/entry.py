"""Command definition, toolbar button and dialog events for the Seven-segment display command."""

from __future__ import annotations

import shutil
import traceback

import adsk.core
import adsk.fusion

from ... import config
from ...lib import addinkit as futil
from ...lib.gen.report import NullLog
from . import dialog

app = adsk.core.Application.get()
ui = app.userInterface

# Local list of event handlers; keeps references so they are not garbage collected.
local_handlers: list = []

_build_label = ""
_digest = None
_log = None
_pending = None  # the parameters of a build waiting for the custom event (config.BUILD_AFTER_COMMAND)
_ready = None  # (parameters, archives, folder) of a build waiting for the build command
_BUILD_EVENT_ID = config.CMD_ID + "_build"
_RUN_CMD_ID = config.CMD_ID + "_run"


def start(build_label, digest, log):
    global _build_label, _digest, _log
    _build_label = build_label
    _digest = digest
    _log = log
    cmd_def = ui.commandDefinitions.addButtonDefinition(config.CMD_ID, config.CMD_NAME, config.CMD_DESCRIPTION, "")
    futil.add_handler(cmd_def.commandCreated, command_created)
    futil.add_handler(app.registerCustomEvent(_BUILD_EVENT_ID), build_requested)
    run_def = ui.commandDefinitions.addButtonDefinition(_RUN_CMD_ID, config.CMD_NAME, config.CMD_DESCRIPTION, "")
    futil.add_handler(run_def.commandCreated, run_created)
    panel = ui.workspaces.itemById(config.WORKSPACE_ID).toolbarPanels.itemById(config.PANEL_ID)
    panel.controls.addCommand(cmd_def, config.COMMAND_BESIDE_ID, False)


def stop():
    global _log
    panel = ui.workspaces.itemById(config.WORKSPACE_ID).toolbarPanels.itemById(config.PANEL_ID)
    control = panel.controls.itemById(config.CMD_ID)
    if control:
        control.deleteMe()
    cmd_def = ui.commandDefinitions.itemById(config.CMD_ID)
    if cmd_def:
        cmd_def.deleteMe()
    app.unregisterCustomEvent(_BUILD_EVENT_ID)
    run_def = ui.commandDefinitions.itemById(_RUN_CMD_ID)
    if run_def:
        run_def.deleteMe()
    if _log is not None:
        _log.close()
        _log = None


def command_created(args: adsk.core.CommandCreatedEventArgs):
    cmd = args.command
    dialog.add_inputs(cmd.commandInputs, _build_label)
    futil.add_handler(cmd.execute, command_execute, local_handlers=local_handlers)
    futil.add_handler(cmd.inputChanged, command_input_changed, local_handlers=local_handlers)
    futil.add_handler(cmd.validateInputs, command_validate_input, local_handlers=local_handlers)
    futil.add_handler(cmd.destroy, command_destroy, local_handlers=local_handlers)


def command_input_changed(args: adsk.core.InputChangedEventArgs):
    dialog.advance_placement_focus(args.inputs, args.input)
    p, err = dialog.read_params(args.inputs)
    dialog.show_status(args.inputs, p, err)


def command_validate_input(args: adsk.core.ValidateInputsEventArgs):
    args.areInputsValid = dialog.read_params(args.inputs)[1] == ""


def command_execute(args: adsk.core.CommandEventArgs):
    # Imported here so the dialog loads without the builders.
    from . import build

    log = _log if _log is not None else NullLog()
    p, err = dialog.read_params(args.command.commandInputs)
    if p is None:
        args.executeFailed = True
        args.executeFailedMessage = err
        return
    design = adsk.fusion.Design.cast(app.activeProduct)
    if design is None:
        args.executeFailed = True
        args.executeFailedMessage = "open a design first"
        return
    if config.BUILD_AFTER_COMMAND:
        # The build runs once the command has ended: an archive import made inside a command handler failed in Fusion
        # (knowledge/performance.md).
        global _pending
        _pending = p
        app.fireCustomEvent(_BUILD_EVENT_ID, "")
        return
    try:
        build.build_display(design, p, log)
    except Exception as e:
        args.executeFailed = True
        args.executeFailedMessage = str(e)
        log.write("error", [("message", str(e))])
        futil.log(traceback.format_exc(), adsk.core.LogLevels.ErrorLogLevel, force_console=True)
        futil.handle_error("execute")


def build_requested(args: adsk.core.CustomEventArgs):
    """Runs after the dialog's command has ended. Phase one makes the archives of the large parts, which opens and closes
    documents; phase two builds in the main design inside a command of its own, so that Undo takes the whole build back
    in one step (`run_execute`)."""
    from . import build

    global _pending, _ready
    p, _pending = _pending, None
    log = _log if _log is not None else NullLog()
    if p is None:
        return
    folder = ""
    try:
        archives = None
        if config.ISOLATE_PARTS:
            archives, folder = build.prepare_archives(p, log)
        _ready = (p, archives, folder)
        if not ui.commandDefinitions.itemById(_RUN_CMD_ID).execute():
            raise RuntimeError("the build command did not start")
    except Exception as e:
        _ready = None
        _fail(log, e, folder)


def run_created(args: adsk.core.CommandCreatedEventArgs):
    futil.add_handler(args.command.execute, run_execute, local_handlers=local_handlers)
    futil.add_handler(args.command.destroy, command_destroy, local_handlers=local_handlers)


def run_execute(args: adsk.core.CommandEventArgs):
    """The build, as one command: one undo step."""
    from . import build

    global _ready
    ready, _ready = _ready, None
    log = _log if _log is not None else NullLog()
    if ready is None:
        return
    p, archives, folder = ready
    try:
        design = adsk.fusion.Design.cast(app.activeProduct)
        if design is None:
            raise RuntimeError("open a design first")
        build.build_display(design, p, log, archives)
    except Exception as e:
        args.executeFailed = True
        args.executeFailedMessage = str(e)
        _fail(log, e, "")
    finally:
        if folder:
            shutil.rmtree(folder, ignore_errors=True)


def _fail(log, e: Exception, folder: str) -> None:
    if folder:
        shutil.rmtree(folder, ignore_errors=True)
    log.write("error", [("message", str(e))])
    futil.log(traceback.format_exc(), adsk.core.LogLevels.ErrorLogLevel, force_console=True)
    ui.messageBox(f"{config.CMD_NAME} failed: {e}")


def command_destroy(args: adsk.core.CommandEventArgs):
    local_handlers.clear()
