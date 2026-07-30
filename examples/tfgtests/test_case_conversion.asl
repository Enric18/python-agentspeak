// Demonstrates .lower_case/.upper_case: mirrors Jason's own
// .lower_case(S1,S2)/.upper_case(S1,S2). A non-string S1 is converted to
// its string representation first, matching Jason's arg[0].toString()
// fallback (same convention as .replace).
!start.

+!start <-
    .lower_case("CArtAgO", R1);
    .print("OK: .lower_case(\"CArtAgO\", R1) -> R1 =", R1);

    .upper_case("CArtAgO", R2);
    .print("OK: .upper_case(\"CArtAgO\", R2) -> R2 =", R2);

    // non-string argument converts to its string representation first
    .lower_case(item(a,b), R3);
    .print("OK: .lower_case(item(a,b), R3) -> R3 =", R3);

    .upper_case(item(a,b), R4);
    .print("OK: .upper_case(item(a,b), R4) -> R4 =", R4);

    // a wrong expected result should fail to unify, not silently succeed
    if (.lower_case("CArtAgO", "wrong")) {
        .print("ERROR: .lower_case(\"CArtAgO\", \"wrong\") should NOT have unified")
    } else {
        .print("OK: mismatched result correctly fails to unify")
    };

    .print("done.").
