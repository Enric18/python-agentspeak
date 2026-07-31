// Test for .succeed_goal(Goal): forces the task working on Goal to stop
// right now and count as SUCCEEDED, as if its plan had finished
// normally -- the positive counterpart of .fail_goal. Two cases:
//   Case 1: a whole separate task (victim) is mid-.wait when we succeed
//     it from outside -- it must stop early instead of finishing its
//     wait and printing its own "ERROR" line.
//   Case 2: a nested goal (inner, running inside outer) is succeeded --
//     this should let outer resume normally afterwards, as if inner had
//     genuinely finished on its own.
!start.

+!start <-
    .print("=== Case 1: succeed a foreign top-level intention early ===");
    !!victim;
    .wait(200);
    .print("start: about to succeed_goal(victim)");
    .succeed_goal(victim);
    .wait(500);

    .print("=== Case 2: succeed a buried goal lets its caller resume ===");
    !!outer;
    .wait(200);
    .print("start: about to succeed_goal(inner)");
    .succeed_goal(inner);
    .wait(500);

    .print("start: all cases dispatched.").

+!victim <-
    .print("victim: about to \"work\" for a while...");
    .wait(3000);
    .print("ERROR (case 1): victim resumed normally, was not succeeded early").

+!outer <-
    .print("outer: calling nested inner goal");
    !inner;
    .print("OK (case 2): outer resumed after inner succeeded early").

+!inner <-
    .print("inner: doing some work...");
    .wait(3000);
    .print("ERROR (case 2): inner resumed normally, was not succeeded early").
