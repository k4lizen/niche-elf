# add-symbol-file notes

Okay so the idea is that we craft a minimal ELF file that contains a bunch of symbols that we want to add to a given binary, and then use the GDB `add-symbol-file` command.

## Debugging

I use this: https://github.com/horsicq/XELFViewer (maybe look into this https://apps.kde.org/de/elf-dissector/ ?). I have added the binary to PATH and named it `elfview`.

GDB has these settings:
```
set debug symtab-create 1000
set debug symfile on
set debug symbol-lookup on
```
but they are franky useless.

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

### e_machine and architecture mismatch

The ELF file format specifies two interesting fields in the ELF header. `e_machine` which specifies the CPU architecture and `e_ident[EI_CLASS]` which specifies a 32 or 64-bit ELF file. I think `e_ident[EI_CLASS]` does not actually have to be the same as the target CPU architecture, but I can easily emit both so it's better safe than sorry.

When I was using EI_CLASS pointing to 64-bit ELF, but trying out some random e_machine values, I had the following issues:

+ The symbols get resolved to 32-bit addresses (the st_value gets cut off).
+ I can set a breakpoint on a symbol but execution does not actually stop there
+ SIGILL gets triggered during execution (possibly related to the line above?)

mahaloz pointed out that GDB likes it when you pass in the ELF for the host machine, rather than the target, which is wild. But truly, both him and bata use gcc to create a blank ELF that is valid for the current host. I tested using x86_64 + ELFCLASS64 for:
1. Debugging x86_64 binary on x86_64 host.
2. Debugging aarch32 binary on x86_64 host.
3. Debugging aarch64 binary on aarch64 host.

And it all seems to work. So for now I am pinning the ELF to be x86_64 + ELFCLASS64 until we encounter an actual issue.


## Bata's design decisions

He actually passes an address to `add-symbol-file`. I see no actual benefit to doing this.

Also he keeps .data and .bss but none of the symbols reference them.

Read his reasoning here: https://github.com/pwndbg/niche-elf/issues/5 . Using relative offsets and passing an `ADDR` allows him to reuse (i.e. not have to regenerate) the same ELF for different KASLR runs.

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

## Debugging "file format not recognized"

I had a bug where I was crafting malformed ELFCLASS32 files (https://github.com/pwndbg/niche-elf/commit/67f61dc4aef76da39453fffe710d4a187886a1c9). This is really a pain to debug, so I will outline the steps here.

We will be crafting an aarch32 ELFCLASS32 elf file. To eliminate potential issues with mismatching the ELF and the actual target architecture, we will debug an actual aarch32 binary.

I am on a x86_64 host. First compile the arm binary:
```bash
zig cc main.c --target=arm-linux-musleabi -o mainarm -static
llvm-strip mainarm
```
Now we can run the binary like this:
```bash
qemu-arm -g 1234 mainarm
```
and connect to it like this:
```bash
gdb mainarm
pwndbg> tar rem :1234
```
Now to test niche-elf creating an aarch32 ELFCLASS32 file we will leverage the pwndbg decompiler integration, so we have something realistic (actually we do it because I'm too lazy to get a better setup). First, edit `niche_elf/__init__.py:ELFFile:__init__()` to set these two variables to their new values:
```python
        ptrbits = 32
        zig_target_arch = "arm"
```
(we find the correct zig_target_arch string by checking `niche_elf/util.py:zig_target_arch_to_elf()`). Now open the binary in a decompiler like `ida mainarm` and run decomp2dbg with Ctrl+Shift+D.

Next we put this into the pwndbg `pyproject.toml` in the `[tool.uv.sources]` section.
```
niche-elf = { path = "/path/to/niche-elf/", editable=true}
```
And rerun `uv sync --all-extras --all-groups` to make pwndbg temporarily track the local edits in niche-elf. Then we make a temporary edit in `pwndbg/integration/__init__.py:update_symbols()` to print the path of the ELF file, and to not have it deleted:
```python
        print("[+] written elf to ", elf_path) # <--- added this line
        inf.add_symbol_file(elf_path, self._connection.binary_base_addr)
        self._latest_symbol_file_path = elf_path
        # Delete the file after GDB closes the file descriptor.
        # os.unlink(elf_path)                  # <--- commented this line
```

Cool, now we start a debugging session with qemu-user as described above. And after connecting we run `di sync`. Now the symbol file will be created, we will know the name, and it will not be deleted. We expect a gdb.error exception with "file format not recognized". We copy the file to a local folder
```bash
cp /tmp/symbols-qhfb5a4a.elf ./forarm
```
and exit. We can check the ELF out with `elfview forarm`.

Now we are going to debug GDB, so it's important to have a debug build of it. See here how to build it: https://pwndbg.re/dev/contributing/setup-pwndbg-dev/#running-with-gdb . If you `sudo make install`ed it, it should be in `/usr/local/bin/gdb`, while the distro-package-installed version should be in `/usr/bin/gdb`.

Start a debugging session as described before:
```bash
# one terminal
qemu-arm -g 1234 mainarm

# another terminal
/usr/local/bin/gdb --nx mainarm
(gdb) tar rem :1234
```
You can check that doing `add-symbol-file mainarm` does in fact give you the error. Now lets attach to that GDB with pwndbg:
```bash
echo 0 | sudo tee /proc/sys/kernel/yama/ptrace_scope
gdb /usr/local/bin/gdb
pwndbg> attachp gdb
pwndbg> b bfd_check_format
pwndbg> continue
```
And now actually run the command to trigger the breakpoint:
```bash
(gdb) add-symbol-file mainarm
# The breakpoint in pwndbg> should be hit now.
```
GDB performs this check by trying the ELF against all the targets it supports, and sees if anything sticks. You can see what target is currently being attempted with `p abfd->xvec`. The actual checks are dispatched by the `BFD_SEND_FMT` calls inside `bfd_check_format`. This will go into a function that is called `elf_object_p` in the code, but exposed as two symbols `bfd_elf64_object_p` and `bfd_elf32_object_p` in the debugger. This function performs the ELF checks. Btw "BFD" refers to ELF files, it is short for Binary File Descriptor. Since we know which target we want to match, we can set a breakpoint on it with:
```bash
pwndbg> b bfd_elf32_object_p if abfd->xvec == &arm_elf32_le_vec
# le is little endian
# elf32 is ELFCLASS32
# arm is aarch32
# Note: The breakpoint that I actually used is
# b bfd/elfcode.h:536 if abfd->xvec == &arm_elf32_le_vec
pwndbg> continue
```
Now we simply step through the code and see where we hit a `goto got_wrong_format_error;` or a `goto got_no_match;` and figure out what is wrong from there, the code is actually quite nicely commented.

## Performance issues

Currently creating an ELF for the linux kernel takes around 15.7s for niche-elf (pwndbg/pwndbg/commands/klookup.py:klookup) and 1.6s for the objcopy method (bata24/gef.py:create_symboled_elf).
