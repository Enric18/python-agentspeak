// beliefs and rules
amr_status(amr_1, idle).
amr_status(amr_3, idle).
amr_status(amr_2, idle).
rack_zone(asrs_2, palmera).
rack_zone(asrs_1, croissant).
rack_zone(asrs_1, donut).
rack_zone(asrs_2, bread).
order(14, croissant, truck_3).
order(order_1, bread, truck_2).
order(10, croissant, truck_3).
order(order_3, donut, truck_4).
order(order_0, croissant, truck_1).
order(11, bread, truck_6).
order(16, croissant, truck_3).
order(12, croissant, truck_3).
order(15, bread, truck_6).
order(13, bread, truck_6).
pallet(11, bread, truck_6)[source(asrs_2)].
delivered(order_0, truck_1).
delivered(13, truck_6).
delivered(16, truck_3).
delivered(order_1, truck_2).
delivered(order_3, truck_4).
delivered(12, truck_3).
delivered(order_6, truck_7).
delivered(14, truck_3).
delivered(15, truck_6).
delivered(10, truck_3).
available_amr(_X_739_1529597a1d0) :- amr_status(_X_739_1529597a1d0, idle).

// initial goals
!warehouse_start.

// plans
+!warehouse_start : true <- .version(V);
.printf("=== Dulcesol warehouse booting (interpreter v%s) ===\n", [V]);
.set_random_seed(7);
!!order_generator(10, croissant);
!!diagnostics;
!!manifest_audit;
!!surge_watch;
!!demo_incidents;
!!deploy_safety_monitor;
.at("now +15 s", "+!shift_end");
.print("warehouse: shift underway, ends in 15s.").
+!fulfil(order_0, Product, Truck) : (.desire(fulfil(order_1, bread, truck_2)) & (not .intend(fulfil(order_1, bread, truck_2)))) <- .print("dispatch: confirmed -- order_1 is still just a desire (queued), not yet an intention.");
+order(order_0, Product, Truck).
+!fulfil(Id, Product, Truck) : true <- +order(Id, Product, Truck).
+!cancel_watch : .drop_event("+!fulfil(order_2, _, _)") <- .print("dispatch: order_2 was cancelled by the customer -- removed before any ASRS could claim it.").
+order(Id, Product, Truck) : rack_zone(asrs_1, Product) <- !!retrieve(asrs_1, Id, Product, Truck).
+order(Id, Product, Truck) : rack_zone(asrs_2, Product) <- !!retrieve(asrs_2, Id, Product, Truck).
+!retrieve(Asrs, Id, Product, Truck) : true <- .wait(400);
.current_intention(IntId);
.add_annot(pallet(Id, Product, Truck), source(Asrs), Tagged);
+Tagged;
.print(Asrs, "[intention", IntId, "]: retrieved pallet for order", Id, "-> buffer.").
+pallet(Id, Product, Truck)[source(Asrs)] : available_amr(Amr) <- -amr_status(Amr, idle);
+amr_status(Amr, busy);
.add_nested_source(pallet(Id, Product, Truck)[source(Asrs)], dispatcher, Provenance);
.print("dispatcher: assigning", Amr, "-> pallet", Id, "| provenance =", Provenance);
!!deliver(Amr, Id, Product, Truck).
+!deliver(Amr, Id, Product, Truck) : true <- .print(Amr, ": en route to the buffer for pallet", Id);
.wait(400);
.print(Amr, ": loaded pallet", Id, ", heading to", Truck);
.wait(1500);
if (true) {
  -pallet(Id, Product, Truck);
  +delivered(Id, Truck);
  -amr_status(Amr, busy);
  +amr_status(Amr, idle);
  .print(Amr, ": delivered pallet", Id, "to", Truck, ". Back to idle.");
} else {
  .print(Amr, ": OK -- redirected away from a normal finish (aisle was blocked).");
  -amr_status(Amr, busy);
  +amr_status(Amr, idle);
}.
+!order_generator(N, _) : (N > 16) <- .print("supervisor: order generator winding down for this shift.").
+!order_generator(N, croissant) : true <- .wait(900);
!!fulfil(N, croissant, truck_3);
(N2 = (N + 1));
!order_generator(N2, bread).
+!order_generator(N, bread) : true <- .wait(900);
!!fulfil(N, bread, truck_6);
(N2 = (N + 1));
!order_generator(N2, croissant).
+!diagnostics : true <- .wait(2000);
.print("=== Diagnostics: rule base ===");
.list_rules;
.relevant_rules(available_amr(_), Rules);
.print("diagnostics: rules relevant to available_amr/1 ->", Rules);
.print("=== Diagnostics: strict belief check vs. ordinary inference ===");
if (.belief(amr_status(amr_2, idle))) {
  .print("diagnostics: amr_status(amr_2, idle) is literally on file -- true");
} else {
  .print("diagnostics: amr_status(amr_2, idle) is NOT literally on file right now");
};
.print("=== Diagnostics: namespace probe ===");
if (.namespace(dulcesol)) {
  .print("ERROR: .namespace should never succeed in this engine");
} else {
  .print("diagnostics: .namespace correctly fails -- no namespace concept in this engine");
};
.print("=== Diagnostics: distinct buffered product types (.setof) ===");
.setof(Product, pallet(_, Product, _), Types);
.print("diagnostics: distinct buffered product types ->", Types);
.print("=== Diagnostics: term inspection (.type) and expression evaluation (.eval) ===");
.type(pallet(order_0, croissant, truck_1), T1);
.print("diagnostics: pallet(order_0, croissant, truck_1) is a", T1);
.type(croissant, T2);
.print("diagnostics: croissant is a(n)", T2);
.eval(Ok, true);
.print("diagnostics: .eval((2+2)==4) ->", Ok);
.wait(1500);
.print("=== Diagnostics: intention roll call (.intention) ===");
for (.intention(Id, State)) {
  .print("  intention", Id, ":", State);
}.
+!manifest_audit : true <- .wait(3200);
.print("=== Manifest audit: list utilities ===");
(Manifest = [order_0, order_1, order_2, order_3, order_4]);
(Loaded = [order_0, order_2]);
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
  .print("manifest: .empty confirms a list's difference with itself is empty");
};
.reverse(Manifest, Rev);
.print("manifest: .reverse(Manifest) ->", Rev);
if (.prefix([order_0, order_1], Manifest)) {
  .print("manifest: [order_0, order_1] is a prefix of the manifest, as expected");
};
if (.suffix([order_4], Manifest)) {
  .print("manifest: [order_4] is the manifest's own suffix, as expected");
};
if (.sublist([order_1, order_3], Manifest)) {
  .print("manifest: [order_1, order_3] appears, in order, within the manifest");
};
.shuffle(Manifest, Shuffled);
.print("manifest: .shuffle(Manifest) -> (order randomised, same elements) ", Shuffled);
.print("=== Manifest audit: string utilities (normalising a truck code) ===");
(Messy = "  Truck_2 ");
.lower_case(Messy, Lowered);
.replace(Lowered, "_", " ", Cleaned);
.print("manifest: normalising '", Messy, "' ->", Cleaned);
.upper_case(Cleaned, Shouted);
.print("manifest: shouted form ->", Shouted).
+!surge_watch : true <- .wait(4500);
.print("=== Surge watch: bringing on a temporary backup unit ===");
.clone(amr_backup);
.wait(500);
.print("dispatcher: briefing amr_backup on a surge delivery via a real message...");
.send("amr_backup@localhost", achieve, deliver(amr_backup, order_backup, palmera, truck_5));
.wait(3000);
.print("dispatcher: surge has cleared -- standing amr_backup down.");
.kill_agent("amr_backup").
+!demo_incidents : true <- .wait(2500);
.print("=== Incident 1: blocked aisle -- .fail_goal redirects amr_2 ===");
!!deliver(amr_2, order_3, donut, truck_4);
.wait(700);
.print("supervisor: amr_2 reports the aisle to truck_4 is blocked by a fallen pallet.");
.fail_goal(deliver(amr_2, order_3, donut, truck_4));
+order(order_3, donut, truck_4);
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
  .print("supervisor: amr_1 is paused, reason =", Reason);
};
.wait(800);
.print("supervisor: aisle is clear -- resuming amr_1.");
.resume(deliver(amr_1, order_6, bread, truck_7)).
+!deploy_safety_monitor : true <- .print("warehouse: deploying the independent safety-monitor agent...");
.create_agent("safety_monitor", "test_warehouse_safety_monitor.asl").
+!shift_end : true <- .print("=== Shift end ===");
.save_agent("warehouse_checkpoint.asl", [warehouse_start]);
.print("warehouse: checkpoint written to warehouse_checkpoint.asl for the next shift.");
.list_plans("+!deliver(_,_,_,_)");
.kill_agent("safety_monitor");
.print("warehouse: closing up -- recalling every desire and intention still on the books.");
.drop_all_intentions.
