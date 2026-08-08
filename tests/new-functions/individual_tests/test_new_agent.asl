// Child agent, spawned dynamically by .create_agent.
// It only needs to PRINT: reaching this line proves it started, connected,
// and registered on the XMPP server (start() must succeed before its
// reasoning cycle runs), which is exactly what .create_agent must produce.
//
// We deliberately do NOT .send anything. Under the SPADE 4.x you have
// installed, bdi.py's receive path does `msg.metadata`, which no longer
// exists (it's now _metadata / get_metadata). Sending would crash the
// RECEIVER on that pre-existing library mismatch - unrelated to create_agent.
!start.

+!start <-
    .print("TIER 1 OK - paco is a live, registered SPADE agent; its reasoning cycle is running.").
