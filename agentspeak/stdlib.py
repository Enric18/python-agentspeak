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

# ---------------------------------------------------------------------------
# MIXED AUTHORSHIP NOTICE
# ---------------------------------------------------------------------------
# This file contains both the original python-agentspeak standard library
# (Niklas Fiekas, copyright above) and a substantial set of internal actions
# added on top of it as part of a TFG (Bachelor's thesis) project: the BDI
# metareasoning actions, plan-library manipulation actions, list/set/string
# actions, meta-programming actions, the communication/lifecycle actions, and
# the persistent event queue's stdlib-side support.
#
# Every function added or modified for the thesis carries an inline
#     # Implemented by Enric Hernandez-Minaya, May-Aug 2026
# comment inside its body, so original vs. added code is unambiguous at a
# glance. Functions without that tag are the original, unmodified baseline.
# All functions, original and added alike, carry step-by-step comments
# explaining what each part of the function does.
# ---------------------------------------------------------------------------

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
#   - .add_plan             #Enric
#   - .plan_label           #Enric
#   - .relevant_plans       #Enric
#   - .relevant_plan        #Enric
#   - .remove_plan          #Enric
#   - .list_plans           #Enric
# * Lists and Strings
#   - .delete                 #Enric
#   - .empty                  #Enric
#   - .reverse                #Enric
#   - .shuffle                #Enric
#   - .nth                    (Base -- already implemented)
#   - .suffix                 #Enric
#   - .prefix                 #Enric
#   - .sublist                #Enric
#   - .difference             #Enric
#   - .intersection           #Enric
#   - .union                  #Enric
# * Belief Base
#   - .belief                #Enric
#   - .count                 (Base -- already implemented)
#   - .namespace              #Enric
#   - .relevant_rules         #Enric
#   - .list_rules             #Enric
#   - .setof                  #Enric
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
#   - .intention             #Enric
#   - .succeed_goal         #Enric
#   - .add_anot / .add_annot #Enric
#   - .at                   #Enric
#   - .create_agent         #Enric
#   - .kill_agent           #Enric
#   - .perceive             #Enric
#   - .suspend               #Enric
#   - .resume                #Enric
#   - .suspended              #Enric


actions = agentspeak.Actions()


@actions.add(".broadcast", 2)
def _broadcast(agent, term, intention):
    # .broadcast(Ilf, Message): send Message to every other agent that
    # shares this agent's own Environment (each BDIAgent builds its own
    # private Environment in practice, so this only reaches agents built
    # via the same Environment object, not arbitrary agents on the
    # platform).

    # Step 1: work out what kind of message this is (tell a belief,
    # take back a belief, or ask the other agent to achieve a goal) from
    # the Ilf ("illocutionary force") argument -- this maps onto the
    # same (trigger, goal_type) pair used everywhere else in the engine
    # to describe an event.
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

    # Step 2: fix the message's content right now (freeze), since the
    # sender's own variables will keep changing after this call
    # returns, and tag it with who sent it (a source(...) annotation)
    # so the receiver knows where it came from.
    # Prepare message.
    message = agentspeak.freeze(term.args[1], intention.scope, {})
    tagged_message = message.with_annotation(
        agentspeak.Literal("source", (agentspeak.Literal(agent.name), )))

    # Step 3: hand the message to every other agent's own .call method
    # -- this is a direct Python call, not real network messaging, and
    # it's exactly the same call the interpreter uses to raise any other
    # kind of event, so the receiver reacts to it just like it would to
    # one of its own internal events.
    # Broadcast.
    for receiver in agent.env.agents.values():
        if receiver == agent:
            continue

        receiver.call(trigger, goal_type, tagged_message, agentspeak.runtime.Intention())

    yield


@actions.add(".send", 3)
def _send(agent, term, intention):
    # .send(Receivers, Ilf, Message): like .broadcast, but only to the
    # named receiver(s) instead of everyone.

    # Step 1: Receivers can be given as one atom/string or as a list of
    # them -- normalise to a list either way, then look each one up by
    # name in this agent's own Environment to get the real Agent object.
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

    # Step 2: work out the (trigger, goal_type) pair from the Ilf
    # argument, same idea as .broadcast but with a few extra
    # performatives supported (unachieve, and the plan-sharing
    # tellHow/untellHow/askHow trio).
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

    # Step 3: build the actual message -- the plan-sharing performatives
    # carry the plan's source code as plain text, everything else
    # carries a frozen (fixed-in-place) copy of the term being sent.
    # TODO: askOne, askAll
    # Prepare message. The message is either a plain text or a structured message.
    if ilf.functor in ["tellHow", "askHow", "untellHow"]:
        message = agentspeak.Literal("plain_text", (term.args[2], ), frozenset())
    else:
        message = agentspeak.freeze(term.args[2], intention.scope, {})

    # Step 4: tag the message with who sent it, same as .broadcast.
    tagged_message = message.with_annotation(
        agentspeak.Literal("source", (agentspeak.Literal(agent.name), )))

    # Step 5: deliver directly to each resolved receiver via its own
    # .call method (again a plain Python call, not real network
    # messaging, in this base engine -- spade_bdi overrides .send with a
    # real XMPP-backed version for actual BDIAgent use).
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
    # .print(Arg0[, Arg1, ...]): print every argument, space-separated,
    # prefixed with the calling agent's name and a colour unique to that
    # agent (so several agents' interleaved output stays readable).

    # Step 1: give this agent a colour the first time it prints, then
    # keep reusing the same one every later call. _color_map and
    # _current_color are default arguments that are only created ONCE,
    # the first time Python defines this function, and then shared and
    # mutated across every call -- a common Python trick for
    # "remembering" state between calls without a class.
    if agent in _color_map:
        color = _color_map[agent]
    else:
        color = COLORS[_current_color[0]]
        _current_color[0] = (_current_color[0] + 1) % len(COLORS)
        _color_map[agent] = color

    # Step 2: fix (freeze) each argument's current value and turn it
    # into text, then join them all with spaces.
    memo = {}
    text = " ".join(asl_str(agentspeak.freeze(t, intention.scope, memo)) for t in term.args)  # freeze+stringify every arg, space-joined

    # Step 3: print the coloured, agent-tagged line to the console.
    with colorama.colorama_text():
        print(color[0], color[1], agent.name, colorama.Fore.RESET, colorama.Back.RESET, " ", text, sep="")

    yield


@actions.add(".printf")  # Enric, variable arity like .concat: format + one or more args
@agentspeak.optimizer.no_scope_effects
def _printf(agent, term, intention, _color_map={}, _current_color=[0]):
    """.printf(Format, Arg0[, Arg1, ...])

    Print Format with Arg0, Arg1, ... substituted in, mirroring Jason's
    own .printf (inspired by Java's printf/format). Uses Python's %
    operator directly: Java's and Python's printf-style directives
    (%d, %s, %f, %08.0f, %10.3f, ...) are the same C-derived syntax, so
    Jason's own docs' examples port unchanged -- .printf("Value
    %08.0f%n", N) becomes .printf("Value %08.0f\\n", N) here, %n not
    being a Python format directive (use a literal newline instead).

    Jason's own docs warn against %d, since Jason's numbers are always
    Java doubles and %d demands an int -- that warning does not carry
    over: Python's % operator converts a float to %d automatically, so
    %d is safe to use here despite this engine's numbers facing the
    exact same always-a-float situation Jason's warning describes.
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    # Step 1: same per-agent colour bookkeeping as .print above.
    if agent in _color_map:
        color = _color_map[agent]
    else:
        color = COLORS[_current_color[0]]
        _current_color[0] = (_current_color[0] + 1) % len(COLORS)
        _color_map[agent] = color

    # Step 2: the first argument must be a plain format string
    # (something like "Value %d").
    memo = {}
    fmt = agentspeak.grounded(term.args[0], intention.scope)
    if not agentspeak.is_string(fmt):
        raise agentspeak.AslError("expected a format string for .printf, got: '%s'" % (fmt, ))

    # Step 3: fix every remaining argument's value, then let Python's
    # own % (printf-style) formatting fill them into the format string.
    args = tuple(agentspeak.freeze(t, intention.scope, memo) for t in term.args[1:])
    text = fmt % args  # classic C-style printf substitution, e.g. "%d apples" % (3,)

    # Step 4: print the coloured, agent-tagged, formatted line.
    with colorama.colorama_text():
        print(color[0], color[1], agent.name, colorama.Fore.RESET, colorama.Back.RESET, " ", text, sep="")

    yield


@actions.add(".fail", 0)
@agentspeak.optimizer.no_scope_effects
def _fail(agent, term, intention):
    # .fail always fails on purpose: it returns before ever reaching the
    # yield below, so this generator produces zero solutions. (The
    # unreachable yield is only there so Python still treats this
    # function as a generator, matching every other action's shape.)
    return
    yield


@actions.add(".my_name", 1)
@agentspeak.optimizer.function_like
def _my_name(agent, term, intention):
    # .my_name(X): succeed by matching X against this agent's own name.
    # agentspeak.unify tries to make the two sides equal -- if X is an
    # unbound variable it gets bound to the agent's name; if X already
    # has a value, unify only succeeds when that value is already the
    # same name.
    if agentspeak.unify(term.args[0], Literal(agent.name), intention.scope, intention.stack):
        yield


@actions.add(".concat")
@agentspeak.optimizer.function_like
def _concat(agent, term, intention):
    # Step 1: read every argument except the last one (the last one is
    # where the result goes).
    args = [agentspeak.grounded(arg, intention.scope) for arg in term.args[:-1]]

    # Step 2: if every argument is a list, glue them into one flat list;
    # otherwise treat them as text and glue their string forms together.
    if all(isinstance(arg, (tuple, list)) for arg in args):
        result = tuple(el for arg in args for el in arg)  # flatten all the lists into one
    else:
        result = "".join(str(arg) for arg in args)

    # Step 3: match the result against the last argument.
    if agentspeak.unify(term.args[-1], result, intention.scope, intention.stack):
        yield


actions.add_function(".random", (), random.random)


@actions.add(".set_random_seed", 1)  # Enric
def _set_random_seed(agent, term, intention):
    """.set_random_seed(N)

    Sets the seed of the random number generator .random/.shuffle draw
    from, mirroring Jason's .set_random_seed(N). Always succeeds.

    Scope difference, stated precisely: Jason seeds a *per-agent* random
    generator (each agent has its own), whereas .random/.shuffle here go
    through Python's global random module -- so this reseeds the same
    generator every agent in the process shares, not just the calling
    agent's own stream. A per-agent generator isn't something this
    engine's Agent class carries today.
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    # Step 1: read the seed value.
    seed = agentspeak.grounded(term.args[0], intention.scope)
    # Step 2: reseed Python's shared random generator, so every future
    # .random/.shuffle call becomes reproducible.
    random.seed(seed)
    yield


actions.add_function(".min", (tuple, ), min)
actions.add_function(".max", (tuple, ), max)
actions.add_function(".length", (None, ), len)


@actions.add_function(".nth", (int, tuple))
def _nth(index, l):
    # .nth(Index, List): plain 0-based indexing into the list, refusing
    # a negative index (Python would otherwise silently count from the
    # end, which isn't what .nth is meant to do).
    assert index >= 0
    return l[index]


@actions.add_function(".sort", (tuple, ))
def _sort(l):
    # .sort(List): return a new sorted copy, the input list is untouched.
    return tuple(sorted(l))


@actions.add(".substring", 3)
@agentspeak.optimizer.function_like
def _substring(agent, term, intention):
    # .substring(Needle, Haystack, Pos): find where Needle occurs inside
    # Haystack. There can be more than one occurrence, so this behaves
    # like a small Prolog-style search: find one match, hand it back
    # (yield) to the caller, and if the caller wants another answer
    # (backtracking) look for the next occurrence instead of stopping.
    needle = asl_str(agentspeak.grounded(term.args[0], intention.scope))
    haystack = asl_str(agentspeak.grounded(term.args[1], intention.scope))

    choicepoint = object()  # a marker used below to undo bindings between attempts

    pos = haystack.find(needle)
    while pos != -1:
        # Step 1: mark a "checkpoint" before trying this position, so it
        # can be undone later if the caller wants another answer.
        intention.stack.append(choicepoint)

        # Step 2: try to match Pos against the position we found (this
        # is unification: if Pos is a free variable it gets bound to the
        # number; if it already has a value, this only succeeds when
        # that value is exactly this position).
        if agentspeak.unify(term.args[2], pos, intention.scope, intention.stack):
            yield

        # Step 3: undo whatever got bound above (reroll = "roll back to
        # the checkpoint"), then look for the next occurrence and repeat.
        agentspeak.reroll(intention.scope, intention.stack, choicepoint)
        pos = haystack.find(needle, pos + 1)


@actions.add(".replace", 4)  # Enric
def _replace(agent, term, intention):
    """.replace(S1, S2, S3, S4)

    Unify S4 with S1 (a string, or any other term converted to its string
    representation, matching Jason's own arg[0].toString() fallback) with
    every occurrence of pattern S2 replaced by S3, mirroring Jason's
    .replace(S1,S2,S3,S4). Jason's own implementation is Java's
    String.replaceAll -- i.e. S2 is a regex, not a literal substring, and
    S3 may contain backreferences -- so this reuses Python's re.sub
    directly rather than a plain str.replace; the one unavoidable
    difference is backreference syntax (Python's re.sub takes \\1, not
    Java's $1), inherent to porting a Java-regex-shaped action onto
    Python's own regex engine, not a deliberate behavioural choice.
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    import re

    # Step 1: read S1 (the text to search), S2 (the pattern) and S3 (the
    # replacement).
    s1 = agentspeak.grounded(term.args[0], intention.scope)
    s2 = agentspeak.grounded(term.args[1], intention.scope)
    s3 = agentspeak.grounded(term.args[2], intention.scope)

    # Step 2: if S1 isn't already a string, convert it to its text form
    # first; S2/S3 must already be strings.
    source = s1 if agentspeak.is_string(s1) else asl_str(s1)
    if not agentspeak.is_string(s2):
        raise agentspeak.AslError("expected pattern for .replace to be a string")
    if not agentspeak.is_string(s3):
        raise agentspeak.AslError("expected replacement for .replace to be a string")

    # Step 3: run the regex substitution (S2 is treated as a regular
    # expression pattern, not just a literal piece of text).
    result = re.sub(s2, s3, source)

    # Step 4: match the result against S4.
    if agentspeak.unify(result, term.args[3], intention.scope, intention.stack):
        yield


@actions.add(".lower_case", 2)  # Enric
def _lower_case(agent, term, intention):
    """.lower_case(S1, S2)

    Unify S2 with S1 (a string, or any other term converted to its string
    representation, matching Jason's own arg[0].toString() fallback)
    lower-cased. Mirrors Jason's .lower_case(S1,S2).
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    # Step 1: read S1, converting it to text first if it wasn't already
    # a string.
    s1 = agentspeak.grounded(term.args[0], intention.scope)
    source = s1 if agentspeak.is_string(s1) else asl_str(s1)

    # Step 2: match the lower-cased text against S2.
    if agentspeak.unify(source.lower(), term.args[1], intention.scope, intention.stack):
        yield


@actions.add(".upper_case", 2)  # Enric
def _upper_case(agent, term, intention):
    """.upper_case(S1, S2)

    Unify S2 with S1 (a string, or any other term converted to its string
    representation, matching Jason's own arg[0].toString() fallback)
    upper-cased. Mirrors Jason's .upper_case(S1,S2).
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    # Step 1: read S1, converting it to text first if it wasn't already
    # a string.
    s1 = agentspeak.grounded(term.args[0], intention.scope)
    source = s1 if agentspeak.is_string(s1) else asl_str(s1)

    # Step 2: match the upper-cased text against S2.
    if agentspeak.unify(source.upper(), term.args[1], intention.scope, intention.stack):
        yield


@actions.add(".member", 2)
@agentspeak.optimizer.function_like
def _member(agent, term, intention):
    # .member(X, List): true if X is one of List's elements. This loop
    # is the classic Prolog-style "try each candidate" pattern: go
    # through the list one element at a time, and for each one attempt
    # to match it against X; every time that succeeds, hand a solution
    # back to the caller (yield). If the caller backtracks and asks for
    # another answer, undo that match (reroll) and try the next element.
    choicepoint = object()

    for member in agentspeak.evaluate(term.args[1], intention.scope):
        intention.stack.append(choicepoint)

        if agentspeak.unify(term.args[0], member, intention.scope, intention.stack):
            yield

        agentspeak.reroll(intention.scope, intention.stack, choicepoint)


def _delete_range(target, start, end):
    """Shared by both .delete arities: remove the half-open index range
    [start, end) from a list or a string. Matches Jason's own delete.java
    exactly (deleteFromList/deleteFromString there use the same half-open
    convention: .delete(1,3,[a,b,c,a],L) keeps indices 0 and 3, unifying L
    with [a,a]).
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    # Step 1: for a string, cut out characters start..end-1 by keeping
    # everything before start and everything from end onward.
    if agentspeak.is_string(target):
        # Java's String.substring throws (caught, returns unchanged) for a
        # negative index; Python slicing instead reinterprets a negative
        # index as counting from the end, which would silently do
        # something different. Guard explicitly rather than inherit that
        # mismatch; an end/start past the string's length is already
        # handled the same way by both languages (Python's slicing clips,
        # Java's exception is caught and returns the string unchanged).
        if start < 0 or end < 0:
            return target
        return target[:start] + target[end:]
    elif agentspeak.is_list(target):
        # Step 2: for a list, keep only the elements whose index falls
        # outside the [start, end) range being removed.
        return tuple(item for i, item in enumerate(target) if i < start or i >= end)  # keep everything NOT in [start, end)
    else:
        raise agentspeak.AslError(
            "expected a list or string target for .delete, got: '%s'" % (target,))


@actions.add(".delete", 3)  # Enric
@actions.add(".delete", 4)  # Enric
def _delete(agent, term, intention):
    """.delete(Arg0, Target, Result) or .delete(Start, End, Target, Result)

    Mirrors Jason's .delete exactly: one action, sharing the same name
    across both arities (not two independent list/string actions), which
    dispatches on the runtime type of its first argument(s) rather than
    on target type alone:

    - 4 args: Start and End are both numbers -- delete the half-open
      index range [Start, End) from Target (a list or a string).
    - 3 args, Arg0 a number: delete a single element/character at index
      Arg0 (equivalent to the 4-arg form with End = Arg0 + 1).
    - 3 args, Arg0 a string: Target must also be a string; delete every
      occurrence of the substring Arg0 from it. Jason's own
      implementation does this via Java's String.replaceAll, which --
      easy to miss -- treats Arg0 as a *regex*, not a literal substring;
      a substring containing regex metacharacters (".", "*", "(", ...)
      would be interpreted as a pattern there. That reads as an
      implementation accident rather than the intended semantics (the
      documentation only ever says "substring"), so this port uses a
      plain literal replace instead, deliberately diverging from the
      reference implementation's literal behaviour to match its
      documented intent.
    - 3 args, Arg0 anything else (atom, literal, structure): Target must
      be a list; delete every element that unifies with Arg0 (full
      unification, not just equality, matching Jason's own
      un.unifies(element, t) check -- e.g. an Arg0 containing variables
      can match structurally, not just identical ground terms).

    In every case Result unifies with the list/string after deletion;
    like any unification, giving a Result that does not match what
    deletion actually produces simply fails
    (.delete(a,[a,b,c,a],[c]) fails, it does not raise an error).
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    args = term.args

    # Step 1: the 4-argument form is a plain numeric index-range delete
    # -- reuse _delete_range directly.
    if len(args) == 4:
        start = agentspeak.grounded(args[0], intention.scope)
        end = agentspeak.grounded(args[1], intention.scope)
        target = agentspeak.grounded(args[2], intention.scope)
        result_arg = args[3]
        if not (agentspeak.is_number(start) and agentspeak.is_number(end)):
            raise agentspeak.AslError("expected numeric Start/End for .delete/4")
        result = _delete_range(target, int(start), int(end))
    else:
        # Step 2: the 3-argument form branches on the TYPE of the first
        # argument to decide what kind of deletion is meant.
        arg0 = agentspeak.grounded(args[0], intention.scope)
        target = agentspeak.grounded(args[1], intention.scope)
        result_arg = args[2]

        if agentspeak.is_number(arg0):
            # A number: delete just that one index (same as the 4-arg
            # form with end = start + 1).
            start = int(arg0)
            result = _delete_range(target, start, start + 1)
        elif agentspeak.is_string(arg0):
            # A string: delete every occurrence of that literal text.
            if not agentspeak.is_string(target):
                raise agentspeak.AslError(
                    "expected a string target for .delete when the first argument is a string")
            result = target.replace(arg0, "")
        else:
            # Anything else (an atom/structure/list element pattern):
            # keep only the list elements that do NOT unify with it --
            # i.e. try to match arg0 against each element in turn, and
            # drop every one where that match succeeds.
            if not agentspeak.is_list(target):
                raise agentspeak.AslError(
                    "expected a list target for .delete when the first argument is a term")
            result = tuple(item for item in target if not agentspeak.unifies(arg0, item))  # drop every item that matches arg0

    # Step 3: match the computed result against the output argument.
    if agentspeak.unify(result, result_arg, intention.scope, intention.stack):
        yield


def _list_or_string(agent, term_arg, intention, action_name):
    """Shared argument check: read a value and make sure it's a list or
    a string, raising a clear error (naming the calling action) if not.
    Used by every list/string action below that accepts either kind.
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    # Step 1: resolve the value.
    value = agentspeak.grounded(term_arg, intention.scope)
    # Step 2: reject anything that isn't a list or a string.
    if not (agentspeak.is_list(value) or agentspeak.is_string(value)):
        raise agentspeak.AslError(
            "expected a list or string for %s, got: '%s'" % (action_name, value))
    return value


@actions.add(".empty", 1)  # Enric
def _empty(agent, term, intention):
    """.empty(X)

    Test whether the list or string X has no elements/characters. Mirrors
    Jason's .empty(Arg): "checks whether the argument does not have any
    term."
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    # Step 1: succeed only if the list/string is length 0 -- no
    # unification needed here, this is a plain true/false test.
    value = _list_or_string(agent, term.args[0], intention, ".empty")
    if len(value) == 0:
        yield


@actions.add(".reverse", 2)  # Enric
def _reverse(agent, term, intention):
    """.reverse(X, Result)

    Unify Result with X (a list or a string) reversed. Mirrors Jason's
    .reverse(Arg, Reversed). Jason's own third example reverses an *open*
    list with a free tail variable ([a,b,c|T]), keeping the tail in
    place; this fork's lists have no such open/cons-with-tail-variable
    syntax at all, so only plain, fully-ground lists and strings are
    supported here.
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    # Step 1: reverse a string with Python's [::-1] slice trick, or a
    # list with the built-in reversed().
    value = _list_or_string(agent, term.args[0], intention, ".reverse")
    if agentspeak.is_string(value):
        result = value[::-1]  # slice with a step of -1 == reversed order
    else:
        result = tuple(reversed(value))

    # Step 2: match the reversed value against Result.
    if agentspeak.unify(result, term.args[1], intention.scope, intention.stack):
        yield


@actions.add(".shuffle", 2)  # Enric
def _shuffle(agent, term, intention):
    """.shuffle(List, Result)

    Unify Result with List in some random order. Mirrors Jason's
    .shuffle(List, Var); like .random, this is a single-shot draw (one
    random permutation per call), not backtracking over every possible
    permutation.
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    # Step 1: read the list, requiring it to actually be one.
    value = agentspeak.grounded(term.args[0], intention.scope)
    if not agentspeak.is_list(value):
        raise agentspeak.AslError("expected a list for .shuffle, got: '%s'" % (value,))

    # Step 2: shuffle a mutable copy in place (Python's tuples can't be
    # shuffled directly), then match it against Result.
    shuffled = list(value)
    random.shuffle(shuffled)

    if agentspeak.unify(tuple(shuffled), term.args[1], intention.scope, intention.stack):
        yield


@actions.add(".suffix", 2)  # Enric
def _suffix(agent, term, intention):
    """.suffix(Suffix, List)

    Test/enumerate whether Suffix is a suffix of List (a list or a
    string). Backtracks from the longest suffix (List itself) down to the
    empty one, matching Jason's own documented order for
    .suffix(Suffix, List) exactly:
    .suffix(X,[a,b,c]) unifies X with [a,b,c], [b,c], [c], [] in that order.
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    value = _list_or_string(agent, term.args[1], intention, ".suffix")

    # This is the same Prolog-style "try each candidate in turn" pattern
    # seen elsewhere in this file: for every possible cut point i (from
    # 0 up to the full length), take the slice value[i:] (everything
    # from i to the end -- a candidate suffix) and try to match Suffix
    # against it. Each match is handed back with yield; if the caller
    # backtracks for another answer, reroll undoes the match and the
    # loop moves to the next, shorter candidate.
    choicepoint = object()
    for i in range(len(value) + 1):
        intention.stack.append(choicepoint)
        if agentspeak.unify(term.args[0], value[i:], intention.scope, intention.stack):
            yield
        agentspeak.reroll(intention.scope, intention.stack, choicepoint)


@actions.add(".prefix", 2)  # Enric
def _prefix(agent, term, intention):
    """.prefix(Prefix, List)

    Test/enumerate whether Prefix is a prefix of List (a list or a
    string). Backtracks from the longest prefix (List itself) down to the
    empty one -- Jason's own documentation is explicit that this is
    deliberately the opposite of the usual logic-programming convention
    of increasing length, and this mirrors that choice exactly:
    .prefix(X,[a,b,c]) unifies X with [a,b,c], [a,b], [a], [] in that order.
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    value = _list_or_string(agent, term.args[1], intention, ".prefix")

    # Same try-each-candidate pattern as .suffix above, just walking the
    # cut point i backwards (from the full length down to 0), so
    # value[:i] (everything from the start up to i -- a candidate
    # prefix) is tried longest-first.
    choicepoint = object()
    for i in range(len(value), -1, -1):
        intention.stack.append(choicepoint)
        if agentspeak.unify(term.args[0], value[:i], intention.scope, intention.stack):
            yield
        agentspeak.reroll(intention.scope, intention.stack, choicepoint)


@actions.add(".sublist", 2)  # Enric
def _sublist(agent, term, intention):
    """.sublist(Sublist, List)

    Test/enumerate whether Sublist is a *contiguous* sublist of List (a
    list or a string) -- not an arbitrary subset. Mirrors Jason's own
    .sublist(S, L) exactly, including its documented enumeration order
    (prefixes of List, then prefixes of each successive suffix of List,
    and finally the empty sublist):
    .sublist(X,[a,b,c]) unifies X with [a,b,c], [a,b], [a], [b,c], [b], [c], []
    in that order.
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    value = _list_or_string(agent, term.args[1], intention, ".sublist")

    def _sublists():
        # Step 1: a small local generator listing every contiguous
        # slice of value, in the exact order Jason documents: for each
        # start position, every end position from longest down to
        # shortest, then finally the empty slice on its own.
        n = len(value)
        for start in range(n):
            for end in range(n, start, -1):
                yield value[start:end]
        yield value[0:0]  # the empty sublist, tried last

    # Step 2: same try-each-candidate-then-backtrack pattern as
    # .suffix/.prefix above, just driven by the _sublists() generator
    # instead of a plain range().
    choicepoint = object()
    for sub in _sublists():
        intention.stack.append(choicepoint)
        if agentspeak.unify(term.args[0], sub, intention.scope, intention.stack):
            yield
        agentspeak.reroll(intention.scope, intention.stack, choicepoint)


def _as_two_lists(term, intention, action_name):
    """Shared argument check for .difference/.intersection/.union: read
    the first two arguments and make sure both are lists.
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    s1 = agentspeak.grounded(term.args[0], intention.scope)
    s2 = agentspeak.grounded(term.args[1], intention.scope)
    if not (agentspeak.is_list(s1) and agentspeak.is_list(s2)):
        raise agentspeak.AslError("expected two lists for %s" % action_name)
    return s1, s2


@actions.add(".difference", 3)  # Enric
def _difference(agent, term, intention):
    """.difference(S1, S2, S3)

    Unify S3 with the elements of S1 (represented as a list) that are not
    in S2, treated as sets: deduplicated and sorted. Mirrors Jason's
    .difference(S1, S2, S3): "the result set is sorted."
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    # Step 1: read both lists.
    s1, s2 = _as_two_lists(term, intention, ".difference")
    # Step 2: treat them as Python sets and subtract -- keep only what's
    # in S1 but not in S2 -- then sort for a predictable order.
    result = tuple(sorted(set(s1) - set(s2)))
    # Step 3: match the result against S3.
    if agentspeak.unify(result, term.args[2], intention.scope, intention.stack):
        yield


@actions.add(".intersection", 3)  # Enric
def _intersection(agent, term, intention):
    """.intersection(S1, S2, S3)

    Unify S3 with the elements common to both S1 and S2 (lists treated as
    sets): deduplicated and sorted. Mirrors Jason's .intersection(S1, S2, S3).
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    # Step 1: read both lists, then keep only elements present in BOTH
    # (set intersection), sorted for a predictable order.
    s1, s2 = _as_two_lists(term, intention, ".intersection")
    result = tuple(sorted(set(s1) & set(s2)))
    # Step 2: match the result against S3.
    if agentspeak.unify(result, term.args[2], intention.scope, intention.stack):
        yield


@actions.add(".union", 3)  # Enric
def _union(agent, term, intention):
    """.union(S1, S2, S3)

    Unify S3 with every element in S1 or S2 (lists treated as sets):
    deduplicated and sorted. Mirrors Jason's .union(S1, S2, S3).
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    # Step 1: read both lists, then combine them (set union, so
    # duplicates collapse), sorted for a predictable order.
    s1, s2 = _as_two_lists(term, intention, ".union")
    result = tuple(sorted(set(s1) | set(s2)))
    # Step 2: match the result against S3.
    if agentspeak.unify(result, term.args[2], intention.scope, intention.stack):
        yield


actions.add_predicate(".atom", (None, ), agentspeak.is_atom)
actions.add_predicate(".literal", (None, ), agentspeak.is_literal)
actions.add_predicate(".list", (None, ), agentspeak.is_list)
actions.add_predicate(".number", (None, ), agentspeak.is_number)
actions.add_predicate(".string", (None, ), agentspeak.is_string)
actions.add_predicate(".structure", (None, ), agentspeak.is_structure)


@actions.add(".type", 2)  # Enric
def _type(agent, term, intention):
    """.type(Term, Type)

    Retrieve or check Term's type(s), mirroring Jason's .type(argument,
    type): a single query, backtracking through every type that applies
    (a plain atom is simultaneously 'atom', 'literal' and 'ground', for
    instance), rather than needing the six separate .atom/.literal/.list/
    .number/.string/.structure predicates above plus .ground one at a
    time. If Type is already bound, this only succeeds for a matching
    type (a plain boolean check); if unbound, it enumerates every
    applicable type via backtracking, most primitive first, exactly as
    Jason orders them.

    Term itself is evaluated, not grounded: Jason's own .type(X,T) with X
    still an unbound variable is well-defined (T unifies with 'free'
    alone, not an error), so this must not raise the way .grounded()
    would for such a Term.

    Jason additionally recognises 'set', 'map', 'queue', 'rule' and
    'plan' as types -- this engine has no equivalent term types for any
    of those, so they can never apply here and are omitted rather than
    included as permanently-dead checks.
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    # Step 1: resolve Term without demanding it be fully bound -- an
    # unbound variable is a valid, expected input here (it should just
    # come out as "free"), unlike most other actions.
    value = agentspeak.evaluate(term.args[0], intention.scope)

    # Step 2: run every applicable type check and collect the ones that
    # pass -- a single value can genuinely match several types at once
    # (e.g. a plain atom is "atom", "literal" AND "ground" all together).
    types = []
    if agentspeak.is_number(value):
        types.append("number")
    if agentspeak.is_atom(value):
        types.append("atom")
    if agentspeak.is_literal(value):
        types.append("literal")
    if agentspeak.is_string(value):
        types.append("string")
    if agentspeak.is_list(value):
        types.append("list")
    if agentspeak.is_structure(value):
        types.append("structure")
    if agentspeak.is_ground(value, intention.scope):
        types.append("ground")
    if isinstance(value, agentspeak.Var):
        types.append("free")

    # Step 3: same try-each-candidate-then-backtrack pattern used
    # throughout this file -- offer each matching type name to Type in
    # turn. If Type was already bound to a specific type name, only that
    # one iteration's unify call can succeed; if Type was a free
    # variable, the caller gets one answer per matching type, one at a
    # time, via backtracking.
    choicepoint = object()
    for type_name in types:
        intention.stack.append(choicepoint)
        if agentspeak.unify(term.args[1], Literal(type_name), intention.scope, intention.stack):
            yield
        agentspeak.reroll(intention.scope, intention.stack, choicepoint)


@actions.add(".eval", 2)  # Enric
def _eval(agent, term, intention):
    """.eval(Var, Expr)

    Evaluate the logical/arithmetic expression Expr and unify Var with
    the atom 'true' or 'false', mirroring Jason's .eval(term,query) --
    e.g. .eval(X, true | false) and .eval(X, 3<5 & not 4+2<3) both unify
    X with 'true', exactly as Jason's own reference examples show.

    Scope limit, stated precisely rather than silently mismatched: Jason's
    own Expr is a genuine LogicalFormula, which can also perform belief-
    base queries (backtracking consultation of beliefs/rules) as part of
    the expression -- Jason's .eval bypasses its normal argument
    evaluation specifically to receive Expr unevaluated, as a query
    object, for exactly this reason. This engine has no equivalent: an
    action's arguments are always compiled as plain terms (via
    BuildTermVisitor), never as queries (only plan contexts and
    if/while/for conditions compile through BuildQueryVisitor into
    query objects) -- so Expr here can only be pure arithmetic/logical
    evaluation over already-bound values (&, |, not, comparisons,
    arithmetic), the same class of expression this engine's BinaryExpr/
    UnaryExpr already reduce to a plain bool without consulting the
    belief base. A belief literal used inside Expr is not looked up the
    way a real query would; if Expr doesn't reduce to a bool, this
    raises rather than silently misbehaving.
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    # Step 1: evaluate the expression down to a plain Python bool
    # (arithmetic/comparisons/&/|/not all reduce this way already).
    value = agentspeak.evaluate(term.args[1], intention.scope)
    if not isinstance(value, bool):
        raise agentspeak.AslError(
            "expected a logical/boolean expression for .eval's second "
            "argument, got: %r" % (value, ))

    # Step 2: match Var against the atom true or false.
    result = Literal("true") if value else Literal("false")
    if agentspeak.unify(term.args[0], result, intention.scope, intention.stack):
        yield


@actions.add(".ground", 1)
@agentspeak.optimizer.no_scope_effects
def _ground(agent, term, intention):
    # .ground(Term): succeed only if Term has no unbound variables left
    # (a plain true/false test, no unification/binding happens here).
    if agentspeak.is_ground(term, intention.scope):
        yield


@actions.add(".add_annot", 3)  # Enric
@agentspeak.optimizer.function_like
def _add_annot(agent, term, intention):
    """.add_annot(Belief, Annotation, Result)

    Add Annotation to Belief and unify the outcome with Result, without
    mutating Belief: .add_annot(a, source(jomi), B) unifies B with
    a[source(jomi)]. If Belief is a list, the annotation is added to every
    element instead, and Result unifies with the resulting list, e.g.
    .add_annot([a1,a2], source(jomi), B) unifies B with
    [a1[source(jomi)], a2[source(jomi)]]. Mirrors Jason's .add_annot
    exactly, args and all -- as Jason's own docs note, plain unification
    (e.g. B = a[source(jomi)]) already does the same thing, so this
    action exists purely for parity with the reference stdlib.
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    # Step 1: fix (freeze) both Belief and Annotation's current values.
    belief = agentspeak.freeze(term.args[0], intention.scope, {})
    annotation = agentspeak.freeze(term.args[1], intention.scope, {})

    # Step 2: if Belief is a list, add the annotation to every literal
    # element in it (non-literal elements pass through unchanged); if
    # it's a single literal, add it directly.
    if agentspeak.is_list(belief):
        result = tuple(
            item.with_annotation(annotation) if agentspeak.is_literal(item) else item
            for item in belief
        )  # tag every literal in the list, leave everything else as-is
    elif agentspeak.is_literal(belief):
        result = belief.with_annotation(annotation)
    else:
        raise agentspeak.AslError(
            "expected a literal or a list of literals for .add_annot, got: '%s'" % belief)

    # Step 3: match the annotated result against Result.
    if agentspeak.unify(term.args[2], result, intention.scope, intention.stack):
        yield


@actions.add(".add_nested_source", 3)  # Enric
def _add_nested_source(agent, term, intention):
    """.add_nested_source(Belief, Source, Result)

    Unify Result with Belief (a literal, or a list of literals -- applied
    to each element), replacing any existing 'source(...)' annotation(s)
    with a new one wrapping Source, nesting the old source annotation(s)
    as annotations *on* the new one rather than discarding them --
    mirrors Jason's own .add_nested_source exactly, including its
    documented provenance-chain example:
    .add_nested_source(a[source(bob)], jomi, B) unifies B with
    a[source(jomi)[source(bob)]], i.e. "I believe a; my source is jomi;
    jomi's own source was bob" -- a chain of who-told-whom, not merely
    who last told me. Anything that isn't a literal or a list passes
    through unchanged, matching Jason's own fallthrough.

    Distinct from .add_annot: .add_annot always *adds* an annotation
    alongside whatever is already there (so a second .add_annot with a
    new source would leave two source(...) annotations side by side).
    This action specifically replaces the existing source(s), preserving
    them as nested provenance instead -- the two actions are not
    interchangeable for source-tracking.
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    # Step 1: fix (freeze) Belief and Source's current values.
    belief = agentspeak.freeze(term.args[0], intention.scope, {})
    source = agentspeak.freeze(term.args[1], intention.scope, {})

    def add_source(value):
        # Step 2: recurse into lists (apply to every element); for a
        # literal, split its existing annotations into the source(...)
        # ones and everything else, wrap the old source(s) *inside* a
        # brand-new source(...) annotation (nesting them, not discarding
        # them), and rebuild the literal with that new annotation set
        # (the old non-source annotations, plus the new nested source).
        if agentspeak.is_list(value):
            return tuple(add_source(item) for item in value)
        if agentspeak.is_literal(value):
            is_source = lambda a: agentspeak.is_literal(a) and a.functor == "source"  # true only for a source(...) annotation
            existing_sources = frozenset(a for a in value.annots if is_source(a))
            remaining = frozenset(a for a in value.annots if not is_source(a))
            new_source = Literal("source", (source, ), existing_sources)  # wraps the old source(s) inside the new one
            return Literal(value.functor, value.args, remaining | frozenset([new_source]))
        # Step 3: anything that isn't a list or a literal is returned
        # unchanged (matches Jason's own fallthrough behaviour).
        return value

    result = add_source(belief)
    if agentspeak.unify(term.args[2], result, intention.scope, intention.stack):
        yield


@actions.add(".findall", 3)
@agentspeak.optimizer.function_like
def _findall(agent, term, intention):
    # .findall(Template, Goal, List): run Goal as a query and collect
    # one copy of Template per solution found. TermQuery.execute is
    # itself a Prolog-style search under the hood (it tries the belief
    # base, then rules, backtracking between attempts) and produces one
    # "yield" per solution -- here we simply run through every one of
    # those solutions and remember Template's value at that point,
    # rather than yielding back to our own caller each time.
    pattern = agentspeak.evaluate(term.args[0], intention.scope)
    query = agentspeak.runtime.TermQuery(term.args[1])
    result = []

    memo = {}
    for _ in query.execute(agent, intention):
        result.append(agentspeak.freeze(pattern, intention.scope, memo))

    # Match the whole collected list against the output argument.
    if agentspeak.unify(tuple(result), term.args[2], intention.scope, intention.stack):
        yield


@actions.add(".count", 2)
@agentspeak.optimizer.function_like
def _count(agent, term, intention):
    # .count(Goal, N): run Goal as a query purely to count how many
    # solutions it has. A choicepoint wraps the whole counting loop so
    # any variable bindings made while trying each solution get undone
    # (reroll) once we're done -- .count must not leave Goal's own
    # bindings lying around afterwards, it should behave as if it never
    # touched the caller's variables at all.
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
    # .abolish(Pattern): remove every belief matching Pattern from the
    # belief base.
    # Step 1: fix Pattern's value and look up the matching belief group
    # (beliefs are stored bucketed by (functor, arity)).
    memo = {}
    pattern = agentspeak.freeze(term.args[0], intention.scope, memo)
    group = agent.beliefs[pattern.literal_group()]

    # Step 2: go through every belief in that group and remove the ones
    # that match Pattern (unifies_annotated just checks whether they
    # COULD match, without keeping any binding around afterwards). We
    # loop over list(group) -- a snapshot copy -- rather than group
    # itself, because removing items from a set while iterating over it
    # directly would be unsafe.
    for old_belief in list(group):
        if agentspeak.unifies_annotated(old_belief, pattern):
            group.remove(old_belief)

    yield


@actions.add(".belief", 1)  # Enric
def _belief(agent, term, intention):
    """.belief(Bel)

    Test/enumerate Bel against the belief base only, excluding rules and
    rule-derived inference -- unlike an ordinary ?Bel or plan-context
    query (TermQuery), which also consults agent.rules. Mirrors Jason's
    .belief(+/-Bel): "considers only the set of beliefs in the BB."
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    # Step 1: resolve Bel and find the matching (functor, arity) belief
    # group.
    pattern = agentspeak.evaluate(term.args[0], intention.scope)
    try:
        group = pattern.literal_group()
    except AttributeError:
        raise agentspeak.AslError("expected a literal for .belief, got: '%s'" % pattern)

    # Step 2: try to match Bel against every belief in that group in
    # turn (this is the try-each-candidate backtracking pattern again:
    # unify_annotated itself is a small generator that yields once per
    # way the two sides can be made to match, including their
    # annotations, e.g. [source(bob)]) -- each match becomes one answer
    # handed back to whoever called .belief.
    for belief in agent.beliefs[group]:
        for _ in agentspeak.unify_annotated(pattern, belief, intention.scope, intention.stack):
            yield


@actions.add(".namespace", 1)  # Enric
def _namespace(agent, term, intention):
    """.namespace(X)

    Test whether X names a namespace. python-agentspeak has no namespace
    ("::") syntax at all -- it appears nowhere in the lexer, parser or
    runtime -- so no term is ever a namespace here. This is a well-defined
    "always fails" fallback, the same reasoning already used for
    .drop_event and .perceive where the reference feature has no
    machinery in this engine to attach to. Kept as a real action (rather
    than left unimplemented) purely for signature parity with Jason's
    .namespace(Arg).
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    # No namespace concept exists in this engine -- always fail (return
    # before the unreachable yield below, same trick as .fail uses).
    return
    yield


@actions.add(".relevant_rules", 2)  # Enric
def _relevant_rules(agent, term, intention):
    """.relevant_rules(Literal, Rules)

    Unify Rules with the list of rules (rendered as strings) whose head
    has the same functor/arity as Literal and unifies with it. Mirrors
    Jason's .relevant_rules(p(_), LP). Companion to .relevant_plans, but
    over agent.rules instead of agent.plans -- rules have no trigger/goal
    type to index by, just (functor, arity).
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    # Step 1: fix Literal's value and require it actually be a literal.
    pattern = agentspeak.freeze(term.args[0], intention.scope, {})
    if not agentspeak.is_literal(pattern):
        raise agentspeak.AslError(
            "expected a literal for .relevant_rules, got: '%s'" % pattern)

    # Step 2: look up the matching (functor, arity) bucket of rules,
    # then keep only the ones whose own head can be matched against
    # Literal (unifies_annotated here is used just as a yes/no check --
    # "would this rule's head line up with Literal?" -- not to actually
    # bind anything), rendering each survivor as its plain text form.
    key = (pattern.functor, len(pattern.args))
    result = tuple(
        str(rule) for rule in agent.rules[key]
        if agentspeak.unifies_annotated(rule.head, pattern)
    )  # keep only rules whose head could match Literal

    # Step 3: match the whole list against Rules.
    if agentspeak.unify(term.args[1], result, intention.scope, intention.stack):
        yield


@actions.add(".list_rules", 0)  # Enric
def _list_rules(agent, term, intention):
    """.list_rules

    Print every rule in the belief base, one per line (Rule.__str__
    already renders as "head :- query"). Mirrors Jason's .list_rules; a
    debug aid like .dump/.list_plans, so it prints directly rather than
    through the agent-tagged .print.
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    # Step 1: print a header, then every rule in every bucket, straight
    # to the console (not through .print, since this is a debug tool,
    # not agent output).
    LOGGER.info("Rules")
    for rules in agent.rules.values():
        for rule in rules:
            print(rule)
    yield


@actions.add(".setof", 3)  # Enric
def _setof(agent, term, intention):
    """.setof(Term, Query, List)

    Like .findall(Term, Query, List), but deduplicated and sorted --
    mirrors both Jason's .setof ("the result set populated with found
    solutions", as opposed to .findall's bag of all solutions including
    duplicates) and the classic Prolog setof/findall distinction. Term
    and Query use the same TermQuery-based belief/rule lookup .findall
    already uses -- like .findall, Query cannot itself be a nested
    internal-action call in this fork (see .relevant_plan's notes).
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    # Step 1: same "run Query, remember Term's value for every
    # solution" pattern as .findall above -- this is the "bag", with
    # duplicates still included.
    pattern = agentspeak.evaluate(term.args[0], intention.scope)
    query = agentspeak.runtime.TermQuery(term.args[1])

    memo = {}
    result = []
    for _ in query.execute(agent, intention):
        result.append(agentspeak.freeze(pattern, intention.scope, memo))

    # Step 2: unlike .findall, turn the bag into a genuine set first
    # (drop duplicates) and sort it before matching against List.
    if agentspeak.unify(tuple(sorted(set(result))), term.args[2], intention.scope, intention.stack):
        yield


@actions.add(".date", 3)
@agentspeak.optimizer.side_effect(
    agentspeak.optimizer.InferenceEvilnessConst.AFFECT_PARAM_ALL,
    agentspeak.optimizer.InferenceEvilnessConst.EFFECT_DOBIND
)
def _date(agent, term, intention):
    # .date(Year, Month, Day): match today's date against the three
    # arguments -- all three unify calls must succeed together (that's
    # what the "and" chain does) for this action to succeed at all.
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
    # .time(Hour, Minute, Second): same idea as .date, but with the
    # current clock time.
    time = datetime.datetime.now()

    if (agentspeak.unify(term.args[0], time.hour, intention.scope, intention.stack) and
        agentspeak.unify(term.args[1], time.minute, intention.scope, intention.stack) and
        agentspeak.unify(term.args[2], time.second, intention.scope, intention.stack)):

        yield


@actions.add(".version", 1)  # Enric
def _version(agent, term, intention):
    """.version(V)

    Unify V with this interpreter's version string, mirroring Jason's
    .version(V) (which unifies with Jason's own version, e.g.
    "2.4-SNAPSHOT"). Reports agentspeak.__version__ -- this fork's own
    version, there being no separate "Jason version" concept here.
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    # Match V against the package's own version string.
    if agentspeak.unify(term.args[0], agentspeak.__version__, intention.scope, intention.stack):
        yield


def _parse_event_spec(source_name, event_str):
    """Parse an event-spec string (e.g. "+!g(1,2)", "-belief") into an
    Event(trigger, goal_type, head), reusing the interpreter's own event
    grammar. Shared by .wait's optional event argument, .at, .drop_event
    and .drop_all_events's matching -- python-agentspeak's grammar has no
    quoted-event term syntax (Jason's own {+!g}), so this string-based
    adaptation is used throughout instead.
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    # Step 1: the parser expects a trailing "." just like a normal plan
    # would end with, so add one if the caller's string didn't have it.
    if not event_str.endswith("."):
        event_str += "."
    # Step 2: run the string through the same lexer/parser the
    # interpreter uses for real .asl source files, just pointed at this
    # one small string instead of a whole file.
    log = agentspeak.Log(LOGGER, 1)
    tokens = agentspeak.lexer.TokenStream(agentspeak.StringSource(source_name, event_str), log)
    tok, ast_event = agentspeak.parser.parse_event(tokens.next(), tokens, log)
    if tok.lexeme != ".":
        raise log.error("expected no further tokens after event, got: '%s'", tok.lexeme, loc=tok.loc)
    # Step 3: convert the parsed event into the runtime's own Event
    # object (trigger + goal type + head term).
    return ast_event.accept(agentspeak.runtime.BuildEventVisitor(log))


@actions.add(".wait", 1)
@actions.add(".wait", 2)
@agentspeak.optimizer.all_bound
def _wait(agent, term, intention):
    # .wait(Timeout) / .wait(Event) / .wait(Event, Timeout): pause this
    # task until a timeout passes, an event happens, or either one
    # (whichever comes first).

    # Step 1: work out which argument is which -- with 2 arguments it's
    # unambiguous (event, timeout); with just 1, decide based on whether
    # it looks like a number (a timeout) or a string (an event spec).
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

    # Step 2: sanity-check the types of whichever ended up set.
    # Type checks.
    if not (millis is None or agentspeak.is_number(millis)):
        raise agentspeak.AslError("expected timeout for .wait to be numeric")
    if not (event is None or agentspeak.is_string(event)):
        raise agentspeak.AslError("expected event for .wait to be a string")

    # Step 3: turn an event spec string into a real Event pattern to
    # watch for.
    # Event.
    if event is not None:
        event = _parse_event_spec("<.wait>", event)

    # Step 4: turn a millisecond timeout into an absolute "wake up at
    # this clock time" deadline.
    # Timeout.
    if millis is None:
        until = None
    else:
        until = agent.env.time() + millis / 1000

    # Step 5: attach a Waiter to this task -- the interpreter's main
    # loop will simply skip over this task on every cycle until the
    # deadline passes and/or the matching event arrives.
    # Create waiter.
    intention.waiter = agentspeak.runtime.Waiter(event=event, until=until)
    yield


# Custom actions for debugging:


@actions.add(".range", 2)
@agentspeak.optimizer.function_like
def _range_2(agent, term, intention):
    # .range(N, X): match X against every whole number from 0 up to
    # (but not including) N, one at a time. This is the standard "try
    # each candidate, hand back an answer, undo and try the next on
    # backtrack" pattern: for each number i, remember a checkpoint,
    # attempt to match X against i, yield if that worked, then roll
    # back to the checkpoint and move on to i+1.
    choicepoint = object()

    for i in range(int(agentspeak.grounded(term.args[0], intention.scope))):
        intention.stack.append(choicepoint)

        if agentspeak.unify(term.args[1], i, intention.scope, intention.stack):
            yield

        agentspeak.reroll(intention.scope, intention.stack, choicepoint)


@actions.add(".dump", 0)
@agentspeak.optimizer.no_scope_effects
def _dump(agent, term, intention):
    # .dump: a debugging aid that prints the agent's whole internal
    # state (beliefs, rules, plans, running tasks) to the console.
    agent.dump()
    yield


@actions.add(".unbind_all", 0)
@agentspeak.optimizer.side_effect(
    agentspeak.optimizer.InferenceEvilnessConst.AFFECT_SCOPE,
    agentspeak.optimizer.InferenceEvilnessConst.EFFECT_UNBIND
)
def _unbind_all(agent, term, intention):
    # .unbind_all: wipe every variable binding this task currently has.
    intention.scope.clear()
    yield


@actions.add(".control_flow", 0)
@agentspeak.optimizer.no_scope_effects
def _control_flow(agent, term, intention):
    # .control_flow: a debugging aid that writes out every plan's
    # compiled instruction chain as a Graphviz ".dot" graph file, so it
    # can be visualised. Not something an ordinary agent script needs to
    # call -- purely for inspecting how a plan body got compiled.

    # Step 1: open the output file and start a Graphviz digraph block.
    out = open("control_flow.dot", "w")
    print("digraph control_flow {", file=out)
    for plans in agent.plans.values():
        for plan in plans:
            # Step 2: draw an edge from the plan's own header (trigger +
            # context) to the first instruction of its body.
            print("  \"%s %s\" -> \"%s\";" % (plan.name(), plan.context, plan.body), file=out)
            closed_instrs = set()
            open_instrs = set([plan.body])
            # Step 3: walk every instruction reachable from the plan
            # body (a small graph-traversal loop: keep a set of
            # instructions still to visit, and a set already visited so
            # nothing gets processed twice), drawing an edge for each
            # "what happens next on success" and "what happens next on
            # failure" link.
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
    # Step 4: close off the graph and the file.
    print("}", file=out)
    out.close()
    print("Graph dumped to control_flow.dot")
    yield

@actions.add(".drop_all_intentions", 0)  #Enric
def _drop_all_intentions(agent, term, intention):
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    # .drop_all_intentions: stop every task the agent is currently
    # running, no matter what goal it's working on.
    # Simply clear the deque of active intentions
    agent.intentions.clear()
    yield

@actions.add(".drop_intention", 1)  #Enric
def _drop_intention(agent, term, intention):
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    # .drop_intention(Goal): stop only the task(s) working on Goal,
    # leaving everything else running.
    import collections

    # 1. Retrieve the goal name you want to drop (e.g. run_step)
    goal = agentspeak.freeze(term.args[0], intention.scope, {})

    # 2. Rebuild the list of running task-stacks, keeping only the ones
    # that do NOT contain a step working on Goal (== here is a plain
    # equality check, not unification -- it's comparing already-fixed
    # values, not trying to bind variables).
    agent.intentions = collections.deque(
        stack for stack in agent.intentions
        if not any(item.head_term == goal for item in stack)
    )
    yield

@actions.add(".current_intention", 1) #Enric
def _current_intention(agent, term, intention):
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    # .current_intention(I): hand back the calling task itself (as an
    # opaque handle other actions like .fail_goal/.succeed_goal can take
    # as their target). Note this yields the raw `intention` object
    # directly rather than unifying it against term.args[0] -- see the
    # commented-out line below, which was the original unify-based
    # attempt, left in place as a record of that design choice.
    # Simply return the current intention
    #if agentspeak.unify(term.args[0], intention.head_term, intention.scope, intention.stack):
    yield intention

@actions.add(".intend") #Enric
def _intend(agent, term, intention):
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    # .intend(Goal[, Id]): test/enumerate whether Goal is already an
    # intention (a task actually running), optionally also reporting an
    # Id that identifies which task-stack it's on.
    if len(term.args) < 1 or len(term.args) > 2:
        raise agentspeak.AslError("internal action .intend expects 1 or 2 arguments")

    goal_arg = term.args[0]
    has_intention_var = len(term.args) == 2

    choicepoint = object()

    # This is the same try-each-candidate-then-backtrack pattern used
    # throughout this file, just walking a nested structure: every
    # top-level task-stack, and every step within it. For each step that
    # has a real goal attached, try to match Goal against it; if that
    # works (and the optional Id also matches, when asked for), hand
    # back one answer, then undo the match and keep looking.
    for stack in agent.intentions:
        for item in stack:
            if item.head_term is None:
                continue

            intention.stack.append(choicepoint)

            if agentspeak.unify(goal_arg, item.head_term, intention.scope, intention.stack):
                if not has_intention_var or agentspeak.unify(term.args[1], id(stack), intention.scope, intention.stack):
                    yield

            agentspeak.reroll(intention.scope, intention.stack, choicepoint)

def _is_pending_desire(pending):
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    # A queued-but-not-yet-started event only counts as a "desire" (in
    # the BDI sense) if it's a goal being requested (an achievement
    # addition, i.e. "!goal") -- a queued belief change is not a desire.
    return (
        pending.goal_type == agentspeak.GoalType.achievement
        and pending.trigger == agentspeak.Trigger.addition
    )


@actions.add(".desire") #Enric
def _desire(agent, term, intention):
    """.desire(Goal[, Id])

    Test/enumerate whether Goal is desired: either still a pending,
    not-yet-committed achievement event sitting in agent.events (a real
    desire now that the interpreter has a persistent event queue), or
    already an intention (an intention is still a desire being pursued,
    matching real BDI terminology -- .desire is a strict superset of what
    .intend checks). The optional 2-arg Id-unifying form is
    intention-only, mirroring .intend's own 2-arg contract exactly: a
    pending event has no id(stack) yet to offer.
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    if len(term.args) < 1 or len(term.args) > 2:
        raise agentspeak.AslError("internal action .desire expects 1 or 2 arguments")

    goal_arg = term.args[0]
    has_intention_var = len(term.args) == 2

    # Step 1: first check the queue of goals that were requested but
    # haven't started running yet -- try each one that's really an
    # achievement request (using the try-candidate/yield/reroll
    # backtracking pattern again), and offer it as a match for Goal.
    if not has_intention_var:
        choicepoint = object()
        for pending in agent.events:
            if not _is_pending_desire(pending):
                continue

            intention.stack.append(choicepoint)
            if agentspeak.unify(goal_arg, pending.frozen, intention.scope, intention.stack):
                yield
            agentspeak.reroll(intention.scope, intention.stack, choicepoint)

    # Step 2: then also check goals that have already started running
    # (an intention) -- reuse .intend's own logic directly rather than
    # duplicating it (yield from forwards every answer .intend produces
    # as if it had been written inline here).
    # Already-committed intentions -- an intention is still a desire.
    yield from _intend(agent, term, intention)


@actions.add(".drop_desire", 1) #Enric
def _drop_desire(agent, term, intention):
    """.drop_desire(Goal)

    Drop Goal as a desire: remove it from the pending-event queue if it
    is still only a pending, uncommitted achievement event, and also drop
    the matching intention if it has already been committed to one
    (reusing .drop_intention's goal lookup and semantics verbatim for the
    latter). Both are checked since a goal is only ever in one of the two
    states at a time, but which one isn't always obvious to the caller.
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    import collections

    # Step 1: fix Goal's current value.
    goal = agentspeak.freeze(term.args[0], intention.scope, {})

    # Step 2: rebuild the pending-events queue without any queued goal
    # request matching Goal.
    agent.events = collections.deque(
        pending for pending in agent.events
        if not (_is_pending_desire(pending) and pending.frozen == goal)
    )

    # Step 3: also drop it if it's already a running intention, reusing
    # .drop_intention's own logic.
    yield from _drop_intention(agent, term, intention)


@actions.add(".drop_all_desires", 0) #Enric
def _drop_all_desires(agent, term, intention):
    """.drop_all_desires

    Drop every desire: clear every pending achievement event (belief
    events are left alone -- a desire is a goal, not a belief update) and
    every intention (reusing .drop_all_intentions verbatim).
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    import collections

    # Step 1: keep only queued events that are NOT goal requests (i.e.
    # drop every pending "!goal" from the queue, keep pending belief
    # changes as-is).
    agent.events = collections.deque(
        pending for pending in agent.events if not _is_pending_desire(pending)
    )

    # Step 2: also drop every already-running intention.
    yield from _drop_all_intentions(agent, term, intention)


# .kill_agent needs a handle on the platform agent .create_agent spawns.
# The integration layer (spade_bdi) is left untouched, so that handle is
# kept here, in a registry owned by the standard-library module itself,
# mapping a created agent's short name (the one given to .create_agent,
# not its full JID) to its platform BDIAgent object. This is deliberately
# global rather than scoped per creator -- the simplest reading of the
# open question recorded in the design notes, and the one that keeps
# .kill_agent broadly useful without any hook into spade_bdi.
_created_agents = {}  # Enric


@actions.add(".create_agent", 2)  # Enric
def _create_agent(agent, term, intention):
    # .create_agent(Name, Source): spawn a brand-new, real platform
    # agent (a separate BDIAgent, not just another task on this same
    # agent) that loads Source as its own .asl script.

    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    import asyncio
    from spade_bdi.bdi import BDIAgent   # lazy import to avoid a circular import at load time

    # Step 1: read the new agent's short name and its .asl source
    # filename.
    name = agentspeak.asl_str(agentspeak.grounded(term.args[0], intention.scope))
    source = agentspeak.asl_str(agentspeak.grounded(term.args[1], intention.scope))

    # Step 2: build the new agent's full XMPP address (JID), reusing
    # this agent's own domain (e.g. "localhost").
    # agent.name was set to self.jid in _load_asl, so reuse its domain
    creator_jid = str(agent.name)
    domain = creator_jid.split("@", 1)[1] if "@" in creator_jid else "localhost"
    new_jid = "{}@{}".format(name, domain)
    password = "secret"        # environment-specific — see below

    # Step 3: actually starting the new agent involves network I/O
    # (connecting to the XMPP server), so it has to happen
    # asynchronously rather than blocking this reasoning cycle -- create
    # a background task on the event loop that's already driving the
    # interpreter, and let it register itself (for .kill_agent to find
    # later) once it's actually up and running.
    loop = asyncio.get_running_loop()

    async def _spawn():
        child = BDIAgent(new_jid, password, source)
        await child.start(auto_register=True)
        _created_agents[name] = child  # Enric: register for .kill_agent

    loop.create_task(_spawn())
    yield


@actions.add(".kill_agent", 1)  # Enric
@actions.add(".kill_agent", 2)  # Enric
def _kill_agent(agent, term, intention):
    """.kill_agent(Name[, Deadline])

    Stop and remove a previously .create_agent-created platform agent
    identified by Name -- the same short name given to .create_agent, not
    its full JID. Goal/registry lookup mirrors Jason's
    .kill_agent(Name[, Deadline]); as in the reference implementation, any
    agent can kill any other agent this way, with no permission check.

    Without Deadline, the target is stopped right away. With Deadline (a
    number of seconds), Jason's own grace-period semantics are followed:
    a +jag_shutting_down(Deadline) belief event is delivered to the target
    first, so it can react (e.g. let a running intention finish) before
    being stopped Deadline seconds later. Message delivery is a direct
    Python call into the target's own agentspeak Agent (agent.bdi_agent) --
    the same shortcut .broadcast/.send already take for agents sharing an
    Environment, here applied via our own registry instead -- rather than
    a real XMPP round trip.

    Exactly like .create_agent's own asynchronous start, both delivering
    the shutdown signal and the eventual stop happen out of line with this
    call, on the asyncio event loop already driving the reasoning cycle
    (the deadline itself reuses .at's loop.call_later mechanism).
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    import asyncio

    # Step 1: look the target up by name in the registry .create_agent
    # filled in earlier -- nothing to kill if it was never created this
    # way, or was already killed.
    name = agentspeak.asl_str(agentspeak.grounded(term.args[0], intention.scope))
    try:
        target = _created_agents.pop(name)
    except KeyError:
        raise agentspeak.AslError(
            ".kill_agent: no agent created via .create_agent is known by the name '%s'" % name)

    loop = asyncio.get_running_loop()

    # Step 2: with a deadline, warn the target first (deliver a
    # jag_shutting_down belief straight into its own belief base, a
    # direct Python call rather than real messaging) and only actually
    # stop it after the deadline elapses (scheduled on the event loop,
    # same trick .at uses); without a deadline, stop it immediately.
    if len(term.args) == 2:
        deadline = agentspeak.grounded(term.args[1], intention.scope)
        if not agentspeak.is_number(deadline):
            raise agentspeak.AslError("expected a numeric deadline for .kill_agent")
        deadline = float(deadline)

        if target.bdi_agent is not None:
            target.bdi_agent.call(
                agentspeak.Trigger.addition, agentspeak.GoalType.belief,
                agentspeak.Literal("jag_shutting_down", (deadline,)),
                agentspeak.runtime.Intention(),
            )
        loop.call_later(deadline, lambda: loop.create_task(target.stop()))
    else:
        loop.create_task(target.stop())

    yield


def _render_agent_source(agent, goals=()):
    """Render agent's beliefs, rules and plans (plus optional initial
    goals) as valid .asl source text -- shared by .save_agent (writes it
    to a user-given file) and .clone (writes it to a temp file, then
    spawns a new BDIAgent from it, exactly like .create_agent does).
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    # Step 1: write out every belief and rule, one .asl statement per
    # line.
    lines = ["// beliefs and rules"]
    for beliefs in agent.beliefs.values():
        for belief in beliefs:
            lines.append(agentspeak.asl_repr(belief) + ".")
    for rules in agent.rules.values():
        for rule in rules:
            lines.append(str(rule) + ".")

    # Step 2: write out the requested initial goals (if any) as
    # "!Goal." lines.
    lines.append("")
    lines.append("// initial goals")
    for g in goals:
        lines.append("!" + agentspeak.asl_repr(g) + ".")

    # Step 3: write out every plan in its full .asl source form. Uses
    # this module's own _plan_to_str, not agentspeak.runtime.plan_to_str:
    # the runtime version is destructive (it pops from plan.args to fill
    # in a plan's head placeholders, so a plan with head arguments can
    # only ever be rendered once, successfully, per process) -- calling
    # .clone and .save_agent on the same agent, in either order, would
    # exhaust the same Plan objects' plan.args on the first call and then
    # crash the second with "IndexError: pop from empty list". Found via
    # exactly that sequence in the warehouse integration scenario
    # (Chapter 5): .clone renders the whole plan library once during the
    # shift, and .save_agent renders it again at shift end.
    lines.append("")
    lines.append("// plans")
    for plans in agent.plans.values():
        for plan in plans:
            lines.append(_plan_to_str(plan))

    # Step 4: join everything into one text blob, one statement per line.
    return "\n".join(lines) + "\n"


@actions.add(".save_agent", 1)  # Enric
@actions.add(".save_agent", 2)  # Enric
def _save_agent(agent, term, intention):
    """.save_agent(File[, InitialGoals])

    Write the calling agent's beliefs, rules and plans to File as valid
    .asl source -- mirrors Jason's own .save_agent(file[,initial_goals]).
    InitialGoals, when given, is a list of goals written into the file
    as "!Goal." lines, exactly as Jason's own does. The written file can
    be read back with .include, or used directly as a fresh agent's
    source (e.g. via .create_agent) -- reuses the same rendering
    .clone(Name) uses internally to seed a new agent from this one.
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    # Step 1: read the destination filename.
    filename = agentspeak.asl_str(agentspeak.grounded(term.args[0], intention.scope))

    # Step 2: read the optional list of initial goals, if given.
    goals = ()
    if len(term.args) == 2:
        goals = agentspeak.grounded(term.args[1], intention.scope)
        if not agentspeak.is_list(goals):
            raise agentspeak.AslError(
                "expected a list of initial goals for .save_agent, got: '%s'" % (goals, ))

    # Step 3: render this agent's current state to .asl text and write
    # it out.
    with open(filename, "w") as f:
        f.write(_render_agent_source(agent, goals))

    yield


@actions.add(".include", 1)  # Enric
def _include(agent, term, intention):
    """.include(File)

    Load File (an .asl file) at runtime, merging its beliefs, rules and
    plans into the calling agent -- mirrors Jason's own .include(File),
    minus its optional second (namespace) argument: this engine has no
    namespace support at all (see .namespace), so only the 1-arg form is
    offered. Initial goals declared in File are raised too, fire-and-
    forget, exactly like an agent's own top-level initial goals.

    Reuses the exact parse-and-populate steps
    Environment.build_agent_from_ast uses to build a fresh agent from
    source, just targeting the already-running calling agent instead of
    constructing a new one.

    Scope limit: included plans are compiled against this module's own
    stdlib.actions registry, not necessarily whatever (possibly
    extended) actions registry the calling agent was itself originally
    built with -- Agent keeps no reference to the registry that built
    it, so there is nothing else here to compile against.
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    # Step 1: read the whole file to include.
    filename = agentspeak.asl_str(agentspeak.grounded(term.args[0], intention.scope))

    with open(filename) as f:
        content = f.read()

    # Step 2: parse it into an AST, the same way any other .asl source
    # file gets parsed.
    log = agentspeak.Log(LOGGER, 3)
    source = agentspeak.StringSource(filename, content)
    tokens = agentspeak.lexer.TokenStream(source, log)
    ast_agent = agentspeak.parser.parse(source.name, tokens, log)
    log.throw()

    rt = agentspeak.runtime

    # Step 3: compile every rule from the included file and add it to
    # THIS agent (not a new one) -- same compilation steps used when
    # building a fresh agent from scratch.
    for ast_rule in ast_agent.rules:
        variables = {}
        head = ast_rule.head.accept(rt.BuildTermVisitor(variables))
        consequence = ast_rule.consequence.accept(rt.BuildQueryVisitor(variables, actions, log))
        agent.add_rule(rt.Rule(head, consequence))

    # Step 4: same for every plan -- compile its head, its context
    # (precondition) query and its body into a runtime Plan, then add it
    # to this agent's plan library.
    for ast_plan in ast_agent.plans:
        variables = {}
        head = ast_plan.event.head.accept(rt.BuildTermVisitor(variables))

        if ast_plan.context:
            context = ast_plan.context.accept(rt.BuildQueryVisitor(variables, actions, log))
        else:
            context = rt.TrueQuery()

        body = rt.Instruction(rt.noop)
        body.f = rt.noop
        if ast_plan.body:
            ast_plan.body.accept(rt.BuildInstructionsVisitor(variables, actions, body, log))

        plan = rt.Plan(ast_plan.event.trigger, ast_plan.event.goal_type, head, context,
                        body, ast_plan.body, ast_plan.annotation)
        plan.args = rt.plan_head_arg_names(ast_plan.event.head)
        plan.str_context = ast_plan.context

        agent.add_plan(plan)

    # Step 5: raise every belief from the included file as a delayed
    # belief-addition event (so it goes through the same queue/plan-
    # matching machinery any other belief change does, rather than
    # being force-inserted).
    for ast_belief in ast_agent.beliefs:
        belief = ast_belief.accept(rt.BuildTermVisitor({}))
        agent.call(agentspeak.Trigger.addition, agentspeak.GoalType.belief,
                   belief, rt.Intention(), delayed=True)

    # Step 6: same for every initial goal declared in the included file
    # -- raised fire-and-forget, exactly like this agent's own top-level
    # initial goals were when it first started.
    for ast_goal in ast_agent.goals:
        goal_term = ast_goal.atom.accept(rt.BuildTermVisitor({}))
        agent.call(agentspeak.Trigger.addition, agentspeak.GoalType.achievement,
                   goal_term, rt.Intention(), delayed=True)

    log.throw()
    yield


@actions.add(".clone", 1)  # Enric
def _clone(agent, term, intention):
    """.clone(Name)

    Spawn a new platform agent under Name, seeded with a copy of the
    calling agent's own current beliefs, rules and plans -- mirrors
    Jason's own .clone(agent). Unlike .create_agent, which builds a new
    agent from a given .asl file, .clone has nothing to read: it renders
    the calling agent's own current state to .asl source (the same
    rendering .save_agent uses) into a fresh temporary file, then spawns
    exactly like .create_agent does from that file -- registered in the
    same agent registry, so .kill_agent(Name) manages a clone exactly
    like any .create_agent-created agent.

    The temporary file is intentionally not cleaned up here: BDIAgent
    reads it asynchronously, out of line with this call (the same
    reason .create_agent's own spawn is asynchronous), so there is no
    single safe point in this function to delete it from. A minor,
    accepted resource cost, not a functional issue.
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    import asyncio
    import tempfile
    from spade_bdi.bdi import BDIAgent  # lazy import to avoid a circular import at load time

    # Step 1: read the new agent's short name.
    name = agentspeak.asl_str(agentspeak.grounded(term.args[0], intention.scope))

    # Step 2: render this agent's own current state to .asl text and
    # write it to a temporary file -- the new agent will load from this
    # file just like .create_agent loads from a user-given one.
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".asl", prefix="clone_", delete=False
    ) as tmp:
        tmp.write(_render_agent_source(agent))
        source = tmp.name

    # Step 3: build the new agent's full address, same idea as
    # .create_agent.
    creator_jid = str(agent.name)
    domain = creator_jid.split("@", 1)[1] if "@" in creator_jid else "localhost"
    new_jid = "{}@{}".format(name, domain)
    password = "secret"

    # Step 4: spawn the new agent as a background task on the running
    # event loop (same reasoning as .create_agent: connecting is real
    # network I/O, so it can't happen synchronously here), registering
    # it once it's actually up so .kill_agent can find it later.
    loop = asyncio.get_running_loop()

    async def _spawn():
        child = BDIAgent(new_jid, password, source)
        await child.start(auto_register=True)
        _created_agents[name] = child

    loop.create_task(_spawn())
    yield


@actions.add(".drop_event", 1) #Enric
def _drop_event(agent, term, intention):
    """.drop_event(EventSpec)

    Remove every pending event matching EventSpec -- a trigger/goal_type
    plus a (possibly partial) head, given as a string using the same
    convention .wait's optional event argument and .at already use (e.g.
    "+!g(_)", "-belief"). A pending event matches if its trigger and
    goal_type are equal and its frozen head *unifies* with the parsed
    head (not plain equality), so unbound variables in EventSpec act as
    wildcards -- the same convention .relevant_plans's trigger string
    already uses. Now genuinely functional: with a persistent event queue
    in place (see Agent.events), there is something real to drop.
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    import collections

    # Step 1: parse the event-spec string into a real trigger/goal_type/
    # head pattern.
    spec_str = agentspeak.asl_str(agentspeak.grounded(term.args[0], intention.scope))
    spec = _parse_event_spec("<.drop_event>", spec_str)

    # Step 2: rebuild the pending-events queue, keeping every event
    # EXCEPT the ones that match: same trigger, same goal type, AND
    # whose stored head can be matched against the spec's head
    # (unifies_annotated here just answers "could these two line up?",
    # any unbound variables in the spec act as wildcards -- it doesn't
    # keep the match around afterwards).
    agent.events = collections.deque(
        pending for pending in agent.events
        if not (
            pending.trigger == spec.trigger
            and pending.goal_type == spec.goal_type
            and agentspeak.unifies_annotated(pending.frozen, spec.head)
        )
    )
    yield


@actions.add(".drop_all_events", 0) #Enric
def _drop_all_events(agent, term, intention):
    """.drop_all_events

    Remove every pending event. Now genuinely functional, for the same
    reason as .drop_event.
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    agent.events.clear()
    yield


@actions.add(".perceive", 0)  # Enric
def _perceive(agent, term, intention):
    """.perceive

    In Jason, perception can run at a lower frequency than the reasoning
    cycle, so .perceive forces an immediate, out-of-cycle perception pass
    over the environment. There is no equivalent lag here to force: under
    spade_bdi, percept beliefs are set from outside the agent (typically
    via BDIBehaviour.set_belief/remove_belief -- see the PERCEPT_TAG
    annotation in bdi.py) into agent.bdi_intention_buffer, which is
    drained unconditionally on every single reasoning cycle, before
    Agent.step runs at all. Perception is therefore never behind the
    reasoning cycle to begin with, so .perceive is a well-defined no-op
    here rather than a fabricated synchronisation that would have nothing
    real to do.
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    # Nothing to actually do -- see the docstring above for why.
    yield


@actions.add(".fail_goal", 1)  # Enric
def _fail_goal(agent, term, intention):
    """.fail_goal(Goal)

    Make the intention(s) pursuing Goal fail, as if their plan had failed,
    instead of silently discarding them the way .drop_intention does. Goal
    lookup mirrors .drop_intention -- agent.intentions only: a Goal that
    is still only a pending, uncommitted desire (see .desire/agent.events)
    is invisible here, a deliberate scope limit, not a bug -- you can't
    fail an intention that doesn't exist yet (.drop_event/.drop_desire
    are what cancel a still-pending goal).

    There is no meta-event mechanism to dispatch a reference-style
    "-!goal" recovery plan to (deliberately out of scope, like the
    pluggable selection functions Jason calls metareasoning -- see the
    project notes), so the only place a failure can resume is a local
    if/else already coded around the goal's own achieve call, and that is
    only available for a *different* intention that is currently idle
    exactly at Goal's own frame (the top of its stack): there we redirect
    it to that frame's own failure branch (the else-branch, or simply
    past the if when there is none). When Goal is buried under active
    subgoals, or is the goal of the intention that is itself calling
    .fail_goal, there is no reliable failure branch left to resume -- in
    the self case, this very call's own continuation would just be
    overwritten the instant it returns successfully -- so the intention
    is dropped outright, the same fallback .drop_intention already uses,
    and the "stop immediately" reading of the self-drop semantics
    discussed in the design notes.
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
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

    # Step 1: fix Goal's current value.
    goal = agentspeak.freeze(term.args[0], intention.scope, {})

    # Step 2: rebuild the list of running task-stacks. For every
    # top-level task NOT working on Goal, keep it untouched. For one
    # that IS: if it's some other, currently-idle task (not the one
    # calling .fail_goal itself) whose top frame is exactly Goal, redirect
    # it to the nearest "else"/failure branch found nearby -- otherwise
    # (Goal is buried under sub-goals, or this is a self-fail, or there's
    # nowhere useful to redirect to) just drop the whole task, same as
    # .drop_intention would.
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

    Goal lookup is agent.intentions only, deliberately: a Goal that is
    still just a pending, uncommitted desire (see .desire/agent.events)
    has no frame to succeed yet, so it's invisible here -- .drop_desire
    is what resolves a still-pending goal instead.
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    import collections

    # Step 1: fix Goal's current value.
    goal = agentspeak.freeze(term.args[0], intention.scope, {})

    kept = collections.deque()
    for stack in agent.intentions:
        # Step 2: find where in this stack (if anywhere) Goal's own
        # frame sits.
        index = None
        for i, item in enumerate(stack):
            if item.head_term == goal:
                index = i
                break
        if index is None:
            kept.append(stack)
            continue

        # Step 3: pop everything from the top of the stack down to and
        # including Goal's own frame -- any subgoal frames stacked above
        # it were only working on Goal's behalf, and are considered
        # accomplished along with it.
        target = stack[index]
        while len(stack) > index:
            stack.pop()

        # Step 4: if a caller remains beneath (i.e. Goal wasn't the
        # top-level goal of this whole stack), match its own head term
        # against whatever the caller was waiting to bind -- this is
        # exactly the same "hand the result back to whoever asked"
        # unification step normal, successful plan completion performs.
        if stack and target.calling_term is not None:
            frozen = target.head_term.freeze(target.scope, {})
            caller = stack[-1]
            agentspeak.unify(target.calling_term, frozen, caller.scope, caller.stack)

        # Step 5: keep the stack only if something is still left running
        # on it.
        if stack:
            kept.append(stack)
        # else: Goal was the last frame on its stack -- the whole
        # intention is now finished, same as a top-level goal completing.

    agent.intentions = kept
    yield


_SUSPEND_REASON = "suspended"  # Enric: tag for waiters .suspend itself set


@actions.add(".suspend", 0)  # Enric
@actions.add(".suspend", 1)  # Enric
def _suspend(agent, term, intention):
    """.suspend[(Goal)]

    Suspend the intention(s) pursuing Goal -- or, with no argument, the
    intention that is itself calling .suspend -- so Agent.step skips them
    entirely until a matching .resume(Goal). Goal lookup (when given)
    mirrors .drop_intention/.fail_goal/.succeed_goal: a stack counts as a
    target if Goal is the head_term of any of its frames, and the block
    is applied to the stack's top frame, the only one Agent.step ever
    inspects for scheduling. agent.intentions only, deliberately: a Goal
    that is still just a pending, uncommitted desire (see .desire/
    agent.events) isn't running yet, so there's nothing to suspend.

    Reuses the interpreter's own blocking primitive, Intention.waiter --
    the same one .wait sets -- rather than inventing a separate mechanism:
    a Waiter with no timeout and no event is never woken by either of its
    two wake-up paths (Waiter.poll's timeout check, and the event-match
    scan in Agent.call), so the intention stays blocked until .resume
    clears the waiter itself. Unlike .fail_goal's self-case, this is safe
    to do directly on the calling intention too: Agent.step only
    overwrites an intention's .instr after its action call returns, never
    its .waiter.

    The reason .suspended/2 later reports is stashed as a plain attribute
    on the Waiter object (it defines no __slots__), tagging it as
    .suspend's own doing rather than an ordinary .wait.

    Also raises Jason's own meta-event: <+!g[state(suspended)]> for the
    goal literal actually transitioning into suspension, fire-and-forget
    (delayed=True, throwaway calling_intention -- nothing should block on
    a plan reacting to this -- the same pattern .at's own call() site
    already uses) through the same agent.events queue, the same
    select_event, and the same Agent._commit_event plan search as any
    ordinary event -- no new machinery. Only fired if something genuinely
    changed state (an already-suspended target is left alone and does
    NOT re-fire the event): this specifically prevents a plan like
    "+!g[state(suspended)] <- .suspend(g)." from being a hidden infinite
    loop -- re-suspending an already-suspended goal is a no-op,
    notification included.

    NOTE for anyone adding a plan reacting to this: self.plans buckets by
    (trigger, goal_type, functor, arity) only -- NOT by annotation. An
    ordinary, unannotated "+!g <- ..." plan of the same functor/arity
    also unifies against this annotated event (Literal.unify_annotated
    only requires the PLAN's own annotations, if any, to be present on
    the event -- zero is trivially satisfied), and Agent._commit_event
    tries applicable plans in source order, first match wins. Declare
    "+!g[state(suspended)] <- ..." BEFORE the ordinary "+!g <- ..." plan
    in the source, or the ordinary plan will win and spuriously re-run.
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    # Step 1: work out which task(s) to suspend -- either every task
    # whose stack has a frame matching Goal (given explicitly), or just
    # this very task if no Goal was given at all.
    if len(term.args) == 1:
        goal = agentspeak.freeze(term.args[0], intention.scope, {})
        targets = [
            stack[-1] for stack in agent.intentions
            if stack and any(item.head_term == goal for item in stack)
        ]
    else:
        goal = intention.head_term  # already frozen -- set by _commit_event
        targets = [intention]

    # Step 2: block each target by giving it an empty Waiter (no
    # timeout, no event to watch for) -- since nothing will ever satisfy
    # it on its own, the task simply stays blocked until .resume clears
    # it manually. Track whether anything actually changed state (an
    # already-suspended target doesn't count).
    newly_suspended = False
    for target in targets:
        already_suspended = (
            target.waiter is not None
            and getattr(target.waiter, "reason", None) == _SUSPEND_REASON
        )
        waiter = agentspeak.runtime.Waiter()
        waiter.reason = _SUSPEND_REASON
        target.waiter = waiter
        if not already_suspended:
            newly_suspended = True

    # Step 3: only if something genuinely just got suspended, raise a
    # notification event (a "meta-event") that a plan elsewhere could
    # react to -- e.g. "+!worker[state(suspended)] <- ...". This goes
    # through the exact same event queue/plan-matching machinery as any
    # ordinary goal request (agent.call), just fire-and-forget
    # (delayed=True) since nothing should have to wait around for a
    # plan reacting to this notification.
    if newly_suspended:
        agent.call(
            agentspeak.Trigger.addition, agentspeak.GoalType.achievement,
            goal.with_annotation(Literal("state", (Literal("suspended"),))),
            agentspeak.runtime.Intention(), delayed=True,
        )

    yield


@actions.add(".resume", 1)  # Enric
def _resume(agent, term, intention):
    """.resume(Goal)

    Resume the intention(s) previously suspended, while pursuing Goal, by
    .suspend -- mirrors Jason's .resume(Goal). Goal lookup mirrors
    .suspend (agent.intentions only, same reasoning). Only clears waiters
    tagged with .suspend's own reason: an
    intention genuinely blocked inside .wait is left alone, since forcing
    it to resume early would not match .wait's own semantics -- .resume
    only ever undoes what .suspend did.

    Mirrors .suspend's own meta-event: <+!g[state(resumed)]>, raised
    fire-and-forget exactly the same way (see .suspend's docstring for
    the full mechanism and the plan-ordering hazard to be aware of when
    reacting to it), and only if at least one target's waiter was
    genuinely tagged _SUSPEND_REASON -- i.e. something actually resumed,
    symmetric with .suspend's own idempotency guard.
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    # Step 1: fix Goal's current value.
    goal = agentspeak.freeze(term.args[0], intention.scope, {})

    # Step 2: for every task-stack matching Goal whose top frame is
    # blocked with a waiter tagged as .suspend's own doing, clear that
    # waiter -- an ordinary .wait-blocked task is deliberately left
    # alone here, since resuming it early wouldn't respect what it was
    # actually waiting for.
    resumed_any = False
    for stack in agent.intentions:
        if not stack or not any(item.head_term == goal for item in stack):
            continue
        top = stack[-1]
        if top.waiter is not None and getattr(top.waiter, "reason", None) == _SUSPEND_REASON:
            top.waiter = None
            resumed_any = True

    # Step 3: only if something genuinely just resumed, raise the
    # matching "resumed" notification event, same mechanism as
    # .suspend's own notification.
    if resumed_any:
        agent.call(
            agentspeak.Trigger.addition, agentspeak.GoalType.achievement,
            goal.with_annotation(Literal("state", (Literal("resumed"),))),
            agentspeak.runtime.Intention(), delayed=True,
        )

    yield


@actions.add(".suspended", 2)  # Enric
def _suspended(agent, term, intention):
    """.suspended(Goal, Reason)

    Test whether Goal belongs to a currently-blocked intention (Goal
    lookup mirrors .suspend/.resume: agent.intentions only), unifying
    Reason with why: "suspended" for an explicit .suspend, or "wait" for
    an intention genuinely blocked inside .wait. Mirrors Jason's
    .suspended(G, R); a test predicate, not backtracking, matching the
    reference documentation. A Goal that is still only a pending,
    uncommitted desire (see .desire/agent.events) reports false here --
    it isn't blocked, it just hasn't started yet.
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    # Step 1: fix Goal's current value.
    goal = agentspeak.freeze(term.args[0], intention.scope, {})

    # Step 2: find the (at most one) task-stack matching Goal; if its
    # top frame is currently blocked, report why by matching Reason
    # against the waiter's tag (defaulting to "wait" for an ordinary
    # .wait-blocked task, which never set an explicit tag).
    for stack in agent.intentions:
        if not stack or not any(item.head_term == goal for item in stack):
            continue
        top = stack[-1]
        if top.waiter is not None:
            reason = getattr(top.waiter, "reason", "wait")
            if agentspeak.unify(term.args[1], Literal(reason), intention.scope, intention.stack):
                yield
            return


@actions.add(".intention", 2)  # Enric
@actions.add(".intention", 3)  # Enric
@actions.add(".intention", 4)  # Enric
def _intention(agent, term, intention):
    """.intention(ID, State[, Stack[, current]])

    Describe the agent's own intentions, backtracking over every
    top-level intention stack in agent.intentions -- ID/State/Stack may be
    left unbound to enumerate, or bound to filter. Mirrors Jason's
    .intention(ID, STATE, STACK, current), adapted to what this engine
    actually tracks:

    - ID is id(stack), the same intention-identifier convention .intend
      already established.
    - State is one of "suspended" (blocked by .suspend), "waiting"
      (blocked for any other reason, e.g. .wait), or "running" (not
      blocked) -- Jason's own state set is richer, but these three are
      everything Agent.step actually distinguishes when deciding what to
      schedule next.
    - Stack, when requested, is the list of goals this intention is
      pursuing, outermost first: each frame's head_term, bottom to top.
      Jason's own Stack holds full im(plan_label, trigger, body, unifier)
      records, but an Intention frame here does not retain which Plan
      object produced it, so a faithful im/4 term cannot be reconstructed
      without extending the runtime -- out of scope for a
      standard-library-only port (see the project's design notes) -- so
      goal identity is what is exposed instead.
    - The optional 4th argument, if given, must be the atom `current`;
      Jason: "the intention executing the plan is used as current" --
      here, the stack the calling intention itself belongs to.

    Only enumerates agent.intentions, deliberately: pending, uncommitted
    desires (see .desire/agent.events) aren't intentions yet, so they
    don't appear here -- check .desire for those.
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    # Step 1: with a 4th argument, it must be the literal atom
    # `current`, and it restricts the results to just the calling
    # task's own stack.
    only_current = False
    if len(term.args) == 4:
        current_flag = agentspeak.grounded(term.args[3], intention.scope)
        if not (agentspeak.is_atom(current_flag) and current_flag.functor == "current"):
            raise agentspeak.AslError(
                "expected the atom 'current' as the 4th argument to .intention")
        only_current = True

    # Step 2: go through every top-level task-stack (skipping the
    # `current`-only filter unless it applies), work out its state
    # (suspended / waiting / running, based on its top frame's waiter),
    # then try to match ID/State (and Stack, if asked for) against it.
    # This is the same try-each-candidate-then-backtrack pattern used
    # throughout this file: each matching stack becomes one answer, and
    # a caller backtracking for another gets the next stack in turn.
    choicepoint = object()
    for stack in agent.intentions:
        if not stack:
            continue
        if only_current and intention not in stack:
            continue

        top = stack[-1]
        if top.waiter is None:
            state = "running"
        elif getattr(top.waiter, "reason", None) == _SUSPEND_REASON:
            state = "suspended"
        else:
            state = "waiting"

        intention.stack.append(choicepoint)

        bound = (
            agentspeak.unify(term.args[0], id(stack), intention.scope, intention.stack)
            and agentspeak.unify(term.args[1], Literal(state), intention.scope, intention.stack)
        )

        if bound and len(term.args) >= 3:
            # Step 3: if requested, also report the full chain of goals
            # this stack is pursuing, from outermost (bottom) to
            # innermost (top).
            goals = tuple(frame.head_term for frame in stack if frame.head_term is not None)
            bound = agentspeak.unify(term.args[2], goals, intention.scope, intention.stack)

        if bound:
            yield

        agentspeak.reroll(intention.scope, intention.stack, choicepoint)


_AT_WHEN_RE = re.compile(
    r"^\s*now\s*\+\s*(\d+(?:\.\d+)?)\s*([a-zA-Z]*)\s*$", re.IGNORECASE)

_AT_UNIT_SECONDS = {
    # A bare number with no unit means milliseconds, matching Jason's .at.
    "": 0.001,
    "ms": 0.001, "milli": 0.001, "millis": 0.001,
    "millisecond": 0.001, "milliseconds": 0.001,
    "s": 1.0, "sec": 1.0, "secs": 1.0, "second": 1.0, "seconds": 1.0,
    "m": 60.0, "min": 60.0, "mins": 60.0, "minute": 60.0, "minutes": 60.0,
    "h": 3600.0, "hour": 3600.0, "hours": 3600.0,
    "d": 86400.0, "day": 86400.0, "days": 86400.0,
}


def _parse_at_when(when):
    """Parse a Jason-style .at delay spec: "now +<number> [<unit>]".

    Supported units: (s)econd(s), (m)inute(s), (h)our(s), (d)ay(s); a bare
    number with no unit means milliseconds. Returns the delay in seconds.
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    # Step 1: match the "now +<number> [unit]" pattern (the regex
    # captures the number and the (optional) unit letters separately).
    match = _AT_WHEN_RE.match(when)
    if not match:
        raise agentspeak.AslError(
            "expected .at time spec of the form 'now +<number> [s|m|h|d]', got: '%s'" % when)

    # Step 2: pull out the number and unit, then convert the unit name
    # into a seconds-per-unit multiplier via the lookup table above.
    amount = float(match.group(1))
    unit = match.group(2).lower()
    try:
        seconds_per_unit = _AT_UNIT_SECONDS[unit]
    except KeyError:
        raise agentspeak.AslError("unknown time unit in .at: '%s'" % unit)

    # Step 3: the delay in seconds is simply amount * seconds-per-unit.
    return amount * seconds_per_unit


@actions.add(".at", 2)  # Enric
def _at(agent, term, intention):
    """.at(When, Event)

    Schedule Event to be generated at some point in the future, as
    described by When -- a string of the form "now +<number> [s|m|h|d]",
    matching Jason's .at (e.g. "now +3 seconds", "now +2 h").

    This is a deliberate departure from Jason's own syntax: Jason's .at
    takes the event as a quoted `{+!g}` term, a syntax python-agentspeak's
    grammar does not support in term position. Instead -- exactly as
    .wait's optional event argument and .relevant_plans's trigger argument
    already do -- Event is given as a plain string (e.g. "+!g", "-belief")
    and parsed with the interpreter's own event grammar.

    There is no persistent, agent-cycle-driven scheduler to hook into:
    python-agentspeak's reasoning cycle only polls per-intention .wait
    timers (see Agent.step), not agent-wide deferred events, and the
    project's scope keeps this port confined to the standard-library
    module rather than extending Agent/Environment. So, exactly like
    .create_agent already does for spawning a platform agent
    asynchronously, firing the event is handed to the asyncio event loop
    that is already driving the agent's reasoning cycle, via
    loop.call_later. This means the event fires out of line with the plan
    that scheduled it, and -- like .create_agent -- any failure (e.g. no
    applicable plan when the event fires) surfaces separately rather than
    as an immediate error to the calling plan.
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    import asyncio
    import functools

    # Step 1: read When (the delay spec string) and Event (the event
    # spec string).
    when = agentspeak.asl_str(agentspeak.grounded(term.args[0], intention.scope))
    event_str = agentspeak.asl_str(agentspeak.grounded(term.args[1], intention.scope))

    # Step 2: turn When into a delay in seconds, and Event into a real
    # trigger/goal_type/head pattern.
    delay = _parse_at_when(when)
    event = _parse_event_spec("<.at>", event_str)

    # Step 3: fix the event's head right now -- by the time the delay
    # elapses and the event actually fires, this plan's own variables
    # may no longer mean anything, so its value has to be locked in
    # before that happens, not when the timer goes off.
    # Freeze now: intention.scope may no longer be meaningful once the
    # callback actually fires, out of line with this action call.
    frozen_head = agentspeak.freeze(event.head, intention.scope, {})

    # Step 4: schedule the event to actually be raised (via agent.call,
    # the same entry point every event goes through) after `delay`
    # seconds, using the asyncio event loop that's already driving the
    # reasoning cycle. functools.partial here just pre-fills agent.call's
    # arguments ahead of time, so the event loop can call the resulting
    # object with no arguments later, once the timer fires -- and
    # delayed=True means fire-and-forget: nothing is left waiting on it.
    loop = asyncio.get_running_loop()
    loop.call_later(
        delay,
        functools.partial(
            agent.call, event.trigger, event.goal_type, frozen_head,
            agentspeak.runtime.Intention(), delayed=True,
        ),
    )

    yield


def _plan_to_str(plan):
    """Render a plan as an AgentSpeak string.

    Non-destructive counterpart of runtime.plan_to_str: the stock version calls
    plan.args.pop(0), which mutates the plan and makes it single-use for plans
    that have head arguments. We copy plan.args so a plan can be rendered any
    number of times.
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    # Step 1: the context clause prints as the plain word "true" when
    # there was no explicit ": Context" in the original plan, otherwise
    # print the ORIGINAL, uncompiled context AST (plan.str_context), not
    # the compiled Query object (plan.context) -- see Plan.str_context's
    # comment in runtime.py. In short: a variable used only in the
    # context (not in the head) gets renamed to an internal, unrecoverable
    # placeholder once compiled, and only head arguments get their
    # original names restored below (via plan.args); printing the
    # compiled query directly would leak that placeholder and, once
    # reparsed, sever the binding between the context and any body code
    # relying on that same variable name.
    if isinstance(plan.context, agentspeak.runtime.TrueQuery):
        context = "true"
    else:
        context = plan.str_context if plan.str_context is not None else plan.context

    body = plan.str_body

    # Step 2: if the plan's head has arguments, its stored text form
    # has placeholder markers instead of the real values (something
    # like "_X_1a2_3b4") -- swap them back in from plan.args, one at a
    # time, in order. Work on a COPY of plan.args (list(plan.args)) so
    # this function can be called again later on the same plan without
    # running out of substitutions.
    if len(plan.head.args):
        args = list(plan.args)  # copy: do NOT mutate the stored plan
        pattern = r"_X_[0-9a-fA-F]{3}_[0-9a-fA-F]+"
        head = re.sub(pattern, lambda m: args.pop(0) if args else m.group(0), str(plan.head))  # fill in each placeholder, left to right
    else:
        head = str(plan.head)

    # Step 3: assemble everything back into one line of valid .asl
    # source, with the @label prefix only if the plan actually has one.
    if plan.annotation:
        return f"@{plan.annotation} {plan.trigger.value}{plan.goal_type.value}{head} : {context} <- {body}."
    return f"{plan.trigger.value}{plan.goal_type.value}{head} : {context} <- {body}."


def _normalise_label(raw):
    """Accept a label as an atom, "label" or "@label"; return "@label"."""
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    # Step 1: turn whatever form the caller gave into plain text.
    label = asl_str(raw)
    # Step 2: make sure it starts with "@", adding it if missing.
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
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    # Step 1: read the plan's source text.
    str_plan = asl_str(agentspeak.grounded(term.args[0], intention.scope))
    # Step 2: hand it off to the same "receive a plan from another
    # agent" machinery (_tell_how) that a real inter-agent plan-sharing
    # message goes through -- it parses the text and adds the resulting
    # plan straight into this agent's own plan library.
    agent._tell_how(Literal("plain_text", (str_plan,), frozenset()))
    yield


@actions.add(".remove_plan", 1)  # Enric
def _remove_plan(agent, term, intention):
    """.remove_plan(Label)

    Remove every plan whose @label matches Label. Label may be given as an atom,
    "label" or "@label". Mirrors the label matching already used by _untell_how.
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    # Step 1: normalise the label to the "@name" form actually stored on
    # a plan.
    label = _normalise_label(agentspeak.grounded(term.args[0], intention.scope))
    # Step 2: go through every bucket in the plan library and remove any
    # plan whose own @label matches. We collect matches into a separate
    # list first (to_delete), then remove them afterwards, rather than
    # removing while looping over the same list directly -- Python
    # doesn't like a list changing size while you're iterating over it.
    for plans in agent.plans.values():
        to_delete = [
            p for p in plans
            if p.annotation and ("@" + str(p.annotation.functor)) == label
        ]
        for p in to_delete:
            plans.remove(p)
    yield


def _plans_for_trigger(agent, intention, trigger_str):
    """Parse a trigger-event string (e.g. "+!task") and return the plan
    objects relevant to it: same trigger/goal type, head unifies with the
    event head. Shared by .relevant_plans, .relevant_plan and .list_plans.
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    # Step 1: the parser expects a trailing "." just like a real plan
    # trigger would end with.
    if not trigger_str.endswith("."):
        trigger_str += "."

    # Step 2: parse the string using the interpreter's own event
    # grammar, the same one real .asl trigger events go through.
    log = agentspeak.Log(LOGGER, 1)
    tokens = agentspeak.lexer.TokenStream(
        agentspeak.StringSource("<.relevant_plan(s)>", trigger_str), log)
    tok, ast_event = agentspeak.parser.parse_event(tokens.next(), tokens, log)
    if tok.lexeme != ".":
        raise log.error(
            "expected a single triggering event, got: '%s'", tok.lexeme, loc=tok.loc)
    event = ast_event.accept(agentspeak.runtime.BuildEventVisitor(log))

    # Step 3: look up the matching plan bucket (same key convention the
    # plan library is always organised by: trigger, goal type, functor,
    # arity).
    frozen = agentspeak.freeze(event.head, intention.scope, {})
    key = (event.trigger, event.goal_type, frozen.functor, len(frozen.args))

    # Step 4: keep only the plans in that bucket whose own head can
    # actually be matched against the parsed event's head
    # (unifies_annotated is used here purely as a yes/no check --
    # "would this plan's head line up?" -- it doesn't keep any binding
    # around afterwards).
    return [
        plan for plan in agent.plans[key]
        if agentspeak.unifies_annotated(plan.head, frozen)
    ]


@actions.add(".relevant_plans", 2)  # Enric
def _relevant_plans(agent, term, intention):
    """.relevant_plans(TriggerString, Plans)

    Unify Plans with the list of plans relevant to the triggering event given as
    a string (e.g. "+!task", "-!task", "+belief"). A plan is relevant when it has
    the same trigger/goal type and its head unifies with the event head.
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    # Step 1: find the matching plans and render each one back to plain
    # .asl text.
    trigger_str = asl_str(agentspeak.grounded(term.args[0], intention.scope))
    result = tuple(_plan_to_str(plan) for plan in _plans_for_trigger(agent, intention, trigger_str))

    # Step 2: match the whole list against Plans in one go.
    if agentspeak.unify(term.args[1], result, intention.scope, intention.stack):
        yield


@actions.add(".relevant_plan", 2)  # Enric
def _relevant_plan(agent, term, intention):
    """.relevant_plan(TriggerString, Plan)

    Backtracking counterpart of .relevant_plans: instead of collecting every
    relevant plan into one list, unify Plan with each relevant plan in turn,
    one per backtrack. Mirrors Jason's .relevant_plan(Trigger, Plan) -- e.g.
    .findall(P, .relevant_plan("+!go", P), L) is equivalent to
    .relevant_plans("+!go", L).
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    trigger_str = asl_str(agentspeak.grounded(term.args[0], intention.scope))
    plans = _plans_for_trigger(agent, intention, trigger_str)

    # Step 1: same try-each-candidate-then-backtrack pattern used
    # throughout this file: offer each matching plan (rendered as text)
    # as one answer for Plan, in turn.
    choicepoint = object()
    for plan in plans:
        intention.stack.append(choicepoint)
        if agentspeak.unify(term.args[1], _plan_to_str(plan), intention.scope, intention.stack):
            yield
        agentspeak.reroll(intention.scope, intention.stack, choicepoint)


@actions.add(".list_plans", 0)  # Enric
@actions.add(".list_plans", 1)  # Enric
def _list_plans(agent, term, intention):
    """.list_plans[(TriggerString)]

    Print every plan in the plan library, one per line, in AgentSpeak
    source form. With an optional TriggerString filter (same string format
    as .relevant_plans/.relevant_plan), only plans relevant to that
    triggering event are printed. Mirrors Jason's .list_plans[(trigger)];
    a debug aid like .dump/.control_flow, so it prints directly rather
    than going through the agent-tagged .print.
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    # Step 1: with a filter argument, use only the matching plans;
    # without one, flatten every bucket in the whole plan library
    # together.
    if len(term.args) == 1:
        trigger_str = asl_str(agentspeak.grounded(term.args[0], intention.scope))
        plans = _plans_for_trigger(agent, intention, trigger_str)
    else:
        plans = [plan for plan_list in agent.plans.values() for plan in plan_list]  # flatten every bucket into one list

    # Step 2: print each one's full .asl source form.
    LOGGER.info("Plans")
    for plan in plans:
        print(_plan_to_str(plan))

    yield


@actions.add(".plan_label", 2)  # Enric
def _plan_label(agent, term, intention):
    """.plan_label(Plan, Label)

    Unify Plan (a plan string) with each plan whose @label matches Label. Label
    may be given as an atom, "label" or "@label". Backtracks over all matches.
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    # Step 1: normalise the requested label.
    label = _normalise_label(agentspeak.grounded(term.args[1], intention.scope))

    # Step 2: go through every plan in every bucket, and for each one
    # whose own @label matches, offer its rendered text as one answer
    # for Plan -- the usual try-each-candidate-then-backtrack pattern.
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
