// Demonstrates .include(File): loads included_fixture.asl at runtime,
// merging its belief (fact(included)) and plan (+!greet) into this
// agent -- mirrors Jason's own .include(File) (1-arg form only; this
// engine has no namespace support for the optional 2nd argument, see
// .namespace). Run from the tfgtests directory so the relative path
// resolves, matching every other file-path-taking test here.
!start.

+!start <-
    .print("=== .include ===");
    if (fact(included)) {
        .print("ERROR: fact(included) should not exist before .include runs")
    } else {
        .print("OK: fact(included) correctly absent before .include")
    };

    .include("included_fixture.asl");

    if (fact(included)) {
        .print("OK: fact(included) is now visible after .include")
    } else {
        .print("ERROR: fact(included) should be visible after .include")
    };

    !greet;
    .print("done.").
