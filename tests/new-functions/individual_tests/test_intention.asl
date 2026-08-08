// Demonstrates .intention(ID, State[, Stack[, current]]): three parallel
// intentions running (start, worker, napper), with napper suspended, so
// running/waiting/suspended states are all visible at once.
//
// .suspend/.resume also raise +!napper[state(suspended)]/[state(resumed)]
// meta-events (see test_meta_events.asl); the two absorbing plans below
// exist only to catch them -- without them they would fall through to
// the ordinary, unannotated +!napper plan below (self.plans buckets by
// functor/arity only, not annotation, so an unannotated plan trivially
// matches an annotated event) and spawn a second, duplicate napper. The
// absorbing intention itself should finish and pop off agent.intentions
// well within the .wait(200) gap before the .intention(I,S) enumeration
// below runs -- timing-dependent in principle, but effectively always
// fine in practice (same framing test_suspended.asl already uses).
!start.

+!napper[state(suspended)] <-
    .print("(napper's suspend meta-event absorbed, ignore)").

+!napper[state(resumed)] <-
    .print("(napper's resume meta-event absorbed, ignore)").

+!start <-
    .print("=== .intention ===");
    !!worker;
    !!napper;
    .wait(300);

    .print("start: suspending napper...");
    .suspend(napper);
    .wait(200);

    .print("=== all intentions: .intention(I, S) ===");
    for (.intention(I, S)) {
        .print("intention", I, "state =", S)
    };

    .print("=== current intention only: .intention(I, S, Stack, current) ===");
    for (.intention(I, S, Stack, current)) {
        .print("current intention", I, "state =", S, "stack =", Stack)
    };

    .print("start: resuming napper...");
    .resume(napper);
    .wait(300);
    .print("done.").

+!worker <-
    !heartbeat(0).

+!heartbeat(N) <-
    .wait(300);
    N2 = N + 1;
    !heartbeat(N2).

+!napper <-
    .wait(5000).
