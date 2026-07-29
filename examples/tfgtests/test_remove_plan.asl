// Test for .remove_plan: remove a plan by label and observe the change.
// Two plans handle +!ping; the labelled one is tried first. After removing
// @temp, only the fallback remains.
// Expected: "ping_from_labelled_plan", then "ping_from_fallback_plan", then "done".
@temp +!ping <- .print(ping_from_labelled_plan).
+!ping <- .print(ping_from_fallback_plan).

!start.

+!start <-
    .print("remove_plan: first !ping (expect labelled plan)");
    !ping;
    .print("remove_plan: removing @temp");
    .remove_plan("@temp");
    .print("remove_plan: second !ping (expect fallback plan)");
    !ping;
    .print("remove_plan: done").
