from __future__ import annotations

from .sevensegment import entry as sevensegment


def start(build_label, digest, log):
    sevensegment.start(build_label, digest, log)


def stop():
    sevensegment.stop()
