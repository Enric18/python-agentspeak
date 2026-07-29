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
