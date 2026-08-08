// Demonstrates .perceive. Under spade_bdi, percept beliefs set from
// outside the agent (BDIBehaviour.set_belief/remove_belief) are applied
// unconditionally on every reasoning cycle -- unlike Jason, where
// perception can run at a lower frequency than reasoning and .perceive
// forces an out-of-cycle catch-up. So this checks: (1) .perceive is safe
// to call with no arguments and does not disturb the surrounding plan,
// and (2) a percept belief fed in from outside the agent (see
// run_perceive.py) is already visible with no .perceive() call needed.
!start.

+!start <-
    .print("start: calling .perceive() as a standalone no-op...");
    .perceive;
    .print("start: .perceive() returned normally, continuing as usual.");
    .wait(1000);
    .print("start: checking for the externally-fed percept belief...");
    if (temperature(T)) {
        .print("OK: percept belief temperature(", T, ") is visible -- no .perceive() call was needed to see it.")
    } else {
        .print("ERROR: percept belief temperature(_) was not found.")
    }.
