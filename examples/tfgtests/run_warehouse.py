import os
import asyncio

import spade
from spade_bdi.bdi import BDIAgent

# .create_agent/.kill_agent/.clone open/spawn .asl files relative to the
# CWD, so this script has to run with that directory as its working
# directory regardless of where it was actually launched from.
os.chdir(os.path.dirname(os.path.abspath(__file__)))


async def main():
    # The warehouse itself runs the ASRS/dispatcher/AMR logic, and every
    # housekeeping intention, as concurrent intentions of its own -- the
    # safety-monitor agent (via .create_agent) and the surge backup unit
    # (via .clone) only come into existence later, spawned from inside
    # test_warehouse.asl itself.
    a = BDIAgent("warehouse@localhost", "secret", "test_warehouse.asl")
    await a.start(auto_register=True)

    # Shift ends at +15s (.at); the safety monitor is deployed near the
    # start and stopped at shift end, the surge backup unit around +4.5s
    # and stood down a few seconds later. Give it a few extra seconds of
    # margin so every scheduled event has had a chance to actually fire
    # before the process is torn down.
    await asyncio.sleep(19)

    print("\n" + "=" * 66)
    print("WHAT TO LOOK FOR ABOVE")
    print("=" * 66)
    print("  dispatch: confirmed -- order_1 is still just a desire...")
    print("    (order_0's own commit-time context catching order_1 still")
    print("    pending, .desire true / .intend false)")
    print()
    print("  dispatch: order_2 was cancelled by the customer -- removed")
    print("    before any ASRS could claim it (.drop_event)")
    print()
    print("  Incident 1: amr_2's blocked-aisle delivery gets redirected by")
    print("    .fail_goal instead of finishing normally.")
    print("  Incident 2: amr_3's delivery is completed early by")
    print("    .succeed_goal (a floor worker's manual hand-off).")
    print("  Incident 3: amr_1's delivery is silently dropped by")
    print("    .drop_intention (a battery fault, no retry).")
    print("  Incident 4: amr_1's next delivery is paused mid-route by")
    print("    .suspend, then resumes exactly where it left off via")
    print("    .resume (.suspended reports the pause in between).")
    print()
    print("  Surge watch: .clone spins up amr_backup@localhost from the")
    print("    warehouse's own current state; a real .send message briefs")
    print("    it on a surge order; .kill_agent stands it down afterwards.")
    print()
    print("  safety_monitor@localhost: deployed via .create_agent, learns")
    print("    a new advisory via .add_plan, confirms it via .relevant_plan,")
    print("    later retires an older one found via .plan_label with")
    print("    .remove_plan, then patrols independently until shift end.")
    print()
    print("  Diagnostics block: rule listing, .belief vs. ordinary")
    print("    inference, the .namespace no-op, .setof, .type, .eval, and")
    print("    a live .intention roll call.")
    print()
    print("  Manifest audit block: .difference/.intersection/.union/")
    print("    .delete/.empty/.reverse/.prefix/.suffix/.sublist/.shuffle")
    print("    on a small pallet-ID list, then .lower_case/.replace/")
    print("    .upper_case normalising a messy truck code.")
    print()
    print("  '=== Shift end ===' writes warehouse_checkpoint.asl")
    print("  (.save_agent), prints the filtered delivery plans")
    print("  (.list_plans), kills the safety monitor, then the warehouse")
    print("  closes -- no line after that (.drop_all_intentions).")
    print("=" * 66 + "\n")

    await a.stop()


if __name__ == "__main__":
    spade.run(main(), embedded_xmpp_server=True)
