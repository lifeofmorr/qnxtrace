#!/usr/bin/env python3
"""Build a minimal newc-format initramfs containing a single static /init.
Usage: make_initramfs.py <init-binary> <output.gz>"""
import gzip
import os
import struct
import sys


def newc_entry(name: bytes, data: bytes, mode: int, uid=0, gid=0, nlink=1, mtime=0, ino=1):
    fields = [ino, mode, uid, gid, nlink, mtime, len(data), 0, 0, 0, 0, len(name) + 1, 0]
    header = b"070701" + b"".join(b"%08x" % f for f in fields)
    out = header + name + b"\x00"
    out += b"\x00" * ((4 - len(out) % 4) % 4)
    out += data
    out += b"\x00" * ((4 - len(out) % 4) % 4)
    return out


def main():
    init_path, out_path = sys.argv[1], sys.argv[2]
    with open(init_path, "rb") as f:
        init_data = f.read()
    archive = newc_entry(b"init", init_data, 0o100755, ino=1)
    archive += newc_entry(b"TRAILER!!!", b"", 0, ino=0)
    archive += b"\x00" * ((512 - len(archive) % 512) % 512)
    with gzip.open(out_path, "wb") as f:
        f.write(archive)
    print(f"wrote {out_path}: {os.path.getsize(out_path)} bytes")


if __name__ == "__main__":
    main()
