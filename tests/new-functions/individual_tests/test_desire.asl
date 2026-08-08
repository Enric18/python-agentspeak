// Test for .desire(Goal): checks whether Goal is currently "wanted" by
// the agent -- either still waiting to be picked up (a pending event) or
// already running as an intention (an intention is still a desire being
// pursued). !!run_step2 is fired first (fire-and-forget: !start doesn't
// wait for it), then !run_step -- since events are queued and serviced
// oldest-first, run_step2's event gets its own turn to start running
// BEFORE run_step's own plan is even chosen, so by the time run_step's
// condition is checked, run_step2 is already an active desire (see
// test_pending_desire.asl for the different case where a goal is still
// only *pending*, not yet started, when it's checked).
// Expected: "Starting test...", then "The two desires are active"
// (proving .desire(run_step2) was true), then "Completed start.",
// then "Running step 2..." (run_step2's own plan body, which had
// already started, finishes).
!start.
+!start <-
    .print("Starting test...");
    !!run_step2;
    !run_step;
    .print("Completed start.").
// Two competing plans for the same goal (+!run_step): whichever
// condition (after ":") matches first, in source order, wins. This one
// fires because run_step2 is currently desired (already running).
+!run_step : .desire(run_step2)<-
    .print("The two desires are active").
// Fallback plan -- would fire instead if run_step2 were NOT desired at all.
+!run_step: not .desire(run_step2)<-
    .print("Running step 1...").
+!run_step2 <-
    .print("Running step 2...").
