// Test for .intend(Goal): checks whether Goal is currently running as
// an intention (a real, committed task) -- narrower than .desire, which
// also counts a goal that's merely waiting in the queue (see
// test_desire.asl, same setup). !!run_step2 is fired first, so its event
// gets serviced (turned into a running task) before run_step's own plan
// is even chosen, meaning .intend(run_step2) is already true by the
// time run_step's condition is checked.
// Expected: "Starting test...", then "The two intentions are active",
// then "Completed start.", then "Running step 2...".
!start.
+!start <-
    .print("Starting test...");
    !!run_step2;
    !run_step;
    .print("Completed start.").
// Two competing plans for +!run_step -- the first whose condition
// matches wins. Fires because run_step2 is already a running intention.
+!run_step : .intend(run_step2)<-
    .print("The two intentions are active").
// Fallback -- would fire instead if run_step2 were not yet an intention.
+!run_step: not .intend(run_step2)<-
    .print("Running step 1...").
+!run_step2 <-
    .print("Running step 2...").
