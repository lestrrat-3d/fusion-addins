"""Command definition, toolbar button and dialog events for the planetary gearbox command."""

from __future__ import annotations

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


def start(build_label, digest, log):
    global _build_label, _digest, _log
    _build_label = build_label
    _digest = digest
    _log = log
    cmd_def = ui.commandDefinitions.addButtonDefinition(config.CMD_ID, config.CMD_NAME, config.CMD_DESCRIPTION, "")
    futil.add_handler(cmd_def.commandCreated, command_created)
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
    dialog.sync_dependent_inputs(args.inputs)
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
    try:
        build.build_gearbox(design, p, log)
    except Exception as e:
        args.executeFailed = True
        args.executeFailedMessage = str(e)
        log.write("error", [("message", str(e))])
        futil.log(traceback.format_exc(), adsk.core.LogLevels.ErrorLogLevel, force_console=True)
        futil.handle_error("execute")


def command_destroy(args: adsk.core.CommandEventArgs):
    local_handlers.clear()
