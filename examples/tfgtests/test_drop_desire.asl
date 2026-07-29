!start.
+!start <-
    .print("Starting test...");
    !!run_step2;
    !run_step;
    .print("Completed start.").
+!run_step <-
    .print(run_step);
    .print("About to drop desire...");
    .drop_desire(run_step);
    .print("ERROR: This line should NOT print because desires was dropped!").
+!run_step2 <-
    .print(run_step2);
    .print("Runstep2: This line should print").