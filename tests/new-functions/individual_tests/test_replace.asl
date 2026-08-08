// Demonstrates .replace(S1,S2,S3,S4): S2 is a regex pattern (Jason's own
// implementation is Java's String.replaceAll, ported here via Python's
// re.sub), S3 the replacement, every occurrence replaced. A non-string
// S1 is converted to its string representation first, matching Jason's
// arg[0].toString() fallback.
!start.

+!start <-
    // plain substring pattern, single occurrence
    .replace("hello world", "world", "there", R1);
    .print("OK: .replace(\"hello world\",\"world\",\"there\",R1) -> R1 =", R1);

    // all occurrences replaced, not just the first
    .replace("banana", "a", "o", R2);
    .print("OK: .replace(\"banana\",\"a\",\"o\",R2) -> R2 =", R2);

    // S2 is a real regex, not a literal substring
    .replace("a1b2c3", "[0-9]", "_", R3);
    .print("OK: .replace(\"a1b2c3\",\"[0-9]\",\"_\",R3) -> R3 =", R3);

    // no match: S4 unifies with S1 unchanged
    .replace("hello", "xyz", "_", R4);
    .print("OK: .replace(\"hello\",\"xyz\",\"_\",R4) -> R4 =", R4);

    // non-string S1 is converted to its string representation first
    .replace(item(1,2), "1", "9", R5);
    .print("OK: .replace(item(1,2),\"1\",\"9\",R5) -> R5 =", R5);

    // a wrong expected result should fail to unify, not silently succeed
    if (.replace("banana", "a", "o", "wrong")) {
        .print("ERROR: .replace(\"banana\",\"a\",\"o\",\"wrong\") should NOT have unified")
    } else {
        .print("OK: mismatched result correctly fails to unify")
    };

    .print("done.").
