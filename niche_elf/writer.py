"""Handles crafting a minimal ELF file using structured classes."""

from pathlib import Path
from typing import cast

from elftools.elf.constants import SH_FLAGS
from elftools.elf.enums import ENUM_SH_TYPE_BASE

from . import datatypes
from .structures import ELFHeader, Section, SHStrTab, Symbol

ELFCLASS64 = 2
ELFDATA2LSB = 1

ENUM_SH_TYPE = ENUM_SH_TYPE_BASE


def align(offset: int, alignment: int) -> int:
    return (offset + alignment - 1) & ~(alignment - 1)


class ELFWriter:
    """Main ELF file builder."""

    def __init__(self, ptrbits: int) -> None:
        if ptrbits not in {32, 64}:
            raise AssertionError(f"ptrbits must be 32 or 64, but is {ptrbits}")

        self.ElfEhdr = {32: datatypes.ElfEhdr32, 64: datatypes.ElfEhdr64}[ptrbits]
        self.ElfPhdr = {32: datatypes.ElfPhdr32, 64: datatypes.ElfPhdr64}[ptrbits]
        self.ElfShdr = {32: datatypes.ElfShdr32, 64: datatypes.ElfShdr64}[ptrbits]
        self.ElfSym = {32: datatypes.ElfSym32, 64: datatypes.ElfSym64}[ptrbits]
        # self.ElfRel = {32: datatypes.ElfRel32, 64: datatypes.ElfRel64}[ptrsize]
        # self.ElfLinkMap = {32: datatypes.ElfLinkMap32, 64: datatypes.ElfLinkMap64}[ptrsize]

        null_section = Section(
            "doesntmatter",
            b"",
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            1,
            0,
            0,
        )
        self.sections: list[Section] = [null_section]
        self.shstrtab = SHStrTab()

    def add_text_section(self, data: bytes, addr: int = 0) -> None:
        name_offset = self.shstrtab.add(".text")
        sec = Section(
            name=".text",
            sh_name=name_offset,
            sh_type=cast("int", ENUM_SH_TYPE["SHT_PROGBITS"]),
            sh_flags=SH_FLAGS.SHF_ALLOC | SH_FLAGS.SHF_EXECINSTR,
            sh_addr=addr,
            sh_size=len(data),
            sh_link=0,
            sh_info=0,
            sh_addralign=4,
            sh_entsize=0,
            data=data,
        )
        self.sections.append(sec)

    def add_symbols(self, symbols: list[Symbol]) -> None:
        strtab = b"\x00"
        name_offsets = {}
        for s in symbols:
            name_offsets[s.name] = len(strtab)
            strtab += s.name.encode() + b"\x00"

        symtab_entries = [
            self.ElfSym(
                st_name=0,
                st_value=0,
                st_size=0,
                bind=0,
                typ=0,
                st_other=0,
                st_shndx=0,
            ),
        ] + [
            self.ElfSym(
                st_name=name_offsets[s.name],
                st_value=s.value,
                st_size=s.size,
                bind=s.bind,
                typ=s.typ,
                st_other=0,
                st_shndx=1,  # Sucks that we are hardcoding, this is .text
            )
            for s in symbols
        ]

        # We add symtab then strtab,
        # so the strtab index = len(self.sections) - 1 + 2
        strtab_index = len(self.sections) + 1

        symtab_data = b"".join(bytes(e) for e in symtab_entries)
        symtab_name_offset = self.shstrtab.add(".symtab")
        symtab_sec = Section(
            name=".symtab",
            sh_name=symtab_name_offset,
            sh_type=cast("int", ENUM_SH_TYPE["SHT_SYMTAB"]),
            sh_flags=0,
            sh_addr=0,
            sh_size=len(symtab_data),
            sh_link=strtab_index,
            # See System V specific part of ELF.
            # > A symbol table section's sh_info section header member holds
            # > the symbol table index for the first non-local symbol.
            # FIXME: Check does GDB actually look at this?
            sh_info=1,
            sh_addralign=8,
            sh_entsize=24,
            data=symtab_data,
        )
        self.sections.append(symtab_sec)

        strtab_name_offset = self.shstrtab.add(".strtab")
        strtab_sec = Section(
            name=".strtab",
            sh_name=strtab_name_offset,
            sh_type=cast("int", ENUM_SH_TYPE["SHT_STRTAB"]),
            sh_flags=0,
            sh_addr=0,
            sh_size=len(strtab),
            sh_link=0,
            sh_info=0,
            sh_addralign=1,
            sh_entsize=0,
            data=strtab,
        )
        self.sections.append(strtab_sec)

    def write(self, path: str) -> None:
        # compute offsets
        offset = 64  # ELF header size
        # Set offsets (but skip the NULL section)
        for sec in self.sections[1:]:
            offset = align(offset, sec.sh_addralign)
            sec.sh_offset = offset
            offset += len(sec.padded_data())

        shstrtab_sec_name_offset: int = self.shstrtab.add(".shstrtab")
        shstrtab_sec = Section(
            name=".shstrtab",
            sh_name=shstrtab_sec_name_offset,
            sh_type=cast("int", ENUM_SH_TYPE["SHT_STRTAB"]),
            sh_flags=0,
            sh_addr=0,
            sh_offset=offset,
            sh_size=len(self.shstrtab.data),
            sh_link=0,
            sh_info=0,
            sh_addralign=8,
            sh_entsize=0,
            data=self.shstrtab.data,
        )
        offset += len(shstrtab_sec.data)

        shoff = align(offset, 8)
        shnum = len(self.sections) + 1  # all + shstrtab
        shstrndx = shnum - 1

        header = ELFHeader(shoff=shoff, shnum=shnum, shstrndx=shstrndx)

        with Path(path).open("wb") as f:
            f.write(header.pack())

            # write sections (but skip the NULL section)
            for sec in self.sections[1:]:
                f.seek(sec.sh_offset)
                f.write(sec.padded_data())

            # write shstrtab
            f.seek(shstrtab_sec.sh_offset)
            f.write(shstrtab_sec.data)

            # write section headers
            f.seek(shoff)
            for sec in [*self.sections, shstrtab_sec]:
                f.write(sec.packed_header())
