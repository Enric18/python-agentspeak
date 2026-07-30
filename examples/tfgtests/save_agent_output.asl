// beliefs and rules
item(2).
item(1).
p(_X_94a_1b697c72b10) :- item(_X_94a_1b697c72b10).

// initial goals
!go.
!say(hi).

// plans
+!start : true <- .save_agent("save_agent_output.asl", [go, say(hi)]);
.print("OK: .save_agent wrote save_agent_output.asl").
