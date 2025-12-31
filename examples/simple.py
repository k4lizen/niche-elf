from niche_elf import ELFFile

elf = ELFFile()
elf.add_function("mycoolhandler")
elf.add_object("mycoolvariable")
elf.write("symbols.o")
