// Night-shift relief rover: a genuinely separate SPADE agent, spawned by
// the mining site via .create_agent -- not another intention on the
// camp agent the way bot_a/bot_b/bot_c are. It runs entirely
// independently (no messaging back to the site -- see
// test_mining_camp.asl's own notes on why two spade_bdi agents can't
// currently talk to each other). Demonstrates a rover growing its own
// plan library at runtime, the way a real robot might download or learn
// a new inspection routine after being deployed: .add_plan,
// .relevant_plan, .list_plans.
!start.

+!start <-
    .print("nightshift unit: powering up, reporting for duty.");
    // Teach this rover a brand-new plan at runtime, from a plain string
    // -- nothing here was written into this .asl file ahead of time.
    // .add_plan parses it and adds it to the plan library exactly as if
    // it had been present from the start.
    .add_plan("@deep_scan +!scan : true <- .print(\"nightshift unit: deep-scanning for a rich seam...\").");
    .print("nightshift unit: checking the new technique made it into the plan library...");
    // Confirm the newly learned plan is really there before relying on
    // it -- .relevant_plan backtracks over every plan whose trigger
    // matches "+!scan", which right now is exactly the one just added.
    for (.relevant_plan("+!scan", P)) {
        .print("nightshift unit: learned ->", P)
    };
    // Now that the technique is confirmed learned, actually use it once...
    !scan;
    // ...then settle into an independent patrol loop for the rest of the
    // night, on its own timeline, with no further reference to the
    // day-shift rovers or the site's own controller.
    !patrol(0).

+!patrol(N) <-
    .print("nightshift unit: on duty, patrol", N);
    .wait(600);
    N2 = N + 1;
    !patrol(N2).
