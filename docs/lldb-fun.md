# Adding symbols to LLDB

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
