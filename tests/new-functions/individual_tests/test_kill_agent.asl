// Parent agent: creates two children then kills them via .kill_agent --
// one immediately (no deadline), one with a 2s grace-period deadline.
!start.

+!start <-
    .print("main: starting...");
    .create_agent("paco", "test_kill_agent_child.asl");
    .create_agent("pepa", "test_kill_agent_child.asl");
    .wait(1500);

    .print("main: about to kill_agent(paco) immediately, no deadline");
    .kill_agent("paco");

    .print("main: about to kill_agent(pepa, 2) with a 2s deadline");
    .kill_agent("pepa", 2);

    .wait(4000);
    .print("main: done -- paco should have stopped right away; pepa should have printed the shutdown signal, kept heartbeating a bit longer, then stopped too.").
