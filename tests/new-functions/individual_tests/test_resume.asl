// Demonstrates .resume: after suspending worker (setup, via .suspend),
// .resume(worker) must make it start ticking again.
//
// .suspend/.resume also raise +!worker[state(suspended)]/[state(resumed)]
// meta-events (see test_meta_events.asl); the two absorbing plans below
// exist only to catch them -- without them they would fall through to
// the ordinary, unannotated +!worker plan below (self.plans buckets by
// functor/arity only, not annotation, so an unannotated plan trivially
// matches an annotated event) and spawn a second, duplicate worker.
!start.

+!worker[state(suspended)] <-
    .print("(worker's suspend meta-event absorbed, ignore)").

+!worker[state(resumed)] <-
    .print("(worker's resume meta-event absorbed, ignore)").

+!start <-
    .print("=== .resume ===");
    !!worker;
    .wait(700);

    .print("start: suspending worker (setup)...");
    .suspend(worker);
    .wait(1000);
    .print("start: worker should be silent above this line...");

    .print("start: resuming worker...");
    .resume(worker);
    .wait(1000);
    .print("done -- check above: worker ticks resumed only after 'resuming worker...'.").

+!worker <-
    !heartbeat(0).

+!heartbeat(N) <-
    .print("worker: tick", N);
    .wait(300);
    N2 = N + 1;
    !heartbeat(N2).
