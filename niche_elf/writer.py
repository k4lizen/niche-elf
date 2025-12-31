"""Handles crafting a minimal ELF file using structured classes."""

import struct
from pathlib import Path
from typing import cast

from elftools.elf.constants import SH_FLAGS
from elftools.elf.enums import ENUM_SH_TYPE_BASE

from .structures import ELFHeader, Section, SHStrTab, Symbol, SymTabEntry

ELFCLASS64 = 2
ELFDATA2LSB = 1

ENUM_SH_TYPE = ENUM_SH_TYPE_BASE


def align(offset: int, alignment: int) -> int:
    return (offset + alignment - 1) & ~(alignment - 1)


class ELFWriter:
    """Main ELF file builder."""

    def __init__(self) -> None:
        self.sections: list[Section] = []
        self.shstrtab = SHStrTab()

    def add_text_section(self, data: bytes) -> None:
        sec = Section(
            name=".text",
            type=cast("int", ENUM_SH_TYPE["SHT_PROGBITS"]),
            flags=SH_FLAGS.SHF_ALLOC | SH_FLAGS.SHF_EXECINSTR,
            data=data,
            align=4,
        )
        sec.name_offset = self.shstrtab.add(sec.name)
        self.sections.append(sec)

    def add_symbols(self, symbols: list[Symbol]) -> None:
        strtab = b"\x00"
        name_offsets = {}
        for s in symbols:
            name_offsets[s.name] = len(strtab)
            strtab += s.name.encode() + b"\x00"

        symtab_entries = [SymTabEntry(0, 0, 0, 0)] + [
            SymTabEntry(
                name_offset=name_offsets[s.name],
                bind=s.bind,
                typ=s.typ,
                shndx=1,
                value=s.value,
                size=s.size,
            )
            for s in symbols
        ]

        symtab_data = b"".join(e.pack() for e in symtab_entries)
        symtab_sec = Section(
            name=".symtab",
            type=cast("int", ENUM_SH_TYPE["SHT_SYMTAB"]),
            flags=0,
            data=symtab_data,
            align=8,
            entsize=24,
            link=0,  # updated later
            info=1,
        )
        symtab_sec.name_offset = self.shstrtab.add(symtab_sec.name)
        self.sections.append(symtab_sec)

        strtab_sec = Section(
            name=".strtab",
            type=cast("int", ENUM_SH_TYPE["SHT_STRTAB"]),
            flags=0,
            data=strtab,
            align=1,
        )
        strtab_sec.name_offset = self.shstrtab.add(strtab_sec.name)
        self.sections.append(strtab_sec)

        # fix symtab link to strtab index
        symtab_sec.link = len(self.sections) - 1

    def write(self, path: str) -> None:
        # compute offsets
        offset = 64  # ELF header size
        for sec in self.sections:
            offset = align(offset, sec.align)
            sec.offset = offset
            offset += len(sec.padded_data())

        shstrtab_sec_name: str = ".shstrtab"
        shstrtab_sec_name_offset: int = self.shstrtab.add(shstrtab_sec_name)
        shstrtab_sec = Section(
            name=shstrtab_sec_name,
            type=cast("int", ENUM_SH_TYPE["SHT_STRTAB"]),
            data=self.shstrtab.data,
            align=1,
            name_offset=shstrtab_sec_name_offset,
            offset=offset,
        )
        offset += len(shstrtab_sec.data)

        shoff = align(offset, 8)
        shnum = len(self.sections) + 2  # NULL + all + shstrtab
        shstrndx = shnum - 1

        header = ELFHeader(shoff=shoff, shnum=shnum, shstrndx=shstrndx)

        with Path(path).open("wb") as f:
            f.write(header.pack())

            # write sections
            for sec in self.sections:
                f.seek(sec.offset)
                f.write(sec.padded_data())

            # write shstrtab
            f.seek(shstrtab_sec.offset)
            f.write(shstrtab_sec.data)

            # write section headers
            f.seek(shoff)
            f.write(b"\x00" * 64)  # NULL section header
            for sec in [*self.sections, shstrtab_sec]:
                f.write(
                    struct.pack(
                        "<IIQQQQIIQQ",
                        sec.name_offset,
                        sec.type,
                        sec.flags,
                        0,
                        sec.offset,
                        len(sec.data),
                        sec.link,
                        sec.info,
                        sec.align,
                        sec.entsize,
                    ),
                )
