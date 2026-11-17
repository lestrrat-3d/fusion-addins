from __future__ import annotations

from .onewayclutch import entry as onewayclutch


def start(build_label, digest, log):
    onewayclutch.start(build_label, digest, log)


def stop():
    onewayclutch.stop()
