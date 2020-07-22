from .operators import *
from misc.functions import elapsed_time
import time

# TODO - can rewire state-space if found a better parent

class Plan(object):
  def __init__(self, start, operators):
    self.start = start
    self.operators = operators
  @property
  def cost(self):
    if not self.operators:
      return 0
    return sum(operator.cost for operator in self.operators)
  @property
  def length(self):
    return len(self.operators)
  def __iter__(self):
    return iter(self.operators)
  def get_states(self):
    states = [self.start]
    for operator in self.operators:
      #assert states[-1] in operator
      #states.append(operator(states[-1]))
      states.append(operator.apply(states[-1]))
    return states
  def get_derived_states(self, axioms):
    states = [self.start]
    derived_state, axiom_plan = derive_predicates(states[-1], axioms)
    derived_states = [derived_state]
    axiom_plans = [axiom_plan]
    for operator in self.operators:
      assert derived_states[-1] in operator
      states.append(operator.apply(states[-1]))
      derived_state, axiom_plan = derive_predicates(states[-1], axioms)
      derived_states.append(derived_state)
      axiom_plans.append(axiom_plan)
    return derived_states, axiom_plans
  def __str__(self):
    s = '{name} | Cost: {self.cost} | Length {self.length}'.format(name=self.__class__.__name__, self=self)
    for i, operator in enumerate(self.operators):
      s += str_line('\n\n%d | '%(i+1), operator)
    return s
  __repr__ = __str__

#################################################################

class Vertex(object):
  def __init__(self, state, state_space):
    self.state = state
    self.derived_state, self.axiom_plan = derive_predicates(state, state_space.axioms)
    self.state_space = state_space
    self.incoming_edges = []
    self.outgoing_edges = []
    self.cost = INF
    self.length = INF
    self.parent_edge = None
    self.extensions = 0
    self.generations = 0
    self.generator = state_space.generator_fn(self)
    self.explored = 0
    self.h_cost = None
  def contained(self, partial_state):
    #return self.state in partial_state
    return self.derived_state in partial_state
  def enumerated(self):
    return (self.generator is None) or (self.state_space.max_generations <= self.generations)
  def is_dead_end(self):
    assert self.h_cost is not None
    h = self.h_cost[0] if isinstance(self.h_cost, tuple) else self.h_cost
    return h == INF
  def generate(self):
    if not self.enumerated():
      try:
        self.h_cost, operators = next(self.generator)
        self.generations += 1
        if not self.is_dead_end():
          for operator in operators: # TODO - should states be expanded before the heuristic check?
            self.state_space.extend(self, operator)
          return True # TODO - decide if to return true if still some unexplored (despite nothing new generated)
      except StopIteration:
        self.generator = None
    return False # TODO: change the semantics of this to be generated at least one new
  def has_unexplored(self):
    return self.explored < len(self.outgoing_edges)
  def unexplored(self):
    while self.has_unexplored():
      self.explored += 1
      yield self.outgoing_edges[self.explored-1].sink
  def disconnect(self):
    assert self.parent_edge is not None
    self.state_space.pop(self.state)
    self.state_space.edges.remove(self.parent_edge)
  def __str__(self):
    #return '{}({})'.format(self.__class__.__name__, id(self))
    return 'h_cost: {self.h_cost} | cost: {self.cost} | length: {self.length} | ' \
           'generations: {self.generations} | unexplored: {unexplored}\n{self.state}'.format(
      self=self, unexplored=(len(self.outgoing_edges)-self.explored))
  __repr__ = __str__

# TODO: lazily evaluate the next state
class Edge(object):
  def __init__(self, source, sink, operator):
    self.source = source
    self.sink = sink
    self.operator = operator
    self.source.outgoing_edges.append(self)
    self.sink.incoming_edges.append(self)
    if source.cost + operator.cost < sink.cost:
      sink.cost = source.cost + operator.cost
      sink.length = source.length + len(operator)
      sink.parent_edge = self
  def __str__(self):
    return '{}({})'.format(self.__class__.__name__, self.operator)
  __repr__ = __str__

#################################################################

class StateSpace(object):
  def __init__(self, generator_fn, start, max_extensions, max_generations, max_cost, max_length):
    self.start_time = time.time()
    self.iterations = 0
    self.vertices = {}
    self.edges = [] # NOTE - allowing parallel-edges
    if isinstance(generator_fn, tuple): # TODO - fix this by making the operators a direct argument
      self.generator_fn, self.axioms = generator_fn
    else:
      self.generator_fn, self.axioms = generator_fn, []
    # TODO: could check whether these are violated generically
    self.max_extensions = max_extensions
    self.max_generations = max_generations
    self.max_cost = max_cost
    self.max_length = max_length
    self.root = self[start]
    self.root.cost = 0
    self.root.length = 0
    self.root.extensions += 1
  def has_state(self, state):
    return state in self.vertices
  __contains__ = has_state
  def get_state(self, state):
    if state not in self:
      self.vertices[state] = Vertex(state, self)
    return self.vertices[state]
  __getitem__ = get_state
  def __iter__(self):
    return iter(self.vertices.values())
  def __len__(self):
    return len(self.vertices)
  def extend(self, vertex, operator):
    if (vertex.cost + operator.cost <= self.max_cost) \
            and (vertex.length + len(operator) <= self.max_length) \
            and vertex.contained(operator):
      #if vertex.state in operator:
      if self.axioms:
        assert not isinstance(operator, MacroOperator)
        sink_state = operator.apply(vertex.state) # TODO - this won't work for MacroOperators yet?
      else:
        sink_state = operator(vertex.state)[-1] if isinstance(operator, MacroOperator) else operator(vertex.state)
      if (sink_state is not None) and (self[sink_state].extensions < self.max_extensions):
        sink_vertex = self[sink_state]
        self.edges.append(Edge(vertex, sink_vertex, operator))
        sink_vertex.extensions += 1
        return sink_vertex
    return None
  def retrace(self, vertex):
    if vertex is not None:
      if vertex == self.root:
        return []
      sequence = self.retrace(vertex.parent_edge.source)
      if sequence is not None:
        return sequence + list(vertex.parent_edge.operator)
    return None
  def plan(self, vertex):
    sequence = self.retrace(vertex)
    if sequence is None:
      return None
    return Plan(self.root.state, sequence)
  def time_elapsed(self):
    return elapsed_time(self.start_time)
  def num_expanded(self):
    return sum(1 for v in self if v.generations > 0) # NOTE - can be very expensive for a large state space
  def num_generations(self):
    return sum(v.generations for v in self) # NOTE - can be very expensive for a large state space
  def __repr__(self):
    return 'Iterations: {iterations} | Time: {time} | State Space: {state_space}\n'.format(
      iterations=self.iterations, time=round(self.time_elapsed(), 3), state_space=len(self))
  #def __repr__(self):
  #  return 'Iterations: {iterations} | Time: {time} | State Space: {state_space} | Expanded: {expanded} | ' \
  #        'Generations: {generations}\n'.format(iterations=self.iterations,
  #        time=round(self.time_elapsed(), 3), state_space=len(self),
  #        expanded=self.num_expanded(),
  #        generations=self.num_generations())