!start.
+!start <-
    .print("Starting test...");
    !!run_step2;
    !run_step;
    .print("Completed start.").
+!run_step <-
    .print("About to drop all intentions...");
    .print(run_step);
    .drop_all_intentions;
    .print("ERROR: This line should NOT print because intentions were dropped!").
+!run_step2 <-
    .print("2: ERROR: This line should NOT print because intentions were dropped!").