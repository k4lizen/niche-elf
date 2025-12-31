"""All the relevant structures are defined here."""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import cast

from elftools.elf.enums import ENUM_E_MACHINE, ENUM_E_TYPE, ENUM_ST_INFO_BIND, ENUM_ST_INFO_TYPE


@dataclass
class Symbol:
    """Represents a symbol (function or global variable) in the binary."""

    name: str
    bind: int
    typ: int
    size: int = 8
    value: int = 0

    @classmethod
    def function(cls, name: str, addr: int) -> Symbol:
        return cls(
            name=name,
            bind=cast("int", ENUM_ST_INFO_BIND["STB_GLOBAL"]),
            typ=cast("int", ENUM_ST_INFO_TYPE["STT_FUNC"]),
            value=addr,
        )

    @classmethod
    def object(cls, name: str, addr: int) -> Symbol:
        return cls(
            name=name,
            bind=cast("int", ENUM_ST_INFO_BIND["STB_GLOBAL"]),
            typ=cast("int", ENUM_ST_INFO_TYPE["STT_OBJECT"]),
            value=addr,
        )


@dataclass
class SymTabEntry:
    name_offset: int
    bind: int
    typ: int
    shndx: int
    value: int = 0
    size: int = 0
    other: int = 0

    def pack(self) -> bytes:
        """Pack symbol into ELF64 symtab entry (24 bytes)."""
        info = (self.bind << 4) | self.typ
        return (
            self.name_offset.to_bytes(4, "little")
            + info.to_bytes(1, "little")
            + self.other.to_bytes(1, "little")
            + self.shndx.to_bytes(2, "little")
            + self.value.to_bytes(8, "little")
            + self.size.to_bytes(8, "little")
        )


@dataclass
class Section:
    name: str
    type: int
    flags: int = 0
    data: bytes = b""
    align: int = 1
    entsize: int = 0
    link: int = 0
    info: int = 0
    offset: int = 0  # set later
    name_offset: int = 0

    def padded_data(self) -> bytes:
        pad_len = (-len(self.data)) % self.align
        return self.data + b"\x00" * pad_len


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
        self.e_type = ENUM_E_TYPE["ET_REL"]
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
