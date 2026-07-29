// Mining camp: three miners dig concurrently (parallel intentions on one
// agent, "communicating" the idiomatic AgentSpeak way -- reactive plans
// triggered by shared belief events, e.g. +ore_deposited(...)), a foreman
// intention supervises them, and a real, separate night-shift agent is
// spawned partway through via .create_agent. Everything is torn down on
// a .at-scheduled shift end.
//
// Actions exercised: .create_agent, .kill_agent, .suspend, .resume,
// .suspended, .intention, .current_intention, .fail_goal, .succeed_goal,
// .add_annot, .at, .list_plans, .drop_all_intentions.

!camp_start.

+!camp_start <-
    .print("=== Mining camp opening ===");
    !!dig(alice, 10);   // alice: vein runs dry after 3 loads -- .fail_goal
    !!dig(bob, 10);     // bob: paused mid-shift for a safety check
    !!dig(carol, 10);   // carol: called in early once she's ahead of pace
    !!foreman;
    .at("now +8 s", "+!shift_end");
    .print("camp: shift underway, ends in 8s.").

// ---------------------------------------------------------------------
// Miners
// ---------------------------------------------------------------------
+!dig(Miner, Quota) <-
    !dig_loop(Miner, Quota, 0).

+!dig_loop(Miner, Quota, Done) : Done >= Quota <-
    .print(Miner, ": quota reached (", Done, "/", Quota, ") -- packing up.").

+!dig_loop(Miner, Quota, Done) <-
    .wait(700);
    .current_intention(Id);
    // Done indexes the deposit (0, 1, 2, ...) so each belief added below
    // is distinct -- beliefs live in a set, so an identical term added
    // twice is a no-op and .count would never see more than one.
    .add_annot(ore_deposited(Miner, Done), source(Miner), Report);
    +Report;
    .print(Miner, "[intention", Id, "]: deposited load", Done, ".");
    Done2 = Done + 1;
    !dig_loop(Miner, Quota, Done2).

// Reactive plan: fires every time alice deposits ore. Once she's made 3
// deposits, her vein is declared exhausted and her whole mining chain is
// stopped mid-stream with .fail_goal, in contrast to the other two
// miners' clean endings below.
+ore_deposited(alice, _) : .count(ore_deposited(alice, _), N) & N >= 3 <-
    .print("foreman: alice's vein looks exhausted after", N, "loads -- calling it.");
    .fail_goal(dig(alice, 10)).

// ---------------------------------------------------------------------
// Foreman
// ---------------------------------------------------------------------
+!foreman <-
    .wait(1500);
    .print("foreman: safety check -- pausing bob...");
    .suspend(dig(bob, 10));
    if (.suspended(dig(bob, 10), R)) {
        .print("foreman: bob is paused, reason =", R)
    };

    .wait(1000);
    .print("foreman: roll call --");
    for (.intention(Id, State)) {
        .print("  intention", Id, ": ", State)
    };

    .print("foreman: all clear -- resuming bob.");
    .resume(dig(bob, 10));

    .wait(1500);
    .print("foreman: carol's ahead of pace, sending her home early.");
    .succeed_goal(dig(carol, 10));

    .wait(2000);
    .print("foreman: spawning the night-shift relief...");
    .create_agent("nightshift", "test_mining_nightshift.asl").
    // nightshift is a genuine, separate SPADE agent from here on: its own
    // reasoning cycle, not wired into this camp's belief board.

+!shift_end <-
    .print("=== Shift end ===");
    .list_plans("+!dig_loop(_,_,_)");
    .kill_agent("nightshift");
    .print("camp: closing up -- dropping any miners still underground.");
    .drop_all_intentions.
