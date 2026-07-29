!start.
+!start <-
    .print("Starting test...");
    !!run_step2;
    !run_step;
    .print("Completed start.").
+!run_step : .intend(run_step2)<-
    .print("The two intentions are active").
+!run_step: not .intend(run_step2)<-
    .print("Running step 1...").
+!run_step2 <-
    .print("Running step 2...").
