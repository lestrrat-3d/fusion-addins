from __future__ import annotations

from .gearbox import entry as gearbox


def start(build_label, digest, log):
    gearbox.start(build_label, digest, log)


def stop():
    gearbox.stop()
