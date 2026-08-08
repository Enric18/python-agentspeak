// Parent agent: creates 'paco' as a real SPADE agent.
!start.

+!start <-
    .print("Main agent starting...");
    .create_agent("paco", "test_new_agent.asl");
    .print("Main agent finished creating paco. Watch for paco's TIER 1 line below.").
