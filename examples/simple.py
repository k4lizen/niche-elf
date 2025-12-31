from niche_elf import ELFFile

elf = ELFFile()
elf.add_function("mycoolhandler", 0x1337)
elf.add_global("mycoolvariable", 0x1448)
elf.write("symbols.o")
