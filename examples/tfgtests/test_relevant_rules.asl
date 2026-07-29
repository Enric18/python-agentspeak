// Demonstrates .relevant_rules(Literal, Rules): lists the rules whose
// head matches Literal's functor/arity and unifies with it.
p(X) :- q(X).
p(X) :- r(X) & s(X).
other(X) :- t(X).

!start.

+!start <-
    .relevant_rules(p(_), Rules);
    .print("OK: rules relevant to p(_) =", Rules).
