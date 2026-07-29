import os
import asyncio

import spade
from spade_bdi.bdi import BDIAgent

# .create_agent opens the child's .asl relative to the CWD.
os.chdir(os.path.dirname(os.path.abspath(__file__)))


async def main():
    a = BDIAgent("testagent@localhost", "secret", "test_create_agent.asl")
    await a.start(auto_register=True)

    # Time for paco to be constructed, connect, register, and step its cycle.
    await asyncio.sleep(8)

    print("\n" + "=" * 58)
    print("WHAT TO LOOK FOR ABOVE")
    print("=" * 58)
    print("  A line from  paco@localhost  containing 'TIER 1 OK'.")
    print()
    print("  PRESENT -> .create_agent works. paco spawned, connected,")
    print("             registered on the XMPP server, and ran its plan.")
    print("             (build_agent alone could never reach this.)")
    print()
    print("  ABSENT  -> paco's spawn coroutine raised silently. In")
    print("             _create_agent, temporarily add:")
    print("               t = loop.create_task(_spawn())")
    print("               t.add_done_callback(")
    print("                 lambda t: t.exception() and print('SPAWN FAILED:', t.exception()))")
    print("             and rerun to see the real error.")
    print("=" * 58 + "\n")

    await a.stop()


if __name__ == "__main__":
    spade.run(main(), embedded_xmpp_server=True)
