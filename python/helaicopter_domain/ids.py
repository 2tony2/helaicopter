"""Nominal identifiers reused across backend boundaries."""

from typing import NewType

AgentId = NewType("AgentId", str)
ConversationId = NewType("ConversationId", str)
ConversationMessageId = NewType("ConversationMessageId", str)
ConversationMessageBlockId = NewType("ConversationMessageBlockId", str)
ConversationPlanRowId = NewType("ConversationPlanRowId", str)
ConversationSubagentRowId = NewType("ConversationSubagentRowId", str)
ConversationTaskRowId = NewType("ConversationTaskRowId", str)
ConversationContextBucketId = NewType("ConversationContextBucketId", str)
ConversationContextStepId = NewType("ConversationContextStepId", str)
EvaluationId = NewType("EvaluationId", str)
ModelId = NewType("ModelId", str)
PlanId = NewType("PlanId", str)
PrefectDeploymentId = NewType("PrefectDeploymentId", str)
PrefectFlowRunId = NewType("PrefectFlowRunId", str)
PrefectWorkPoolId = NewType("PrefectWorkPoolId", str)
PrefectWorkerId = NewType("PrefectWorkerId", str)
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
    "ConversationMessageId",
    "ConversationMessageBlockId",
    "ConversationPlanRowId",
    "ConversationSubagentRowId",
    "ConversationTaskRowId",
    "ConversationContextBucketId",
    "ConversationContextStepId",
    "EvaluationId",
    "ModelId",
    "PlanId",
    "PrefectDeploymentId",
    "PrefectFlowRunId",
    "PrefectWorkPoolId",
    "PrefectWorkerId",
    "ProjectId",
    "PromptId",
    "RunId",
    "SessionId",
    "SubagentTypeId",
    "TaskId",
    "ToolId",
]
