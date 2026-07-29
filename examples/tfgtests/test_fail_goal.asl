!start.

+!start <-
    .print("=== Case 1: redirect a foreign intention idle at an if/else ===");
    !!victim;
    .wait(200);
    .print("start: about to fail_goal(victim)");
    .fail_goal(victim);
    .wait(500);

    .print("=== Case 2: fail_goal on the running goal itself stops it ===");
    !!self_stop;
    .wait(500);

    .print("=== Case 3: fail_goal on a buried (nested) goal drops the chain ===");
    !!outer;
    .wait(200);
    .print("start: about to fail_goal(outer)");
    .fail_goal(outer);
    .wait(500);

    .print("start: all cases dispatched.").

+!victim <-
    .print("victim: waiting to see whether fail_goal redirects me...");
    .wait(1500);
    if (true) {
        .print("ERROR (case 1): victim resumed via THEN - fail_goal had no effect")
    } else {
        .print("OK (case 1): victim resumed via ELSE - fail_goal redirected it")
    }.

+!self_stop <-
    .print("self_stop: about to fail_goal on my own running goal");
    .fail_goal(self_stop);
    .print("ERROR (case 2): this line should NOT print, self_stop should have stopped").

+!outer <-
    .print("outer: calling nested inner goal");
    !inner;
    .print("ERROR (case 3): outer should not resume, it was dropped along with inner").

+!inner <-
    .print("inner: doing some work...");
    .wait(3000);
    .print("ERROR (case 3): inner should not resume, outer (and inner) were dropped").
