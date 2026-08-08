// Demonstrates meta-events: .suspend/.resume raise a reactive
// +!worker[state(suspended)] / +!worker[state(resumed)] achievement
// event (Jason's own convention) carrying the SAME goal literal,
// annotated, through the ordinary event queue -- committed by the same
// Agent._commit_event plan search as any other achievement event.
//
// Plan order below is load-bearing, not stylistic: self.plans buckets
// by (trigger, goal_type, functor, arity) only, NOT by annotation, so
// the unannotated "+!worker <- ..." plan is ALSO applicable when the
// annotated event arrives (Literal.unify_annotated only requires the
// PLAN's own annotations to be found on the event -- zero is trivially
// satisfied). Agent._commit_event tries applicable plans in source
// order, first match wins -- so the two reactive plans are declared
// BEFORE the ordinary worker plan; if they were declared after, the
// ordinary plan would win and spuriously re-run the whole worker body
// instead.
//
// Expected order, and why (worth tracing precisely, not hand-wavy):
// a couple of "worker: tick" lines during the 700ms head start, then
// "start: suspending worker..." -- .suspend sets worker's waiter
// immediately (deterministic, no race), so "worker: suspended" prints
// during the following .wait(500) with no tick able to race it. Then
// "start: resuming worker...", then -- the non-obvious part -- the
// very next "worker: tick N" is GUARANTEED to print before
// "worker: resumed", never after. Reason: .resume clears the waiter
// synchronously but only ENQUEUES the state(resumed) meta-event, which
// needs its own full commit cycle before it's even an intention; every
// top-level intention stack here is appended to the back of
// agent.intentions in creation order (start first, worker second via
// !!worker, the reactive-plan stack only much later, when the
// meta-event actually commits), and step()'s execution phase always
// runs exactly one instruction of the FIRST unblocked stack it finds --
// so worker's stack, being earlier, always wins the turn over the
// freshly-committed reactive stack whenever both are ready. This is a
// structural consequence of insertion order + one-instruction-per-cycle
// scanning, not wall-clock luck -- if "worker: resumed" ever appeared
// BEFORE the next tick, that would indicate a real regression.
!start.

+!worker[state(suspended)] <-
    .print("worker: suspended").

+!worker[state(resumed)] <-
    .print("worker: resumed").

+!start <-
    .print("=== meta-events ===");
    !!worker;
    .wait(700);

    .print("start: suspending worker...");
    .suspend(worker);
    .wait(500);

    .print("start: resuming worker...");
    .resume(worker);
    .wait(1000);
    .print("done.").

+!worker <-
    !heartbeat(0).

+!heartbeat(N) <-
    .print("worker: tick", N);
    .wait(300);
    N2 = N + 1;
    !heartbeat(N2).
