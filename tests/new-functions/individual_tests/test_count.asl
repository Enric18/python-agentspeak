// Demonstrates .count(Query, N): counts the solutions of a query.
// (Pre-existing baseline action -- see stdlib.py's function table --
// tested here for completeness alongside the new belief-base actions.)
!start.

+!start <-
    +item(apple);
    +item(banana);
    +item(cherry);
    .count(item(_), N);
    .print("OK: counted", N, "item(_) beliefs (expected 3)").
