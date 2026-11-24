#!/usr/bin/env python3
"""Disassemble one native method from an IL2CPP GameAssembly.dll.

Useful when dump.cs gives you an RVA but the method body matters -- for
example, finding the string literals used to build regexes in a .cctor.

Requires: pip install pefile capstone
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import pefile
    from capstone import Cs, CS_ARCH_X86, CS_MODE_64
    from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_REG_RIP
except ImportError as exc:  # pragma: no cover
    sys.exit(f"missing dependency: {exc.name}; pip install pefile capstone")


def printable(data: bytes) -> bool:
    if not data:
        return False
    allowed = sum(1 for b in data if b in (9, 10, 13) or 32 <= b < 127)
    return allowed / len(data) >= 0.9


def read_cstring(blob: bytes, offset: int, limit: int = 256) -> str | None:
    if offset < 0 or offset >= len(blob):
        return None
    chunk = blob[offset : offset + limit]
    end = chunk.find(b"\x00")
    if end < 0:
        return None
    raw = chunk[:end]
    if len(raw) < 2 or not printable(raw):
        return None
    return raw.decode("ascii", errors="replace")


def rva_to_offset(pe: pefile.PE, rva: int) -> int | None:
    try:
        return pe.get_offset_from_rva(rva)
    except pefile.PEFormatError:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("assembly", type=Path, help="GameAssembly.dll")
    ap.add_argument("rva", help="method RVA from dump.cs, e.g. 0x4190A0")
    ap.add_argument("-n", "--bytes", default="0x400", help="bytes to disassemble")
    ap.add_argument("--no-strings", action="store_true", help="do not resolve string references")
    args = ap.parse_args()

    rva = int(args.rva, 0)
    count = int(args.bytes, 0)
    if count <= 0:
        ap.error("--bytes must be positive")

    pe = pefile.PE(str(args.assembly), fast_load=True)
    blob = args.assembly.read_bytes()
    base = pe.OPTIONAL_HEADER.ImageBase
    file_off = rva_to_offset(pe, rva)
    if file_off is None or file_off + count > len(blob):
        ap.error(f"RVA {rva:#x} maps outside the file")

    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    start_va = base + rva
    for ins in md.disasm(blob[file_off : file_off + count], start_va):
        note = ""
        if not args.no_strings:
            for op in ins.operands:
                target: int | None = None
                if op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP:
                    target = ins.address + ins.size + op.mem.disp
                elif op.type == X86_OP_IMM:
                    target = op.imm
                if target is None:
                    continue
                target_rva = target - base
                if not (0 <= target_rva < len(blob)):
                    continue
                target_off = rva_to_offset(pe, target_rva)
                text = read_cstring(blob, target_off) if target_off is not None else None
                if text:
                    note = f'  ; "{text}" @ {target_rva:#x}'
                    break
        print(f"{ins.address - base:#08x}  {ins.mnemonic:<8} {ins.op_str}{note}")
        if ins.mnemonic == "ret":
            break

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
