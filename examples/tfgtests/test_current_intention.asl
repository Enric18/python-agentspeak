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
