!start.
+!start <-
    .print("Starting test...");
    !!run_step2;
    !run_step;
    .print("Completed start.").
+!run_step : .desire(run_step2)<-
    .print("The two desires are active").
+!run_step: not .desire(run_step2)<-
    .print("Running step 1...").
+!run_step2 <-
    .print("Running step 2...").
