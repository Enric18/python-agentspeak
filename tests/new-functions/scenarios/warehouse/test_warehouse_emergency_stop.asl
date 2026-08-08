// Demonstrates .drop_desire / .drop_all_desires: an emergency stop that
// clears every queued order and in-flight delivery in one motion. Kept as
// its own small, standalone test (run via the fast agentspeak.runtime
// harness, no SPADE needed) rather than folded into test_warehouse.asl,
// because triggering a real emergency stop partway through the main
// integrated run would truncate everything after it -- the opposite of
// what an integrated test is for. The "still just a desire, not yet an
// intention" half of .desire/.intend is already demonstrated precisely,
// with the exact commit-time-context technique this needs to be reliable,
// by test_warehouse.asl's own order_0/order_1 pair; this file focuses on
// what is genuinely new here: .drop_all_desires reaching a real, running
// delivery intention and clearing it out entirely.

rack_zone(asrs_1, croissant).
amr_status(amr_1, idle).

!start.

+!start <-
    !!fulfil(order_a, croissant, truck_1);
    !!emergency_stop.

+!fulfil(Id, Product, Truck) <-
    +order(Id, Product, Truck).

+order(Id, Product, Truck) : rack_zone(asrs_1, Product) <-
    !!retrieve(asrs_1, Id, Product, Truck).

+!retrieve(Asrs, Id, Product, Truck) <-
    .wait(200);
    +pallet(Id, Product, Truck).

+pallet(Id, Product, Truck) : amr_status(amr_1, idle) <-
    -amr_status(amr_1, idle);
    +amr_status(amr_1, busy);
    !!deliver(amr_1, Id, Product, Truck).

+!deliver(Amr, Id, Product, Truck) <-
    .print(Amr, ": delivering", Id, "-- long haul, should never finish in this test.");
    .wait(5000);
    .print("ERROR:", Amr, "should have been dropped by the emergency stop before this line.").

+!emergency_stop <-
    .wait(600);
    .print("=== Before the stop: roll call ===");
    for (.intention(Id, State)) {
        .print("  intention", Id, ":", State)
    };
    .print("=== Emergency stop called ===");
    // .drop_all_desires would also destroy THIS intention (the one
    // calling it) along with everything else, so the "after" report is
    // scheduled as a brand-new event first, via .at, exactly the way
    // test_mining_camp.asl's own shift_end puts .drop_all_intentions
    // deliberately last for the same reason -- the difference here is
    // that something still needs to run afterwards to prove the sweep
    // worked, so that something has to be a fresh event, not a
    // continuation of this same intention.
    .at("now +300 ms", "+!after_stop_report");
    .drop_all_desires.

+!after_stop_report <-
    .print("=== After the stop: roll call ===");
    for (.intention(Id, State)) {
        .print("  intention", Id, ":", State)
    };
    .print("emergency_stop: done -- no delivery intention should be left running above.").
