import struct
from .symbols import Symbol
from elftools.elf.constants import SH_FLAGS
from elftools.elf.enums import ENUM_E_TYPE, ENUM_E_MACHINE, ENUM_SH_TYPE_BASE

ELFCLASS64 = 2
ELFDATA2LSB = 1


def align(off: int, a: int) -> int:
    return (off + a - 1) & ~(a - 1)


class ELFWriter:
    def __init__(self) -> None:
        self.sections = []
        self.section_names = [""]

    def add_text_section(self, data: bytes) -> None:
        self.sections.append(
            {
                "name": ".text",
                "type": ENUM_SH_TYPE_BASE["SHT_PROGBITS"],
                "flags": SH_FLAGS.SHF_ALLOC | SH_FLAGS.SHF_EXECINSTR,
                "data": data,
                "align": 4,
                "entsize": 0,
                "link": 0,
                "info": 0,
            }
        )

    def add_symbols(self, symbols: list[Symbol]) -> None:
        strtab = b"\x00"
        offsets = {}

        for s in symbols:
            offsets[s.name] = len(strtab)
            strtab += s.name.encode() + b"\x00"

        symtab = b"\x00" * 24
        for s in symbols:
            info = (s.bind << 4) | s.typ
            symtab += struct.pack(
                "<IBBHQQ",
                offsets[s.name],
                info,
                0,
                1,
                s.value,
                s.size,
            )

        self.sections.append(
            {
                "name": ".symtab",
                "type": ENUM_SH_TYPE_BASE["SHT_SYMTAB"],
                "flags": 0,
                "data": symtab,
                "align": 8,
                "entsize": 24,
                "link": 3,
                "info": 1,
            }
        )

        self.sections.append(
            {
                "name": ".strtab",
                "type": ENUM_SH_TYPE_BASE["SHT_STRTAB"],
                "flags": 0,
                "data": strtab,
                "align": 1,
                "entsize": 0,
                "link": 0,
                "info": 0,
            }
        )

    def write(self, path: str) -> None:
        shstrtab = b"\x00"
        name_offsets = {}

        for s in self.sections:
            name_offsets[s["name"]] = len(shstrtab)
            shstrtab += s["name"].encode() + b"\x00"

        shstrtab_name_off = len(shstrtab)
        shstrtab += b".shstrtab\x00"

        offset = 64
        section_offsets = []

        for s in self.sections:
            offset = align(offset, s["align"])
            section_offsets.append(offset)
            offset += len(s["data"])

        shstrtab_off = offset
        offset += len(shstrtab)
        shoff = align(offset, 8)

        shnum = len(self.sections) + 2
        shstrndx = shnum - 1

        elf_header = struct.pack(
            "<16sHHIQQQIHHHHHH",
            b"\x7fELF" + bytes([ELFCLASS64, ELFDATA2LSB, 1, 0]) + b"\x00" * 8,
            ENUM_E_TYPE["ET_REL"],
            ENUM_E_MACHINE["EM_X86_64"],
            1,
            0,
            0,
            shoff,
            0,
            64,
            0,
            0,
            64,
            shnum,
            shstrndx,
        )

        with open(path, "wb") as f:
            f.write(elf_header)

            for s, off in zip(self.sections, section_offsets):
                f.seek(off)
                f.write(s["data"])

            f.seek(shstrtab_off)
            f.write(shstrtab)

            f.seek(shoff)
            f.write(b"\x00" * 64)

            for s, off in zip(self.sections, section_offsets):
                f.write(
                    struct.pack(
                        "<IIQQQQIIQQ",
                        name_offsets[s["name"]],
                        s["type"],
                        s["flags"],
                        0,
                        off,
                        len(s["data"]),
                        s["link"],
                        s["info"],
                        s["align"],
                        s["entsize"],
                    )
                )

            f.write(
                struct.pack(
                    "<IIQQQQIIQQ",
                    shstrtab_name_off,
                    ENUM_SH_TYPE_BASE["SHT_STRTAB"],
                    0,
                    0,
                    shstrtab_off,
                    len(shstrtab),
                    0,
                    0,
                    1,
                    0,
                )
            )
