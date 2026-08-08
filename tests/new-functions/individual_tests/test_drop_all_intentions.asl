// Test for .drop_all_intentions: stops every task the agent is
// currently running, all at once (the blunt version of .drop_intention,
// which only targets one named goal -- see test_drop_intention.asl).
// Expected: only "Starting test...", "About to drop all intentions...",
// and "run_step" print. Neither "ERROR" line ever runs -- both run_step
// (which calls .drop_all_intentions on itself, mid-execution) and
// run_step2 (fired earlier with "!!") are already running intentions by
// the time this fires, and .drop_all_intentions clears them all.
// Notably "Completed start." also never prints -- !start's own
// intention gets wiped out too, since .drop_all_intentions has no way to
// spare the caller.
!start.
+!start <-
    .print("Starting test...");
    !!run_step2;
    !run_step;
    .print("Completed start.").
+!run_step <-
    .print("About to drop all intentions...");
    .print(run_step);
    .drop_all_intentions;   // wipes every running task, including this one and !start's
    .print("ERROR: This line should NOT print because intentions were dropped!").
+!run_step2 <-
    .print("2: ERROR: This line should NOT print because intentions were dropped!").