// Test for .add_plan: add a plan at runtime, then trigger it.
// Expected output: the "adding" line, then "added_plan_ran", then "done".
// If .add_plan failed, !greet would have no plan and nothing would run for it.
!start.

+!start <-
    .print("add_plan: adding +!greet at runtime...");
    .add_plan("+!greet <- .print(added_plan_ran).");
    .print("add_plan: plan added, now triggering !greet");
    !greet;
    .print("add_plan: done").
