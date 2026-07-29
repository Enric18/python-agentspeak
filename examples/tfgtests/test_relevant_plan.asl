// Demonstrates .relevant_plan, the backtracking counterpart of
// .relevant_plans: instead of collecting matches into one list, it
// unifies its second argument with each relevant plan in turn, one per
// backtrack. Jason's own docs show it combined with .findall, but this
// fork's .findall wraps its query argument in a plain belief/rule
// TermQuery that never recognises a nested `.foo(...)` as an action call
// -- a pre-existing limitation, not specific to .relevant_plan -- so a
// `for` loop is used here instead, since `for`'s query *is* built through
// the compiler path that supports action calls.
+!task(X) : X > 0 <- .print("task/positive handling X =", X).
+!task(X) : X <= 0 <- .print("task/non-positive handling X =", X).
+!other <- .print("other handled").

!start.

+!start <-
    .print("=== .relevant_plan (backtracking via for) ===");
    for (.relevant_plan("+!task(_)", P)) {
        .print("relevant plan:", P)
    };

    .print("=== cross-check against .relevant_plans ===");
    .relevant_plans("+!task(_)", Ps2);
    .print("Ps2 =", Ps2);

    .print("done.").
