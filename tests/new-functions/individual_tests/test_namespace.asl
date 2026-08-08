// Demonstrates .namespace(X). python-agentspeak has no namespace ("::")
// syntax at all, so .namespace always fails here -- a well-defined
// "no namespaces exist" fallback, kept only for signature parity with
// Jason's .namespace(Arg).
!start.

+!start <-
    +family(bob);
    if (.namespace(family)) {
        .print("ERROR: .namespace(family) should not succeed -- namespaces don't exist here")
    } else {
        .print("OK: .namespace(family) correctly fails -- no namespace support in this engine")
    };
    if (.namespace(anything)) {
        .print("ERROR: .namespace(anything) should not succeed either")
    } else {
        .print("OK: .namespace(anything) also correctly fails")
    }.
