# add-symbol-file notes

Okay so the idea is that we craft a minimal ELF file that contains a bunch of symbols that we want to add to a given binary, and then use the GDB `add-symbol-file` command.

## Debugging

I use this: https://github.com/horsicq/XELFViewer . I have added the binary to PATH and named it `elfview`.

## Issues

While the decompiler symbol syncing works quite well, the kernel is giving lots of trouble. For the decompiler syncing, I don't even have to pass an address to `add-symbol-file`. The absolute addresses are hardcoded into the ELF anyway (the same is true for bata), so it just works™.

I have seen two weird behaviours:

### Wrong address

I problem I've encountered is that `ks commit_creds` shows one address, but after `ks --apply`, `print commit_creds` shows another one. For instance:
```
pwndbg> ks commit_creds
0xffffffff81110ca0 T commit_creds
0xffffffff81fc0efc t commit_creds.cold
pwndbg> p commit_creds
❌️ Cannot access memory at address 0xffffffff02110ca0
```
I checked that in fact, inside the ELF file the address (the value field in the symtab entry) is 0xffffffff81110ca0, so I don't know what is going on. Is it a GDB bug? It happens regardless of the type of the symbol (COMMON vs FUNCTION). In both cases I set the type to GLOBAL (surely this is not the issue).

This problem happens when I **do** pass in the kernel .text address (`0xffffffff81000000` with ASLR off) to `add-symbol-file`. It works correctly when I don't do that. Note that I observe the same behaviour regardless of if my ELF e_type is EXEC or REL.

Ou, I found the issue! `0xffffffff81000000 + 0xffffffff81110ca0 = 0x1ffffffff02110ca0`.

But, accoring to the "Symbol Values" section of https://refspecs.linuxbase.org/elf/elf.pdf . When the ELF is an executable (and shared object file), the st_value field describes a virtual address and not a section offset. I have this issue even when I set `e_type` to EXEC (is that a GDB bug?).

Note that my sh_addr is 0 for .text, but bata uses the correct VMA.

Okay it seems GDB performs this calculation to determine a symbol's address: `ADDR + (st_value - sh_addr)` where `ADDR`is the address passed to the `add-symbol-file` command, `st-value` the symbol address specified in the symtab entry, and `sh_addr` the address specified in the section header table for the `.text` section entry. For example, when I set `sh_addr` of `.text` to `4` and do `p commit_creds` I get `0xffffffff02110c9c`.

When you don't pass in the `ADDR` the `sh_addr` doesn't matter, and a symbol's address is calculated as just `st_value`. :S

So all in all, the safe bet is in fact setting `sh_addr` (because it is required if you want `ADDR` to work, and doesn't do anything if you don't pass `ADDR` in).

### Examine doesn't work

The second issue, is that even if `ks` and `print` show the same address, examining with `x/20i mysym` doesn't show the symbol. Similarly, it doesn't get populated properly in the context disassembly. This works in bata's method and it also works for me in the decompilation view.

```
pwndbg> p commit_creds
$2 = {<text variable, no debug info>} 0xffffffff81110ca0
pwndbg> x/20i commit_creds
   0xffffffff81110ca0:	nop    DWORD PTR [rax+rax*1+0x0]
   0xffffffff81110ca5:	push   r13
   0xffffffff81110ca7:	mov    r13,QWORD PTR gs:0x20bc0
   0xffffffff81110cb0:	push   r12
   0xffffffff81110cb2:	push   rbp
```

This is probably a good sanity test. bata:
```
gef> info symbol commit_creds+0x10
commit_creds + 16 in section .text
```
Us:
```
pwndbg> info symbol commit_creds+0x10
No symbol matches commit_creds+0x10.
```

The root cause of this issue is the same as [[#Offsets not shown in the context]].

### Offsets not shown in the context

This happens even in the decompilation workflow. The problem is simply that the output looks like this:
```
0x555555555060 <start>    endbr64         [...]
0x555555555064 <start>    xor    ebp, ebp [...]
0x555555555066 <start>    mov    r9, rdx  [...]
0x555555555069 <start>    pop    rsi      [...]
```
whereas I would expect `<start>`, `<start+4>`, `<start+6>`...

The root cause of this issue is the same as [[#Examine doesn't work]]. bata24 explained to me that for this to work, I have to set up the sh_size of the `.text` section (he has code for this in gef.py:create_blank_elf()). And indeed, doing that fixes the issue fully.

For GDB to not throw a warning on `add-symbol-file` though, I have to make `.text` a NOBITS section (which makes sense to do anyway).


## Bata is weird

He actually passes an address to `add-symbol-file`. I see no actual benefit to doing this.

Also he keeps .data and .bss but none of the symbols reference them.

## Design choices

### Passing an address

The usage of the `add-symbol-file` command is (GDB 18.0):
```
Usage: add-symbol-file FILE [-readnow|-readnever] [-o OFF] [ADDR] [-s SECT-NAME SECT-ADDR]...
```
but it seems for older versions of GDB (8.x) (re: bata, VmlinuxToElfApplyCommand), the `ADDR` was mandatory.

The `ADDR` is supposed to represent the Virtual Memory Address (VMA) of the `.text` section of the ELF file we are adding. Note that the actual sections of the objfile we are trying to symbolicate don't really matter.

There are a few weird things to mention here. Firstly, there shouldn't be a need/benefit to pass this address because all of our symbol addresses are hardcoded in the ELF file anyway.

Secondly, bata and decomp2dbg always pass in this address.

Thirdly, decomp2dbg actually intentionally leaves in a `.bss` section in the binary, but no symbols actually reference it (they only reference `.text`).

Neither of them really use the `-s` flag with the `add-symbol-file` command (bata, VmlinuxToElfApplyCommand is an exception, but thats because the file we are adding only has a `.kernel` section).

Interestingly, when I DON'T pass an address I don't have the [[#Wrong address]] issue.

Passing in an address also isn't necessary for the [[#Examine doesn't work]] [[#Offsets not shown in the context]] fix.

### ELF type

An ELF file can be one of a few types (determined by the e_type field in the ELF header), namely: REL, EXEC, DYN, and CORE. The LIEF way to craft the file emits an EXEC. Bata also emits an EXEC. I think it doesn't matter because I don't see any noticable difference in behaviour when I try to play around with it.
