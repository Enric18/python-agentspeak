// Test for .at(When, Event): schedule Event (given as text, e.g. "+!goal"
// or "+belief") to fire once, later, after a delay described by When
// (e.g. "now +0.6 s"). Four different events are scheduled here, each
// with a different delay -- deliberately out of order (late, mid, early,
// belief) to prove they each really fire on their OWN timer rather than
// in the order they were scheduled.
// Expected order of prints: early_task (~0.2s), mid_task (~0.6s),
// observed_belief (~0.9s), then late_task (~5.2s), each roughly that many
// seconds after the test starts.
!start.

+!start <-
    .print("start: scheduling four .at events...");
    .at("now +5.2 s", "+!late_task");        // fires last
    .at("now +0.6 s", "+!mid_task");
    .at("now +0.2 s", "+!early_task");       // fires first
    .at("now +0.9 s", "+observed_belief");   // schedules a belief ADDITION, not a goal
    .print("start: events scheduled, now waiting for them to fire...");
    .wait(10000);  // long enough for even the 5.2s event to have fired well before this ends
    .print("start: done waiting, test finished.").

+!early_task <-
    .print("OK: early_task fired (~0.2s)").

+!mid_task <-
    .print("OK: mid_task fired (~0.6s)").

+!late_task <-
    .print("OK: late_task fired (~5.2s)").

// This plan reacts to the belief actually being added (+observed_belief),
// not to a goal -- proving .at can schedule belief changes too, not just
// achievement goals.
+observed_belief <-
    .print("OK: observed_belief fired as a belief-addition event (~0.9s)").
