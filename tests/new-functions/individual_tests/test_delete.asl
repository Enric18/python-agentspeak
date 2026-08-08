// Demonstrates .delete: one action, two arities, dispatching on the
// runtime type of its arguments -- index/range removal from lists or
// strings (numeric arg), value removal from a list (term arg), or
// substring removal from a string (string arg).
!start.

+!start <-
    // 3-arg, value removal (all occurrences) from a list
    .delete(a, [a,b,c,a], L1);
    .print("OK: .delete(a, [a,b,c,a], L1) -> L1 =", L1);

    // 3-arg, index removal from a list (single element at index 0)
    .delete(0, [a,b,c,a], L2);
    .print("OK: .delete(0, [a,b,c,a], L2) -> L2 =", L2);

    // 4-arg, range removal from a list (half-open [start,end))
    .delete(1, 3, [a,b,c,a], L3);
    .print("OK: .delete(1, 3, [a,b,c,a], L3) -> L3 =", L3);

    // 3-arg, substring removal (all occurrences) from a string
    .delete("a", "banana", S1);
    .print("OK: .delete(\"a\", \"banana\", S1) -> S1 =", S1);

    // 3-arg, index removal from a string (single character at index 0)
    .delete(0, "banana", S2);
    .print("OK: .delete(0, \"banana\", S2) -> S2 =", S2);

    // A wrong expected result should fail to unify, not silently succeed
    if (.delete(a, [a,b,c,a], [c])) {
        .print("ERROR: .delete(a, [a,b,c,a], [c]) should NOT have unified")
    } else {
        .print("OK: .delete(a, [a,b,c,a], [c]) correctly fails to unify")
    };

    .print("done.").
