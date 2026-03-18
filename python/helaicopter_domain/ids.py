"""Nominal identifiers reused across backend boundaries."""

from typing import NewType

AgentId = NewType("AgentId", str)
ConversationId = NewType("ConversationId", str)
EvaluationId = NewType("EvaluationId", str)
ModelId = NewType("ModelId", str)
PlanId = NewType("PlanId", str)
ProjectId = NewType("ProjectId", str)
PromptId = NewType("PromptId", str)
RunId = NewType("RunId", str)
SessionId = NewType("SessionId", str)
SubagentTypeId = NewType("SubagentTypeId", str)
TaskId = NewType("TaskId", str)
ToolId = NewType("ToolId", str)

__all__ = [
    "AgentId",
    "ConversationId",
    "EvaluationId",
    "ModelId",
    "PlanId",
    "ProjectId",
    "PromptId",
    "RunId",
    "SessionId",
    "SubagentTypeId",
    "TaskId",
    "ToolId",
]
