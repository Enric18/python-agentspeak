// Test for .drop_desire(Goal): cancels only the one named desire,
// leaving every other running/pending goal alone -- contrast with
// .drop_all_desires (test_drop_all_desires.asl), which wipes everything.
// Here run_step drops itself; run_step2 is a separate, unrelated goal
// and is NOT targeted, so it should run to completion normally.
// Expected: run_step's own last line never prints, but run_step2's does.
!start.
+!start <-
    .print("Starting test...");
    !!run_step2;   // unrelated goal -- .drop_desire(run_step) below will not touch it
    !run_step;     // this one cancels itself partway through
    .print("Completed start.").
+!run_step <-
    .print(run_step);
    .print("About to drop desire...");
    .drop_desire(run_step);   // cancels only this desire -- the next line never runs
    .print("ERROR: This line should NOT print because desires was dropped!").
+!run_step2 <-
    .print(run_step2);
    .print("Runstep2: This line should print").