!start.

+!start <-
    .print("start: scheduling four .at events...");
    .at("now +5.2 s", "+!late_task");
    .at("now +0.6 s", "+!mid_task");
    .at("now +0.2 s", "+!early_task");
    .at("now +0.9 s", "+observed_belief");
    .print("start: events scheduled, now waiting for them to fire...");
    .wait(10000);
    .print("start: done waiting, test finished.").

+!early_task <-
    .print("OK: early_task fired (~0.2s)").

+!mid_task <-
    .print("OK: mid_task fired (~0.6s)").

+!late_task <-
    .print("OK: late_task fired (~5.2s)").

+observed_belief <-
    .print("OK: observed_belief fired as a belief-addition event (~0.9s)").
