// Demonstrates .clone(Name): spawns a new platform agent seeded with a
// copy of the CALLING agent's own current beliefs and plans (not from a
// fresh .asl file, unlike .create_agent). To prove the clone genuinely
// received both the belief base and the plan library -- not just that
// spawning itself succeeded -- the original .sends the clone a real
// achieve message asking it to run a plan that reads an inherited
// belief; only a correctly-cloned agent could have +!prove_alive and
// mood(happy) both available to run it.
!start.

mood(happy).

+!start <-
    .print("original: cloning myself as 'twin'...");
    .clone(twin);
    .wait(6000);
    .print("original: sending twin a message to prove its plan library and beliefs transferred...");
    .send("twin@localhost", achieve, prove_alive);
    .wait(4000);
    .print("original: done.").

+!prove_alive <-
    ?mood(M);
    .print("TWIN ALIVE -- inherited mood =", M, "-- clone's plan library and beliefs both transferred correctly").
