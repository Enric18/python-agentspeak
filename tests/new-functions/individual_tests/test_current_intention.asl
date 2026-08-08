// Test for .current_intention(Id): while a plan is running, this should
// unify Id with an identifier for the task (intention) currently
// executing that plan -- a way for a plan to "know its own name" from
// the inside, useful together with .intention/.drop_intention elsewhere.
// Expected: prints run_step's own identifier, proving the call works and
// returns something meaningful while the plan is mid-execution.
!start.
+!start <-
    .print("Starting test...");
    !run_step;
    .print("Completed start.").
+!run_step <-
    .print("About to write my intention...");
    .print(run_step);
    .current_intention(CurrentIntention);
    .print("I am currently executing the intention: ", CurrentIntention).
