// Demonstrates .setof(Term, Query, List) vs .findall: setof deduplicates
// (and sorts) solutions; findall keeps every derivation, including ones
// that happen to bind the same value via a different rule path.
tasty(X) :- fruit(X).
sweet(X) :- fruit(X).
snack(X) :- tasty(X).
snack(X) :- sweet(X).

!start.

+!start <-
    +fruit(apple);
    +fruit(banana);
    .findall(X, snack(X), All);
    .print("findall (bag, with duplicates) =", All);
    .setof(X, snack(X), Set);
    .print("OK: setof (deduplicated, sorted) =", Set).
