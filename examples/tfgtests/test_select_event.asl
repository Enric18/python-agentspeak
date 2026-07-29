// Shared source for the select_event pluggability demo (see
// test_select_event.py). !a, !b, !c are three initial goals, enqueued
// in this source order before the agent's very first step() ever runs
// (Environment.build_agent_from_ast calls agent.call(..., delayed=True)
// for every initial !goal. in source order, synchronously, during
// construction). A custom select_event picking a different one first
// will visibly commit (and print) these plans in a different order than
// the default FIFO Agent.
!a.
!b.
!c.

+!a <- .print("a").
+!b <- .print("b").
+!c <- .print("c").
