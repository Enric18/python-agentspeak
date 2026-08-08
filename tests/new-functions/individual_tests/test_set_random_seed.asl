// Demonstrates .set_random_seed(N): mirrors Jason's own
// .set_random_seed(N) -- reseeding before each .random() call must make
// the draws reproducible. Note the scope difference documented on the
// action itself: this reseeds the process-global random module (shared
// by every agent), not a per-agent generator the way Jason's own does.
!start.

+!start <-
    .set_random_seed(42);
    .random(R1);
    .set_random_seed(42);
    .random(R2);
    if (R1 == R2) {
        .print("OK: same seed -> same draw:", R1, "==", R2)
    } else {
        .print("ERROR: same seed should reproduce the same draw")
    };

    .set_random_seed(1);
    .random(R3);
    .set_random_seed(2);
    .random(R4);
    if (R3 \== R4) {
        .print("OK: different seeds -> different draws:", R3, "\\==", R4)
    } else {
        .print("ERROR: different seeds should (almost certainly) differ")
    };

    .print("done.").
