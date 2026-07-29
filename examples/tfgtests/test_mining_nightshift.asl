// Night-shift relief: a genuinely separate SPADE agent, spawned by the
// camp via .create_agent. Runs independently (no messaging back to the
// camp -- see test_mining_camp.asl's notes on why). Demonstrates growing
// its own plan library at runtime: .add_plan, .relevant_plan, .list_plans.
!start.

+!start <-
    .print("nightshift: reporting for duty.");
    .add_plan("@deep_scan +!scan : true <- .print(\"nightshift: deep-scanning for a rich seam...\").");
    .print("nightshift: checking the new technique made it into the plan library...");
    for (.relevant_plan("+!scan", P)) {
        .print("nightshift: learned ->", P)
    };
    !scan;
    !patrol(0).

+!patrol(N) <-
    .print("nightshift: on duty, patrol", N);
    .wait(600);
    N2 = N + 1;
    !patrol(N2).
