import os
import asyncio

import spade
from spade_bdi.bdi import BDIAgent

# .clone writes its temp source file relative to the process CWD's temp
# dir, but the *original* agent's own .asl is opened relative to CWD too.
os.chdir(os.path.dirname(os.path.abspath(__file__)))


async def main():
    a = BDIAgent("testagent@localhost", "secret", "test_clone.asl")
    await a.start(auto_register=True)

    # Time for the clone to be constructed, connect, register, receive
    # the .send, and run its cycle.
    await asyncio.sleep(16)

    print("\n" + "=" * 58)
    print("WHAT TO LOOK FOR ABOVE")
    print("=" * 58)
    print("  A line from  twin@localhost  containing 'TWIN ALIVE'.")
    print()
    print("  PRESENT -> .clone works: twin spawned, connected, received")
    print("             the original's real .send message, and correctly")
    print("             ran +!prove_alive using its own inherited")
    print("             mood(happy) belief.")
    print("=" * 58 + "\n")

    await a.stop()


if __name__ == "__main__":
    spade.run(main(), embedded_xmpp_server=True)
