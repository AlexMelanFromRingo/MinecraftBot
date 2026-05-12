"""Behaviour-tree module.

Re-exports the core node primitives + action factories so callers can
``from minecraft_bot.behaviour import Selector, Sequence, WalkTo``.
"""

from minecraft_bot.behaviour.nodes import (
    Action, AlwaysSucceed, BehaviourNode, BehaviourRunner, Condition,
    Inverter, NodeStatus, Repeat, RepeatUntilFail, Selector, Sequence, Wait,
)
from minecraft_bot.behaviour.actions import (
    AttackNearest, Command, DropItem, EatWhenHungry, FollowPlayer,
    HasItem, IsHealthBelow, IsHungryBelow, Say, WalkTo,
)

__all__ = [
    # Primitives
    "NodeStatus", "BehaviourNode", "BehaviourRunner",
    "Selector", "Sequence",
    "Inverter", "AlwaysSucceed", "RepeatUntilFail", "Repeat", "Wait",
    "Condition", "Action",
    # Actions
    "WalkTo", "FollowPlayer", "AttackNearest", "EatWhenHungry",
    "DropItem", "Say", "Command",
    # Conditions
    "IsHungryBelow", "IsHealthBelow", "HasItem",
]
