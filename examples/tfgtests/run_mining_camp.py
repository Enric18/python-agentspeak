import os
import asyncio

import spade
from spade_bdi.bdi import BDIAgent

# .create_agent/.kill_agent open .asl files relative to the CWD, so this
# script has to run with that directory as its working directory
# regardless of where it was actually launched from.
os.chdir(os.path.dirname(os.path.abspath(__file__)))


async def main():
    # This single BDIAgent runs all three mining rovers (bot_a/bot_b/bot_c)
    # and the controller as concurrent intentions of its own -- the
    # second, genuinely separate agent (the night-shift rover) only comes
    # into existence later, spawned from inside test_mining_camp.asl
    # itself via .create_agent.
    a = BDIAgent("camp@localhost", "secret", "test_mining_camp.asl")
    await a.start(auto_register=True)

    # Shift ends at +8s (.at); the night-shift rover is deployed around
    # +6s and killed at shift end. Give it a few extra seconds of margin
    # so every scheduled event has had a chance to actually fire before
    # the process is torn down.
    await asyncio.sleep(12)

    print("\n" + "=" * 62)
    print("WHAT TO LOOK FOR ABOVE")
    print("=" * 62)
    print("  bot_a deposits ~3 loads, then 'ore vein looks exhausted...")
    print("  calling it in' and goes silent (.fail_goal) -- no")
    print("  quota-reached line for it.")
    print()
    print("  bot_b deposits a couple of loads, goes silent during 'bot_b")
    print("  is paused, reason = suspended', then resumes depositing right")
    print("  after 'resuming bot_b' (.suspend/.resume/.suspended).")
    print()
    print("  the roll call lists the intentions still alive at that point")
    print("  (bot_a's is usually already gone via .fail_goal by then) with")
    print("  states running/waiting/suspended (.intention).")
    print()
    print("  bot_c never prints 'quota reached' -- it is cut off directly")
    print("  after 'recalling it early' (.succeed_goal).")
    print()
    print("  nightshift@localhost powers up, learns +!scan via .add_plan,")
    print("  lists it back via .relevant_plan, runs it once, then patrols")
    print("  on its own -- then goes silent once shift end kills it")
    print("  (.create_agent / .kill_agent).")
    print()
    print("  '=== Shift end ===' prints the filtered dig_loop plans")
    print("  (.list_plans), then the site closes -- no line after that.")
    print("=" * 62 + "\n")

    await a.stop()


if __name__ == "__main__":
    spade.run(main(), embedded_xmpp_server=True)
