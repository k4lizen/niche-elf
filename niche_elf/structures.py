"""All the relevant structures are defined here."""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import cast

from elftools.elf.enums import ENUM_E_MACHINE, ENUM_E_TYPE, ENUM_ST_INFO_TYPE


@dataclass
class Symbol:
    """Represents a symbol (function or global variable) in the binary."""

    name: str
    bind: int
    typ: int
    value: int
    size: int

    @classmethod
    def generic(cls, name: str, addr: int, size: int, bind: int) -> Symbol:
        return cls(
            name=name,
            bind=bind,
            # LIEF emits this type, so I trust.
            typ=cast("int", ENUM_ST_INFO_TYPE["STT_COMMON"]),
            value=addr,
            size=size,
        )

    @classmethod
    def function(cls, name: str, addr: int, size: int, bind: int) -> Symbol:
        return cls(
            name=name,
            bind=bind,
            typ=cast("int", ENUM_ST_INFO_TYPE["STT_FUNC"]),
            value=addr,
            size=size,
        )

    @classmethod
    def object(cls, name: str, addr: int, size: int, bind: int) -> Symbol:
        return cls(
            name=name,
            bind=bind,
            typ=cast("int", ENUM_ST_INFO_TYPE["STT_OBJECT"]),
            value=addr,
            size=size,
        )


@dataclass
class Section:
    # `name` is not in the section header, but rather added to the shstrtab.
    name: str
    # `data` is the data of the section (also not in the section header)
    data: bytes
    # https://www.man7.org/linux/man-pages/man5/elf.5.html#:~:text=Section%20header%20%28Shdr
    sh_name: int
    sh_type: int
    sh_flags: int
    sh_addr: int
    # sh_offset is here in the actual order
    sh_size: int
    sh_link: int
    sh_info: int
    sh_addralign: int
    sh_entsize: int
    sh_offset: int = -1  # populated during write()

    def padded_data(self) -> bytes:
        pad_len = (-len(self.data)) % self.sh_addralign
        return self.data + b"\x00" * pad_len

    def packed_header(self) -> bytes:
        if len(self.data) != self.sh_size:
            raise AssertionError(
                f"Section data is not the same size as sh_size for section {self.name} "
                f"({len(self.data)} vs {self.sh_size}).",
            )
        if self.sh_offset == -1:
            raise AssertionError(f"sh_offset in section {self.name} was not initialized.")

        return struct.pack(
            "<IIQQQQIIQQ",
            self.sh_name,
            self.sh_type,
            self.sh_flags,
            self.sh_addr,
            self.sh_offset,
            self.sh_size,
            self.sh_link,
            self.sh_info,
            self.sh_addralign,
            self.sh_entsize,
        )


@dataclass
class SHStrTabEntry:
    name: str
    offset: int = 0


@dataclass
class SHStrTab:
    entries: list[SHStrTabEntry] = field(default_factory=list)
    data: bytes = b"\x00"

    def add(self, name: str) -> int:
        """Add a name and return its offset."""
        offset = len(self.data)
        self.entries.append(SHStrTabEntry(name, offset))
        self.data += name.encode() + b"\x00"
        return offset


class ELFHeader:
    def __init__(self, shoff: int = 0, shnum: int = 0, shstrndx: int = 0) -> None:
        self.e_ident = b"\x7fELF" + bytes([2, 1, 1, 0]) + b"\x00" * 8
        self.e_type = ENUM_E_TYPE["ET_EXEC"]
        self.e_machine = ENUM_E_MACHINE["EM_X86_64"]
        self.e_version = 1
        self.e_entry = 0
        self.e_phoff = 0
        self.e_shoff = shoff
        self.e_flags = 0
        self.e_ehsize = 64
        self.e_phentsize = 0
        self.e_phnum = 0
        self.e_shentsize = 64
        self.e_shnum = shnum
        self.e_shstrndx = shstrndx

    def pack(self) -> bytes:
        return struct.pack(
            "<16sHHIQQQIHHHHHH",
            self.e_ident,
            self.e_type,
            self.e_machine,
            self.e_version,
            self.e_entry,
            self.e_phoff,
            self.e_shoff,
            self.e_flags,
            self.e_ehsize,
            self.e_phentsize,
            self.e_phnum,
            self.e_shentsize,
            self.e_shnum,
            self.e_shstrndx,
        )
