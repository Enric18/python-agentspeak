# -*- coding: utf-8 -*-
#
# This file is part of the python-agentspeak interpreter.
# Copyright (C) 2016-2019 Niklas Fiekas <niklas.fiekas@tu-clausthal.de>.
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
# This file contains both the original python-agentspeak runtime (Niklas
# Fiekas, copyright above) and additions made for a TFG (Bachelor's thesis)
# project by Enric Hernandez-Minaya: the persistent event queue (the
# PendingEvent class, the self.events line in Agent.__init__, the
# deferred-dispatch part of Agent.call, Agent._commit_event,
# Agent._clear_pending_waiter, and the interleaved commit/execution phases
# in Agent.step), and the pluggable Agent.select_event extension point.
#
# Every piece of code added or changed for the thesis carries an inline
#     # Implemented by Enric Hernandez-Minaya, May-Aug 2026
# comment right where it happens, so it's always clear which parts are
# original and which were added. Everything else in this file -- classes,
# methods, functions with no such tag -- is the original, unmodified
# python-agentspeak code. Every function, original or added, has
# step-by-step comments explaining what it does in plain language.
# ---------------------------------------------------------------------------

from __future__ import print_function

import collections
import copy
import functools
import os.path
import sys
import time
import re

import agentspeak
import agentspeak.lexer
import agentspeak.parser
import agentspeak.util
from agentspeak import UnaryOp, BinaryOp, AslError, asl_str



LOGGER = agentspeak.get_logger(__name__)


class BuildTermVisitor:
    """Walks a parsed piece of AgentSpeak source (an "AST", the tree the
    parser produces) and turns it into the actual runtime objects the
    interpreter works with: Literal, tuple (for lists), LinkedList,
    UnaryExpr/BinaryExpr, Var/Wildcard. One instance is shared for a
    whole plan/query so the same variable name always maps to the same
    Var object (see visit_variable)."""
    def __init__(self, variables):
        # Step 1: variables remembers, by name, which Var/Wildcard object
        # was created for it so far -- shared across this whole visit.
        self.variables = variables

    def visit_literal(self, ast_literal):
        # Step 1: build a Literal (an AgentSpeak term like foo(1,2)) by
        # recursively converting its functor's arguments and annotations.
        return agentspeak.Literal(ast_literal.functor,
            (t.accept(self) for t in ast_literal.terms),
            (t.accept(self) for t in ast_literal.annotations))

    def visit_const(self, ast_const):
        # Step 1: a plain constant (number, string, etc.) is already its
        # own value, nothing to convert.
        return ast_const.value

    def visit_list(self, ast_list):
        # Step 1: an AgentSpeak list becomes a plain Python tuple of its
        # (recursively converted) elements.
        return tuple(t.accept(self) for t in ast_list.terms)

    def visit_linked_list(self, ast_linked_list):
        # Step 1: the "[Head|Tail]" list-pattern syntax becomes a
        # LinkedList pairing a converted head with a converted tail.
        return agentspeak.LinkedList(
            ast_linked_list.head.accept(self),
            ast_linked_list.tail.accept(self))

    def visit_unary_op(self, ast_unary_op):
        # Step 1: something like "not X" becomes a UnaryExpr that can be
        # evaluated later (lazily, once X's value is known).
        return agentspeak.UnaryExpr(
            ast_unary_op.operator.value,
            ast_unary_op.operand.accept(self))

    def visit_binary_op(self, ast_binary_op):
        # Step 1: something like "X + Y" or "X & Y" becomes a BinaryExpr,
        # again left for later evaluation.
        return agentspeak.BinaryExpr(
            ast_binary_op.operator.value,
            ast_binary_op.left.accept(self),
            ast_binary_op.right.accept(self))

    def visit_variable(self, ast_variable):
        # Step 1: if this exact variable name has already shown up
        # earlier in this same plan/query, reuse the same Var object --
        # that's what makes "X" in two different places in a plan refer
        # to the same binding.
        try:
            return self.variables[ast_variable.name]
        except KeyError:
            # Step 2: first time seeing this name. "_" is AgentSpeak's
            # anonymous/"don't care" variable -- it always gets its own
            # fresh Wildcard (never reused, since each "_" should match
            # independently), any other name gets a fresh Var that IS
            # remembered for next time.
            if ast_variable.name == "_":
                var = agentspeak.Wildcard()
            else:
                var = agentspeak.Var()

            self.variables[ast_variable.name] = var
            return var


class BuildReplacePatternVisitor(BuildTermVisitor):
    """A small variant of BuildTermVisitor used only for the "-+belief"
    replace formula: everything works the same as the base visitor
    except any expression (X+Y, not X, etc.) collapses to a Wildcard
    instead of being built into a real expression -- a replace pattern
    is only ever used to find and remove a matching belief, never to
    compute a value, so there's nothing to evaluate there."""
    def __init__(self):
        # Step 1: always starts with its own fresh, empty variable map.
        BuildTermVisitor.__init__(self, {})

    def visit_unary_op(self, ast_unary_op):
        # Step 1: collapse to "don't care".
        return agentspeak.Wildcard()

    def visit_binary_op(self, ast_binary_op):
        # Step 1: same as above.
        return agentspeak.Wildcard()


class BuildQueryVisitor:
    """Walks a parsed AgentSpeak query/condition (a plan's ": Context"
    part, or the argument of "?query") and turns it into a runtime Query
    object (TermQuery, AndQuery, OrQuery, NotQuery, UnifyQuery,
    ActionQuery, TrueQuery, FalseQuery) that actually knows how to run
    itself against beliefs, rules, and internal actions like .print."""
    def __init__(self, variables, actions, log):
        # Step 1: variables is shared with any BuildTermVisitor this
        # visitor creates along the way, so query-side variables line up
        # with the same-named ones in the surrounding plan; actions is
        # the table of available internal actions (.print, .send, ...);
        # log collects warnings/errors together with where in the
        # source file they came from.
        self.variables = variables
        self.actions = actions
        self.log = log

    def visit_literal(self, ast_literal):
        # Step 1: build the plain term first either way.
        term = ast_literal.accept(BuildTermVisitor(self.variables))
        try:
            # Step 2: if this literal's name and number of arguments
            # match a registered internal action (like .my_name(X) used
            # inside a plan condition), wrap it as an ActionQuery so
            # running this query actually calls that action.
            arity = len(ast_literal.terms)
            action_impl = self.actions.lookup(ast_literal.functor, arity)

            return ActionQuery(term, action_impl)
        except KeyError:
            # Step 3: no action by that name -- warn only if the name
            # looks like it was meant to be one (starts with "."), then
            # treat it as an ordinary belief/rule lookup instead.
            if "." in ast_literal.functor:
                self.log.warning("no such action '%s/%d'", ast_literal.functor, arity,
                                 loc=ast_literal.loc,
                                 extra_locs=[t.loc for t in ast_literal.terms])
            return TermQuery(term)

    def visit_const(self, ast_const):
        # Step 1: only the plain words true/false are valid queries on
        # their own -- anything else makes no sense as a condition.
        if ast_const.value is True:
            return TrueQuery()
        elif ast_const.value is False:
            return FalseQuery()
        else:
            raise self.log.error("non-boolean const in query context: '%s'",
                                 ast_const.value, loc=ast_const.loc)

    def visit_binary_op(self, ast_binary_op):
        # Step 1: "&" (and) / "|" (or) become AndQuery/OrQuery wrapping
        # the two sides, each side built the same recursive way.
        if ast_binary_op.operator == BinaryOp.op_and:
            return AndQuery(ast_binary_op.left.accept(self),
                            ast_binary_op.right.accept(self))
        elif ast_binary_op.operator == BinaryOp.op_or:
            return OrQuery(ast_binary_op.left.accept(self),
                           ast_binary_op.right.accept(self))
        elif ast_binary_op.operator == BinaryOp.op_unify:
            # Step 2: "=" becomes a UnifyQuery over the two sides built
            # as plain terms (not as sub-queries -- unification isn't a
            # yes/no query by itself, it's "try to make these equal").
            return UnifyQuery(ast_binary_op.left.accept(BuildTermVisitor(self.variables)),
                              ast_binary_op.right.accept(BuildTermVisitor(self.variables)))
        elif not ast_binary_op.operator.value.comp_op:
            # Step 3: anything else has to at least be a comparison
            # (<, >, etc.) to make sense here; if it isn't, that's an
            # error in the source file.
            self.log.error("invalid operator in query context: '%s'",
                           ast_binary_op.operator.value.lexeme,
                           loc=ast_binary_op.loc,
                           extra_locs=[ast_binary_op.left.loc, ast_binary_op.right.loc])

        # Step 4: comparisons (X < Y, etc.) fall through to a plain
        # TermQuery -- at run time, evaluating that expression gives a
        # plain True/False, which TermQuery.execute already knows how
        # to treat as an instant success or failure.
        return TermQuery(ast_binary_op.accept(BuildTermVisitor(self.variables)))

    def visit_unary_op(self, ast_unary_op):
        # Step 1: "not" is the only unary operator that's valid as a
        # whole query on its own.
        if ast_unary_op.operator == UnaryOp.op_not:
            return NotQuery(ast_unary_op.operand.accept(self))
        else:
            raise self.log.error("non-boolean unary operator in query context: '%s'",
                                 ast_unary_op.operator.lexeme, ast_unary_op.loc)

    def visit_variable(self, ast_variable):
        # Step 1: a bare variable used as a whole query (rare, but
        # legal) is wrapped as a TermQuery over the built variable.
        return TermQuery(ast_variable.accept(BuildTermVisitor(self.variables)))


class BuildEventVisitor(BuildTermVisitor):
    """Walks a parsed triggering-event expression (e.g. "+!goal(X)" or
    "-belief") and turns it into a runtime Event(trigger, goal_type,
    head). Used both for a plan's own trigger, and -- reused from
    stdlib.py -- for parsing event specs given as plain strings, like
    .wait's optional event argument, .at, .drop_event, and friends."""
    def __init__(self, log):
        # Step 1: an event's head always starts with its own fresh,
        # empty variable map (never shared with a surrounding plan
        # body); log collects errors with their source location.
        super(BuildEventVisitor, self).__init__({})
        self.log = log

    def visit_event(self, ast_event):
        # Step 1: fold any compile-time-computable arithmetic in the
        # event first (e.g. turn "1+1" into "2" ahead of time), then
        # build the runtime Event from its trigger/goal_type plus the
        # (now-converted) head term.
        ast_event = ast_event.accept(agentspeak.parser.ConstFoldVisitor(self.log))
        return Event(ast_event.trigger, ast_event.goal_type, ast_event.head.accept(self))

    def visit_unary_op(self, op):
        # Step 1: an event's head has to be a plain, matchable pattern
        # -- an expression like "not X" doesn't make sense as one, so
        # this is a hard error.
        raise self.log.error("event is supposed to be unifiable, but contains non-const expression", loc=op.loc)

    def visit_binary_op(self, op):
        # Step 1: same restriction as visit_unary_op above.
        raise self.log.error("event is supposed to be unifiable, but contains non-const expression", loc=op.loc)


class TrueQuery:
    """The query for the literal word "true" -- always succeeds, exactly
    once, no matter what."""
    def execute(self, agent, intention):
        # Step 1: one free success, no conditions attached.
        yield


class FalseQuery:
    """The query for the literal word "false" -- never succeeds."""
    def execute(self, agent, intention):
        # Step 1: produce nothing at all. The `yield` after `return` can
        # never run -- it's only there so Python still treats this
        # method as a generator (matching every other Query.execute).
        return
        yield


class ActionQuery:
    """Wraps a call to an internal action (like .print(...)) so it can
    be run as one step inside a bigger query, e.g. inside a plan's
    condition."""
    def __init__(self, term, impl):
        # Step 1: term is the call itself (e.g. .my_name(X)); impl is
        # the actual Python function implementing that action.
        self.term = term
        self.impl = impl

    def execute(self, agent, intention):
        # Step 1: just hand off to the action's own implementation and
        # pass along every solution it produces.
        for _ in self.impl(agent, self.term, intention):
            yield


class TermQuery:
    """The general-purpose query: check/search whether a given term
    matches a belief, or can be proven true via a rule. This is what an
    ordinary plan condition or "?something" ends up as once it isn't a
    recognized internal action, an and/or/not, or a "=" unification."""
    def __init__(self, term):
        # Step 1: term is the (possibly still partly symbolic) pattern
        # to look for.
        self.term = term

    def execute(self, agent, intention):
        # Step 1: evaluate the term first. If it's already a plain
        # true/false (e.g. it came from a comparison like X < 5), treat
        # that as an instant success or failure, no belief lookup
        # needed at all.
        # Boolean constants.
        term = agentspeak.evaluate(self.term, intention.scope)
        if term is True:
            yield
            return
        elif term is False:
            return

        # Step 2: otherwise this has to be a real term (like
        # item(X, red)) -- get the (name, number-of-arguments) key used
        # to group beliefs/rules together.
        try:
            group = term.literal_group()
        except AttributeError:
            raise AslError("expected boolean or literal in query context, got: '%s'" % term)

        # Step 3: first, try every belief stored under that same group.
        # agentspeak.unify_annotated is Prolog-style unification: it
        # tries to make `term` and this specific `belief` identical by
        # filling in any of `term`'s still-unbound variables with
        # whatever value the belief actually has there (and fails
        # outright if they already disagree on something). Each time
        # that succeeds, this hands one solution back to whoever asked
        # (yield); if the caller wants another answer (backtracking),
        # it comes back here and simply moves on to the next belief.
        # Query on the belief base.
        for belief in agent.beliefs[group]:
            for _ in agentspeak.unify_annotated(term, belief, intention.scope, intention.stack):
                yield

        choicepoint = object()

        # Step 4: then, try every rule (head :- body) in the same
        # group. Each rule is deep-copied first so its own internal
        # variables don't get mixed up with a previous attempt's
        # bindings. A choicepoint marks "this is where to undo bindings
        # back to if this rule doesn't pan out" -- unify the rule's head
        # against `term`, and if that works, recursively run the rule's
        # own body as a query too (a rule can only really succeed if
        # both its head matches AND its body holds). Either way,
        # `reroll` undoes whatever this rule attempt bound, so the next
        # rule starts with a clean slate.
        # Follow rules.
        for rule in agent.rules[group]:
            rule = copy.deepcopy(rule)  # avoid mixing this rule's variables with a previous attempt

            intention.stack.append(choicepoint)

            if agentspeak.unify(term, rule.head, intention.scope, intention.stack):
                for _ in rule.query.execute(agent, intention):
                    yield

            agentspeak.reroll(intention.scope, intention.stack, choicepoint)  # undo this rule's bindings before trying the next

    def __str__(self):
        return str(self.term)


class AndQuery:
    """The "&" (and) query: both sides have to succeed. For every way
    the left side can succeed, try every way the right side can succeed
    too (with the left side's bindings already in place) -- this is how
    "X & Y" can produce more than one combined answer if either side
    has more than one."""
    def __init__(self, left, right):
        self.left = left
        self.right = right

    def execute(self, agent, intention):
        # Step 1: nested loops -- for each left solution, try every
        # right solution under those same bindings.
        for _ in self.left.execute(agent, intention):
            for _ in self.right.execute(agent, intention):
                yield

    def __str__(self):
        return "(%s & %s)" % (self.left, self.right)


class OrQuery:
    """The "|" (or) query: either side succeeding is enough. Yields
    every solution from the left side, then every solution from the
    right side -- the two sides don't interact with each other."""
    def __init__(self, left, right):
        self.left = left
        self.right = right

    def execute(self, agent, intention):
        # Step 1: every answer from the left side first...
        for _ in self.left.execute(agent, intention):
            yield

        # Step 2: ...then every answer from the right side.
        for _ in self.right.execute(agent, intention):
            yield

    def __str__(self):
        return "(%s | %s)" % (self.left, self.right)


class NotQuery:
    """The "not" query: succeeds (once) exactly when the thing inside
    has NO solutions at all -- "negation as failure", the standard
    Prolog-style way of doing "not"."""
    def __init__(self, query):
        self.query = query

    def execute(self, agent, intention):
        # Step 1: run the inner query purely to see if it finds
        # anything at all -- push a choicepoint first so whatever
        # bindings it makes while trying can be undone afterwards
        # either way (a `not` check shouldn't leave any trace of
        # variables it bound while probing).
        choicepoint = object()
        intention.stack.append(choicepoint)

        success = any(True for _ in self.query.execute(agent, intention))

        agentspeak.reroll(intention.scope, intention.stack, choicepoint)  # undo any bindings made while probing

        # Step 2: succeed only if the inner query found nothing.
        if not success:
            yield

    def __str__(self):
        return "not " + str(self.query.term)


class UnifyQuery:
    """The "=" query: try to make the left and right side identical
    (Prolog-style unification -- filling in any unbound variables on
    either side so both sides end up equal, failing if they already
    disagree)."""
    def __init__(self, left, right):
        self.left = left
        self.right = right

    def execute(self, agent, intention):
        # Step 1: unify_annotated does all the actual work here -- it's
        # itself already a generator that yields once if the match
        # succeeds (possibly more than once, if annotations allow more
        # than one way to line up) and yields nothing if it can't.
        return agentspeak.unify_annotated(self.left, self.right, intention.scope, intention.stack)

    def __str__(self):
        return "(%s = %s)" % (self.left, self.right)


class Rule:
    """One "head :- body" rule, as stored in Agent.rules under its
    head's (name, number-of-arguments) key. When a query like
    TermQuery.execute is trying to prove something and no matching
    belief is found directly, it tries proving it through a rule
    instead."""
    def __init__(self, head, query):
        self.head = head
        self.query = query

    def __str__(self):
        return "%s :- %s" % (self.head, self.query)


class Plan:
    """One compiled AgentSpeak plan, as stored in Agent.plans keyed by
    (trigger, goal type, name, number-of-arguments). This is the
    interpreter's own internal, ready-to-run form of a plan -- head
    pattern to match against an event, a context query (the precondition
    after ":"), and body (compiled into a chain of Instruction objects,
    see BuildInstructionsVisitor further below)."""
    def __init__(self, trigger, goal_type, head, context, body, str_body, annotation):
        # Step 1: the plan's own trigger event pieces (e.g. "+" and "!"
        # for "+!goal"), its condition query, its compiled body, a
        # pre-rendered text form of the body (str_body, used when
        # printing the plan back out), and its optional @label.
        self.trigger = trigger
        self.goal_type = goal_type
        self.head = head
        self.context = context
        self.body = body
        self.str_body = str_body
        self.annotation = annotation
        # Step 2: a tiny 2-slot scratch list used when re-rendering the
        # plan's head back to text (see plan_to_str below).
        self.args = [None,None]

    def name(self):
        # Step 1: render as "<trigger><goal type><head>", e.g. "+!goal".
        return "%s%s%s" % (self.trigger.value, self.goal_type.value, self.head)


class Event:
    """A description of a triggering-event pattern: what kind of change
    (trigger: addition/removal), what kind of thing changed (goal type:
    belief/achievement/etc.), and what it looked like (head). Used both
    for a plan's own trigger, and for event specs parsed from plain
    strings (.wait, .at, .drop_event, ...)."""
    def __init__(self, trigger, goal_type, head):
        # Step 1: just remember the three pieces.
        self.trigger = trigger
        self.goal_type = goal_type
        self.head = head

    def __str__(self):
        # Step 1: render as "<trigger><goal type><head>", e.g. "+!goal".
        return "%s%s%s" % (self.trigger.value, self.goal_type.value, self.head)


class PendingEvent:
    """An event that has happened but hasn't yet been handled -- it's
    sitting in Agent.events, waiting for Agent.step to pick it and start
    (or reject) a plan for it. This is different from the Event class
    above: Event just describes a pattern to match against (e.g. for
    .wait's event argument); a PendingEvent is a concrete thing that
    actually occurred and is queued up for processing, carrying
    everything Agent._commit_event needs to handle it later, the same
    way Agent.call used to do immediately before events went through a
    queue. `frozen` -- the event's content with all variables fixed to
    their current values -- has to be computed right away, at the
    moment the event is queued, because the intention that raised it
    keeps changing its own variable bindings afterwards; `term` is kept
    around unfrozen too, for the calling intention's own later use.
    """
    # Implemented by Enric Hernandez-Minaya, May-Aug 2026
    def __init__(self, trigger, goal_type, frozen, term, calling_intention, delayed):
        # Step 1: what kind of event this is (addition/removal of a
        # belief, achievement goal, etc.).
        self.trigger = trigger
        self.goal_type = goal_type
        # Step 2: frozen is the event's content, fixed at the moment it
        # was raised (see the docstring above for why this can't wait).
        self.frozen = frozen
        # Step 3: term is kept unfrozen too, so whoever eventually
        # handles this event can still connect it back to the caller's
        # own (still-changing) variables.
        self.term = term
        # Step 4: which task raised this event (used to wake it back up
        # once the event is handled), and whether it's "fire and
        # forget" (delayed=True, the caller doesn't wait around) or the
        # caller is blocked until this gets handled.
        self.calling_intention = calling_intention
        self.delayed = delayed

    def __str__(self):
        # Step 1: render the same way a normal Event would.
        return "%s%s%s" % (self.trigger.value, self.goal_type.value, self.frozen)


class Waiter:
    """Attached to an Intention (a running task) to pause it. A task
    can be paused waiting for a specific event to happen, waiting for a
    deadline to pass, or both -- or, as a special case, blocked with
    neither (just a placeholder marker, e.g. the "pending-event" waiter
    Agent.call attaches below while a task's own event hasn't been
    handled yet)."""
    def __init__(self, event=None, until=None):
        # Step 1: event is a pattern that, if something matching it
        # happens (see Agent.call's "wake up waiting intentions" loop
        # below), clears this waiter and lets the task carry on; until
        # is a point in time (using the environment's own clock) after
        # which this waiter clears itself automatically.
        self.event = event
        self.until = until

    def poll(self, env):
        # Step 1: true only if a deadline was actually set and it has
        # now passed.
        return self.until is not None and self.until < env.time()

class Intention:
    """One running (or paused) task: think of it as one thread of
    execution following one plan. A single logical goal can actually be
    a whole STACK of these (this class doesn't hold the stack itself --
    Agent.intentions does, as a list of stacks -- but each Intention
    remembers who's "above" it via calling_term) when a plan calls a
    sub-goal, which starts its own nested task on top."""
    def __init__(self):
        # Step 1: instr is the next compiled instruction to run next
        # time this task gets a turn; head_term is this task's own
        # (frozen) triggering event; calling_term is the term the
        # PARENT task (the one that started this one, if any) is
        # waiting to match once this task finishes.
        self.instr = None
        self.head_term = None
        self.calling_term = None

        # Step 2: scope holds this task's own variable bindings so far;
        # stack is the "undo log" reroll uses to backtrack those
        # bindings when a unification attempt doesn't work out.
        self.scope = {}
        self.stack = collections.deque()

        # Step 3: query_stack/choicepoint_stack support running nested
        # queries (if/while/for) one small step at a time across
        # multiple reasoning cycles instead of all at once -- see
        # push_query/next_or_fail/pop_query/push_choicepoint/
        # pop_choicepoint further below.
        self.query_stack = collections.deque()
        self.choicepoint_stack = collections.deque()

        # Step 4: None while this task is free to run; set to a Waiter
        # to pause it (checked in Agent.step).
        self.waiter = None


class Agent:
    """One BDI agent: its own beliefs, rules, plans, running tasks
    (intentions), and events waiting to be handled. Most of what makes
    this interpreter tick lives here -- call() decides what happens
    when something occurs, step() runs one small unit of work per
    call."""
    def __init__(self, env, name, beliefs=None, rules=None, plans=None):
        # Step 1: which Environment owns this agent, and its own name.
        self.env = env
        self.name = name

        # Step 2: the belief base, rule base, and plan library, each
        # grouped by (name, number-of-arguments) -- plans additionally
        # by (trigger, goal type). These are defaultdicts, so looking up
        # a group that's never been used yet just gives back an empty
        # set/list instead of an error.
        self.beliefs = collections.defaultdict(lambda: set()) if beliefs is None else beliefs
        self.rules = collections.defaultdict(lambda: []) if rules is None else rules
        self.plans = collections.defaultdict(lambda: []) if plans is None else plans

        # Step 3: the running tasks, as a list of stacks (each stack is
        # one chain of sub-goals, most-recently-started task last).
        self.intentions = collections.deque()
        # Implemented by Enric Hernandez-Minaya, May-Aug 2026
        # Step 4: events that have happened but haven't been handled
        # yet. Agent.call adds to this queue instead of reacting
        # straight away; Agent.step's first phase (via select_event and
        # _commit_event) handles at most one of these per reasoning
        # cycle, the same one-event-per-cycle rhythm Jason itself uses.
        self.events = collections.deque()  # pending PendingEvents, not yet committed to an intention

    def dump(self):
        # Step 1: print every belief, across every group, in full detail.
        LOGGER.info("Belief base")
        for beliefs in self.beliefs.values():
            for belief in beliefs:
                print(agentspeak.asl_repr(belief))

        # Step 2: print every rule.
        LOGGER.info("Rules")
        for rules in self.rules.values():
            for rule in rules:
                print(rule)

        # Step 3: print every plan's trigger/head/condition (not its
        # full body -- just "..." -- this is a quick overview, not a
        # full source dump; see stdlib.py's .list_plans for that).
        LOGGER.info("Plans")
        for plans in self.plans.values():
            for plan in plans:
                print("* %s%s%s : %s <- ... ." % (plan.trigger.value, plan.goal_type.value, plan.head, plan.context))

        # Step 4: print every currently running task.
        LOGGER.info("Intentions")
        for i, intention_stack in enumerate(self.intentions):
            for j, intention in enumerate(intention_stack):
                print(i, j, intention)

    def add_rule(self, rule):
        # Step 1: file the rule under its head's (name,
        # number-of-arguments) group.
        self.rules[(rule.head.functor, len(rule.head.args))].append(rule)

    def add_plan(self, plan):
        # Step 1: file the plan under (trigger, goal type, name,
        # number-of-arguments) -- the same key used everywhere else in
        # this file to look up which plans could react to a given event.
        self.plans[(plan.trigger, plan.goal_type, plan.head.functor, len(plan.head.args))].append(plan)

    def call(self, trigger, goal_type, term, calling_intention, delayed=False):
        # Step 1: a belief change (+belief or -belief) is applied to
        # the belief base right here, immediately -- only the REACTION
        # to it (any plan listening for it) goes through the delayed
        # queue further down. If a removal doesn't actually find a
        # matching belief, there's nothing to react to either, so bail
        # out early.
        # Modify beliefs.
        if goal_type == agentspeak.GoalType.belief:
            if trigger == agentspeak.Trigger.addition:
                self.add_belief(term, calling_intention.scope)
            else:
                found = self.remove_belief(term, calling_intention)
                if not found:
                    return True

        # Step 2: fix the term's current value under the caller's
        # variable bindings right now -- the caller's own bindings will
        # keep changing after this call returns, so this snapshot has
        # to be taken immediately.
        # Freeze with caller scope.
        frozen = agentspeak.freeze(term, calling_intention.scope, {})

        if not isinstance(frozen, agentspeak.Literal):
            raise AslError("expected literal")

        # Step 3: if any currently-paused task is specifically waiting
        # for an event like this one (see .wait's optional event
        # argument), wake it up right now. unifies_annotated here is a
        # yes/no check: "does this waiting task's pattern actually match
        # what just happened?" -- if so, clear its waiter so it's free
        # to run again on its next turn. This check is separate from,
        # and happens before, the plan-matching/dispatch logic below.
        # Wake up waiting intentions.
        for intention_stack in self.intentions:
            if not intention_stack:
                continue
            intention = intention_stack[-1]

            if not intention.waiter or not intention.waiter.event:
                continue
            event = intention.waiter.event

            if event.trigger != trigger or event.goal_type != goal_type:
                continue

            if agentspeak.unifies_annotated(event.head, frozen):
                intention.waiter = None

        # Step 4: four kinds of events are handled right here,
        # immediately, and then this whole function returns -- none of
        # them go through the deferred queue below.
        # If the goal is an achievement and the trigger is a removal, then the agent will delete the goal from his list of
        # intentions
        if (
            goal_type == agentspeak.GoalType.achievement
            and trigger == agentspeak.Trigger.removal
        ):
            self._unachieve(term)
            return True

        # If the goal is an tellHow and the trigger is an addition, then the agent will add the goal received as string to his
        # list of plans
        if (
            goal_type == agentspeak.GoalType.tellHow
            and trigger == agentspeak.Trigger.addition
        ):
            self._tell_how(term)
            return True

        # If the goal is an askHow and the trigger is an addition, then the agent will find the plan in his list of plans and
        # send it to the agent that asked
        if (
            goal_type == agentspeak.GoalType.askHow
            and trigger == agentspeak.Trigger.addition
        ):
            return self._ask_how(term)

        # If the goal is an unTellHow and the trigger is a removal, then the agent will delete the goal from his list of plans
        if (
            goal_type == agentspeak.GoalType.tellHow
            and trigger == agentspeak.Trigger.removal
        ):
            self._untell_how(term)
            return True

        # Step 5: "test" goals (checking a belief right now, like
        # "?foo") are also handled immediately, never deferred: first
        # try a matching reactive plan, then fall back to a plain
        # belief/rule check.
        #
        # This loop is the actual "which plan should run?" decision the
        # interpreter makes every time something happens -- worth
        # walking through slowly, since the exact same pattern shows up
        # again below in Agent._commit_event:
        #   1. `self.plans[...]` looks up only the plans that are even
        #      candidates: same trigger (+/-), same goal kind, same
        #      name and number of arguments as the event.
        #   2. For each candidate, in the order it was written in the
        #      source file, `unify_annotated` checks whether the plan's
        #      own head pattern (e.g. "+!go(X)") actually matches this
        #      specific event (e.g. "+!go(5)") -- filling in the plan's
        #      own variables (X = 5) if it does.
        #   3. If the head matched, `plan.context.execute(...)` then
        #      checks the plan's own condition (the part after ":") --
        #      the same kind of Prolog-style search TermQuery does
        #      above. A plan only really "fires" if both its head AND
        #      its condition succeed.
        #   4. The FIRST plan that gets through both checks wins -- this
        #      is why plan order in the source file matters, and why a
        #      more specific reacting plan should usually be written
        #      before a more general one for the same event.
        if goal_type == agentspeak.GoalType.test:
            applicable_plans = self.plans[
                (trigger, goal_type, frozen.functor, len(frozen.args))
            ]
            intention = Intention()
            for plan in applicable_plans:
                for _ in agentspeak.unify_annotated(
                    plan.head, frozen, intention.scope, intention.stack
                ):
                    for _ in plan.context.execute(self, intention):
                        # Step 6: found a plan that fits -- set this new
                        # task up to start running its body.
                        intention.head_term = frozen
                        intention.instr = plan.body
                        intention.calling_term = term

                        # Step 7: if this isn't a fire-and-forget call
                        # and the caller is still an active task, attach
                        # the new task ON TOP of the caller's own stack
                        # (a sub-goal); otherwise it becomes its own
                        # independent, brand-new stack.
                        if not delayed and self.intentions:
                            for intention_stack in self.intentions:
                                if intention_stack[-1] == calling_intention:
                                    intention_stack.append(intention)
                                    return True

                        new_intention_stack = collections.deque()
                        new_intention_stack.append(intention)
                        self.intentions.append(new_intention_stack)
                        return True
            return self.test_belief(term, calling_intention)

        # Implemented by Enric Hernandez-Minaya, May-Aug 2026
        # Step 8: everything else that gets here -- new achievement
        # goals, and belief-change reactions -- doesn't get handled
        # right away. Instead it's added to the waiting-events queue as
        # a PendingEvent, and Agent.step's first phase picks one such
        # event per reasoning cycle to actually process (see
        # Agent._commit_event) -- matching Jason's own event-queue
        # behaviour, rather than reacting to everything the instant it
        # happens.
        pending = PendingEvent(trigger, goal_type, frozen, term, calling_intention, delayed)
        self.events.append(pending)

        # Step 9: a non-delayed caller (an ordinary "!subgoal", or a
        # belief change) must not keep running past this point until
        # its own event has actually been picked up and handled --
        # reuse the same Waiter mechanism .wait/.suspend already use to
        # pause it, tagged "pending-event" so _clear_pending_waiter
        # knows it's safe to clear once that specific event is done.
        if not delayed:
            calling_intention.waiter = Waiter()
            calling_intention.waiter.reason = "pending-event"

        return True

    def _commit_event(self, pending):
        """Picks one waiting event (called from Agent.step's first
        phase) and either starts a task for it or drops it -- doing
        exactly what Agent.call used to do immediately, before events
        started going through a queue instead.
        """
        # Implemented by Enric Hernandez-Minaya, May-Aug 2026
        # Step 1: find the group of plans that could react to this
        # event (matching trigger kind, goal kind, name, argument-count).
        frozen = pending.frozen
        applicable_plans = self.plans[
            (pending.trigger, pending.goal_type, frozen.functor, len(frozen.args))
        ]
        intention = Intention()
        # Step 2: try each candidate plan in turn -- its name has to
        # match, and its condition has to hold too. Same plan-selection
        # walk described in detail in Agent.call's test-goal branch
        # above: first plan (in source order) whose head unifies AND
        # whose context query succeeds is the one that runs.
        for plan in applicable_plans:
            for _ in agentspeak.unify_annotated(
                plan.head, frozen, intention.scope, intention.stack
            ):
                for _ in plan.context.execute(self, intention):
                    # Step 3: the first plan that actually fits becomes
                    # the new task.
                    intention.head_term = frozen
                    intention.instr = plan.body
                    intention.calling_term = pending.term

                    # Step 4: if the task that raised this event was
                    # waiting on it, it can now carry on.
                    self._clear_pending_waiter(pending.calling_intention)

                    # Step 5: if the event wasn't fire-and-forget, and
                    # the task that raised it is still around, attach
                    # the new task on top of it (a "sub-goal"); in every
                    # other case (fire-and-forget events, or a caller
                    # that's gone), this becomes its own brand-new,
                    # independent task.
                    if not pending.delayed and self.intentions:
                        for intention_stack in self.intentions:
                            if intention_stack[-1] == pending.calling_intention:
                                intention_stack.append(intention)
                                return

                    new_intention_stack = collections.deque()
                    new_intention_stack.append(intention)
                    self.intentions.append(new_intention_stack)
                    return

        # Step 6: no plan fit -- still let the caller carry on if it was
        # waiting.
        self._clear_pending_waiter(pending.calling_intention)

        # Step 7: an achievement goal with no plan that fits is treated
        # as a real error (matching what a plain !goal with no matching
        # plan should do); any other kind of event (mostly belief
        # changes) with no reactive plan simply has nothing happen.
        if pending.goal_type == agentspeak.GoalType.achievement:
            raise AslError(
                "no applicable plan for %s%s%s/%d"
                % (pending.trigger.value, pending.goal_type.value, frozen.functor, len(frozen.args))
            )
        # Belief events (and anything else that reaches here) with no
        # matching reactive plan are simply dropped -- same as the old
        # inline fallback for anything that wasn't an achievement or test
        # goal.

    @staticmethod
    def _clear_pending_waiter(calling_intention):
        # Implemented by Enric Hernandez-Minaya, May-Aug 2026
        # Step 1: only clear a waiter this event queue itself put there
        # (tagged "pending-event" back in Agent.call) -- never touch a
        # different kind of waiter (like an ordinary .wait) that just
        # happens to be sitting on the same task right now.
        waiter = calling_intention.waiter
        if waiter is not None and getattr(waiter, "reason", None) == "pending-event":
            calling_intention.waiter = None

    def _unachieve(self, term):
        """
            Unachieve is a performative that allows the agent to remove and stop an achievement to another agent.

            Only searches self.intentions, deliberately: a same-named goal
            that is still only a pending, uncommitted event in self.events
            (see PendingEvent) is untouched by a -!goal arriving before it
            was ever committed -- a known, accepted scope limit, not fixed
            here (see stdlib.py's .drop_event for cancelling those).
        """
        # Step 1: this only makes sense for a real term (a goal name),
        # not a variable or number.
        if not agentspeak.is_literal(term):
                raise AslError("expected literal term")

        # Step 2: look through every running task-stack; if the task
        # currently on top of a stack matches this goal (same name, and
        # `unifies` -- a plain yes/no version of unify, without keeping
        # any bindings -- says its arguments line up), drop it from its
        # stack.
        # Remove a intention passed by the parameters.
        for intention_stack in self.intentions:
            if not intention_stack:
                continue

            intention = intention_stack[-1]

            if intention.head_term.functor == term.functor:
                if agentspeak.unifies(term.args, intention.head_term.args):
                    intention_stack.remove(intention)

    def _tell_how(self, term):
        """
            tellHow is a performative that allows the agent to add a plan to another agent.
        """
        # Step 1: the incoming plan arrives as one big string of
        # AgentSpeak source -- lex (tokenize) it first.
        str_plan = term.args[0]

        tokens = []
        # extend tokens with the tokens of the string plan
        tokens.extend(agentspeak.lexer.tokenize(agentspeak.StringSource("<stdin>", str_plan), agentspeak.Log(LOGGER), 1))

        # Step 2: peel off the first token (should be @, + or -, the
        # start of a plan) and parse the rest into an AST plan (the
        # tree form the parser produces, not yet the runtime Plan form).
        # Prepare the conversion from tokens to AstPlan
        first_token = tokens[0]
        log = agentspeak.Log(LOGGER)
        tokens.pop(0)
        tokens = iter(tokens)

        # Converts the list of tokens to an Astplan
        if first_token.lexeme in ["@", "+", "-"]:
            tok, ast_plan = agentspeak.parser.parse_plan(first_token, tokens, log)
            if tok.lexeme != ".":
                raise log.error("", tok, "expected end of plan")

        # Step 3: convert that parsed AST plan into a real, compiled
        # Plan object -- head term, condition query (or "true" if there
        # was none), and body compiled into an instruction chain -- all
        # sharing the same variable map, so the same variable name means
        # the same thing throughout the plan.
        # Prepare the conversion of Astplan to Plan
        variables = {}
        actions = agentspeak.stdlib.actions

        head = ast_plan.event.head.accept(BuildTermVisitor(variables))

        if ast_plan.context:
            context = ast_plan.context.accept(BuildQueryVisitor(variables, actions, log))
        else:
            context = TrueQuery()

        body = Instruction(noop)
        body.f = noop
        if ast_plan.body:
            ast_plan.body.accept(BuildInstructionsVisitor(variables, actions, body, log))

        # Step 4: assemble the finished Plan and add it to the plan
        # library, exactly like a plan loaded from a source file would be.
        # Converts the Astplan to Plan

        plan = Plan(ast_plan.event.trigger, ast_plan.event.goal_type, head, context, body, ast_plan.body, ast_plan.annotation)

        plan.args = [str(i) for i in ast_plan.event.head.terms] + [str(j) for i in ast_plan.event.head.annotations for j in i.terms]

        self.add_plan(plan)

    def _call_ask_how(self, receiver, message, intention):
        # Step 1: deliver the requested plan to the receiver as a
        # tellHow message.
        receiver.call(agentspeak.Trigger.addition, agentspeak.GoalType.tellHow, message, intention)

    def _ask_how(self, term):
        """
            AskHow is a performative that allows the agent to ask for a plan to another agent.
            We look in the plan.list of the slave agent for the plan that master wants,
            if we find it: master agent use tellHow to tell the plan to slave agent
        """
        sender_name = None

        # Step 1: work out who's asking, from the message's own
        # "source(...)" annotation.
        # Receive the agent that ask for the plan
        for annotation in list(term.annots):
            if(annotation.functor == "source"):
                sender_name = annotation.args[0].functor

        if sender_name is None:
            raise AslError("expected source annotation")

        # Step 2: collect every plan in this agent's own library whose
        # name matches what was asked for, grouped the same way the
        # plan library itself is grouped.
        plans_wanted = collections.defaultdict(lambda: [])
        plans = self.plans.values()
        for plan in plans:
            for differents in plan:
                if differents.head.functor in term.args[0]:
                    plans_wanted[(differents.trigger, differents.goal_type, differents.head.functor, len(differents.head.args))].append(differents)

        # Step 3: if any matching plan(s) were found, send each one
        # (rendered back to plain text) to whoever asked; otherwise log
        # that nothing matched.
        # If the agent has any plan that match with the plan wanted, then the agent will send the plan to the agent that asked
        if plans_wanted:
            intention = agentspeak.runtime.Intention()
            receivers = agentspeak.grounded(sender_name, intention)
            if not agentspeak.is_list(receivers):
                receivers = [receivers]
            receiving_agents = []
            for receiver in receivers:
                if agentspeak.is_atom(receiver):
                    receiving_agents.append(self.env.agents[receiver.functor])
                else:
                    receiving_agents.append(self.env.agents[receiver])

            for plan in plans_wanted.values():
                for differents in plan:
                    strplan = plan_to_str(differents)
                    message = agentspeak.Literal("plain_text", (strplan,), frozenset())
                for receiver in receiving_agents:
                    self._call_ask_how(receiver, message, intention)
        else:
            log = agentspeak.Log(LOGGER)
            raise log.warning(f"The agent not know the plan {term.args[2]}")

    def _untell_how(self, term):
        """
            UntellHow is a performative that allows the agent to remove a plan to another agent.
        """
        # Step 1: the message carries the @label of the plan to remove.
        label = term.args[0]

        # Step 2: go through every group in the plan library, collect
        # (without modifying the list mid-scan) every plan whose @label
        # matches, then remove them all afterwards.

        plans = self.plans.values()
        for plan in plans:
            plans_to_delete = []
            for plan_instance in plan:
                if plan_instance.annotation:
                    if ("@" + str(plan_instance.annotation.functor)) == label:
                        plans_to_delete.append(plan_instance)

            for plan_instance in plans_to_delete:
                plan.remove(plan_instance)


    def add_belief(self, term, scope):
        # Step 1: fully resolve the term under the given scope -- a
        # belief has to be a concrete, fully-known value, not something
        # still containing unbound variables.
        term = term.grounded(scope)

        if term.functor is None:
            raise AslError("expected belief literal")

        # Step 2: add it to the belief set for its (name,
        # number-of-arguments) group. Beliefs live in a Python set, so
        # adding the exact same belief twice is harmless -- it just
        # stays a single entry.
        self.beliefs[(term.functor, len(term.args))].add(term)

    def test_belief(self, term, intention):
        # Step 1: evaluate the term and make sure it's a real term, not
        # some other kind of value.
        term = agentspeak.evaluate(term, intention.scope)

        if not isinstance(term, agentspeak.Literal):
            raise AslError("expected belief literal, got: '%s'" % term)

        # Step 2: run it as an ordinary query and just check whether at
        # least one answer exists -- `next(...)` pulls the very first
        # solution, and if there isn't one, Python raises StopIteration,
        # which is caught and turned into a plain False. The caller only
        # needs a yes/no here, not the actual bindings.
        query = TermQuery(term)

        try:
            next(query.execute(self, intention))
            return True
        except StopIteration:
            return False

    def remove_belief(self, term, intention):
        # Step 1: evaluate the term and get its (name,
        # number-of-arguments) group key.
        term = agentspeak.evaluate(term, intention.scope)

        try:
            group = term.literal_group()
        except AttributeError:
            raise AslError("expected belief literal, got: '%s'" % term)

        choicepoint = object()

        # Step 2: try each belief stored in that group in turn. As soon
        # as one actually unifies (Prolog-style matching, binding
        # whatever's still unbound in `term`) with a real stored belief,
        # remove that belief and report success right away. If a
        # particular belief DOESN'T match, `reroll` undoes any partial
        # bindings that attempt made before moving on to the next one --
        # a failed match shouldn't leave stray bindings behind.
        relevant_beliefs = self.beliefs[group]
        for belief in relevant_beliefs:
            intention.stack.append(choicepoint)
            if agentspeak.unifies_annotated(term, belief, intention.scope, intention.stack):
                relevant_beliefs.remove(belief)
                return True
            agentspeak.reroll(intention.scope, intention.stack, choicepoint)

        return False

    def waiters(self):
        # Step 1: collect the Waiter (if any) of whichever task is
        # currently on top of each non-empty task-stack.
        return (intention[-1].waiter for intention in self.intentions
                if intention and intention[-1].waiter)

    def shortest_deadline(self):
        # Step 1: out of every task that's waiting for a specific point
        # in time, find the soonest one -- so a caller driving this
        # agent (e.g. Environment.run_agent) knows exactly how long it
        # can safely sleep before there's work to do again.
        deadlines = [waiter.until for waiter in self.waiters() if waiter.until is not None]
        if deadlines:
            return min(deadlines)

    def select_event(self):
        """Jason's pluggable SelEv. Default: FIFO (oldest raised first) --
        identical to this fork's prior, non-pluggable commit-phase
        behavior. Override in an Agent subclass (pass as agent_cls=... to
        Environment.build_agent/build_agent_from_ast/build_agents -- an
        existing, correctly-plumbed extension point already used to
        construct every Agent, just never previously exercised with a
        non-default value) for a custom policy: priority by annotation,
        goal type, or any agent-specific heuristic.

        Contract: must actually remove and return the chosen PendingEvent
        from self.events (or leave the queue untouched and return None to
        skip a commit this cycle) -- not just peek. No leading underscore,
        unlike this class's other internal helpers (_commit_event,
        _clear_pending_waiter, ...): this one is meant to be overridden
        from outside the module.
        """
        # Implemented by Enric Hernandez-Minaya, May-Aug 2026
        # Step 1: default behaviour -- just pop the oldest waiting
        # event, or None if the queue is currently empty.
        if not self.events:
            return None
        return self.events.popleft()

    def step(self):
        # Implemented by Enric Hernandez-Minaya, May-Aug 2026
        # Step 1 (event-handling phase): pick and handle at most one
        # waiting event this cycle. This happens interleaved with the
        # instruction-running phase below -- one event handled, one
        # instruction run, each time step() is called -- matching
        # Jason's own rhythm rather than reacting to every event
        # instantly and synchronously. Any error while handling the
        # event is reported through the same logging path used for
        # errors further down, so both phases fail the same way.
        # Commit phase: select and commit at most one pending event this
        # cycle -- interleaved with the execution phase below, matching
        # Jason's own SelEv-then-SelInt reasoning cycle (one event
        # selected, one intention stepped, each pass) rather than this
        # fork's previous immediate, synchronous dispatch.
        committed_event = False
        pending = self.select_event()
        if pending is not None:
            try:
                self._commit_event(pending)
            except AslError as err:
                log = agentspeak.Log(LOGGER)
                raise log.error("%s", err)
            except Exception as err:
                log = agentspeak.Log(LOGGER)
                raise log.exception(
                    "agent %r raised python exception while committing event %r: %r",
                    self.name, str(pending), err)
            committed_event = True

        # Step 2 (instruction-running phase, baseline behaviour):
        # first, drop any task-stacks at the front that have gone
        # completely empty. Then find the first stack whose top task is
        # actually ready to run right now -- a task with no waiter, or
        # one whose waiter's deadline has just passed, is ready; a task
        # still genuinely blocked gets skipped in favor of checking the
        # next stack. If nothing at all is ready, this cycle only did
        # the event-handling above (if anything).
        while self.intentions and not self.intentions[0]:
            self.intentions.popleft()

        for intention_stack in self.intentions:
            # Check if the intention has no length
            if not intention_stack:
                continue

            intention = intention_stack[-1]

            # Suspended / waiting.
            if intention.waiter is not None:
                if intention.waiter.poll(self.env):
                    intention.waiter = None
                else:
                    continue

            break
        else:
            return committed_event

        # Ignore if the intentiosn stack is empty
        if not intention_stack:
            return committed_event

        instr = intention.instr

        # Step 3: a task with no next instruction has finished running
        # its plan's body -- pop it off its stack. If that leaves the
        # stack empty, drop the stack entirely; otherwise, "return" this
        # finished task's own result back to whichever task called it
        # (now on top of the stack) by unifying what it was waiting on
        # against this task's own (now frozen) triggering term.
        if not instr:
            intention_stack.pop()
            if not intention_stack:
                self.intentions.remove(intention_stack)
            elif intention.calling_term:
                frozen = intention.head_term.freeze(intention.scope, {})
                calling_intention = intention_stack[-1]
                if not agentspeak.unify(intention.calling_term, frozen, calling_intention.scope, calling_intention.stack):
                    raise RuntimeError("back unification failed")
            return True

        # Step 4: otherwise, run exactly one compiled instruction and
        # follow its success or failure link depending on the result. A
        # plan running out of both instructions AND a failure branch to
        # fall back to counts as the plan failing outright. Any Python
        # exception the instruction itself raises gets wrapped with
        # where in the source file it came from, so the error message
        # actually points somewhere useful.
        try:
            if instr.f(self, intention):
                intention.instr = instr.success
            else:
                intention.instr = instr.failure
                if not intention.instr:
                    raise AslError("plan failure")
        except AslError as err:
            log = agentspeak.Log(LOGGER)
            raise log.error("%s", err, loc=instr.loc, extra_locs=instr.extra_locs)
        except Exception as err:
            log = agentspeak.Log(LOGGER)
            raise log.exception("agent %r raised python exception: %r", self.name, err,
                                loc=instr.loc, extra_locs=instr.extra_locs)

        return True

    def run(self):
        # Step 1: just keep calling step() until a whole cycle does
        # nothing at all (no event handled, no instruction run).
        while self.step():
            pass


def plan_to_str(plan):
    """
    This function recieves a plan and return the plan as string
    """
    # Step 1: a plan with no explicit condition renders its condition
    # as the word "true"; otherwise render the condition query itself.
    if isinstance(plan.context, type(TrueQuery())):
        context = "true"
    else:
        context = plan.context

    # Step 2: the body's text form was already prepared ahead of time.
    body = plan.str_body

    # Step 3: if the plan's head has arguments, its stored text form
    # has placeholder tokens where the real argument values go --
    # regex-substitute them back in, one at a time, from plan.args
    # (note: this eats items out of plan.args as it goes, so calling
    # this twice on the same plan would run out of substitutions).
    if len(plan.head.args):
        pattern = r"_X_[0-9a-fA-F]{3}_[0-9a-fA-F]+"
        head = re.sub(pattern, lambda m: plan.args.pop(0), str(plan.head))  # fill in each placeholder with the next real argument
    else:
        head = str(plan.head)

    # Step 4: put it all back together as one AgentSpeak source line,
    # with the @label prefix if the plan has one.
    if plan.annotation:
        label = str(plan.annotation)
    else:
        label = ""
        return  f"{plan.trigger.value}{plan.goal_type.value}{head} : {context} <- {body}."

    return f"@{label} {plan.trigger.value}{plan.goal_type.value}{head} : {context} <- {body}."


class Environment:
    """Holds a group of named Agents and drives them forward. Each
    BDIAgent (in the separate spade_bdi package) builds its own private
    Environment, which is why .broadcast/.send only ever reach other
    agents built through that same Environment, not every agent on the
    whole platform."""
    def __init__(self):
        # Step 1: agents maps each agent's name to its Agent object.
        self.agents = {}

    def _make_name(self, path):
        # Step 1: turn the source file's own base filename into a valid
        # AgentSpeak name; fall back to plain "agent" if that produces
        # nothing usable.
        base_name = agentspeak.sanitize_functor(os.path.splitext(os.path.basename(path))[0])
        if not base_name:
            base_name = "agent"
        # Step 2: if that name is already taken, keep adding a number
        # until it isn't.
        name = base_name
        i = 1
        while name in self.agents:
            name = base_name + str(i)
            i += 1
        return name

    def build_agent_from_ast(self, source, ast_agent, actions, agent_cls=Agent, name=None):
        # This function is also called by the optimizer.

        # Step 1: create the new agent object, naming it either from
        # the given name or the source file's own name.
        log = agentspeak.Log(LOGGER, 3)
        agent = agent_cls(self, self._make_name(name or source.name))

        # Step 2: compile every parsed rule and register it.
        # Add rules to agent prototype.
        for ast_rule in ast_agent.rules:
            variables = {}
            head = ast_rule.head.accept(BuildTermVisitor(variables))
            consequence = ast_rule.consequence.accept(BuildQueryVisitor(variables, actions, log))
            agent.add_rule(Rule(head, consequence))

        # Step 3: compile every parsed plan (head, condition, body) --
        # same conversion _tell_how does for a plan received at run
        # time, just here for every plan written directly in the file.
        # Add plans to agent prototype.
        for ast_plan in ast_agent.plans:
            variables = {}

            head = ast_plan.event.head.accept(BuildTermVisitor(variables))

            if ast_plan.context:
                context = ast_plan.context.accept(BuildQueryVisitor(variables, actions, log))
            else:
                context = TrueQuery()

            body = Instruction(noop)
            body.f = noop
            if ast_plan.body:
                ast_plan.body.accept(BuildInstructionsVisitor(variables, actions, body, log))

            str_body = str(ast_plan.body)

            plan = Plan(ast_plan.event.trigger, ast_plan.event.goal_type, head, context, body, ast_plan.body, ast_plan.annotation)

            plan.args = [str(i) for i in ast_plan.event.head.terms] + [str(j) for i in ast_plan.event.head.annotations for j in i.terms]



            agent.add_plan(plan)

        # Step 4: every initial belief written in the file (a plain
        # "Bel." line, before any plan) is added the same way any other
        # belief change would be -- through agent.call, as a delayed
        # (fire-and-forget) belief-addition event -- so a plan reacting
        # to it fires through the normal event queue, no special-casing
        # needed here.
        # Add beliefs to agent prototype.
        for ast_belief in ast_agent.beliefs:
            belief = ast_belief.accept(BuildTermVisitor({}))
            agent.call(agentspeak.Trigger.addition, agentspeak.GoalType.belief,
                       belief, Intention(), delayed=True)

        # Step 5: every initial goal ("!goal." line) is likewise raised
        # as a delayed achievement event, in the order they're written
        # in the file, before this function returns the finished agent.
        # Call initial goals on agent prototype.
        for ast_goal in ast_agent.goals:
            term = ast_goal.atom.accept(BuildTermVisitor({}))
            agent.call(agentspeak.Trigger.addition, agentspeak.GoalType.achievement,
                       term, Intention(), delayed=True)

        # Step 6: now that the whole agent has been built, raise
        # anything that went wrong along the way (parse errors, unknown
        # actions, etc.) as a proper error.
        # Report errors.
        log.throw()

        self.agents[agent.name] = agent
        return ast_agent, agent

    def _build_agent(self, source, actions, agent_cls=Agent, name=None):
        # Step 1: lex and parse the raw source text into an AST agent.
        # Parse source.
        log = agentspeak.Log(LOGGER, 3)
        tokens = agentspeak.lexer.TokenStream(source, log)
        ast_agent = agentspeak.parser.parse(source.name, tokens, log)
        log.throw()

        # Step 2: hand it off to build_agent_from_ast to do the actual
        # compiling.
        return self.build_agent_from_ast(source, ast_agent, actions, agent_cls, name)

    def build_agent(self, source, actions, agent_cls=Agent, name=None):
        # Step 1: build one agent and return just the agent (the parsed
        # AST is only needed internally, for build_agents' reuse trick
        # below).
        _, agent = self._build_agent(source, actions, agent_cls, name)
        return agent

    def build_agents(self, source, n, actions, agent_cls=Agent, name=None):
        # Step 1: asking for zero or fewer agents is a no-op.
        if n <= 0:
            return []

        # Step 2: build one real "prototype" agent the normal way,
        # parsing and compiling the source from scratch.
        ast_agent, prototype_agent = self._build_agent(source, actions, agent_cls=agent_cls)

        # Create more instances from the prototype, but with their own
        # callstacks. This is more efficient than making complete deep copies.
        agents = [prototype_agent]

        # Step 3: every further agent reuses the prototype's own
        # already-compiled beliefs/rules/plans (a shallow copy each, so
        # every agent gets its own independent container without
        # re-parsing the whole source file again) but naturally starts
        # with its own fresh, empty running-tasks/events, then re-raises
        # the same initial goals for itself.
        while len(agents) < n:
            agent = agent_cls(self, self._make_name(name or source.name),
                copy.copy(prototype_agent.beliefs),
                copy.copy(prototype_agent.rules),
                copy.copy(prototype_agent.plans))

            for ast_goal in ast_agent.goals:
                term = ast_goal.atom.accept(BuildTermVisitor({}))
                agent.call(agentspeak.Trigger.addition, agentspeak.GoalType.achievement,
                           term, Intention(), delayed=True)

            agents.append(agent)
            self.agents[agent.name] = agent

        return agents

    def time(self):
        # Step 1: this Environment's own idea of "now" -- everything
        # else in this file (deadlines, .wait, .at) is built on top of
        # this single clock reference.
        return time.time()

    def run_agent(self, agent):
        # Step 1: keep stepping this one agent for as long as it's
        # doing something; the moment a cycle does nothing at all, sleep
        # exactly until its very next deadline (instead of spinning in a
        # busy loop checking over and over) before trying again.
        more_work = True
        while more_work:
            more_work = agent.step()

            if not more_work:
                # Sleep until the next deadline.
                wait_until = agent.shortest_deadline()
                if wait_until:
                    time.sleep(wait_until - self.time())
                    more_work = True

    def run(self):
        # Step 1: give every registered agent one turn (one step()
        # call) per pass, and keep passing as long as any of them are
        # still doing something.
        maybe_more_work = True
        while maybe_more_work:
            maybe_more_work = False
            for agent in self.agents.values():
                if agent.step():
                    maybe_more_work = True

            # Step 2: once a whole pass does nothing for any agent,
            # sleep exactly until the earliest deadline across ALL
            # agents (not busy-looping) before trying again.
            if not maybe_more_work:
                deadlines = (agent.shortest_deadline() for agent in self.agents.values())
                deadlines = [deadline for deadline in deadlines if deadline is not None]
                if deadlines:
                    time.sleep(min(deadlines) - self.time())
                    maybe_more_work = True

    def shutdown(self):
        # Step 1: exit the whole process outright.
        sys.exit(1)


def noop(agent, intention):
    # Step 1: does literally nothing except always "succeed" -- used as
    # the placeholder first instruction every plan body starts from
    # before its real instructions get chained on (see
    # BuildInstructionsVisitor below), and as the empty else-branch of
    # an if/then with no else.
    return True


# The functions below are the actual pieces of code a compiled plan
# body runs, one at a time, one per reasoning cycle (see Agent.step:
# "instr.f(self, intention)"). Each one returns True or False to say
# whether the NEXT instruction to run should be the "success" link or
# the "failure" link. BuildInstructionsVisitor, further down, is what
# strings a parsed plan body together into a chain of these.

def add_belief(term, agent, intention):
    # Step 1: a "+belief" line in a plan body -- raise it as a real
    # belief-addition event through the agent's own call()/event-queue
    # machinery, same as any other event.
    return agent.call(agentspeak.Trigger.addition, agentspeak.GoalType.belief, term, intention)


def remove_belief(term, agent, intention):
    # Step 1: a "-belief" line -- raise a belief-removal event.
    return agent.call(agentspeak.Trigger.removal, agentspeak.GoalType.belief, term, intention)


def test_belief(term, agent, intention):
    # Step 1: a "?belief" line -- raise a test-goal event (handled
    # immediately by Agent.call, never queued/deferred).
    return agent.call(agentspeak.Trigger.addition, agentspeak.GoalType.test, term, intention)


def call(trigger, goal_type, term, agent, intention):
    # Step 1: a plain "!goal" line (not delayed) -- the calling task
    # will pause (via the pending-event waiter) until this event is
    # actually picked up and handled.
    return agent.call(trigger, goal_type, term, intention, delayed=False)


def call_delayed(trigger, goal_type, term, agent, intention):
    # Step 1: a "!!goal" line (fire-and-forget) -- the calling task
    # does NOT wait around for this one to be handled.
    return agent.call(trigger, goal_type, term, intention, delayed=True)


def push_query(query, agent, intention):
    # Step 1: start running a Query's own generator and stash it on
    # query_stack, so next_or_fail can pull one solution out of it at a
    # time, across separate reasoning cycles, instead of all at once.
    intention.query_stack.append(query.execute(agent, intention))
    return True


def next_or_fail(agent, intention):
    # Step 1: pull the next solution out of whatever query is currently
    # on top of query_stack. Succeeds if one came out; once the query
    # runs dry (raises StopIteration, Python's normal "no more items"
    # signal), that's treated as failure -- there's nothing left to try.
    try:
        next(intention.query_stack[-1])
        return True
    except StopIteration:
        return False


def pop_query(agent, intention):
    # Step 1: done with whatever query is on top -- discard it.
    intention.query_stack.pop()
    return True


def push_choicepoint(agent, intention):
    # Step 1: mark a fresh backtracking point. The same marker object
    # goes on both choicepoint_stack (so pop_choicepoint later knows
    # exactly which point to undo back to) and the task's own
    # binding-undo stack.
    choicepoint = object()
    intention.choicepoint_stack.append(choicepoint)
    intention.stack.append(choicepoint)
    return True


def pop_choicepoint(agent, intention):
    # Step 1: undo every variable binding made since the matching
    # push_choicepoint -- this is what makes a "while" loop start each
    # new pass with a clean slate instead of piling up bindings from
    # every earlier pass.
    choicepoint = intention.choicepoint_stack.pop()
    agentspeak.reroll(intention.scope, intention.stack, choicepoint)
    return True


class Instruction:
    """One link in a compiled plan body's chain: a Python function (f)
    to call, plus two pointers (success/failure) to whichever
    Instruction comes next depending on whether f returned True or
    False. A whole plan body ends up as a linked graph of these,
    walked one node at a time -- one node per reasoning cycle -- by
    Agent.step."""
    def __init__(self, f, loc=None, extra_locs=()):
        # Step 1: f is what actually runs; success/failure links get
        # filled in afterwards, as the chain is being built by
        # BuildInstructionsVisitor; loc/extra_locs remember where in
        # the source file this came from, for error messages.
        self.f = f
        self.success = None
        self.failure = None
        self.loc = loc
        self.extra_locs = extra_locs

    def __repr__(self):
        # Step 1: show both links by their Python object id (or "0" if
        # not set yet) -- useful for debug dumps like .control_flow.
        success = hex(id(self.success)) if self.success is not None else "0"
        failure = hex(id(self.failure)) if self.failure is not None else "0"
        return "<Instruction %s: %r %s %s>" % (hex(id(self)), self.f, success, failure)


class BuildInstructionsVisitor:
    """Walks a parsed plan body (a sequence of formulas, plus
    if/then/else, for-loops, and while-loops) and compiles it into a
    chain of Instruction nodes. Builds onto an existing "tail"
    Instruction (either the plan's own placeholder starting point, or
    wherever a surrounding if/for/while construct left off), so nested
    control-flow can be compiled piece by piece."""
    def __init__(self, variables, actions, tail, log):
        # Step 1: variables/actions/log get passed along to every
        # BuildTermVisitor/BuildQueryVisitor this visitor creates along
        # the way; tail is the current end of the instruction chain
        # being built.
        self.variables = variables
        self.actions = actions
        self.tail = tail
        self.log = log

    def add_instr(self, f, loc=None, extra_locs=()):
        # Step 1: append a new Instruction right after the current tail
        # (always on its success link -- the chain being built here is
        # a straight line unless something below branches it) and move
        # tail forward to the new node.
        self.tail.success = Instruction(f, loc, extra_locs)
        self.tail = self.tail.success
        return self.tail

    def visit_formula(self, ast_formula):
        # Step 1: each kind of plan-body line compiles down to a small,
        # fixed handful of Instruction nodes. functools.partial here
        # just pre-fills in the specific term/query each instruction
        # function needs, so it can be called later with just
        # (agent, intention).
        if ast_formula.formula_type == agentspeak.FormulaType.add:
            # +belief
            term = ast_formula.term.accept(BuildTermVisitor(self.variables))
            self.add_instr(functools.partial(add_belief, term),
                           loc=ast_formula.loc, extra_locs=[ast_formula.term.loc])
        elif ast_formula.formula_type == agentspeak.FormulaType.remove:
            # -belief
            term = ast_formula.term.accept(BuildTermVisitor(self.variables))
            self.add_instr(functools.partial(remove_belief, term))
        elif ast_formula.formula_type == agentspeak.FormulaType.test:
            # ?belief
            term = ast_formula.term.accept(BuildTermVisitor(self.variables))
            self.add_instr(functools.partial(test_belief, term),
                           loc=ast_formula.loc, extra_locs=[ast_formula.term.loc])
        elif ast_formula.formula_type == agentspeak.FormulaType.replace:
            # -+belief: first remove anything matching the head (using
            # a wildcarded version, via BuildReplacePatternVisitor, so
            # only the name/argument-count need match, not the exact
            # values), then add the new belief.
            removal_term = ast_formula.term.accept(BuildReplacePatternVisitor())
            self.add_instr(functools.partial(remove_belief, removal_term))

            term = ast_formula.term.accept(BuildTermVisitor(self.variables))
            self.add_instr(functools.partial(add_belief, term),
                           loc=ast_formula.loc, extra_locs=[ast_formula.term.loc])
        elif ast_formula.formula_type == agentspeak.FormulaType.achieve:
            # !goal
            term = ast_formula.term.accept(BuildTermVisitor(self.variables))
            self.add_instr(functools.partial(call, agentspeak.Trigger.addition, agentspeak.GoalType.achievement, term),
                           loc=ast_formula.loc, extra_locs=[ast_formula.term.loc])
        elif ast_formula.formula_type == agentspeak.FormulaType.achieve_later:
            # !!goal
            term = ast_formula.term.accept(BuildTermVisitor(self.variables))
            self.add_instr(functools.partial(call_delayed, agentspeak.Trigger.addition, agentspeak.GoalType.achievement, term),
                           loc=ast_formula.loc, extra_locs=[ast_formula.term.loc])
        elif ast_formula.formula_type == agentspeak.FormulaType.term:
            # A bare call/query used as a plan-body line on its own
            # (e.g. .print(...)): push the query, pull exactly one
            # solution from it (the whole line fails if there isn't
            # one), then pop it back off again.
            query = ast_formula.term.accept(BuildQueryVisitor(self.variables, self.actions, self.log))
            self.add_instr(functools.partial(push_query, query))
            self.add_instr(next_or_fail, loc=ast_formula.term.loc)
            self.add_instr(pop_query)

        return self.tail

    def visit_for(self, ast_for):
        # Step 1: push the loop's generator query, then keep pulling
        # solutions from it one at a time (for_head). Each time a
        # solution comes out, run the loop body once, then loop back to
        # for_head to pull the next one.
        query = ast_for.generator.accept(BuildQueryVisitor(self.variables, self.actions, self.log))
        self.add_instr(functools.partial(push_query, query))

        for_head = self.add_instr(next_or_fail)

        last_in_loop = ast_for.body.accept(self)
        last_in_loop.success = for_head

        # Step 2: once the generator has nothing left (for_head fails),
        # pop the query and move on to whatever comes after the loop.
        self.tail = Instruction(pop_query)
        for_head.failure = self.tail
        return self.tail

    def visit_if_then_else(self, ast_if_then_else):
        # Step 1: push the condition and pull (at most) one solution.
        query = ast_if_then_else.condition.accept(BuildQueryVisitor(self.variables, self.actions, self.log))
        self.add_instr(functools.partial(push_query, query))
        test_instr = self.add_instr(next_or_fail)

        tail = Instruction(pop_query)

        # Step 2: if the condition succeeded, run the "then" part (if
        # there is one) and rejoin at the shared tail (which pops the
        # condition query).
        if ast_if_then_else.if_body:
            if_tail = ast_if_then_else.if_body.accept(self)
            if_tail.success = tail
        else:
            test_instr.success = tail

        # Step 3: if the condition failed, run the "else" part (if
        # there is one, starting from a fresh do-nothing head) and
        # rejoin at the same tail; with no else at all, failure goes
        # straight to the tail.
        if ast_if_then_else.else_body:
            else_head = Instruction(noop)
            test_instr.failure = else_head
            self.tail = else_head
            ast_if_then_else.else_body.accept(self)
            self.tail.success = tail
        else:
            test_instr.failure = tail

        self.tail = tail
        return self.tail

    def visit_while(self, ast_while):
        # Step 1: tail is where control ends up once the loop condition
        # finally fails for good.
        tail = Instruction(pop_choicepoint)

        # Step 2: each pass through the loop pushes the condition query
        # fresh (while_head), marks a choicepoint (so anything bound
        # while testing/running this pass can be undone before the
        # next), then pulls one solution -- if that fails, the loop
        # exits via tail.
        query = ast_while.condition.accept(BuildQueryVisitor(self.variables, self.actions, self.log))
        while_head = self.add_instr(functools.partial(push_query, query))
        self.add_instr(push_choicepoint)

        test_instr = self.add_instr(next_or_fail)
        test_instr.failure = tail

        self.add_instr(pop_query)

        # Step 3: if the condition held, run the loop body, then undo
        # this pass's bindings (pop_choicepoint) and jump back to
        # while_head to try again.
        ast_while.body.accept(self)
        while_tail = self.add_instr(pop_choicepoint)
        while_tail.success = while_head

        # Step 4: tail itself still needs to pop the (now exhausted)
        # condition query before whatever comes after the loop can run.
        self.tail = tail
        return self.add_instr(pop_query)

    def visit_body(self, ast_body):
        # Step 1: compile each line of the plan body in order, each one
        # appending onto the chain being built so far.
        for formula in ast_body.formulas:
            formula.accept(self)

        return self.tail


def dump_variables(variables, scope):
    # Step 1: for every named variable seen while compiling the last
    # thing typed in the REPL, print its current value if it actually
    # got bound to something; otherwise, remember it as still unbound.
    not_in_scope = []

    for name, variable in sorted(variables.items()):
        if variable in scope:
            print("%s = %s" % (name, asl_str(agentspeak.deref(variable, scope))))
        else:
            not_in_scope.append("%s = %s" % (name, variable))

    # Step 2: list all the still-unbound ones together on one line.
    if not_in_scope:
        print("%d unbound: %s" % (len(not_in_scope), ", ".join(not_in_scope)))


def repl(agent, env, actions):
    """An interactive prompt: keeps asking for AgentSpeak plan-body
    lines, compiles and runs each one as a new task on the given agent,
    then prints out whatever the variables ended up bound to. This is
    what main() drops into when it's run without a script file."""
    lineno = 0
    tokens = []

    # Step 1: use one fresh Environment/variables/Intention for the
    # whole session, reused across everything typed.
    env = Environment()
    variables = {}
    intention = Intention()

    while True:
        try:
            log = agentspeak.Log(LOGGER, 3)

            # Step 2: ask for a line of input -- a different prompt is
            # shown when continuing a statement that isn't finished yet
            # (leftover tokens from the previous line). Ctrl-C exits
            # cleanly.
            try:
                if not tokens:
                    line = agentspeak.util.prompt("%s >>> " % agent.name)
                else:
                    line = agentspeak.util.prompt("%s ... " % agent.name)
            except KeyboardInterrupt:
                print()
                sys.exit(0)

            lineno += 1

            tokens.extend(agentspeak.lexer.tokenize(agentspeak.StringSource("<stdin>", line), log, lineno))

            # Step 3: try to parse as many complete plan-body
            # statements as possible out of what's been typed so far;
            # an incomplete one (Python's StopIteration signal) just
            # waits quietly for more input on the next prompt.
            while tokens:
                token_stream = iter(tokens)
                try:
                    tok = next(token_stream)
                    tok, body = agentspeak.parser.parse_plan_body(tok, token_stream, log)
                except StopIteration:
                    log.throw()
                    break
                else:
                    log.throw()
                    tokens = list(token_stream)

                    # Step 4: compile what was typed into a fresh
                    # instruction chain, run it as a task on the agent
                    # until it's done, then show what the variables
                    # ended up as.
                    intention.instr = Instruction(noop)
                    body.accept(BuildInstructionsVisitor(variables, actions, intention.instr, log))
                    log.throw()
                    agent.intentions.append(collections.deque([intention]))
                    env.run_agent(agent)
                    dump_variables(variables, intention.scope)
        except agentspeak.AggregatedError as error:
            # Step 5: something went wrong parsing/compiling -- report
            # it and throw away whatever was typed so far so the next
            # prompt starts clean.
            print(str(error), file=sys.stderr)
            tokens = []
        except agentspeak.AslError as error:
            LOGGER.error("%s", error)
            tokens = []


def main(post_repl=True):
    """The command-line entry point: run a given .asl file (or read
    from stdin) to completion, then optionally drop into the
    interactive REPL above for further poking around."""
    import agentspeak.ext_stdlib
    env = Environment()
    try:
        # Step 1: given a file argument, build and run that agent, then
        # optionally continue into the REPL (only the first file
        # argument is ever actually used -- the loop always stops after
        # one).
        args = sys.argv[1:]
        if args:
            for arg in args:
                with open(arg) as source:
                    agent = env.build_agent(source, agentspeak.ext_stdlib.actions)
                    env.run_agent(agent)
                    if post_repl:
                        repl(agent, env, agentspeak.ext_stdlib.actions)
                    break
        elif sys.stdin.isatty():
            # Step 2: no file given, and this is a real interactive
            # terminal -- jump straight into the REPL with a brand new,
            # empty agent.
            agent = Agent(env, "stdin")
            repl(agent, env, agentspeak.ext_stdlib.actions)
        else:
            # Step 3: no file given, and input is piped in from
            # somewhere -- treat that piped input itself as the agent's
            # source and just run it (no REPL, since there's no real
            # terminal to interact through).
            env.run_agent(env.build_agent(sys.stdin, agentspeak.ext_stdlib.actions))
    except agentspeak.AggregatedError as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
    except agentspeak.AslError as error:
        LOGGER.error("%s", error)
        sys.exit(1)


if __name__ == "__main__":
    main()
