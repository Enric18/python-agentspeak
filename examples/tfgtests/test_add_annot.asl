// Demonstrates .add_annot(Belief, Annotation, Result), mirroring Jason's
// own documented examples.
!start.

+!start <-
    .print("start: single-literal .add_annot...");
    .add_annot(a, source(jomi), B);
    .print("OK: B =", B);

    .print("start: list-form .add_annot...");
    .add_annot([a1,a2], source(jomi), L);
    .print("OK: L =", L);

    .print("start: mismatched result should fail to unify...");
    if (.add_annot(a, source(jomi), b[jomi])) {
        .print("ERROR: mismatched result unexpectedly unified")
    } else {
        .print("OK: mismatched result correctly failed to unify")
    };

    .print("start: matching against the expected annotated term...");
    if (.add_annot(a, source(jomi), a[source(jomi)])) {
        .print("OK: result matches a[source(jomi)] as expected")
    } else {
        .print("ERROR: expected match against a[source(jomi)] failed")
    }.
