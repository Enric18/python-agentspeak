// Test for .relevant_plans: query the plans relevant to +!task.
// Expected: L is bound to the two labelled task plans (as strings); the +!other
// plan must NOT appear. The task-plan bodies do not run: we only query.
@p1 +!task : true <- .print(p1_body).
@p2 +!task <- .print(p2_body).
+!other <- .print(other_body).

!start.

+!start <-
    .print("relevant_plans: querying +!task");
    .relevant_plans("+!task", L);
    .print("relevant_plans: result = ", L).
