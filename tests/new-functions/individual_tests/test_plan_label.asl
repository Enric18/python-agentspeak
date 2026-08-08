// Test for .plan_label: look up a plan by its @label.
// Expected: P is bound to the @myplan plan, rendered as a string.
@myplan +!do_it <- .print(do_it_body).

!start.

+!start <-
    .print("plan_label: looking up @myplan");
    .plan_label(P, "@myplan");
    .print("plan_label: found = ", P).
