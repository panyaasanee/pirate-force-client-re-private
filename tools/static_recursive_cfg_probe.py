#!/usr/bin/env python3
"""Read-only recursive CFG decoder for one x86 PE entry point."""

from __future__ import annotations

import argparse
import hashlib
from collections import deque
from pathlib import Path

import pefile
from capstone import CS_ARCH_X86, CS_MODE_32, Cs, CS_GRP_CALL, CS_GRP_JUMP, CS_GRP_RET
from capstone.x86 import X86_OP_IMM


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("entry", type=lambda value: int(value, 0))
    parser.add_argument("--limit", type=lambda value: int(value, 0), default=0x4000)
    args = parser.parse_args()

    image = args.image.read_bytes()
    pe = pefile.PE(data=image, fast_load=True)
    image_base = int(pe.OPTIONAL_HEADER.ImageBase)
    entry_rva = args.entry - image_base
    section = next(
        (
            candidate
            for candidate in pe.sections
            if int(candidate.VirtualAddress)
            <= entry_rva
            < int(candidate.VirtualAddress) + max(int(candidate.Misc_VirtualSize), int(candidate.SizeOfRawData))
        ),
        None,
    )
    if section is None:
        raise RuntimeError(f"entry 0x{args.entry:08X} is outside PE sections")

    section_va = image_base + int(section.VirtualAddress)
    section_start = int(section.PointerToRawData)
    section_size = int(section.SizeOfRawData)
    section_end_va = section_va + section_size

    def va_to_offset(va: int) -> int:
        if not section_va <= va < section_end_va:
            raise ValueError(f"VA 0x{va:08X} leaves entry section")
        return section_start + (va - section_va)

    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True
    pending = deque([args.entry])
    visited: dict[int, object] = {}
    block_starts: set[int] = {args.entry}
    errors: list[str] = []
    indirect_jumps: list[int] = []
    external_jumps: list[tuple[int, int]] = []

    while pending:
        va = pending.popleft()
        while va not in visited:
            if va - args.entry >= args.limit or va < args.entry - args.limit:
                errors.append(f"limit exceeded at 0x{va:08X}")
                break
            try:
                offset = va_to_offset(va)
            except ValueError as exc:
                errors.append(str(exc))
                break
            insns = list(md.disasm(image[offset : offset + 15], va, count=1))
            if not insns or insns[0].address != va:
                errors.append(f"decode failed at 0x{va:08X}")
                break
            insn = insns[0]
            visited[va] = insn
            fallthrough = va + insn.size

            if insn.group(CS_GRP_RET):
                break
            if insn.group(CS_GRP_JUMP):
                target = None
                if insn.operands and insn.operands[0].type == X86_OP_IMM:
                    target = int(insn.operands[0].imm) & 0xFFFFFFFF
                if target is None:
                    indirect_jumps.append(va)
                    break
                if target - args.entry >= args.limit or target < args.entry - args.limit:
                    external_jumps.append((va, target))
                    if insn.mnemonic == "jmp":
                        break
                    block_starts.add(fallthrough)
                    va = fallthrough
                    continue
                block_starts.add(target)
                pending.append(target)
                if insn.mnemonic == "jmp":
                    break
                block_starts.add(fallthrough)
                va = fallthrough
                continue
            va = fallthrough

    if not visited:
        raise RuntimeError("no instructions decoded")
    span_start = min(visited)
    span_end = max(address + instruction.size for address, instruction in visited.items())
    span_offset = va_to_offset(span_start)
    span = image[span_offset : span_offset + (span_end - span_start)]
    covered = sum(instruction.size for instruction in visited.values())
    print(f"ENTRY=0x{args.entry:08X}")
    print(f"SECTION={section.Name.rstrip(bytes((0,))).decode('ascii', errors='replace')}")
    print(f"SPAN=[0x{span_start:08X},0x{span_end:08X})")
    print(f"FILE_OFFSET=0x{span_offset:08X}")
    print(f"SPAN_LEN={len(span)}")
    print(f"SPAN_SHA256={hashlib.sha256(span).hexdigest()}")
    print(f"DECODED_INSTRUCTIONS={len(visited)}")
    print(f"DECODED_BYTES={covered}")
    print(f"SPAN_GAP_BYTES={len(span) - covered}")
    print(f"BASIC_BLOCK_STARTS={len(block_starts)}")
    print(f"INDIRECT_JUMPS={len(indirect_jumps)}")
    print(f"EXTERNAL_JUMPS={len(external_jumps)}")
    for site, target in external_jumps:
        print(f"EXTERNAL_JUMP=0x{site:08X}->0x{target:08X}")
    print(f"DECODE_ERRORS={len(errors)}")
    for error in errors:
        print(f"ERROR={error}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

