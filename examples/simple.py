from niche_elf import ELFFile

elf = ELFFile(0, 64)
elf.add_generic_symbol("mycoolsymbol", 0x1330)
elf.add_function("mycoolhandler", 0x1370)
elf.add_object("mycoolvariable", 0x1480)
elf.write("symbols.o")
