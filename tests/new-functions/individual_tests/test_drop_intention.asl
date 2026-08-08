// Test for .drop_intention(Goal): stop only the task working on Goal,
// leaving every other running task alone (unlike .drop_all_intentions,
// which wipes out everything -- see test_drop_all_intentions.asl).
// run_step drops ITSELF (.drop_intention(run_step)), so its own last
// line should never print. run_step2 is a separate, unrelated goal, so
// it is NOT targeted and keeps running normally -- note its print text
// below says "ERROR", but that label is misleading/left over from
// copying test_drop_all_intentions.asl: with .drop_intention (as opposed
// to .drop_all_intentions), run_step2's line SHOULD print, since only
// run_step was named as the goal to drop.
!start.
+!start <-
    .print("Starting test...");
    !!run_step2;   // unrelated goal -- .drop_intention(run_step) below will not touch it
    !run_step;     // this one cancels itself partway through
    .print("Completed start.").
+!run_step <-
    .print("About to drop all intentions...");
    .print(run_step);
    .drop_intention(run_step);  // stops only this task -- the next line never runs
    .print("ERROR: This line should NOT print because intentions were dropped!").
+!run_step2 <-
    .print("2: ERROR: This line should NOT print because intentions were dropped!").