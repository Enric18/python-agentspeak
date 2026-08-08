// Demonstrates the list/set/collection actions: .empty, .reverse,
// .shuffle, .nth, .suffix, .prefix, .sublist, .difference,
// .intersection, .union.
!start.

+!start <-
    .print("=== .empty ===");
    if (.empty([])) { .print("OK: .empty([]) succeeds") } else { .print("ERROR: .empty([]) should succeed") };
    if (.empty([a,b])) { .print("ERROR: .empty([a,b]) should fail") } else { .print("OK: .empty([a,b]) correctly fails") };
    if (.empty("")) { .print("OK: .empty(\"\") succeeds") } else { .print("ERROR: .empty(\"\") should succeed") };
    if (.empty("a")) { .print("ERROR: .empty(\"a\") should fail") } else { .print("OK: .empty(\"a\") correctly fails") };

    .print("=== .reverse ===");
    .reverse([a,b,c], R1);
    .print("OK: .reverse([a,b,c], R1) -> R1 =", R1);
    .reverse("abc", R2);
    .print("OK: .reverse(\"abc\", R2) -> R2 =", R2);

    .print("=== .shuffle ===");
    .shuffle([a,b,c,d,e], Sh);
    .print("OK: .shuffle([a,b,c,d,e], Sh) -> Sh =", Sh);

    .print("=== .nth (pre-existing baseline action) ===");
    .nth(0, [a,b,c], N0);
    .print("OK: .nth(0, [a,b,c], N0) -> N0 =", N0);
    .nth(2, [a,b,c], N2);
    .print("OK: .nth(2, [a,b,c], N2) -> N2 =", N2);

    .print("=== .suffix ===");
    if (.suffix([c], [a,b,c])) { .print("OK: .suffix([c],[a,b,c]) succeeds") } else { .print("ERROR") };
    if (.suffix([a,b], [a,b,c])) { .print("ERROR: .suffix([a,b],[a,b,c]) should fail") } else { .print("OK: .suffix([a,b],[a,b,c]) correctly fails") };
    // With SX left unbound, .suffix backtracks through every suffix of
    // [a,b,c] in turn ([a,b,c], [b,c], [c], []) -- the "for" loop here
    // runs its body once per answer, printing each one as it's found.
    for (.suffix(SX, [a,b,c])) {
        .print("  suffix:", SX)
    };

    .print("=== .prefix ===");
    if (.prefix([a,b], [a,b,c])) { .print("OK: .prefix([a,b],[a,b,c]) succeeds") } else { .print("ERROR") };
    for (.prefix(PX, [a,b,c])) {
        .print("  prefix:", PX)
    };

    .print("=== .sublist ===");
    if (.sublist([b,c], [a,b,c])) { .print("OK: .sublist([b,c],[a,b,c]) succeeds") } else { .print("ERROR") };
    if (.sublist([a,c], [a,b,c])) { .print("ERROR: .sublist([a,c],[a,b,c]) should fail (non-contiguous)") } else { .print("OK: .sublist([a,c],[a,b,c]) correctly fails (non-contiguous)") };
    for (.sublist(SubX, [a,b,c])) {
        .print("  sublist:", SubX)
    };

    .print("=== .difference / .intersection / .union ===");
    .difference([a,b,a,c], [f,e,a,c], Diff);
    .print("OK: .difference([a,b,a,c],[f,e,a,c],Diff) -> Diff =", Diff);
    .intersection([a,b,a,c], [f,e,a,c], Inter);
    .print("OK: .intersection([a,b,a,c],[f,e,a,c],Inter) -> Inter =", Inter);
    .union([a,b,a,c], [f,e], Un);
    .print("OK: .union([a,b,a,c],[f,e],Un) -> Un =", Un);

    .print("done.").
