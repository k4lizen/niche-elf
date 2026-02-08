# Adding symbols to LLDB

## Overview

See relevant issues:
+ https://github.com/pwndbg/pwndbg/issues/3595
+ https://github.com/llvm/llvm-project/issues/179839

There are a few potential approaches:
+ `target create`
+ `target modules add`
+ `target symbols add`
+ JSON (https://lldb.llvm.org/use/symbolfilejson.html#usage)

It isn't really clear to me what the differences and implications of the first three approaches are, so `target symbols add` seems most sensible. Unfortunately, as mentioned in https://github.com/llvm/llvm-project/issues/179839 , it does not work. I could probably get the JSON approach to work but I'd be easier from a software engineering perspective if both subsystems used ELF, especially for the use-case of delta/incremental symbolication. Also, why does the JSON approach need a target triple specified.

So, I'm going to try to figure out the LLDB issue.

For debugging program headers, `readelf -l binary` is useful.

## Getting a "proper" symbol file
Get an actual minimal working symbols file for LLDB like this:
```bash
gcc thing.c -o thing
strip --only-keep-debug thing -o thing.bloatedsyms
strip thing -o thing.nosyms
objcopy --remove-section=.note.gnu.property --remove-section=.note.gnu.build-id --remove-section=.interp --remove-section=.gnu.hash --remove-section=.dynsym --remove-section=.dynstr --remove-section=.gnu.version --remove-section=.gnu.version_r --remove-section=.rela.dyn --remove-section=.rela.plt --remove-section=.init --remove-section=.plt --remove-section=.fini --remove-section=.rodata --remove-section=.eh_frame_hdr --remove-section=.eh_frame --remove-section=.note.ABI-tag --remove-section=.init_array --remove-section=.fini_array --remove-section=.dynamic --remove-section=.got --remove-section=.got.plt --remove-section=.data --remove-section=.bss --remove-section=.comment thing.bloatedsyms thing.syms
```
After this you will be left with only the following sections: `NULL`, `.text`, `.symtab`, `.strtab`, `.shstrtab`, which you can verify with `readelf -S thing.syms`.
You can test that this does in fact work with LLDB:
```bash
~❯ lldb thing.nosyms
(lldb) target create "thing.nosyms"
Current executable set to '/thing.nosyms' (x86_64).
(lldb) b main
Breakpoint 1: no locations (pending).
WARNING:  Unable to resolve breakpoint to any actual locations.
(lldb) target symbols add thing.syms -s thing.nosyms
symbol file '/thing.syms' has been added to '/thing.nosyms'
1 location added to breakpoint 1
(lldb) r
Process 29082 launched: '/thing.nosyms' (x86_64)
Process 29082 stopped
* thread #1, name = 'thing.nosyms', stop reason = breakpoint 1.1
    frame #0: 0x00005555555553a4 thing.nosyms`main
thing.nosyms`main:
->  0x5555555553a4 <+0>: pushq  %rbp
    0x5555555553a5 <+1>: movq   %rsp, %rbp
    0x5555555553a8 <+4>: subq   $0x30, %rsp
    0x5555555553ac <+8>: movq   %fs:0x28, %rax
(lldb) ^D
```

But for some god-forsaken reason this does not work with GDB:
```bash
~> gdb --nx thing.nosyms
(gdb) starti
(gdb) info proc mappings
# Both using 0x0000555555554000 (start of objfile)
# and 0x0000555555555000 (start of text segment) doesn't work.
(gdb) add-symbol-file thing.syms 0x0000555555555000
(gdb) b main
Breakpoint 1 at 0x555555555334
(gdb) continue
# ....
```
Clearly the breakpoint was set at the wrong place, and it doesn't stop when it should.

## The program header table
By playing around and comparing the ELF that niche-elf generates versus the one generated like above, I figured out that the problem for LLDB is the lack of a program header table. I added this table and have a working LLDB setup which you can look at on the `lldb-support` branch.

There are lots of hardcoded values on that branch so it won't work in general but if you set the proper values (same as in the reference binary, `thing.syms`) it does work.

There are two huge problems though:
1. It doesn't work with GDB for some reason
2. The text segment program header requires a precise `p_memsz` value.

Regarding the second point: I took this value from `thing.syms`, and using any other value than exactly that one, makes LLDB not work (breakpoints don't work). The problem is that, that value is not even the same one as in `thing` nor `thing.syms` (0x521 in my case). Somehow, `objcopy` sets it (to 0x4a2 in my case), and I don't know based on what. As such, I literarly cannot produce a binary that works for LLDB given an original ELF without invoking `objcopy` (and not invoking `objcopy` is kinda the point of niche-elf).

I am tired of essentially black-box fuzzing GDB's and LLDB's ELF parsers, so I think the only feasible solution at this point is using the JSON solution if we want to support LLDB.
