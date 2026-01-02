"""The main library entrypoint."""

from . import datatypes
from .builder import ELFBuilder
from .structures import Symbol

DEFAULT_BIND: int = datatypes.Constants.STB_GLOBAL


class ELFFile:
    """Represents an ELF file (public API)."""

    def __init__(self, textbase: int, ptrbits: int) -> None:
        """
        Initialize a 32 or 64 bit ELF file.

        Arguments:
            textbase: The Virtual Memory Address of the .text section of the file we are
                trying to symbolicate. (there does not need to be an actual ".text" section there)
            ptrbits: Can either be 32 or 64. Determines the type of the elf file.

        """
        if ptrbits not in {32, 64}:
            raise AssertionError(f"ptrbits must be 32 or 64, but is {ptrbits}")

        self.textbase = textbase
        self.ptrsize = ptrbits
        self.symbols: list[Symbol] = []

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
        writer = ELFBuilder(self.ptrsize)

        writer.add_text_section(self.textbase)
        writer.add_symbols(self.symbols)

        writer.write(path)
