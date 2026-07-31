// Test for .drop_all_desires: wipes out every desire the agent has --
// both goals still waiting in the queue (like run_step2, fired with
// "!!" so it hasn't started yet) AND goals already running as an
// intention (like run_step itself, which is mid-execution when it calls
// this). Belief events are left untouched (a desire is a goal, not a
// belief change) -- not exercised directly here.
// Expected: neither "ERROR" line below should ever print -- run_step
// cancels itself the moment it calls .drop_all_desires, and run_step2
// never gets the chance to start at all.
!start.
+!start <-
    .print("Starting test...");
    !!run_step2;
    !run_step;
    .print("Completed start.").
+!run_step <-
    .print(run_step);
    .print("About to drop all desires...");
    .drop_all_desires;   // cancels this very intention too -- nothing after this line runs
    .print("ERROR: This line should NOT print because desires were dropped!").
+!run_step2 <-
    .print("runstep2: ERROR: This line should NOT print because desires were dropped!").