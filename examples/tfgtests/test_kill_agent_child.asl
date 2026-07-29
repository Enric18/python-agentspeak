// Child agent used by test_kill_agent.asl. Heartbeats forever so that,
// watching the output, you can see exactly when a child stops -- and
// reacts to the +jag_shutting_down(Deadline) belief event that
// .kill_agent's optional deadline argument delivers before actually
// stopping the agent.
!start.

+!start <-
    .print("started, beginning heartbeat loop.");
    !heartbeat(0).

+!heartbeat(N) <-
    .print("heartbeat", N);
    .wait(500);
    N2 = N + 1;
    !heartbeat(N2).

+jag_shutting_down(Deadline) <-
    .print("received shutdown signal, stopping in", Deadline, "seconds").
