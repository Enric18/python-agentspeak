// Demonstrates .suspend: worker ticks in the background; after
// .suspend(worker), it must stop ticking entirely.
//
// .suspend also raises a +!worker[state(suspended)] meta-event (see
// test_meta_events.asl for the feature itself); the two absorbing plans
// below exist only to catch it -- without them it would fall through to
// the ordinary, unannotated +!worker plan below (self.plans buckets by
// functor/arity only, not annotation, so an unannotated plan trivially
// matches an annotated event) and spawn a second, duplicate worker.
!start.

+!worker[state(suspended)] <-
    .print("(worker's suspend meta-event absorbed, ignore)").

+!worker[state(resumed)] <-
    .print("(worker's resume meta-event absorbed, ignore)").

+!start <-
    .print("=== .suspend ===");
    !!worker;
    .wait(700);

    .print("start: suspending worker...");
    .suspend(worker);

    .print("start: waiting 1.5s -- worker must NOT tick during this window...");
    .wait(1500);
    .print("done -- check above: no worker ticks appear after 'suspending worker...'.").

+!worker <-
    !heartbeat(0).

+!heartbeat(N) <-
    .print("worker: tick", N);
    .wait(300);
    N2 = N + 1;
    !heartbeat(N2).
