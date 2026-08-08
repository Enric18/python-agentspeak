// Demonstrates that .desire sees a goal that is still only a pending,
// uncommitted event -- something .intend structurally cannot do. !ev1
// and !ev2 are both initial goals, enqueued in source order before the
// agent ever steps. ev1's plan is selected (committed) first; its
// context is checked at that exact moment, while ev2's own event is
// still sitting untouched in the queue (ev2's commit is one reasoning
// cycle away). So .desire(ev2) must succeed and .intend(ev2) must fail
// right there, or the plan below would not even be applicable.
!ev1.
!ev2.

+!ev1 : .desire(ev2) & not .intend(ev2) <-
    .print("OK: ev2 is desired (still pending) but not yet an intention").

+!ev1 <-
    .print("ERROR: expected .desire(ev2) true and .intend(ev2) false at ev1's commit time").

+!ev2 <-
    .print("ev2: now running as a committed intention.").
