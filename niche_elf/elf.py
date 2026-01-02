"""The main library entrypoint."""

from typing import cast

from elftools.elf.enums import ENUM_ST_INFO_BIND

from .structures import Symbol
from .writer import ELFWriter

DEFAULT_BIND: int = cast("int", ENUM_ST_INFO_BIND["STB_GLOBAL"])


class ELFFile:
    """Represents an ELF file (public API)."""

    def __init__(self, ptrsize: int) -> None:
        """
        Initialize a 32 or 64 bit ELF file.

        Arguments:
            ptrsize: Can either be 32 or 64. Determines the type of the elf file.

        """
        if ptrsize not in {32, 64}:
            raise AssertionError(f"ptrsize must be 32 or 64, but is {ptrsize}")

        self.ptrsize = ptrsize
        self.symbols: list[Symbol] = []
        self.text = b"\x90\x90\x90"

    # I'm not sure whether size=0 or size=ptrsize or whatever makes a difference as a default.
    # I don't observer a difference.

    def add_generic_symbol(
        self,
        name: str,
        addr: int,
        size: int = 0,
        bind: int = DEFAULT_BIND,
    ) -> None:
        """If you don't know whether the symbols is a function or global variable use this."""
        self.symbols.append(Symbol.generic(name, addr, size, bind))

    def add_function(self, name: str, addr: int, size: int = 0, bind: int = DEFAULT_BIND) -> None:
        """Use this if you know the symbol is a function."""
        self.symbols.append(Symbol.function(name, addr, size, bind))

    def add_object(self, name: str, addr: int, size: int = 0, bind: int = DEFAULT_BIND) -> None:
        """Use this if you know the symbols is a global or local variable."""
        self.symbols.append(Symbol.object(name, addr, size, bind))

    def write(self, path: str) -> None:
        writer = ELFWriter(self.ptrsize)

        writer.add_text_section(self.text)
        writer.add_symbols(self.symbols)

        writer.write(path)
