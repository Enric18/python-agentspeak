// Robotic mining site: three autonomous mining robots (rovers) dig
// concurrently. They are NOT three separate agents -- they are three
// parallel intentions running on a single agent, "communicating" the
// idiomatic AgentSpeak way: reactive plans triggered by shared belief
// events (e.g. +ore_deposited(...)), the same way any agent reacts to a
// percept from its environment. A controller intention supervises the
// three rovers, and a real, separate night-shift rover is spawned
// partway through the run via .create_agent -- that one genuinely is a
// second SPADE agent, not just another intention. Everything is torn
// down on a .at-scheduled shift end.
//
// Actions exercised: .create_agent, .kill_agent, .suspend, .resume,
// .suspended, .intention, .current_intention, .fail_goal, .succeed_goal,
// .add_annot, .at, .list_plans, .drop_all_intentions.

!camp_start.

+!camp_start <-
    .print("=== Robotic mining site: powering up ===");
    // Three rovers start digging at the same time, each as its own
    // independent intention (the "!!" is what makes it a separate,
    // fire-and-forget intention rather than a subgoal of camp_start that
    // camp_start would then have to wait for).
    !!dig(bot_a, 10);   // bot_a: ore vein runs dry after 3 loads -- .fail_goal
    !!dig(bot_b, 10);   // bot_b: paused mid-shift for a diagnostic check
    !!dig(bot_c, 10);   // bot_c: recalled early once it's ahead of pace
    !!controller;
    // Schedule the shift-end event 8 (fictional) seconds from now --
    // .at doesn't block anything, it just arranges for +!shift_end to
    // be raised later, on its own, while everything else keeps running.
    .at("now +8 s", "+!shift_end");
    .print("site: shift underway, ends in 8s.").

// ---------------------------------------------------------------------
// Mining rovers
// ---------------------------------------------------------------------

// !dig(Rover, Quota) just kicks off the actual digging loop, starting the
// deposit counter at 0. Splitting this from !dig_loop keeps the "how many
// loads so far" bookkeeping (the Done argument) out of the goal a rover
// is first asked to pursue.
+!dig(Rover, Quota) <-
    !dig_loop(Rover, Quota, 0).

// Base case: quota reached, this rover's digging intention ends cleanly
// here (there is no further !dig_loop call, so the recursion simply
// stops).
+!dig_loop(Rover, Quota, Done) : Done >= Quota <-
    .print(Rover, ": quota reached (", Done, "/", Quota, ") -- powering down.").

// Recursive case: dig one more load, log it as a belief, then call
// !dig_loop again with the counter incremented. This is how an
// AgentSpeak plan expresses a loop -- there is no "while" needed here,
// recursion through a fresh intention step each time does the same job.
+!dig_loop(Rover, Quota, Done) <-
    .wait(700);
    // .current_intention lets a rover report which of its own concurrent
    // intentions is doing the talking -- useful once several rovers'
    // prints are interleaved in the console.
    .current_intention(Id);
    // Done indexes the deposit (0, 1, 2, ...) so each belief added below
    // is distinct -- beliefs live in a set, so an identical term added
    // twice is a no-op and .count would never see more than one.
    .add_annot(ore_deposited(Rover, Done), source(Rover), Report);
    +Report;
    .print(Rover, "[intention", Id, "]: deposited load", Done, ".");
    Done2 = Done + 1;
    !dig_loop(Rover, Quota, Done2).

// Reactive plan: fires every time bot_a deposits ore -- it is triggered
// by the belief addition itself, not called from anywhere. Once bot_a
// has made 3 deposits, its ore vein is declared exhausted and its whole
// digging chain is stopped mid-stream with .fail_goal, in contrast to
// the other two rovers' clean endings below (quota reached, or recalled
// early).
+ore_deposited(bot_a, _) : .count(ore_deposited(bot_a, _), N) & N >= 3 <-
    .print("controller: bot_a's ore vein looks exhausted after", N, "loads -- calling it in.");
    .fail_goal(dig(bot_a, 10)).

// ---------------------------------------------------------------------
// Controller
// ---------------------------------------------------------------------

// The controller intention is the site's own supervisory logic: it
// doesn't dig anything itself, it just watches and occasionally reaches
// into the other rovers' intentions from the outside, by naming the goal
// they are pursuing (dig(bot_b, 10), dig(bot_c, 10)) -- none of these
// actions need a handle or an identifier to be given to them up front.
+!controller <-
    .wait(1500);
    .print("controller: running a diagnostic check -- pausing bot_b...");
    // .suspend blocks bot_b's intention in place (it keeps its exact
    // position in its own dig_loop, nothing is lost) until .resume is
    // called on the same goal later.
    .suspend(dig(bot_b, 10));
    if (.suspended(dig(bot_b, 10), R)) {
        .print("controller: bot_b is paused, reason =", R)
    };

    .wait(1000);
    .print("controller: intention roll call --");
    // .intention backtracks over every intention the agent currently
    // has, one solution per intention, reporting its running/waiting/
    // suspended state -- a live snapshot of what every rover is doing
    // right now.
    for (.intention(Id, State)) {
        .print("  intention", Id, ": ", State)
    };

    .print("controller: all clear -- resuming bot_b.");
    .resume(dig(bot_b, 10));

    .wait(1500);
    .print("controller: bot_c is ahead of pace, recalling it early.");
    // .succeed_goal makes bot_c's digging intention finish as if it had
    // completed normally -- a clean, deliberate early success, not a
    // failure and not an interruption.
    .succeed_goal(dig(bot_c, 10));

    .wait(2000);
    .print("controller: deploying the night-shift relief unit...");
    .create_agent("nightshift", "test_mining_nightshift.asl").
    // nightshift is a genuine, separate SPADE agent from here on: its own
    // reasoning cycle, not wired into this site's shared belief board --
    // it cannot see ore_deposited(...) beliefs the way the three rovers
    // above can, because those are just beliefs of THIS agent.

+!shift_end <-
    .print("=== Shift end ===");
    // Print every plan whose trigger matches +!dig_loop(_,_,_), whatever
    // rovers still happen to be mid-loop at this exact moment -- a debug
    // aid, not something the scenario depends on for correctness.
    .list_plans("+!dig_loop(_,_,_)");
    .kill_agent("nightshift");
    .print("site: closing up -- recalling any rovers still underground.");
    // Deliberately the LAST thing this plan does: .drop_all_intentions
    // also destroys the intention that is running right now, so nothing
    // written after this call would ever execute anyway.
    .drop_all_intentions.
