// Dulcesol automated warehouse: two ASRS (shelf-retrieval) units and three
// AMRs (mobile delivery robots) work off a shared belief board, exactly the
// same idiom as test_mining_camp.asl -- a reactive plan triggered by
// another intention's own belief addition, not real messaging. Unlike the
// mining camp, the ASRS/AMR "roles" here are not persistent, self-looping
// intentions: an order is a belief, and every step of its life (retrieval,
// dispatch, delivery) is a reactive plan or a one-shot subgoal, triggered
// by the previous step's own belief update. Only the housekeeping
// intentions below (order generator, diagnostics, manifest audit, surge
// watch, scripted incidents) are long-lived, explicitly concurrent
// intentions, the same role Scenario 1's foreman played.
//
// Actions exercised: .desire, .intend (event queue), .drop_event,
// .fail_goal, .succeed_goal, .drop_intention, .suspend, .resume,
// .suspended, .intention, .current_intention, .clone, .send, .create_agent,
// .kill_agent, .add_plan, .relevant_plan, .belief, .setof, .relevant_rules,
// .list_rules, .namespace, .delete, .empty, .reverse, .shuffle, .prefix,
// .suffix, .sublist, .difference, .intersection, .union, .replace,
// .lower_case, .upper_case, .type, .eval, .add_annot, .add_nested_source,
// .version, .set_random_seed, .printf, .save_agent, .at, .list_plans,
// .drop_all_intentions.

// ---------------------------------------------------------------------
// Initial beliefs and rules
// ---------------------------------------------------------------------
amr_status(amr_1, idle).
amr_status(amr_2, idle).
amr_status(amr_3, idle).

rack_zone(asrs_1, croissant).
rack_zone(asrs_1, donut).
rack_zone(asrs_2, bread).
rack_zone(asrs_2, palmera).

// A rule, deliberately: .belief (used in diagnostics, below) asks whether
// something is literally on file; an ordinary query like this one also
// accepts anything derivable from a rule -- the two can disagree, which is
// the whole point of demonstrating both.
available_amr(Amr) :- amr_status(Amr, idle).

// Four orders are already in the pipe the instant the shift starts,
// declared as separate TOP-LEVEL initial goals rather than raised from
// inside +!warehouse_start's own body. This is deliberate, and not just
// stylistic: Environment.build_agent_from_ast enqueues every top-level
// "!goal." synchronously, in source order, during construction -- BEFORE
// the agent ever takes its first step(). That is the one place all four
// of these events genuinely, simultaneously sit in the queue together,
// untouched, before any of them has had a chance to commit. Sequential
// "!!" calls from inside a single plan body cannot reproduce this: each
// step() commits at most one event and then advances at most one
// instruction, so a second "!!" raised right after a first one is never
// actually enqueued until the cycle *after* the first has already
// committed -- structurally too late for the first to ever observe the
// second still queued. (This was verified the hard way: an earlier draft
// of this file tried exactly that, sequential "!!fulfil(...)" calls, and
// the "still just a desire" plan below never once fired.) The technique
// used here instead mirrors this project's own test_pending_desire.asl.
!warehouse_start.
!fulfil(order_0, croissant, truck_1).
!fulfil(order_1, bread, truck_2).
!cancel_watch.
!fulfil(order_2, donut, truck_3).

+!warehouse_start <-
    .version(V);
    .printf("=== Dulcesol warehouse booting (interpreter v%s) ===\n", [V]);
    .set_random_seed(7);  // reproducible demo runs

    // Long-lived housekeeping intentions.
    !!order_generator(10, croissant);
    !!diagnostics;
    !!manifest_audit;
    !!surge_watch;
    !!demo_incidents;
    !!deploy_safety_monitor;

    .at("now +15 s", "+!shift_end");
    .print("warehouse: shift underway, ends in 15s.").

// ---------------------------------------------------------------------
// Order intake: .desire / .intend and .drop_event
// ---------------------------------------------------------------------

// order_0, order_1, cancel_watch and order_2 were all pre-seeded together
// as top-level initial goals above (see the comment there for why), so by
// the time order_0's own event commits -- the second of the five to do
// so, right after warehouse_start itself -- order_1, cancel_watch and
// order_2 are all still sitting, genuinely untouched, in the queue behind
// it. That is the guaranteed moment .desire and .intend can be checked
// against each other and disagree. Declared before the general fallback
// plan below so it is tried first for this specific order.
+!fulfil(order_0, Product, Truck) :
        .desire(fulfil(order_1, bread, truck_2)) & not .intend(fulfil(order_1, bread, truck_2)) <-
    .print("dispatch: confirmed -- order_1 is still just a desire (queued), not yet an intention.");
    +order(order_0, Product, Truck).

// By the same pre-seeding, cancel_watch commits third (after order_0 and
// order_1), with order_2's event still sitting, untouched, in the queue
// behind it. Putting the .drop_event call in the CONTEXT (not the body)
// is what guarantees it runs synchronously, during cancel_watch's own
// commit -- strictly before order_2's event has had any chance to commit.
+!cancel_watch : .drop_event("+!fulfil(order_2, _, _)") <-
    .print("dispatch: order_2 was cancelled by the customer -- removed before any ASRS could claim it.").

// The general case: every other order just becomes a plain belief. The
// ASRS units below react to that belief, not to this goal directly.
+!fulfil(Id, Product, Truck) <-
    +order(Id, Product, Truck).

// ---------------------------------------------------------------------
// ASRS retrieval (reactive: one plan per rack zone)
// ---------------------------------------------------------------------
+order(Id, Product, Truck) : rack_zone(asrs_1, Product) <-
    !!retrieve(asrs_1, Id, Product, Truck).

+order(Id, Product, Truck) : rack_zone(asrs_2, Product) <-
    !!retrieve(asrs_2, Id, Product, Truck).

+!retrieve(Asrs, Id, Product, Truck) <-
    .wait(400);  // simulated shelf-to-buffer time
    .current_intention(IntId);
    // Tag the pallet with which ASRS retrieved it before it is ever
    // asserted -- a pure term utility, no belief-base lookup involved.
    .add_annot(pallet(Id, Product, Truck), source(Asrs), Tagged);
    +Tagged;
    .print(Asrs, "[intention", IntId, "]: retrieved pallet for order", Id, "-> buffer.").

// ---------------------------------------------------------------------
// Dispatcher (reactive: fires whenever a pallet reaches the buffer)
// ---------------------------------------------------------------------

// The plan's own annotation, source(Asrs), has Asrs left free -- matching
// it against the incoming event's actual annotation binds Asrs directly
// from the trigger, the same mechanism the meta-event plans use for
// state(suspended)/state(resumed).
+pallet(Id, Product, Truck)[source(Asrs)] : available_amr(Amr) <-
    -amr_status(Amr, idle);
    +amr_status(Amr, busy);
    // Nested provenance: the pallet already carries source(Asrs); wrap it
    // with a second, outer source(dispatcher) rather than replacing it,
    // mirroring Jason's own a[source(jomi)[source(bob)]] example.
    .add_nested_source(pallet(Id,Product,Truck)[source(Asrs)], dispatcher, Provenance);
    .print("dispatcher: assigning", Amr, "-> pallet", Id, "| provenance =", Provenance);
    !!deliver(Amr, Id, Product, Truck).

// ---------------------------------------------------------------------
// AMR delivery
// ---------------------------------------------------------------------
+!deliver(Amr, Id, Product, Truck) <-
    .print(Amr, ": en route to the buffer for pallet", Id);
    .wait(400);
    .print(Amr, ": loaded pallet", Id, ", heading to", Truck);
    .wait(1500);
    if (true) {
        -pallet(Id, Product, Truck);
        +delivered(Id, Truck);
        -amr_status(Amr, busy);
        +amr_status(Amr, idle);
        .print(Amr, ": delivered pallet", Id, "to", Truck, ". Back to idle.")
    } else {
        // Reachable only if something (fail_goal, below) redirects this
        // intention here instead of letting it finish normally.
        .print(Amr, ": OK -- redirected away from a normal finish (aisle was blocked).");
        -amr_status(Amr, busy);
        +amr_status(Amr, idle)
    }.

// ---------------------------------------------------------------------
// Ongoing order generator -- keeps the pipeline busy for the whole shift.
// ---------------------------------------------------------------------
+!order_generator(N, _) : N > 16 <-
    .print("supervisor: order generator winding down for this shift.").

+!order_generator(N, croissant) <-
    .wait(900);
    !!fulfil(N, croissant, truck_3);
    N2 = N + 1;
    !order_generator(N2, bread).

+!order_generator(N, bread) <-
    .wait(900);
    !!fulfil(N, bread, truck_6);
    N2 = N + 1;
    !order_generator(N2, croissant).

// ---------------------------------------------------------------------
// Diagnostics: .belief, .setof, .relevant_rules, .list_rules, .namespace,
// .type, .eval, .intention
// ---------------------------------------------------------------------
+!diagnostics <-
    .wait(2000);
    .print("=== Diagnostics: rule base ===");
    .list_rules;
    .relevant_rules(available_amr(_), Rules);
    .print("diagnostics: rules relevant to available_amr/1 ->", Rules);

    .print("=== Diagnostics: strict belief check vs. ordinary inference ===");
    if (.belief(amr_status(amr_2, idle))) {
        .print("diagnostics: amr_status(amr_2, idle) is literally on file -- true")
    } else {
        .print("diagnostics: amr_status(amr_2, idle) is NOT literally on file right now")
    };

    .print("=== Diagnostics: namespace probe ===");
    if (.namespace(dulcesol)) {
        .print("ERROR: .namespace should never succeed in this engine")
    } else {
        .print("diagnostics: .namespace correctly fails -- no namespace concept in this engine")
    };

    .print("=== Diagnostics: distinct buffered product types (.setof) ===");
    .setof(Product, pallet(_, Product, _), Types);
    .print("diagnostics: distinct buffered product types ->", Types);

    .print("=== Diagnostics: term inspection (.type) and expression evaluation (.eval) ===");
    .type(pallet(order_0, croissant, truck_1), T1);
    .print("diagnostics: pallet(order_0, croissant, truck_1) is a", T1);
    .type(croissant, T2);
    .print("diagnostics: croissant is a(n)", T2);
    .eval(Ok, (2 + 2) == 4);
    .print("diagnostics: .eval((2+2)==4) ->", Ok);

    .wait(1500);
    .print("=== Diagnostics: intention roll call (.intention) ===");
    for (.intention(Id, State)) {
        .print("  intention", Id, ":", State)
    }.

// ---------------------------------------------------------------------
// Manifest audit: list/set/string utilities
// ---------------------------------------------------------------------
+!manifest_audit <-
    .wait(3200);
    .print("=== Manifest audit: list utilities ===");

    Manifest = [order_0, order_1, order_2, order_3, order_4];
    Loaded = [order_0, order_2];

    .difference(Manifest, Loaded, StillPending);
    .print("manifest: still pending ->", StillPending);

    .intersection(Manifest, [order_2, order_4, order_9], Overlap);
    .print("manifest: overlap with a spot-check list ->", Overlap);

    .union(Loaded, [order_5], AllHandled);
    .print("manifest: union with a late add ->", AllHandled);

    .delete(order_1, Manifest, Trimmed);
    .print("manifest: .delete(order_1, Manifest, _) ->", Trimmed);

    .difference(Loaded, Loaded, NothingLeft);
    if (.empty(NothingLeft)) {
        .print("manifest: .empty confirms a list's difference with itself is empty")
    };

    .reverse(Manifest, Rev);
    .print("manifest: .reverse(Manifest) ->", Rev);

    if (.prefix([order_0, order_1], Manifest)) {
        .print("manifest: [order_0, order_1] is a prefix of the manifest, as expected")
    };
    if (.suffix([order_4], Manifest)) {
        .print("manifest: [order_4] is the manifest's own suffix, as expected")
    };
    if (.sublist([order_1, order_3], Manifest)) {
        .print("manifest: [order_1, order_3] appears, in order, within the manifest")
    };

    .shuffle(Manifest, Shuffled);
    .print("manifest: .shuffle(Manifest) -> (order randomised, same elements) ", Shuffled);

    .print("=== Manifest audit: string utilities (normalising a truck code) ===");
    Messy = "  Truck_2 ";
    .lower_case(Messy, Lowered);
    .replace(Lowered, "_", " ", Cleaned);
    .print("manifest: normalising '", Messy, "' ->", Cleaned);
    .upper_case(Cleaned, Shouted);
    .print("manifest: shouted form ->", Shouted).

// ---------------------------------------------------------------------
// Surge watch: .clone, .send (real messaging), .kill_agent
//
// The message targets .deliver(...) directly, not .fulfil(...): .fulfil
// would cascade through the whole order/pallet/dispatcher reactive chain,
// which depends on amr_status and rack_zone beliefs as they stood at the
// exact instant of cloning -- a snapshot, not a live view of the real
// warehouse. Routing through it was originally dropped because it
// triggered a "term not ground" crash, at the time blamed on that
// snapshot being somehow stale/racy -- that diagnosis was wrong. The
// actual cause was two real bugs in .clone's own plan-rendering path
// (agentspeak.runtime.plan_to_str/Plan.str_context and plan.args, see
// runtime.py), both since fixed; the dispatcher's own plan -- inherited
// by amr_backup unchanged -- now renders and re-parses correctly, so the
// crash is gone regardless of which goal the message targets. .deliver
// is kept anyway, not as a workaround: it is still the simpler, more
// self-contained way to demonstrate that amr_backup inherited a full,
// working copy of the plan library, not just a name, without also
// depending on amr_status/rack_zone exactly as they stood at cloning
// time.
// ---------------------------------------------------------------------
+!surge_watch <-
    .wait(4500);
    .print("=== Surge watch: bringing on a temporary backup unit ===");
    .clone(amr_backup);
    .wait(500);
    .print("dispatcher: briefing amr_backup on a surge delivery via a real message...");
    .send("amr_backup@localhost", achieve, deliver(amr_backup, order_backup, palmera, truck_5));
    .wait(3000);
    .print("dispatcher: surge has cleared -- standing amr_backup down.");
    .kill_agent("amr_backup").

// ---------------------------------------------------------------------
// Scripted incidents: .fail_goal, .succeed_goal, .drop_intention,
// .suspend / .resume / .suspended
// ---------------------------------------------------------------------
+!demo_incidents <-
    .wait(2500);
    .print("=== Incident 1: blocked aisle -- .fail_goal redirects amr_2 ===");
    !!deliver(amr_2, order_3, donut, truck_4);
    .wait(700);
    .print("supervisor: amr_2 reports the aisle to truck_4 is blocked by a fallen pallet.");
    .fail_goal(deliver(amr_2, order_3, donut, truck_4));
    +order(order_3, donut, truck_4);  // back into the ordinary pipeline for reassignment

    .wait(1200);
    .print("=== Incident 2: manual hand-off -- .succeed_goal for amr_3 ===");
    !!deliver(amr_3, order_4, bread, truck_2);
    .wait(600);
    .print("supervisor: a floor worker carried pallet order_4 to truck_2 by hand.");
    .succeed_goal(deliver(amr_3, order_4, bread, truck_2));

    .wait(1200);
    .print("=== Incident 3: breakdown -- .drop_intention for amr_1 ===");
    !!deliver(amr_1, order_5, croissant, truck_1);
    .wait(300);
    .print("supervisor: amr_1 reports a battery fault mid-route on order_5.");
    .drop_intention(deliver(amr_1, order_5, croissant, truck_1));
    .print("supervisor: order_5's delivery was dropped -- no retry scheduled for this demo.");

    .wait(1200);
    .print("=== Incident 4: aisle conflict -- .suspend / .resume for amr_1 ===");
    !!deliver(amr_1, order_6, bread, truck_7);
    .wait(700);
    .print("supervisor: amr_1 and the backup unit are converging in the same aisle -- pausing amr_1...");
    .suspend(deliver(amr_1, order_6, bread, truck_7));
    if (.suspended(deliver(amr_1, order_6, bread, truck_7), Reason)) {
        .print("supervisor: amr_1 is paused, reason =", Reason)
    };
    .wait(800);
    .print("supervisor: aisle is clear -- resuming amr_1.");
    .resume(deliver(amr_1, order_6, bread, truck_7)).

// ---------------------------------------------------------------------
// Life cycle: .create_agent for a real second SPADE agent
// ---------------------------------------------------------------------
+!deploy_safety_monitor <-
    .print("warehouse: deploying the independent safety-monitor agent...");
    .create_agent("safety_monitor", "test_warehouse_safety_monitor.asl").

// ---------------------------------------------------------------------
// Shift end: .save_agent, .list_plans, .kill_agent, .drop_all_intentions
// ---------------------------------------------------------------------
+!shift_end <-
    .print("=== Shift end ===");
    .save_agent("warehouse_checkpoint.asl", [warehouse_start]);
    .print("warehouse: checkpoint written to warehouse_checkpoint.asl for the next shift.");
    .list_plans("+!deliver(_,_,_,_)");
    .kill_agent("safety_monitor");
    .print("warehouse: closing up -- recalling every desire and intention still on the books.");
    .drop_all_intentions.
