from __future__ import annotations

from .escapement import entry as escapement


def start(build_label, digest, log):
    escapement.start(build_label, digest, log)


def stop():
    escapement.stop()
