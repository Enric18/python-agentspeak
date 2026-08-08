// Demonstrates .drop_event actually removing a still-pending, not-yet-
// committed event from the event queue. !ev1 and !ev2 are both initial
// goals, enqueued in source order before the agent ever steps. Plan
// selection for !ev1 runs synchronously as part of !ev1's own commit
// (the very first reasoning cycle) -- putting .drop_event in ev1's
// context guard, rather than its body, runs it exactly there, before
// ev2's own event has had any chance to commit (that needs a whole
// separate, later reasoning cycle). A body placement can't guarantee
// this: the event queue drains one event per cycle regardless of what
// a plan body is doing, so a body-level .drop_event risks losing the
// race to ev2's own commit. If .drop_event works, ev2's plan never
// runs at all.
!ev1.
!ev2.

+!ev1 : .drop_event("+!ev2") <-
    .print("ev1: dropped the still-pending ev2 event.").

+!ev2 <-
    .print("ERROR: ev2 should never run -- its pending event should have been dropped by ev1").
