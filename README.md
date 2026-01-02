# niche-elf

**In development.**

A small library that optimizes some niche ELF operations commonly used by debugger extensions.

Main use-case currently is building an ELF from a list of symbols for the purposes of `add-symbol-file`ing it into the debbuger. This is useful for stuff like [`ks --apply`](https://pwndbg.re/dev/commands/kernel/klookup/#optional-arguments) and syncing symbols for [decompiler integration](https://pwndbg.re/dev/tutorials/decompiler-integration/).

See `examples/simple.py` for usage. Install with `pip install niche-elf`.

### TODO
+ Add an enable_prints and disable_prints() API so the library can choose to print helpful <pending\> messages? maybe not?
+ Make a re-entrant verison which optimizes for symbol updates.
