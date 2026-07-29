// Demonstrates .list_plans[(TriggerString)]: prints every plan in the
// plan library, or, with an optional trigger-string filter (same format
// as .relevant_plans/.relevant_plan), only the plans relevant to it.
+!task(X) : X > 0 <- .print("task/positive handling X =", X).
+!task(X) : X <= 0 <- .print("task/non-positive handling X =", X).
+!other <- .print("other handled").

!start.

+!start <-
    .print("=== .list_plans (no filter) ===");
    .list_plans;

    .print("=== .list_plans(\"+!task(_)\") (filtered) ===");
    .list_plans("+!task(_)");

    .print("done.").
