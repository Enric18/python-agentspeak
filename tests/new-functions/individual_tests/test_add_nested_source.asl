// Demonstrates .add_nested_source(Belief, Source, Result): mirrors
// Jason's own .add_nested_source exactly, including its documented
// provenance-chain example (third case below, reproduced verbatim) --
// an existing source(...) annotation is nested INSIDE the new one
// rather than sitting alongside it, recording who-told-whom, not just
// who last told me. Contrast with .add_annot (test_add_annot.asl),
// which always adds alongside instead of replacing.
!start.

+!start <-
    .add_nested_source(a, jomi, B1);
    .print("OK: .add_nested_source(a,jomi,B1) -> B1 =", B1);

    .add_nested_source([a1,a2], jomi, B2);
    .print("OK: .add_nested_source([a1,a2],jomi,B2) -> B2 =", B2);

    // provenance chain: an existing source is nested, not discarded
    .add_nested_source(a[source(bob)], jomi, B3);
    .print("OK: .add_nested_source(a[source(bob)],jomi,B3) -> B3 =", B3);

    // a non-literal, non-list argument passes through unchanged
    .add_nested_source(42, jomi, B4);
    .print("OK: .add_nested_source(42,jomi,B4) -> B4 =", B4);

    // a wrong expected result should fail to unify, not silently succeed
    if (.add_nested_source(a, jomi, wrong)) {
        .print("ERROR: .add_nested_source(a, jomi, wrong) should NOT have unified")
    } else {
        .print("OK: mismatched result correctly fails to unify")
    };

    .print("done.").
