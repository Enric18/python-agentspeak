// Demonstrates .type(Term, Type): backtracks through every type that
// applies to Term, most primitive first, mirroring Jason's own
// .type(argument,type) -- a single query in place of testing
// .atom/.literal/.list/.number/.string/.structure/.ground one at a
// time. Also demonstrates the check-mode form (Type already bound).
!start.

+!start <-
    .print("=== enumerate mode (Type unbound) ===");
    for (.type(42, T)) { .print("42 ->", T) };            // number, ground
    for (.type(foo, T)) { .print("foo ->", T) };           // atom, literal, structure, ground
    for (.type(foo(1,2), T)) { .print("foo(1,2) ->", T) }; // literal, structure, ground (not atom: has args)
    for (.type("hello", T)) { .print("hello ->", T) };     // string, ground
    for (.type([1,2,3], T)) { .print("[1,2,3] ->", T) };   // list, structure, ground
    for (.type(X, T)) { .print("X (unbound) ->", T) };     // free (only)

    .print("=== check mode (Type bound) ===");
    if (.type(foo, atom)) {
        .print("OK: .type(foo, atom) succeeds")
    } else {
        .print("ERROR: .type(foo, atom) should succeed")
    };
    if (.type(foo, list)) {
        .print("ERROR: .type(foo, list) should NOT succeed")
    } else {
        .print("OK: .type(foo, list) correctly fails")
    };

    .print("done.").
