from __future__ import annotations

from .plaquestand import entry as plaquestand


def start(build_label, digest, log):
    plaquestand.start(build_label, digest, log)


def stop():
    plaquestand.stop()
