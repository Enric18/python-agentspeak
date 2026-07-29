import os
import asyncio

import spade
from spade_bdi.bdi import BDIAgent

# .create_agent/.kill_agent open .asl files relative to the CWD.
os.chdir(os.path.dirname(os.path.abspath(__file__)))


async def main():
    a = BDIAgent("camp@localhost", "secret", "test_mining_camp.asl")
    await a.start(auto_register=True)

    # Shift ends at +8s (.at); nightshift is spawned around +6s and
    # killed at shift end. Give it a few extra seconds of margin.
    await asyncio.sleep(12)

    print("\n" + "=" * 62)
    print("WHAT TO LOOK FOR ABOVE")
    print("=" * 62)
    print("  alice deposits ~3 loads, then 'vein looks exhausted... calling")
    print("  it' and goes silent (.fail_goal) -- no quota-reached line for her.")
    print()
    print("  bob deposits a couple of loads, goes silent during 'bob is")
    print("  paused, reason = suspended', then resumes depositing right")
    print("  after 'resuming bob' (.suspend/.resume/.suspended).")
    print()
    print("  the roll call lists the intentions still alive at that point")
    print("  (alice's is usually already gone via .fail_goal by then) with")
    print("  states running/waiting/suspended (.intention).")
    print()
    print("  carol never prints 'quota reached' -- she's cut off directly")
    print("  after 'sending her home early' (.succeed_goal).")
    print()
    print("  nightshift@localhost reports for duty, learns +!scan via")
    print("  .add_plan, lists it back via .relevant_plan, runs it once,")
    print("  then patrols on its own -- then goes silent once shift end")
    print("  kills it (.create_agent / .kill_agent).")
    print()
    print("  '=== Shift end ===' prints the filtered dig_loop plans")
    print("  (.list_plans), then the camp closes -- no line after that.")
    print("=" * 62 + "\n")

    await a.stop()


if __name__ == "__main__":
    spade.run(main(), embedded_xmpp_server=True)
