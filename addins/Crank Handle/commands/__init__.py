from __future__ import annotations

from .crankhandle import entry as crankhandle


def start(build_label, digest, log):
    crankhandle.start(build_label, digest, log)


def stop():
    crankhandle.stop()
