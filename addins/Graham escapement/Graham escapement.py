from __future__ import annotations

import os

import adsk.core

from . import commands, config
from .lib import addinkit as futil
from .lib.addinkit import fingerprint
from .lib.gen.report import SinkLog


def run(context):
    try:
        root = os.path.dirname(os.path.abspath(__file__))
        try:
            digest = fingerprint.compute(root)
            label = "Build: " + fingerprint.short(digest)
            futil.log(f"escapement fingerprint {digest}", force_console=True)
        except Exception as e:
            digest = None
            label = "Build: unknown"
            futil.log(f"escapement fingerprint failed: {e}", adsk.core.LogLevels.ErrorLogLevel)
        futil.log(f"escapement gallery {config.GALLERY_REVISION}", force_console=True)
        commands.start(label, digest, SinkLog(lambda line: futil.log(line, force_console=True)))
    except:
        futil.handle_error("run")


def stop(context):
    try:
        futil.clear_handlers()
        commands.stop()
    except:
        futil.handle_error("stop")
