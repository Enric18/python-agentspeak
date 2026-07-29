# AgentSpeak core & implemented `stdlib.py` actions

Scope: the interpreter classes in `agentspeak/__init__.py` and `agentspeak/runtime.py` that the standard-library actions actually touch, plus every internal action implemented this project (`#Enric` in `stdlib.py`), grouped the same way the project's own function table groups them. Pre-existing baseline actions (`.print`, `.findall`, `.wait`, …) are omitted — this is a map of what was *built*, not the whole stdlib.

**Color key** — grey boxes are the interpreter's own runtime classes (unmodified); the external `spade_bdi` layer is warm brown; the four implemented-action groups are blue (BDI/intentions), ochre (plan library), plum (agent life-cycle), teal (term/environment/scheduling). Dashed arrows show which runtime state each group actually reads or mutates.

```mermaid
classDiagram
    direction LR

    class Environment {
        +agents : dict
        +build_agent(source, actions) Agent
        +build_agents(source, n, actions) list
        +run_agent(agent)
        +time() float
    }

    class Agent {
        +env : Environment
        +name : str
        +beliefs : dict
        +rules : dict
        +plans : dict
        +intentions : deque
        +call(trigger, goal_type, term, caller) bool
        +step() bool
        +run()
        +add_belief(term, scope)
        +add_plan(plan)
        +test_belief(term, intention) bool
        +remove_belief(term, intention) bool
    }

    class Intention {
        +instr : Instruction
        +head_term : Literal
        +calling_term : Literal
        +scope : dict
        +stack : deque
        +waiter : Waiter
    }

    class Waiter {
        +event : Event
        +until : float
        +poll(env) bool
    }

    class Plan {
        +trigger : Trigger
        +goal_type : GoalType
        +head : Literal
        +context : Query
        +body : Instruction
        +annotation : Literal
    }

    class Literal {
        +functor : str
        +args : tuple
        +annots : frozenset
        +with_annotation(annot) Literal
        +freeze(scope, memo) Literal
        +unify(right, scope, stack) bool
    }

    class Actions {
        +add(name, arity)
        +add_function(name, types)
        +add_predicate(name, types)
        +lookup(name, arity) callable
    }

    Environment "1" o-- "many" Agent
    Agent "1" *-- "many" Intention : intentions
    Agent "1" *-- "many" Plan : plans
    Intention "1" --> "0..1" Waiter : waiter
    Agent ..> Actions : dispatches via

    class BDIAgent {
        <<spade_bdi, external>>
        +bdi_agent : Agent
        +bdi : BDIBehaviour
        +jid : str
        +start(auto_register)
        +stop()
    }

    class BDIBehaviour {
        <<spade_bdi, external>>
        +set_belief(name, args)
        +remove_belief(name, args)
    }

    BDIAgent "1" *-- "1" Agent : bdi_agent
    BDIAgent "1" *-- "1" BDIBehaviour : bdi

    class BDIActions {
        <<stdlib.py — BDI / intentions>>
        +currentIntention(Id)
        +intend(Goal, Id?)
        +desire(Goal, Id?)
        +dropIntention(Goal)
        +dropAllIntentions()
        +dropDesire(Goal)
        +dropAllDesires()
        +dropEvent(E)
        +dropAllEvents()
        +failGoal(Goal)
        +succeedGoal(Goal)
        +suspend(Goal?)
        +resume(Goal)
        +suspended(Goal, Reason)
        +intention(Id, State, Stack?, current?)
    }

    class PlanLibraryActions {
        <<stdlib.py — plan library>>
        +addPlan(PlanString)
        +removePlan(Label)
        +planLabel(Plan, Label)
        +relevantPlans(Trigger, Plans)
        +relevantPlan(Trigger, Plan)
        +listPlans(Trigger?)
    }

    class LifecycleActions {
        <<stdlib.py — agent life-cycle>>
        +createAgent(Name, Source)
        +killAgent(Name, Deadline?)
    }

    class MiscActions {
        <<stdlib.py — term / env / scheduling>>
        +addAnnot(Belief, Annot, Result)
        +at(When, Event)
        +perceive()
    }

    BDIActions ..> Intention : reads/sets waiter
    BDIActions ..> Agent : rewrites intentions
    PlanLibraryActions ..> Plan : builds/renders
    PlanLibraryActions ..> Agent : reads/writes plans
    LifecycleActions ..> BDIAgent : spawns/stops
    MiscActions ..> Literal : with_annotation
    MiscActions ..> Agent : schedules via call()

    Actions o-- BDIActions : registers
    Actions o-- PlanLibraryActions : registers
    Actions o-- LifecycleActions : registers
    Actions o-- MiscActions : registers

    classDef core fill:#3A3D42,stroke:#222427,color:#F2F1EE
    classDef ext fill:#7A6A55,stroke:#5B4E3E,color:#F7F3EC
    classDef bdi fill:#35578C,stroke:#223A61,color:#EFF3FA
    classDef plan fill:#8C6A1F,stroke:#5F4813,color:#FBF3E4
    classDef life fill:#6A4090,stroke:#4A2C67,color:#F5EFFA
    classDef misc fill:#1F7A6C,stroke:#134F45,color:#E9FAF5

    class Environment:::core
    class Agent:::core
    class Intention:::core
    class Waiter:::core
    class Plan:::core
    class Literal:::core
    class Actions:::core
    class BDIAgent:::ext
    class BDIBehaviour:::ext
    class BDIActions:::bdi
    class PlanLibraryActions:::plan
    class LifecycleActions:::life
    class MiscActions:::misc
```

## Reference: exact signatures

| Group | Action | Arity | Notes |
|---|---|---|---|
| BDI | `.current_intention(Id)` | 1 | binds the running intention |
| BDI | `.intend(Goal, Id?)` | 1–2 | test/enumerate intended goals |
| BDI | `.desire(Goal, Id?)` | 1–2 | alias of `.intend` (no event queue) |
| BDI | `.drop_intention(Goal)` | 1 | |
| BDI | `.drop_all_intentions()` | 0 | |
| BDI | `.drop_desire(Goal)` | 1 | alias of `.drop_intention` |
| BDI | `.drop_all_desires()` | 0 | alias of `.drop_all_intentions` |
| BDI | `.drop_event(E)` / `.drop_all_events()` | 1 / 0 | well-defined no-ops |
| BDI | `.fail_goal(Goal)` | 1 | redirects to failure branch or drops |
| BDI | `.succeed_goal(Goal)` | 1 | pops + back-unifies like natural completion |
| BDI | `.suspend(Goal?)` | 0–1 | reuses `Intention.waiter` |
| BDI | `.resume(Goal)` | 1 | clears only `.suspend`-tagged waiters |
| BDI | `.suspended(Goal, Reason)` | 2 | test predicate |
| BDI | `.intention(Id, State, Stack?, current?)` | 2–4 | backtracks over `agent.intentions` |
| Plan library | `.add_plan(PlanString)` | 1 | via `_tell_how` |
| Plan library | `.remove_plan(Label)` | 1 | |
| Plan library | `.plan_label(Plan, Label)` | 2 | backtracking |
| Plan library | `.relevant_plans(Trigger, Plans)` | 2 | collects into a list |
| Plan library | `.relevant_plan(Trigger, Plan)` | 2 | backtracking counterpart |
| Plan library | `.list_plans(Trigger?)` | 0–1 | prints, debug aid |
| Life-cycle | `.create_agent(Name, Source)` | 2 | spawns real `BDIAgent` via the event loop |
| Life-cycle | `.kill_agent(Name, Deadline?)` | 1–2 | optional `jag_shutting_down` grace period |
| Misc | `.add_annot(Belief, Annot, Result)` | 3 | pure term utility |
| Misc | `.at(When, Event)` | 2 | `loop.call_later`-scheduled event |
| Misc | `.perceive()` | 0 | no-op (perception is unconditional every cycle) |
