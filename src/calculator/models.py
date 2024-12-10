from dataclasses import dataclass


@dataclass
class Action:

    source: int
    target: int


class Suspicion(Action):

    breaking_weght = 0.2
    strength = 0.2


class StrongSuspicion(Action):
    breaking_weght = 0.3
    strength = 0.3


class Voted(Action):
    breaking_weght = 0.6
    strength = 0.6


class RequestedCheck(Action):
    breaking_weght = 0.8
    strength = 0.5


class CheckedBlack(Action):
    breaking_weght = 0.9
    strength = 1


class CheckedRed(Action):
    breaking_weght = 0
    strength = 1


class Other(Action):
    breaking_weght = 0.8
    strength = 0


"""
Graph calculator

We have a fully connected graph of 10 verticies when each node is connected with every other node 
with certain percentage number.
All connections are started with 1 and then modified in our program.
Goad is to write calculator that will calculate all possible triplets of that graph ordered by 
possible edge weight.

Another operation is to print all possible triplets same way but removing specific node from that 
sorting.

For example we have graph where 
edges are:
AB = 1
AC = 1
BC = 0.5

then if we want to print possible pairs in that graph we will print those in this order:
AB,AC, BC

We just need to extrapolate it for triplets based on edges.
Idea is that when cetrain edge is close to 0 all triplets incliding that edge should be listed 
after other having higher multiplied probability. So for example in graph of ABCDEFGHIJ when AB 
is 0.1 and BC is 0.1 ABC should have lowest probability to appear.

"""
