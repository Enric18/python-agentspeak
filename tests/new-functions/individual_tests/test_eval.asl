// Demonstrates .eval(Var, Expr): mirrors Jason's own .eval(term,query)
// for pure logical/arithmetic expressions -- both examples below are
// Jason's own documented examples, reproduced verbatim. Belief-base
// queries as part of Expr are NOT supported (a real scope limit, not a
// bug -- see the action's docstring): this engine compiles action
// arguments as plain terms, never as queries, so Expr can only be
// arithmetic/logical evaluation over already-bound values.
!start.

+!start <-
    .eval(X1, true | false);
    .print("OK: .eval(X1, true | false) -> X1 =", X1);

    .eval(X2, 3<5 & not 4+2<3);
    .print("OK: .eval(X2, 3<5 & not 4+2<3) -> X2 =", X2);

    .eval(X3, 3>5);
    .print("OK: .eval(X3, 3>5) -> X3 =", X3);

    // a wrong expected result should fail to unify, not silently succeed
    if (.eval(false, true | false)) {
        .print("ERROR: .eval(false, true | false) should NOT have unified")
    } else {
        .print("OK: mismatched result correctly fails to unify")
    };

    .print("done.").
