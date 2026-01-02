from niche_elf import ELFFile

elf = ELFFile(0, 64)
elf.add_generic_symbol("mycoolsymbol", 0x1330)
elf.add_function("mycoolhandler", 0x1370)
elf.add_object("mycoolvariable", 0x1480)
elf.write("symbols.o")

# Here is how the pwndbg decompiler integration code uses it
"""
_, elf_path = tempfile.mkstemp(prefix="symbols-", suffix=".elf")
# Assuming the binary starts with the executable .text section.
elf = niche_elf.ELFFile(self._connection.binary_base_addr, pwndbg.aglib.arch.ptrbits)
for sym_name, sym_addr in syms_to_add:
 elf.add_generic_symbol(sym_name, sym_addr)

elf.write(elf_path)
inf.add_symbol_file(elf_path, self._connection.binary_base_addr)
"""

# Here is how the pwndbg ks --apply code uses it:
"""
_, elf_path = tempfile.mkstemp(prefix="symbols-", suffix=".elf")
base = pwndbg.aglib.kernel.arch_paginginfo().kbase
elf = niche_elf.ELFFile(base, pwndbg.aglib.arch.ptrbits)
for sym_name, sym_type, sym_addr in syms:
    # I trust bata: bata24/gef.py:create_symboled_elf()
    if sym_type and sym_type in "abcdefghijklmnopqrstuvwxyz":
        bind: int = cast(int, ENUM_ST_INFO_BIND["STB_LOCAL"])
    else:
        bind = cast(int, ENUM_ST_INFO_BIND["STB_GLOBAL"])

    if sym_type in ["T", "t", "W", None]:
        elf.add_function(sym_name, sym_addr, bind=bind)
    else:
        elf.add_object(sym_name, sym_addr, bind=bind)

elf.write(elf_path)
pwndbg.dbg.selected_inferior().add_symbol_file(elf_path, base)
"""
