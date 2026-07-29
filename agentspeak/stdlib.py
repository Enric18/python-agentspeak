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


def _delete_range(target, start, end):
    """Shared by both .delete arities: remove the half-open index range
    [start, end) from a list or a string. Matches Jason's own delete.java
    exactly (deleteFromList/deleteFromString there use the same half-open
    convention: .delete(1,3,[a,b,c,a],L) keeps indices 0 and 3, unifying L
    with [a,a]).
    """
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
        return tuple(item for i, item in enumerate(target) if i < start or i >= end)
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
    args = term.args

    if len(args) == 4:
        start = agentspeak.grounded(args[0], intention.scope)
        end = agentspeak.grounded(args[1], intention.scope)
        target = agentspeak.grounded(args[2], intention.scope)
        result_arg = args[3]
        if not (agentspeak.is_number(start) and agentspeak.is_number(end)):
            raise agentspeak.AslError("expected numeric Start/End for .delete/4")
        result = _delete_range(target, int(start), int(end))
    else:
        arg0 = agentspeak.grounded(args[0], intention.scope)
        target = agentspeak.grounded(args[1], intention.scope)
        result_arg = args[2]

        if agentspeak.is_number(arg0):
            start = int(arg0)
            result = _delete_range(target, start, start + 1)
        elif agentspeak.is_string(arg0):
            if not agentspeak.is_string(target):
                raise agentspeak.AslError(
                    "expected a string target for .delete when the first argument is a string")
            result = target.replace(arg0, "")
        else:
            if not agentspeak.is_list(target):
                raise agentspeak.AslError(
                    "expected a list target for .delete when the first argument is a term")
            result = tuple(item for item in target if not agentspeak.unifies(arg0, item))

    if agentspeak.unify(result, result_arg, intention.scope, intention.stack):
        yield


def _list_or_string(agent, term_arg, intention, action_name):
    value = agentspeak.grounded(term_arg, intention.scope)
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
    value = _list_or_string(agent, term.args[0], intention, ".reverse")
    if agentspeak.is_string(value):
        result = value[::-1]
    else:
        result = tuple(reversed(value))

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
    value = agentspeak.grounded(term.args[0], intention.scope)
    if not agentspeak.is_list(value):
        raise agentspeak.AslError("expected a list for .shuffle, got: '%s'" % (value,))

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
    value = _list_or_string(agent, term.args[1], intention, ".suffix")

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
    value = _list_or_string(agent, term.args[1], intention, ".prefix")

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
    value = _list_or_string(agent, term.args[1], intention, ".sublist")

    def _sublists():
        n = len(value)
        for start in range(n):
            for end in range(n, start, -1):
                yield value[start:end]
        yield value[0:0]

    choicepoint = object()
    for sub in _sublists():
        intention.stack.append(choicepoint)
        if agentspeak.unify(term.args[0], sub, intention.scope, intention.stack):
            yield
        agentspeak.reroll(intention.scope, intention.stack, choicepoint)


def _as_two_lists(term, intention, action_name):
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
    s1, s2 = _as_two_lists(term, intention, ".difference")
    result = tuple(sorted(set(s1) - set(s2)))
    if agentspeak.unify(result, term.args[2], intention.scope, intention.stack):
        yield


@actions.add(".intersection", 3)  # Enric
def _intersection(agent, term, intention):
    """.intersection(S1, S2, S3)

    Unify S3 with the elements common to both S1 and S2 (lists treated as
    sets): deduplicated and sorted. Mirrors Jason's .intersection(S1, S2, S3).
    """
    s1, s2 = _as_two_lists(term, intention, ".intersection")
    result = tuple(sorted(set(s1) & set(s2)))
    if agentspeak.unify(result, term.args[2], intention.scope, intention.stack):
        yield


@actions.add(".union", 3)  # Enric
def _union(agent, term, intention):
    """.union(S1, S2, S3)

    Unify S3 with every element in S1 or S2 (lists treated as sets):
    deduplicated and sorted. Mirrors Jason's .union(S1, S2, S3).
    """
    s1, s2 = _as_two_lists(term, intention, ".union")
    result = tuple(sorted(set(s1) | set(s2)))
    if agentspeak.unify(result, term.args[2], intention.scope, intention.stack):
        yield


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
    belief = agentspeak.freeze(term.args[0], intention.scope, {})
    annotation = agentspeak.freeze(term.args[1], intention.scope, {})

    if agentspeak.is_list(belief):
        result = tuple(
            item.with_annotation(annotation) if agentspeak.is_literal(item) else item
            for item in belief
        )
    elif agentspeak.is_literal(belief):
        result = belief.with_annotation(annotation)
    else:
        raise agentspeak.AslError(
            "expected a literal or a list of literals for .add_annot, got: '%s'" % belief)

    if agentspeak.unify(term.args[2], result, intention.scope, intention.stack):
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


@actions.add(".belief", 1)  # Enric
def _belief(agent, term, intention):
    """.belief(Bel)

    Test/enumerate Bel against the belief base only, excluding rules and
    rule-derived inference -- unlike an ordinary ?Bel or plan-context
    query (TermQuery), which also consults agent.rules. Mirrors Jason's
    .belief(+/-Bel): "considers only the set of beliefs in the BB."
    """
    pattern = agentspeak.evaluate(term.args[0], intention.scope)
    try:
        group = pattern.literal_group()
    except AttributeError:
        raise agentspeak.AslError("expected a literal for .belief, got: '%s'" % pattern)

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
    pattern = agentspeak.freeze(term.args[0], intention.scope, {})
    if not agentspeak.is_literal(pattern):
        raise agentspeak.AslError(
            "expected a literal for .relevant_rules, got: '%s'" % pattern)

    key = (pattern.functor, len(pattern.args))
    result = tuple(
        str(rule) for rule in agent.rules[key]
        if agentspeak.unifies_annotated(rule.head, pattern)
    )

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
    pattern = agentspeak.evaluate(term.args[0], intention.scope)
    query = agentspeak.runtime.TermQuery(term.args[1])

    memo = {}
    result = []
    for _ in query.execute(agent, intention):
        result.append(agentspeak.freeze(pattern, intention.scope, memo))

    if agentspeak.unify(tuple(sorted(set(result))), term.args[2], intention.scope, intention.stack):
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


def _parse_event_spec(source_name, event_str):
    """Parse an event-spec string (e.g. "+!g(1,2)", "-belief") into an
    Event(trigger, goal_type, head), reusing the interpreter's own event
    grammar. Shared by .wait's optional event argument, .at, .drop_event
    and .drop_all_events's matching -- python-agentspeak's grammar has no
    quoted-event term syntax (Jason's own {+!g}), so this string-based
    adaptation is used throughout instead.
    """
    if not event_str.endswith("."):
        event_str += "."
    log = agentspeak.Log(LOGGER, 1)
    tokens = agentspeak.lexer.TokenStream(agentspeak.StringSource(source_name, event_str), log)
    tok, ast_event = agentspeak.parser.parse_event(tokens.next(), tokens, log)
    if tok.lexeme != ".":
        raise log.error("expected no further tokens after event, got: '%s'", tok.lexeme, loc=tok.loc)
    return ast_event.accept(agentspeak.runtime.BuildEventVisitor(log))


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
        event = _parse_event_spec("<.wait>", event)

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

def _is_pending_desire(pending):
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
    if len(term.args) < 1 or len(term.args) > 2:
        raise agentspeak.AslError("internal action .desire expects 1 or 2 arguments")

    goal_arg = term.args[0]
    has_intention_var = len(term.args) == 2

    if not has_intention_var:
        choicepoint = object()
        for pending in agent.events:
            if not _is_pending_desire(pending):
                continue

            intention.stack.append(choicepoint)
            if agentspeak.unify(goal_arg, pending.frozen, intention.scope, intention.stack):
                yield
            agentspeak.reroll(intention.scope, intention.stack, choicepoint)

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
    import collections

    goal = agentspeak.freeze(term.args[0], intention.scope, {})

    agent.events = collections.deque(
        pending for pending in agent.events
        if not (_is_pending_desire(pending) and pending.frozen == goal)
    )

    yield from _drop_intention(agent, term, intention)


@actions.add(".drop_all_desires", 0) #Enric
def _drop_all_desires(agent, term, intention):
    """.drop_all_desires

    Drop every desire: clear every pending achievement event (belief
    events are left alone -- a desire is a goal, not a belief update) and
    every intention (reusing .drop_all_intentions verbatim).
    """
    import collections

    agent.events = collections.deque(
        pending for pending in agent.events if not _is_pending_desire(pending)
    )

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
    import asyncio

    name = agentspeak.asl_str(agentspeak.grounded(term.args[0], intention.scope))
    try:
        target = _created_agents.pop(name)
    except KeyError:
        raise agentspeak.AslError(
            ".kill_agent: no agent created via .create_agent is known by the name '%s'" % name)

    loop = asyncio.get_running_loop()

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
    import collections

    spec_str = agentspeak.asl_str(agentspeak.grounded(term.args[0], intention.scope))
    spec = _parse_event_spec("<.drop_event>", spec_str)

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

    Goal lookup is agent.intentions only, deliberately: a Goal that is
    still just a pending, uncommitted desire (see .desire/agent.events)
    has no frame to succeed yet, so it's invisible here -- .drop_desire
    is what resolves a still-pending goal instead.
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
    if len(term.args) == 1:
        goal = agentspeak.freeze(term.args[0], intention.scope, {})
        targets = [
            stack[-1] for stack in agent.intentions
            if stack and any(item.head_term == goal for item in stack)
        ]
    else:
        goal = intention.head_term  # already frozen -- set by _commit_event
        targets = [intention]

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
    goal = agentspeak.freeze(term.args[0], intention.scope, {})

    resumed_any = False
    for stack in agent.intentions:
        if not stack or not any(item.head_term == goal for item in stack):
            continue
        top = stack[-1]
        if top.waiter is not None and getattr(top.waiter, "reason", None) == _SUSPEND_REASON:
            top.waiter = None
            resumed_any = True

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
    goal = agentspeak.freeze(term.args[0], intention.scope, {})

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
    only_current = False
    if len(term.args) == 4:
        current_flag = agentspeak.grounded(term.args[3], intention.scope)
        if not (agentspeak.is_atom(current_flag) and current_flag.functor == "current"):
            raise agentspeak.AslError(
                "expected the atom 'current' as the 4th argument to .intention")
        only_current = True

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
    match = _AT_WHEN_RE.match(when)
    if not match:
        raise agentspeak.AslError(
            "expected .at time spec of the form 'now +<number> [s|m|h|d]', got: '%s'" % when)

    amount = float(match.group(1))
    unit = match.group(2).lower()
    try:
        seconds_per_unit = _AT_UNIT_SECONDS[unit]
    except KeyError:
        raise agentspeak.AslError("unknown time unit in .at: '%s'" % unit)

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
    import asyncio
    import functools

    when = agentspeak.asl_str(agentspeak.grounded(term.args[0], intention.scope))
    event_str = agentspeak.asl_str(agentspeak.grounded(term.args[1], intention.scope))

    delay = _parse_at_when(when)
    event = _parse_event_spec("<.at>", event_str)

    # Freeze now: intention.scope may no longer be meaningful once the
    # callback actually fires, out of line with this action call.
    frozen_head = agentspeak.freeze(event.head, intention.scope, {})

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


def _plans_for_trigger(agent, intention, trigger_str):
    """Parse a trigger-event string (e.g. "+!task") and return the plan
    objects relevant to it: same trigger/goal type, head unifies with the
    event head. Shared by .relevant_plans, .relevant_plan and .list_plans.
    """
    if not trigger_str.endswith("."):
        trigger_str += "."

    log = agentspeak.Log(LOGGER, 1)
    tokens = agentspeak.lexer.TokenStream(
        agentspeak.StringSource("<.relevant_plan(s)>", trigger_str), log)
    tok, ast_event = agentspeak.parser.parse_event(tokens.next(), tokens, log)
    if tok.lexeme != ".":
        raise log.error(
            "expected a single triggering event, got: '%s'", tok.lexeme, loc=tok.loc)
    event = ast_event.accept(agentspeak.runtime.BuildEventVisitor(log))

    frozen = agentspeak.freeze(event.head, intention.scope, {})
    key = (event.trigger, event.goal_type, frozen.functor, len(frozen.args))

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
    trigger_str = asl_str(agentspeak.grounded(term.args[0], intention.scope))
    result = tuple(_plan_to_str(plan) for plan in _plans_for_trigger(agent, intention, trigger_str))

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
    trigger_str = asl_str(agentspeak.grounded(term.args[0], intention.scope))
    plans = _plans_for_trigger(agent, intention, trigger_str)

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
    if len(term.args) == 1:
        trigger_str = asl_str(agentspeak.grounded(term.args[0], intention.scope))
        plans = _plans_for_trigger(agent, intention, trigger_str)
    else:
        plans = [plan for plan_list in agent.plans.values() for plan in plan_list]

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
