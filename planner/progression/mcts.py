import random
import math
import numpy

from collections import defaultdict
from planner.state_space import test_goal, test_parent_operator, StateSpace, Solution, Plan
from misc.numerical import INF
from misc.functions import randomize
from misc.priority_queue import FIFOClassicPriorityQueue, FILOClassicPriorityQueue, FIFOPriorityQueue, FILOPriorityQueue


def random_policy(current_vertex):
    current_vertex.generate_all()
    if not current_vertex.outgoing_edges:
        return None # current_vertex
    edge = random.choice(current_vertex.outgoing_edges)
    return edge

def greedy_policy(current_vertex, weight=1, shuffle=True):
    # TODO: function that returns the policy
    # TODO: use evaluators
    current_vertex.generate_all()
    edges = current_vertex.outgoing_edges
    if not edges:
        return None
    for edge in edges:
        edge.sink.generate_all() # To compute h_cost
    if shuffle:
        edges = randomize(edges)
    return min(edges, key=lambda e: e.cost + weight*e.sink.h_cost)

##################################################

def random_walk(start, goal, generator, _=None, policy=greedy_policy, debug=None, **kwargs):
    space = StateSpace(generator, start, max_extensions=INF, **kwargs)
    current_vertex = space.root
    edge_path = []
    while space.is_active(): # TODO: max_length
        current_vertex.generate_all()
        space.new_iteration(current_vertex)
        if debug is not None:
            debug(current_vertex)
        if test_goal(current_vertex, goal):
            operator_path = [edge.operator for edge in edge_path]
            plan = Plan(start, operator_path)
            return Solution(plan, space)
            #return space.solution(current_vertex)
        edge = policy(current_vertex)
        if edge is None:
            break
        edge_path.append(edge)
        current_vertex = edge.sink
    return space.failure()

##################################################

def uct(total_cost, num, parent, c=math.sqrt(2)):
    # https://en.wikipedia.org/wiki/Monte_Carlo_tree_search
    return float(total_cost) / num + c*math.sqrt(math.log(parent) / num)

class TreeNode(object):
    def __init__(self, vertex, parent_edge=None, parent_node=None):
        self.vertex = vertex
        self.parent_edge = parent_edge
        self.parent_node = parent_node
        self.rollouts = []
        self.children = []
        if self.parent_node is not None:
            self.parent_node.children.append(self)
    def is_leaf(self):
        return not bool(self.children)
    def get_estimate(self):
        if not self.rollouts:
            return INF
        return numpy.average(self.rollouts)
    def ancestors(self):
        if self.parent_node is None:
            return []
        return self.parent_node.ancestors() + [self.parent_node]
    def descendants(self):
        nodes = [self]
        for child in self.children:
            nodes.extend(child.descendants())
        return nodes

def mcts(start, goal, generator, _=None, debug=None, **kwargs):
    # TODO: dynamic programming instead of tree
    # https://gist.github.com/qpwo/c538c6f73727e254fdc7fab81024f6e1
    # https://github.com/pbsinclair42/MCTS/blob/master/mcts.py
    # https://github.com/int8/monte-carlo-tree-search/blob/master/mctspy/tree/search.py
    space = StateSpace(generator, start, max_extensions=INF, **kwargs)
    # total_costs = defaultdict(float)
    # num_visits = defaultdict(int)

    root = TreeNode(space.root)
    while space.is_active():
        leaves = list(filter(TreeNode.is_leaf, root.descendants()))
        leaf = random.choice(leaves)
        vertex = leaf.vertex
        space.new_iteration(vertex)
        if debug is not None:
            debug(vertex)
        if test_goal(vertex, goal):
            return space.solution(vertex)
        vertex.generate_all()
        for edge in vertex.outgoing_edges:
            new_vertex = edge.sink
            new_vertex.generate_all()
            node = TreeNode(new_vertex, parent_edge=edge, parent_node=leaf)
            rollout = 0
            #rollout = new_vertex.h_cost
            for ancestor in reversed(node.ancestors() + [node]):
                ancestor.rollouts.append(rollout) # TODO: multiple rollouts
                if ancestor.parent_edge is not None:
                    rollout += ancestor.parent_edge.cost
    return space.failure()
