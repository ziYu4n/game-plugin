#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Small, dependency-free helpers for durable local state files."""

import json
import os
import stat
import tempfile


def atomic_write_json(path, data, *, indent=2, trailing_newline=True):
    """Write JSON beside the destination, then atomically replace it.

    A crash while serializing can only leave a temporary file behind; readers
    continue to see the previous complete JSON document.
    """
    target = os.path.abspath(path)
    folder = os.path.dirname(target)
    os.makedirs(folder, exist_ok=True)

    mode = 0o644
    try:
        mode = stat.S_IMODE(os.stat(target).st_mode)
    except FileNotFoundError:
        pass

    fd, tmp_path = tempfile.mkstemp(
        prefix=".%s." % os.path.basename(target), suffix=".tmp", dir=folder
    )
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=indent)
            if trailing_newline:
                stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp_path, target)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.remove(tmp_path)
        except FileNotFoundError:
            pass
        raise
    return data
