# -*- coding: utf-8 -*-
#
# This file is part of the python-agentspeak interpreter.
# Copyright (C) 2016-2019 Niklas Fiekas <niklas.fiekas@tu-
# clausthal.de>.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

from __future__ import print_function, division

import datetime
import random

import colorama
import spade

import re
import agentspeak
import agentspeak.optimizer
import agentspeak.runtime
from agentspeak import asl_str, Literal

LOGGER = agentspeak.get_logger(__name__)


# TODO:
# * Plan Library Manipulation
#   - .add_plan
#   - .plan_label
#   - .relevant_plans
#   - .remove_plan
# * BDI
#   - .current_intention    #Enric
#   - .desire               #Enric
#   - .drop_all_desires     #Enric
#   - .drop_all_events      #-----
#   - .drop_all_intentions  #Enric
#   - .drop_desire          #Enric
#   - .drop_event           #-----
#   - .drop_intention       #Enric
#   - .fail_goal            #Enric
#   - .intend               #Enric
#   - .succeed_goal         #Enric
#   - .add_anot
#   - .at
#   - .create_agent
#   - .kill_agent
#   - .perceive


actions = agentspeak.Actions()


@actions.add(".broadcast", 2)
def _broadcast(agent, term, intention):
    # Illocutionary force.
    ilf = agentspeak.grounded(term.args[0], intention.scope)
    if not agentspeak.is_atom(ilf):
        return
    if ilf.functor == "tell":
        goal_type = agentspeak.GoalType.belief
        trigger = agentspeak.Trigger.addition
    elif ilf.functor == "untell":
        goal_type = agentspeak.GoalType.belief
        trigger = agentspeak.Trigger.removal
    elif ilf.functor == "achieve":
        goal_type = agentspeak.GoalType.achievement
        trigger = agentspeak.Trigger.addition
    else:
        raise agentspeak.AslError("unknown illocutionary force: %s" % ilf)

    # Prepare message.
    message = agentspeak.freeze(term.args[1], intention.scope, {})
    tagged_message = message.with_annotation(
        agentspeak.Literal("source", (agentspeak.Literal(agent.name), )))

    # Broadcast.
    for receiver in agent.env.agents.values():
        if receiver == agent:
            continue

        receiver.call(trigger, goal_type, tagged_message, agentspeak.runtime.Intention())

    yield


@actions.add(".send", 3)
def _send(agent, term, intention):
    # Find the receivers: By a string, atom or list of strings or atoms.
    receivers = agentspeak.grounded(term.args[0], intention.scope)
    if not agentspeak.is_list(receivers):
        receivers = [receivers]
    receiving_agents = []
    for receiver in receivers:
        if agentspeak.is_atom(receiver):
            receiving_agents.append(agent.env.agents[receiver.functor])
        else:
            receiving_agents.append(agent.env.agents[receiver])

    # Illocutionary force.
    ilf = agentspeak.grounded(term.args[1], intention.scope)
    if not agentspeak.is_atom(ilf):
        return
    if ilf.functor == "tell":
        goal_type = agentspeak.GoalType.belief
        trigger = agentspeak.Trigger.addition
    elif ilf.functor == "untell":
        goal_type = agentspeak.GoalType.belief
        trigger = agentspeak.Trigger.removal
    elif ilf.functor == "achieve":
        goal_type = agentspeak.GoalType.achievement
        trigger = agentspeak.Trigger.addition
    elif ilf.functor == "unachieve":
        goal_type = agentspeak.GoalType.achievement
        trigger = agentspeak.Trigger.removal
    elif ilf.functor == "tellHow":
        goal_type = agentspeak.GoalType.tellHow
        trigger = agentspeak.Trigger.addition
    elif ilf.functor == "untellHow":
        goal_type = agentspeak.GoalType.tellHow
        trigger = agentspeak.Trigger.removal
    elif ilf.functor == "askHow":
        goal_type = agentspeak.GoalType.askHow
        trigger = agentspeak.Trigger.addition
    else:
        raise agentspeak.AslError("unknown illocutionary force: %s" % ilf)

    # TODO: askOne, askAll
    # Prepare message. The message is either a plain text or a structured message.
    if ilf.functor in ["tellHow", "askHow", "untellHow"]:
        message = agentspeak.Literal("plain_text", (term.args[2], ), frozenset())
    else:
        message = agentspeak.freeze(term.args[2], intention.scope, {})
    
    tagged_message = message.with_annotation(
        agentspeak.Literal("source", (agentspeak.Literal(agent.name), )))

    # Broadcast.
    for receiver in receiving_agents:
        receiver.call(trigger, goal_type, tagged_message, agentspeak.runtime.Intention())

    yield


COLORS = [(colorama.Back.GREEN, colorama.Fore.WHITE),
          (colorama.Back.MAGENTA, colorama.Fore.WHITE),
          (colorama.Back.YELLOW, colorama.Fore.BLACK),
          (colorama.Back.BLUE, colorama.Fore.WHITE),
          (colorama.Back.CYAN, colorama.Fore.BLACK),
          (colorama.Back.RED, colorama.Fore.WHITE)]


@actions.add(".print")
@agentspeak.optimizer.no_scope_effects
def _print(agent, term, intention, _color_map={}, _current_color=[0]):
    if agent in _color_map:
        color = _color_map[agent]
    else:
        color = COLORS[_current_color[0]]
        _current_color[0] = (_current_color[0] + 1) % len(COLORS)
        _color_map[agent] = color

    memo = {}
    text = " ".join(asl_str(agentspeak.freeze(t, intention.scope, memo)) for t in term.args)

    with colorama.colorama_text():
        print(color[0], color[1], agent.name, colorama.Fore.RESET, colorama.Back.RESET, " ", text, sep="")

    yield


@actions.add(".fail", 0)
@agentspeak.optimizer.no_scope_effects
def _fail(agent, term, intention):
    return
    yield


@actions.add(".my_name", 1)
@agentspeak.optimizer.function_like
def _my_name(agent, term, intention):
    if agentspeak.unify(term.args[0], Literal(agent.name), intention.scope, intention.stack):
        yield


@actions.add(".concat")
@agentspeak.optimizer.function_like
def _concat(agent, term, intention):
    args = [agentspeak.grounded(arg, intention.scope) for arg in term.args[:-1]]

    if all(isinstance(arg, (tuple, list)) for arg in args):
        result = tuple(el for arg in args for el in arg)
    else:
        result = "".join(str(arg) for arg in args)

    if agentspeak.unify(term.args[-1], result, intention.scope, intention.stack):
        yield


actions.add_function(".random", (), random.random)

actions.add_function(".min", (tuple, ), min)
actions.add_function(".max", (tuple, ), max)
actions.add_function(".length", (None, ), len)


@actions.add_function(".nth", (int, tuple))
def _nth(index, l):
    assert index >= 0
    return l[index]


@actions.add_function(".sort", (tuple, ))
def _sort(l):
    return tuple(sorted(l))


@actions.add(".substring", 3)
@agentspeak.optimizer.function_like
def _substring(agent, term, intention):
    needle = asl_str(agentspeak.grounded(term.args[0], intention.scope))
    haystack = asl_str(agentspeak.grounded(term.args[1], intention.scope))

    choicepoint = object()

    pos = haystack.find(needle)
    while pos != -1:
        intention.stack.append(choicepoint)

        if agentspeak.unify(term.args[2], pos, intention.scope, intention.stack):
            yield

        agentspeak.reroll(intention.scope, intention.stack, choicepoint)
        pos = haystack.find(needle, pos + 1)


@actions.add(".member", 2)
@agentspeak.optimizer.function_like
def _member(agent, term, intention):
    choicepoint = object()

    for member in agentspeak.evaluate(term.args[1], intention.scope):
        intention.stack.append(choicepoint)

        if agentspeak.unify(term.args[0], member, intention.scope, intention.stack):
            yield

        agentspeak.reroll(intention.scope, intention.stack, choicepoint)


actions.add_predicate(".atom", (None, ), agentspeak.is_atom)
actions.add_predicate(".literal", (None, ), agentspeak.is_literal)
actions.add_predicate(".list", (None, ), agentspeak.is_list)
actions.add_predicate(".number", (None, ), agentspeak.is_number)
actions.add_predicate(".string", (None, ), agentspeak.is_string)
actions.add_predicate(".structure", (None, ), agentspeak.is_structure)


@actions.add(".ground", 1)
@agentspeak.optimizer.no_scope_effects
def _ground(agent, term, intention):
    if agentspeak.is_ground(term, intention.scope):
        yield


@actions.add(".findall", 3)
@agentspeak.optimizer.function_like
def _findall(agent, term, intention):
    pattern = agentspeak.evaluate(term.args[0], intention.scope)
    query = agentspeak.runtime.TermQuery(term.args[1])
    result = []

    memo = {}
    for _ in query.execute(agent, intention):
        result.append(agentspeak.freeze(pattern, intention.scope, memo))

    if agentspeak.unify(tuple(result), term.args[2], intention.scope, intention.stack):
        yield


@actions.add(".count", 2)
@agentspeak.optimizer.function_like
def _count(agent, term, intention):
    query = agentspeak.runtime.TermQuery(term.args[0])

    choicepoint = object()
    count = 0
    intention.stack.append(choicepoint)
    for _ in query.execute(agent, intention):
        count += 1
    agentspeak.reroll(intention.scope, intention.stack, choicepoint)

    if agentspeak.unify(count, term.args[1], intention.scope, intention.stack):
        yield


@actions.add(".abolish", 1)
# TODO: Inform optimizer.
def _abolish(agent, term, intention):
    memo = {}
    pattern = agentspeak.freeze(term.args[0], intention.scope, memo)
    group = agent.beliefs[pattern.literal_group()]

    for old_belief in list(group):
        if agentspeak.unifies_annotated(old_belief, pattern):
            group.remove(old_belief)

    yield


@actions.add(".date", 3)
@agentspeak.optimizer.side_effect(
    agentspeak.optimizer.InferenceEvilnessConst.AFFECT_PARAM_ALL,
    agentspeak.optimizer.InferenceEvilnessConst.EFFECT_DOBIND
)
def _date(agent, term, intention):
    date = datetime.datetime.now()

    if (agentspeak.unify(term.args[0], date.year, intention.scope, intention.stack) and
        agentspeak.unify(term.args[1], date.month, intention.scope, intention.stack) and
        agentspeak.unify(term.args[2], date.day, intention.scope, intention.stack)):

        yield


@actions.add(".time", 3)
@agentspeak.optimizer.side_effect(
    agentspeak.optimizer.InferenceEvilnessConst.AFFECT_PARAM_ALL,
    agentspeak.optimizer.InferenceEvilnessConst.EFFECT_DOBIND
)
def _time(agent, term, intention):
    time = datetime.datetime.now()

    if (agentspeak.unify(term.args[0], time.hour, intention.scope, intention.stack) and
        agentspeak.unify(term.args[1], time.minute, intention.scope, intention.stack) and
        agentspeak.unify(term.args[2], time.second, intention.scope, intention.stack)):

        yield


@actions.add(".wait", 1)
@actions.add(".wait", 2)
@agentspeak.optimizer.all_bound
def _wait(agent, term, intention):
    # Handle optional arguments.
    args = [agentspeak.grounded(arg, intention.scope) for arg in term.args]
    if len(args) == 2:
        event, millis = args
    else:
        if agentspeak.is_number(args[0]):
            millis = args[0]
            event = None
        else:
            millis = None
            event = args[0]

    # Type checks.
    if not (millis is None or agentspeak.is_number(millis)):
        raise agentspeak.AslError("expected timeout for .wait to be numeric")
    if not (event is None or agentspeak.is_string(event)):
        raise agentspeak.AslError("expected event for .wait to be a string")

    # Event.
    if event is not None:
        # Parse event.
        if not event.endswith("."):
            event += "."
        log = agentspeak.Log(LOGGER, 1)
        tokens = agentspeak.lexer.TokenStream(agentspeak.StringSource("<.wait>", event), log)
        tok, ast_event = agentspeak.parser.parse_event(tokens.next(), tokens, log)
        if tok.lexeme != ".":
            raise log.error("expected no further tokens after event for .wait, got: '%s'", tok.lexeme, loc=tok.loc)

        # Build term.
        event = ast_event.accept(agentspeak.runtime.BuildEventVisitor(log))

    # Timeout.
    if millis is None:
        until = None
    else:
        until = agent.env.time() + millis / 1000

    # Create waiter.
    intention.waiter = agentspeak.runtime.Waiter(event=event, until=until)
    yield


# Custom actions for debugging:


@actions.add(".range", 2)
@agentspeak.optimizer.function_like
def _range_2(agent, term, intention):
    choicepoint = object()

    for i in range(int(agentspeak.grounded(term.args[0], intention.scope))):
        intention.stack.append(choicepoint)

        if agentspeak.unify(term.args[1], i, intention.scope, intention.stack):
            yield

        agentspeak.reroll(intention.scope, intention.stack, choicepoint)


@actions.add(".dump", 0)
@agentspeak.optimizer.no_scope_effects
def _dump(agent, term, intention):
    agent.dump()
    yield


@actions.add(".unbind_all", 0)
@agentspeak.optimizer.side_effect(
    agentspeak.optimizer.InferenceEvilnessConst.AFFECT_SCOPE,
    agentspeak.optimizer.InferenceEvilnessConst.EFFECT_UNBIND
)
def _unbind_all(agent, term, intention):
    intention.scope.clear()
    yield


@actions.add(".control_flow", 0)
@agentspeak.optimizer.no_scope_effects
def _control_flow(agent, term, intention):
    out = open("control_flow.dot", "w")
    print("digraph control_flow {", file=out)
    for plans in agent.plans.values():
        for plan in plans:
            print("  \"%s %s\" -> \"%s\";" % (plan.name(), plan.context, plan.body), file=out)
            closed_instrs = set()
            open_instrs = set([plan.body])
            while open_instrs:
                instr = open_instrs.pop()

                if instr.success:
                    print("  \"%s\" -> \"%s\";" % (instr, instr.success), file=out)

                if instr.failure:
                    print("  \"%s\" -> \"%s\" [label=\"failure\"];" % (instr, instr.failure), file=out)

                closed_instrs.add(instr)
                if instr.success and instr.success not in closed_instrs:
                    open_instrs.add(instr.success)
                if instr.failure and instr.failure not in closed_instrs:
                    open_instrs.add(instr.failure)
    print("}", file=out)
    out.close()
    print("Graph dumped to control_flow.dot")
    yield

@actions.add(".drop_all_intentions", 0)  #Enric
def _drop_all_intentions(agent, term, intention):
    # Simply clear the deque of active intentions
    agent.intentions.clear()
    yield

@actions.add(".drop_intention", 1)  #Enric
def _drop_intention(agent, term, intention):
    import collections
    
    # 1. Retrieve the goal name you want to drop (e.g. run_step)
    goal = agentspeak.freeze(term.args[0], intention.scope, {})
    
    # 2. Re-create the intentions list, filtering out the stack containing the goal
    agent.intentions = collections.deque(
        stack for stack in agent.intentions
        if not any(item.head_term == goal for item in stack)
    )
    yield

@actions.add(".current_intention", 1) #Enric
def _current_intention(agent, term, intention):
    # Simply return the current intention
    #if agentspeak.unify(term.args[0], intention.head_term, intention.scope, intention.stack):
    yield intention

@actions.add(".intend") #Enric
def _intend(agent, term, intention):
    if len(term.args) < 1 or len(term.args) > 2:
        raise agentspeak.AslError("internal action .intend expects 1 or 2 arguments")
    
    goal_arg = term.args[0]
    has_intention_var = len(term.args) == 2
    
    choicepoint = object()
    
    for stack in agent.intentions:
        for item in stack:
            if item.head_term is None:
                continue
            
            intention.stack.append(choicepoint)
            
            if agentspeak.unify(goal_arg, item.head_term, intention.scope, intention.stack):
                if not has_intention_var or agentspeak.unify(term.args[1], id(stack), intention.scope, intention.stack):
                    yield
            
            agentspeak.reroll(intention.scope, intention.stack, choicepoint)

@actions.add(".desire") #Enric
def _desire(agent, term, intention):
    # In python-agentspeak, desires and intentions are equivalent
    # since there is no persistent event queue.
    yield from _intend(agent, term, intention)


@actions.add(".drop_desire", 1) #Enric
def _drop_desire(agent, term, intention):
    # In python-agentspeak, dropping a desire is equivalent to dropping an intention
    # since there is no persistent event queue.
    yield from _drop_intention(agent, term, intention)


@actions.add(".drop_all_desires", 0) #Enric
def _drop_all_desires(agent, term, intention):
    # In python-agentspeak, dropping all desires is equivalent to dropping all intentions
    # since there is no persistent event queue.
    yield from _drop_all_intentions(agent, term, intention)


@actions.add(".create_agent", 2)  # Enric
def _create_agent(agent, term, intention):
    import asyncio
    from spade_bdi.bdi import BDIAgent   # lazy import to avoid a circular import at load time

    name = agentspeak.asl_str(agentspeak.grounded(term.args[0], intention.scope))
    source = agentspeak.asl_str(agentspeak.grounded(term.args[1], intention.scope))

    # agent.name was set to self.jid in _load_asl, so reuse its domain
    creator_jid = str(agent.name)
    domain = creator_jid.split("@", 1)[1] if "@" in creator_jid else "localhost"
    new_jid = "{}@{}".format(name, domain)
    password = "secret"        # environment-specific — see below

    loop = asyncio.get_running_loop()

    async def _spawn():
        child = BDIAgent(new_jid, password, source)
        await child.start(auto_register=True)

    loop.create_task(_spawn())
    yield


@actions.add(".drop_event", 1) #Enric
def _drop_event(agent, term, intention):
    # Since python-agentspeak does not have a persistent event queue
    # (events are processed immediately and synchronously),
    # there are no pending events to drop.
    yield


@actions.add(".drop_all_events", 0) #Enric
def _drop_all_events(agent, term, intention):
    # Since python-agentspeak does not have a persistent event queue,
    # there are no pending events to drop.
    yield


@actions.add(".fail_goal", 1)  # Enric
def _fail_goal(agent, term, intention):
    """.fail_goal(Goal)

    Make the intention(s) pursuing Goal fail, as if their plan had failed,
    instead of silently discarding them the way .drop_intention does. Goal
    lookup mirrors .drop_intention.

    There is no persistent event queue to dispatch a reference-style
    "-!goal" recovery plan to (see .drop_event), so the only place a
    failure can resume is a local if/else already coded around the goal's
    own achieve call, and that is only available for a *different*
    intention that is currently idle exactly at Goal's own frame (the top
    of its stack): there we redirect it to that frame's own failure
    branch (the else-branch, or simply past the if when there is none).
    When Goal is buried under active subgoals, or is the goal of the
    intention that is itself calling .fail_goal, there is no reliable
    failure branch left to resume -- in the self case, this very call's
    own continuation would just be overwritten the instant it returns
    successfully -- so the intention is dropped outright, the same
    fallback .drop_intention already uses, and the "stop immediately"
    reading of the self-drop semantics discussed in the design notes.
    """
    import collections

    def _nearest_failure_branch(instr, max_hops=3):
        # An idle intention's instr sits at the *start* of its next
        # formula (e.g. the push_query of an if/while condition); the
        # instruction actually carrying a wired .failure (next_or_fail)
        # is a couple of .success hops further along the same straight
        # line of compiled instructions. Walk forward to find it.
        node = instr
        for _ in range(max_hops):
            if node is None:
                return None
            if node.failure is not None:
                return node.failure
            node = node.success
        return None

    goal = agentspeak.freeze(term.args[0], intention.scope, {})

    kept = collections.deque()
    for stack in agent.intentions:
        if not stack or not any(item.head_term == goal for item in stack):
            kept.append(stack)
            continue

        top = stack[-1]
        failure_branch = None if top is intention or top.head_term != goal \
            else _nearest_failure_branch(top.instr)
        if failure_branch is not None:
            top.instr = failure_branch
            kept.append(stack)
        # else: self-target, a buried target, or no failure branch to
        # resume into -- drop the intention.

    agent.intentions = kept
    yield


@actions.add(".succeed_goal", 1)  # Enric
def _succeed_goal(agent, term, intention):
    """.succeed_goal(Goal)

    Make the intention(s) pursuing Goal succeed immediately, as if their
    plan had run to completion, instead of merely discarding them the way
    .drop_intention does. Goal lookup mirrors .drop_intention/.fail_goal.

    Unlike .fail_goal, this needs no self/foreign distinction and no
    failure-branch lookup: forcing success is exactly what the interpreter
    already does when a plan's body runs off its end (see step()'s
    "if not instr" branch), so we simply replicate that. For each
    intention stack in which Goal is intended: any subgoal frames stacked
    above Goal's own frame are discarded too (they were only working on
    Goal's behalf, and Goal is now considered accomplished), Goal's own
    frame is popped, and -- if a caller remains beneath it -- its head
    term is back-unified against the calling instruction, exactly as
    normal completion does, so a caller waiting on e.g. `!goal(X)` still
    gets a binding for X. If Goal's frame was the last one on its stack,
    the whole intention simply disappears, like a top-level goal that
    finished on its own.
    """
    import collections

    goal = agentspeak.freeze(term.args[0], intention.scope, {})

    kept = collections.deque()
    for stack in agent.intentions:
        index = None
        for i, item in enumerate(stack):
            if item.head_term == goal:
                index = i
                break
        if index is None:
            kept.append(stack)
            continue

        target = stack[index]
        while len(stack) > index:
            stack.pop()

        if stack and target.calling_term is not None:
            frozen = target.head_term.freeze(target.scope, {})
            caller = stack[-1]
            agentspeak.unify(target.calling_term, frozen, caller.scope, caller.stack)

        if stack:
            kept.append(stack)
        # else: Goal was the last frame on its stack -- the whole
        # intention is now finished, same as a top-level goal completing.

    agent.intentions = kept
    yield


def _plan_to_str(plan):
    """Render a plan as an AgentSpeak string.

    Non-destructive counterpart of runtime.plan_to_str: the stock version calls
    plan.args.pop(0), which mutates the plan and makes it single-use for plans
    that have head arguments. We copy plan.args so a plan can be rendered any
    number of times.
    """
    if isinstance(plan.context, agentspeak.runtime.TrueQuery):
        context = "true"
    else:
        context = plan.context

    body = plan.str_body

    if len(plan.head.args):
        args = list(plan.args)  # copy: do NOT mutate the stored plan
        pattern = r"_X_[0-9a-fA-F]{3}_[0-9a-fA-F]+"
        head = re.sub(pattern, lambda m: args.pop(0) if args else m.group(0), str(plan.head))
    else:
        head = str(plan.head)

    if plan.annotation:
        return f"@{plan.annotation} {plan.trigger.value}{plan.goal_type.value}{head} : {context} <- {body}."
    return f"{plan.trigger.value}{plan.goal_type.value}{head} : {context} <- {body}."


def _normalise_label(raw):
    """Accept a label as an atom, "label" or "@label"; return "@label"."""
    label = asl_str(raw)
    if not label.startswith("@"):
        label = "@" + label
    return label


@actions.add(".add_plan", 1)  # Enric
def _add_plan(agent, term, intention):
    """.add_plan(PlanString)

    Parse a full plan (optionally carrying an @label) from a string and add it
    to the plan library. The string must be a complete plan ending in '.', e.g.
        .add_plan("@l +!g : true <- .print(done).")
    Reuses the interpreter's own tellHow pipeline.
    """
    str_plan = asl_str(agentspeak.grounded(term.args[0], intention.scope))
    agent._tell_how(Literal("plain_text", (str_plan,), frozenset()))
    yield


@actions.add(".remove_plan", 1)  # Enric
def _remove_plan(agent, term, intention):
    """.remove_plan(Label)

    Remove every plan whose @label matches Label. Label may be given as an atom,
    "label" or "@label". Mirrors the label matching already used by _untell_how.
    """
    label = _normalise_label(agentspeak.grounded(term.args[0], intention.scope))
    for plans in agent.plans.values():
        to_delete = [
            p for p in plans
            if p.annotation and ("@" + str(p.annotation.functor)) == label
        ]
        for p in to_delete:
            plans.remove(p)
    yield


@actions.add(".relevant_plans", 2)  # Enric
def _relevant_plans(agent, term, intention):
    """.relevant_plans(TriggerString, Plans)

    Unify Plans with the list of plans relevant to the triggering event given as
    a string (e.g. "+!task", "-!task", "+belief"). A plan is relevant when it has
    the same trigger/goal type and its head unifies with the event head.
    """
    trigger_str = asl_str(agentspeak.grounded(term.args[0], intention.scope))
    if not trigger_str.endswith("."):
        trigger_str += "."

    log = agentspeak.Log(LOGGER, 1)
    tokens = agentspeak.lexer.TokenStream(
        agentspeak.StringSource("<.relevant_plans>", trigger_str), log)
    tok, ast_event = agentspeak.parser.parse_event(tokens.next(), tokens, log)
    if tok.lexeme != ".":
        raise log.error(
            "expected a single triggering event for .relevant_plans, got: '%s'",
            tok.lexeme, loc=tok.loc)
    event = ast_event.accept(agentspeak.runtime.BuildEventVisitor(log))

    frozen = agentspeak.freeze(event.head, intention.scope, {})
    key = (event.trigger, event.goal_type, frozen.functor, len(frozen.args))

    result = tuple(
        _plan_to_str(plan)
        for plan in agent.plans[key]
        if agentspeak.unifies_annotated(plan.head, frozen)
    )

    if agentspeak.unify(term.args[1], result, intention.scope, intention.stack):
        yield


@actions.add(".plan_label", 2)  # Enric
def _plan_label(agent, term, intention):
    """.plan_label(Plan, Label)

    Unify Plan (a plan string) with each plan whose @label matches Label. Label
    may be given as an atom, "label" or "@label". Backtracks over all matches.
    """
    label = _normalise_label(agentspeak.grounded(term.args[1], intention.scope))

    choicepoint = object()
    for plans in agent.plans.values():
        for plan in plans:
            if plan.annotation and ("@" + str(plan.annotation.functor)) == label:
                intention.stack.append(choicepoint)
                if agentspeak.unify(term.args[0], _plan_to_str(plan),
                                    intention.scope, intention.stack):
                    yield
                agentspeak.reroll(intention.scope, intention.stack, choicepoint)

                
# Add the actions used by the optimizer as markers
agentspeak.optimizer.init_optimizer_actions(actions)
