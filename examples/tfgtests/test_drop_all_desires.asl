!start.
+!start <-
    .print("Starting test...");
    !!run_step2;
    !run_step;
    .print("Completed start.").
+!run_step <-
    .print(run_step);
    .print("About to drop all desires...");
    .drop_all_desires;
    .print("ERROR: This line should NOT print because desires were dropped!").
+!run_step2 <-
    .print("runstep2: ERROR: This line should NOT print because desires were dropped!").