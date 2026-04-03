from __future__ import annotations

from dataclasses import dataclass, field
from typing import List
from uuid import uuid4


@dataclass
class Goal:
    title: str
    priority: int = 50
    status: str = "pending"
    completion_criteria: list[str] = field(default_factory=list)
    goal_id: str = field(default_factory=lambda: str(uuid4()))


class GoalEngine:
    def __init__(self) -> None:
        self._goals: List[Goal] = []

    def add_goal(self, title: str, priority: int = 50, completion_criteria: list[str] | None = None) -> Goal:
        goal = Goal(title=title, priority=priority, completion_criteria=completion_criteria or [])
        self._goals.append(goal)
        self._goals.sort(key=lambda g: g.priority, reverse=True)
        return goal

    def current_goal(self) -> Goal | None:
        return next((g for g in self._goals if g.status == "pending"), None)

    def complete_goal(self, goal_id: str) -> None:
        for goal in self._goals:
            if goal.goal_id == goal_id:
                goal.status = "complete"
                break

    def all_goals(self) -> list[Goal]:
        return list(self._goals)
