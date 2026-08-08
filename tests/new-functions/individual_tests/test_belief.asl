// Demonstrates .belief(Bel): queries the belief base directly, excluding
// rules and rule-derived inference (unlike an ordinary query, which also
// consults rules).
b(X) :- a(X).

!start.

+!start <-
    +a(1);
    .print("start: added belief a(1); b(X) :- a(X) is a rule.");

    if (.belief(a(1))) {
        .print("OK: .belief(a(1)) succeeds -- a(1) is a direct belief")
    } else {
        .print("ERROR: .belief(a(1)) should have succeeded")
    };

    if (.belief(b(1))) {
        .print("ERROR: .belief(b(1)) should NOT succeed -- b/1 is only a rule")
    } else {
        .print("OK: .belief(b(1)) correctly fails -- rules are excluded")
    };

    if (b(1)) {
        .print("OK: an ordinary query b(1) succeeds via rule inference")
    } else {
        .print("ERROR: ordinary query b(1) should have succeeded via the rule")
    }.
