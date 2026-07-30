// Demonstrates .save_agent(File[, InitialGoals]): writes this agent's
// beliefs, rules and plans to File as valid .asl source, mirroring
// Jason's own .save_agent(file[,initial_goals]). Writes
// save_agent_output.asl into this directory as a generated artifact
// (harmless to delete; regenerated each run) -- a companion Python
// round-trip check (parsing that file back into a fresh, independently
// working agent) was run manually during verification, not repeated
// here since this harness has no assertion mechanism beyond .print.
item(1).
item(2).
p(X) :- item(X).

!start.

+!start <-
    .save_agent("save_agent_output.asl", [go, say(hi)]);
    .print("OK: .save_agent wrote save_agent_output.asl").
