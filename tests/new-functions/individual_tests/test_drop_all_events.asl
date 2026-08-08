// Demonstrates .drop_all_events clearing every still-pending event at
// once. !ev1, !ev2 and !ev3 are all initial goals, enqueued in source
// order before the agent ever steps. Plan selection for !ev1 runs
// synchronously as part of !ev1's own commit (the very first reasoning
// cycle) -- putting .drop_all_events in ev1's context guard, rather than
// its body, runs it exactly there, before ev2's or ev3's own events have
// had any chance to commit (see test_drop_event.asl for why a body
// placement can't guarantee the same race).
!ev1.
!ev2.
!ev3.

+!ev1 : .drop_all_events <-
    .print("ev1: dropped all pending events.").

+!ev2 <-
    .print("ERROR: ev2 should never run -- it was a pending event, dropped by .drop_all_events").

+!ev3 <-
    .print("ERROR: ev3 should never run -- it was a pending event, dropped by .drop_all_events").
