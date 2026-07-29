// Demonstrates .list_rules: prints every rule in the belief base.
p(X) :- q(X).
grandparent(X, Z) :- parent(X, Y) & parent(Y, Z).

!start.

+!start <-
    .print("=== .list_rules ===");
    .list_rules.
