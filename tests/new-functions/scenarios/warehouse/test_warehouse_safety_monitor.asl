// Safety-monitor rover: a genuinely separate SPADE agent, deployed by the
// warehouse via .create_agent partway through the shift -- not another
// intention on the warehouse agent the way the ASRS/AMR roles are. It runs
// entirely independently (no messaging back to the warehouse -- the same
// env-scoping reason test_mining_camp.asl's own notes already explain).
// Demonstrates growing its own advisory-plan library at runtime and later
// retiring part of it by label: .add_plan, .relevant_plan, .plan_label,
// .remove_plan.
!start.

+!start <-
    .print("safety monitor: online, loading baseline advisory rules.");
    !advisory(clear_aisle);

    .wait(600);
    .print("safety monitor: learning a new de-escalation advisory at runtime...");
    .add_plan("@slow_reroute +!advise(close_pass) : true <- .print(\"safety monitor: advise -- slow to 0.5 m/s and reroute (close pass).\").");
    .print("safety monitor: confirming the new advisory made it into the library...");
    for (.relevant_plan("+!advise(_)", P)) {
        .print("safety monitor: registered advisory ->", P)
    };
    !advise(close_pass);

    .wait(1200);
    .print("safety monitor: firmware update received -- retiring the old blanket-stop advisory.");
    .plan_label(OldPlan, "blanket_stop");
    .print("safety monitor: found the outdated advisory ->", OldPlan);
    .remove_plan("blanket_stop");
    .print("safety monitor: retired -- only the newer, targeted advisories remain.");
    !patrol(0).

@blanket_stop
+!advisory(clear_aisle) <-
    .print("safety monitor: baseline advisory -- full stop on any aisle conflict (superseded later).").

+!patrol(N) <-
    .print("safety monitor: patrol", N, "-- floor nominal.");
    .wait(700);
    N2 = N + 1;
    !patrol(N2).
