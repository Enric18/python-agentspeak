import spade
import asyncio
from spade_bdi.bdi import BDIAgent
async def main():
    # Swap the filename below to try a different test.
    a = BDIAgent("testagent@localhost", "secret", "test_perceive.asl")
    await a.start()

    # How long the harness script keeps the process alive before killing the agent.
    await asyncio.sleep(10)

    await a.stop()
if __name__ == "__main__":
    spade.run(main(), embedded_xmpp_server=True)