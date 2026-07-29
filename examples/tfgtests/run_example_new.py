import os
import asyncio

import spade
from spade_bdi.bdi import BDIAgent

# Some tests (.create_agent/.kill_agent) open .asl files relative to the
# CWD; chdir here so this runner works from any invocation directory.
os.chdir(os.path.dirname(os.path.abspath(__file__)))


async def main():
    # Swap the filename below to try a different test.
    a = BDIAgent("testagent@localhost", "secret", "test_lists_and_sets.asl")
    await a.start(auto_register=True)

    # Only needed for test_perceive.asl: feeds a percept belief in from
    # outside the agent, the way a real sensor/environment would, via
    # spade_bdi's existing perception path (BDIBehaviour.set_belief).
    # Harmless no-op for tests that don't react to it -- leave it in, or
    # comment it out if it's ever in the way.
    await asyncio.sleep(0.3)
    a.bdi.set_belief("temperature", 21.5)

    # How long the harness script keeps the process alive before killing
    # the agent. Bump this for tests that need more time (e.g. dynamically
    # created/killed agents, .at events with longer delays).
    await asyncio.sleep(3)

    await a.stop()


if __name__ == "__main__":
    spade.run(main(), embedded_xmpp_server=True)
