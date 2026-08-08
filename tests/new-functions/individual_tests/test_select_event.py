import os

import agentspeak
import agentspeak.runtime
import agentspeak.stdlib

# select_event/.at/.wait etc. don't need SPADE; open the .asl relative to
# this file so this script works from any invocation directory.
os.chdir(os.path.dirname(os.path.abspath(__file__)))


class LIFOAgent(agentspeak.runtime.Agent):
    """Smallest possible non-default select_event: newest-raised-event
    first instead of the default oldest-first. Chosen only because it's
    guaranteed to produce a visibly different commit order than the
    default on three simultaneously-pending events -- a real policy
    would more likely be priority- or annotation-based.
    """

    def select_event(self):
        if not self.events:
            return None
        return self.events.pop()


def run(agent_cls, label):
    print("--- %s ---" % label)
    with open("test_select_event.asl") as f:
        content = f.read()
    # Fresh StringSource per build: source is consumed while parsing, so
    # the same file content is re-read (not reused) for each build.
    source = agentspeak.StringSource("test_select_event.asl", content)
    env = agentspeak.runtime.Environment()
    agent = env.build_agent(source, agentspeak.stdlib.actions, agent_cls=agent_cls)
    while agent.step():
        pass


run(agentspeak.runtime.Agent, "default FIFO")
run(LIFOAgent, "custom LIFO")
