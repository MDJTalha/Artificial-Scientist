"""Phase 11: bounded specialist delegation and conflict handling."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CollaborationError(ValueError):
    """Raised when collaboration exceeds a declared boundary."""


class TaskState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CONFLICT = "conflict"


@dataclass(frozen=True)
class AgentRole:
    name: str
    specialty: str
    max_tasks: int = 5


@dataclass
class AgentTask:
    task_id: str
    role: str
    budget: int
    state: TaskState = TaskState.PENDING
    result: str | None = None


class CollaborationEngine:
    def __init__(self, roles: list[AgentRole]):
        if not roles or len(roles) > 32:
            raise CollaborationError("bounded role set required")
        self.roles = {role.name: role for role in roles}
        self.tasks: dict[str, AgentTask] = {}

    def delegate(self, task_id: str, role: str, *, budget: int) -> AgentTask:
        if task_id in self.tasks or role not in self.roles:
            raise CollaborationError("invalid delegation")
        if budget < 1 or budget > 100:
            raise CollaborationError("invalid resource budget")
        if sum(task.role == role for task in self.tasks.values()) >= self.roles[role].max_tasks:
            raise CollaborationError("role budget exhausted")
        task = AgentTask(task_id, role, budget, TaskState.RUNNING)
        self.tasks[task_id] = task
        return task

    def complete(self, task_id: str, result: str) -> AgentTask:
        task = self.tasks[task_id]
        if not result or len(result) > 10000:
            raise CollaborationError("bounded result required")
        task.result = result
        task.state = TaskState.DONE
        return task

    def resolve(self, task_ids: list[str], decision: str) -> str:
        if len(task_ids) < 2 or any(
            self.tasks[task_id].state is not TaskState.DONE for task_id in task_ids
        ):
            raise CollaborationError("independent completed results required")
        if not decision or len(decision) > 10000:
            raise CollaborationError("bounded resolution required")
        for task_id in task_ids:
            task = self.tasks[task_id]
            task.state = TaskState.DONE if task.result == decision else TaskState.CONFLICT
        return decision
