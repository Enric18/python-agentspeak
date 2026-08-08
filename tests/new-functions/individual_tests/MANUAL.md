# new-functions — manual

Test directory for the `python-agentspeak` (`agentspeak/stdlib.py`,
`agentspeak/runtime.py`) internal-action implementation and its integration
with `spade_bdi` (`BDIAgent`). This file explains what is here and how to
run it. For what each action actually does and why, see the main report
(`../../../../latex/TFG-MAIN-Claude-Resolved.tex`), Chapters 4 and 5.

This directory sits at `python-agentspeak/tests/new-functions/`, alongside
`python-agentspeak/tests/`'s own pre-existing test suite
(`test_parser.py`, `test_stdlib.py`, `test_terms.py`, `asl/`) — that suite
predates this project and is unrelated to it; `new-functions/` is this
project's own addition, not a replacement for it.

(This directory has moved twice. It started as `tfgtests`, flat, directly
under `python-agentspeak/examples/`. It was then reorganised into
`individual_tests/` and `scenarios/` subfolders and renamed to
`new-function`, still under `examples/`. It now lives here, under
`python-agentspeak/tests/`, renamed again to `new-functions`.)

## Prerequisites

- A sibling `spade_bdi` checkout (or an environment with it installed),
  next to `python-agentspeak` — needed by every runner that uses a real
  `BDIAgent`. Not needed for `test_select_event.py`, which only imports
  `agentspeak` directly.
- `spade.run(..., embedded_xmpp_server=True)` starts its own local XMPP
  server, so no external XMPP account or server is required. Agents
  connect as `name@localhost`.

## Layout

```
python-agentspeak/tests/new-functions/
└── individual_tests/
    ├── MANUAL.md               (this file)
    ├── run_test.py             generic runner for any individual test
    ├── test_select_event.py    standalone runner, no SPADE needed
    └── test_*.asl              ~50 individual-action tests, one file each
└── scenarios/
    ├── mining/                 the Robotic Miners Scenario
    │   ├── run_mining_camp.py
    │   ├── test_mining_camp.asl
    │   └── test_mining_nightshift.asl
    └── warehouse/               the Dulcesol Warehouse Scenario
        ├── run_warehouse.py
        ├── test_warehouse.asl
        ├── test_warehouse_safety_monitor.asl
        └── test_warehouse_emergency_stop.asl
```

## Running an individual test

Run these from inside `individual_tests/`. Almost every `test_*.asl` file
there is run the same way, through `run_test.py`:

```
cd individual_tests
python run_test.py
```

Open `run_test.py` first and change the filename on this line to whichever
test you want:

```python
a = BDIAgent("testagent@localhost", "secret", "test_type.asl")
```

Two things in `run_test.py` are there for specific tests but harmless for
everything else, so you do not need to touch them when switching files:

- `a.bdi.set_belief("temperature", 21.5)` — only meaningful for
  `test_perceive.asl` (feeds a percept in from outside, the way a real
  sensor would). A no-op for every other test.
- The final `asyncio.sleep(3)` before the agent stops — long enough for
  most tests, but bump it for anything that schedules something further
  out (e.g. `test_at.asl`, or anything spawning/killing a second agent).

### Exception: `test_select_event.py` needs no SPADE at all

```
cd individual_tests
python test_select_event.py
```

This one is not run through `run_test.py`, on purpose. It demonstrates the
pluggable `select_event` extension point (which of several pending events
gets committed first each reasoning cycle) by passing a custom `agent_cls`
straight to `agentspeak.runtime.Environment.build_agent(...)`. That
argument is not something `spade_bdi`'s `BDIAgent` exposes, so this is the
only way to exercise the feature at all right now. Running it prints the
same three initial goals committed in two different orders — FIFO
(default) and LIFO (the custom policy) — so you can see the pluggability
actually changing behaviour.

**Careful if you ever run `pytest` from `python-agentspeak/tests/`**: pytest's
default discovery matches any `test_*.py` file, so it will try to *import*
`test_select_event.py` as a test module too, which runs both `run(...)`
calls at import time (they are not wrapped in a `test_`-prefixed function,
since this file was written to be run directly with `python`, not
collected by pytest). That is harmless on its own — it does not need
SPADE and does not affect other tests — but it does mean its two `---
default FIFO ---`/`--- custom LIFO ---` print blocks will show up in a
`pytest tests/` run of the original, pre-existing test suite too.

### Exception: `test_warehouse_emergency_stop.asl` also needs no SPADE, but has no dedicated runner yet

This one (in `scenarios/warehouse/`) demonstrates `.drop_all_desires` and
is deliberately kept out of the main warehouse scenario, since triggering
a real emergency stop mid-scenario would cut off everything scripted
after it. It is meant to run through the same fast, no-SPADE harness as
`test_select_event.py`, but no small `.py` driver for it has been
committed yet. Until one exists, run this from `new-functions/` (one
level above both `individual_tests/` and `scenarios/`):

```python
import asyncio, agentspeak, agentspeak.runtime, agentspeak.stdlib

async def run():
    env = agentspeak.runtime.Environment()
    with open("scenarios/warehouse/test_warehouse_emergency_stop.asl") as f:
        agent = env.build_agent(f, agentspeak.stdlib.actions, name="testagent")
    start = asyncio.get_event_loop().time()
    while asyncio.get_event_loop().time() - start < 3:
        if not agent.step():
            await asyncio.sleep(0.02)

asyncio.run(run())
```

(`test_select_event.py` is a good template if you want to turn this into
a proper committed script, placed alongside the other files in
`scenarios/warehouse/`.)

## Files that are not tests on their own

A few `.asl` files exist only to be loaded by another test, and printing
their own output means nothing on its own:

| File | Loaded by |
|---|---|
| `included_fixture.asl` | `test_include.asl`, via `.include(...)` |
| `test_new_agent.asl` | `test_create_agent.asl`, via `.create_agent("paco", ...)` |
| `test_kill_agent_child.asl` | `test_kill_agent.asl`, spawned twice as `paco` and `pepa` |

All three live in `individual_tests/`, next to the tests that load them.

## Running the integrated scenarios

Each scenario is self-contained in its own folder under `scenarios/`, with
its own launcher:

```
cd scenarios/mining
python run_mining_camp.py

cd scenarios/warehouse
python run_warehouse.py
```

Both need the same `spade_bdi` prerequisite as `run_test.py`. Both print a
"WHAT TO LOOK FOR ABOVE" summary at the end explaining what each beat of
the run was supposed to demonstrate — read that first if the raw log is
hard to follow.

**Mining** (`run_mining_camp.py`, ~12s): three mining rovers digging
independently off a shared belief log, a controller pausing/resuming one,
failing another, succeeding a third early, and deploying a genuinely
separate night-shift relief rover partway through.

**Warehouse** (`run_warehouse.py`, ~19s): a continuous stream of orders
through two ASRS units and a fleet of AMRs, exercising the event queue
(`.desire`/`.intend`), `.drop_event`, all four goal-control actions
together, a real second agent (`.create_agent`) that grows its own plan
library at runtime, and a cloned backup agent (`.clone`) briefed over a
real `.send` message.

Both scenarios write a few generated files as they run (for example
`.save_agent` output such as `warehouse_checkpoint.asl` from the
warehouse scenario), inside their own `scenarios/<name>/` folder. These
are regenerated every run and safe to delete between runs if you want a
clean directory.

## Individual tests, by group

Grouped the same way the main report groups the standard library, so you
can find the test for a given action quickly. Some actions share one test
file; see the file's own header comment for the exact detail. All of
these are in `individual_tests/`.

**Belief base**: `test_belief.asl`, `test_setof.asl`, `test_namespace.asl`,
`test_relevant_rules.asl`, `test_list_rules.asl`, `test_add_annot.asl`,
`test_add_nested_source.asl`, `test_count.asl`

**Plan library**: `test_add_plan.asl`, `test_remove_plan.asl`,
`test_plan_label.asl`, `test_relevant_plan.asl`, `test_relevant_plans.asl`,
`test_list_plans.asl`

**Mental state (event queue)**: `test_desire.asl`, `test_pending_desire.asl`,
`test_intend.asl`, `test_current_intention.asl`, `test_drop_desire.asl`,
`test_drop_all_desires.asl`, `test_drop_all_intentions.asl`

**Goal control**: `test_fail_goal.asl`, `test_succeed_goal.asl`,
`test_drop_intention.asl`, `test_drop_event.asl`, `test_drop_all_events.asl`,
`test_suspend.asl`, `test_resume.asl`, `test_suspended.asl`,
`test_intention.asl`, `test_meta_events.asl`, `test_select_event.asl`
(driven by `test_select_event.py`, see above)

**Agent life cycle**: `test_create_agent.asl` (+ `test_new_agent.asl`),
`test_kill_agent.asl` (+ `test_kill_agent_child.asl`)

**Execution control**: `test_at.asl`, `test_perceive.asl`

**Lists, strings and collections**: `test_lists_and_sets.asl`,
`test_delete.asl`, `test_replace.asl`, `test_case_conversion.asl`

**Miscellaneous**: `test_version.asl`, `test_set_random_seed.asl`,
`test_printf.asl`, `test_eval.asl`, `test_type.asl`, `test_save_agent.asl`,
`test_include.asl` (+ `included_fixture.asl`), `test_clone.asl`
