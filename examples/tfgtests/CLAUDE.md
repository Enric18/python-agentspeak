# tfgtests

Test/scratch directory for `python-agentspeak` (`agentspeak/stdlib.py`, `runtime.py`) and
`spade_bdi` (BDIAgent) development. Sits in `python-agentspeak/examples/tfgtests` (moved
here from `spade_bdi/examples/tfgtests`); SPADE-dependent runners (`run_example.py`,
`run_example_new.py`, `run_create_agent.py`, `run_mining_camp.py`) expect a sibling
`spade_bdi` checkout providing `spade_bdi.bdi.BDIAgent`.

## Layout

- `run_example.py` — minimal runner: starts one `BDIAgent` against a `.asl` file with an
  embedded XMPP server, sleeps, stops. Swap the `.asl` filename to try a different test.
- `run_create_agent.py` — runner for `test_create_agent.asl`; exercises
  `BDIAgent.create_agent`, which spawns a second real SPADE agent (`paco`) at runtime.
  Has an inline debugging note about a silent-failure spot in `_create_agent`
  (spawn coroutine exceptions get swallowed unless a `done_callback` is added).
- `test_*.asl` — individual AgentSpeak test cases, one BDI feature each: desires,
  intentions, dropping desires/intentions (single and all), current intention,
  plan add/remove, plan labels, relevant-plans lookup, agent creation.
- `stdlib_plan_group.py` — **not imported by anything**; it's a patch block meant to be
  pasted into `agentspeak/stdlib.py`. Implements plan-library manipulation actions:
  `.add_plan`, `.remove_plan`, `.relevant_plans`, `.plan_label`. These back the
  `test_add_plan.asl`, `test_remove_plan.asl`, `test_plan_label.asl`,
  `test_relevant_plans.asl` cases.

## Running a test

```
python run_example.py          # edit the .asl filename inside to pick a test
python run_create_agent.py     # create_agent / paco spawn test
```

Requires an XMPP env (uses `embedded_xmpp_server=True`, agents on `@localhost`).
