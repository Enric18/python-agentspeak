// Demonstrates .printf(Format, Arg0[, Arg1, ...]): mirrors Jason's own
// .printf, format directives ported unchanged since Java's and Python's
// printf-style syntax are the same C-derived directives. Unlike Jason's
// own docs, %d is safe to use here with a plain Python int/float --
// see the action's docstring for why Jason's own "don't use %d" warning
// doesn't carry over.
!start.

+!start <-
    .printf("plain string, no directives");
    .printf("value: %d", 461012);
    .printf("value: %08.0f", 461012);
    .printf("value: %10.3f", 3.14159);
    .printf("%s and %s", hello, "world");
    .print("done.").
