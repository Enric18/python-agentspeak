// Demonstrates .suspended(Goal, Reason): reports true+reason while a
// goal's intention is blocked (whether by .suspend or an ordinary
// .wait), and false once it is not.
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
    .print("=== .suspended ===");
    !!worker;

    .print("start: checking .suspended(worker, R) while worker is merely mid-.wait...");
    if (.suspended(worker, R0)) {
        .print("worker reported blocked, reason =", R0, "(expected: wait, from its own .wait call)")
    } else {
        .print("worker not currently blocked at this exact instant (timing-dependent; harmless)")
    };

    .wait(700);
    .print("start: suspending worker...");
    .suspend(worker);

    if (.suspended(worker, R1)) {
        .print("OK: worker is suspended, reason =", R1)
    } else {
        .print("ERROR: worker should be reported as suspended right after .suspend")
    };

    .print("start: resuming worker...");
    .resume(worker);

    if (.suspended(worker, R2)) {
        .print("ERROR: worker should no longer be reported as suspended after .resume")
    } else {
        .print("OK: worker is no longer suspended")
    };

    .wait(500);
    .print("done.").

+!worker <-
    !heartbeat(0).

+!heartbeat(N) <-
    .print("worker: tick", N);
    .wait(300);
    N2 = N + 1;
    !heartbeat(N2).
