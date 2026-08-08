// Demonstrates .version(V): unifies V with this interpreter's version
// string, mirroring Jason's own .version(V).
!start.

+!start <-
    .version(V);
    .print("OK: .version(V) -> V =", V);

    if (.string(V)) {
        .print("OK: version is reported as a string")
    } else {
        .print("ERROR: version should be a string")
    };

    .print("done.").
