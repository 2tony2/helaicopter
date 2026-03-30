from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class OltpBase(DeclarativeBase):
    pass


class ProvenanceMixin:
    record_source: Mapped[str | None] = mapped_column(Text)
    source_file_modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    loaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    first_ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_refreshed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RefreshRun(OltpBase):
    __tablename__ = "refresh_runs"

    run_id: Mapped[str] = mapped_column(Text, primary_key=True)
    trigger: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(Text)
    scope_label: Mapped[str | None] = mapped_column(Text)
    window_days: Mapped[int | None] = mapped_column(Integer)
    window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_conversation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)
    conversations_loaded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    messages_loaded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tool_calls_loaded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    plans_loaded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class EvaluationPromptRecord(OltpBase):
    __tablename__ = "evaluation_prompts"
    __table_args__ = (Index("ix_evaluation_prompts_name", "name"),)

    prompt_id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SubscriptionSettingRecord(OltpBase):
    __tablename__ = "subscription_settings"

    provider: Mapped[str] = mapped_column(Text, primary_key=True)
    has_subscription: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    monthly_cost: Mapped[float] = mapped_column(Float, nullable=False, default=200)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ConversationEvaluationRecord(OltpBase):
    __tablename__ = "conversation_evaluations"
    __table_args__ = (
        Index("ix_conversation_evaluations_conversation_id_created_at", "conversation_id", "created_at"),
    )

    evaluation_id: Mapped[str] = mapped_column(Text, primary_key=True)
    conversation_id: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_id: Mapped[str | None] = mapped_column(ForeignKey("evaluation_prompts.prompt_id", ondelete="SET NULL"))
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    selection_instruction: Mapped[str | None] = mapped_column(Text)
    prompt_name: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    report_markdown: Mapped[str | None] = mapped_column(Text)
    raw_output: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    command: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)


class AuthCredentialRecord(OltpBase):
    __tablename__ = "auth_credentials"
    __table_args__ = (
        Index("ix_auth_credentials_provider", "provider"),
        Index("ix_auth_credentials_status", "status"),
    )

    credential_id: Mapped[str] = mapped_column(Text, primary_key=True)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    credential_type: Mapped[str] = mapped_column(Text, nullable=False)
    access_token_encrypted: Mapped[bytes | None] = mapped_column()
    refresh_token_encrypted: Mapped[bytes | None] = mapped_column()
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    oauth_scopes_json: Mapped[str | None] = mapped_column(Text)
    api_key_encrypted: Mapped[bytes | None] = mapped_column()
    cli_config_path: Mapped[str | None] = mapped_column(Text)
    subscription_id: Mapped[str | None] = mapped_column(Text)
    subscription_tier: Mapped[str | None] = mapped_column(Text)
    rate_limit_tier: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_refreshed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cumulative_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cost_since_reset: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)


class ConversationRecord(ProvenanceMixin, OltpBase):
    __tablename__ = "conversations"
    __table_args__ = (
        Index("ix_conversations_provider_started_at", "provider", "started_at"),
        Index("ix_conversations_project_path", "project_path"),
    )

    conversation_id: Mapped[str] = mapped_column(Text, primary_key=True)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    session_id: Mapped[str] = mapped_column(Text, nullable=False)
    project_path: Mapped[str] = mapped_column(Text, nullable=False)
    project_name: Mapped[str] = mapped_column(Text, nullable=False)
    thread_type: Mapped[str] = mapped_column(Text, nullable=False, default="main")
    first_message: Mapped[str] = mapped_column(Text, nullable=False)
    route_slug: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    model: Mapped[str | None] = mapped_column(Text)
    git_branch: Mapped[str | None] = mapped_column(Text)
    reasoning_effort: Mapped[str | None] = mapped_column(Text)
    speed: Mapped[str | None] = mapped_column(Text)
    total_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_cache_write_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_cache_read_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_reasoning_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tool_use_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    subagent_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    task_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_input_cost: Mapped[str | None] = mapped_column(Text)
    estimated_output_cost: Mapped[str | None] = mapped_column(Text)
    estimated_cache_write_cost: Mapped[str | None] = mapped_column(Text)
    estimated_cache_read_cost: Mapped[str | None] = mapped_column(Text)
    estimated_total_cost: Mapped[str | None] = mapped_column(Text)

    messages: Mapped[list["ConversationMessage"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
    )
    plans: Mapped[list["ConversationPlanRecord"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
    )
    subagents: Mapped[list["ConversationSubagentRecord"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
    )
    tasks: Mapped[list["ConversationTaskRecord"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
    )
    context_buckets: Mapped[list["ContextBucketRecord"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
    )
    context_steps: Mapped[list["ContextStepRecord"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
    )


class ConversationMessage(ProvenanceMixin, OltpBase):
    __tablename__ = "conversation_messages"
    __table_args__ = (
        Index("ix_messages_conversation_id_timestamp", "conversation_id", "timestamp"),
    )

    message_id: Mapped[str] = mapped_column(Text, primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.conversation_id", ondelete="CASCADE"),
        nullable=False,
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    model: Mapped[str | None] = mapped_column(Text)
    reasoning_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    speed: Mapped[str | None] = mapped_column(Text)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_write_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_read_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    text_preview: Mapped[str] = mapped_column(Text, nullable=False, default="")

    conversation: Mapped[ConversationRecord] = relationship(back_populates="messages")
    blocks: Mapped[list["MessageBlockRecord"]] = relationship(
        back_populates="message",
        cascade="all, delete-orphan",
    )


class MessageBlockRecord(ProvenanceMixin, OltpBase):
    __tablename__ = "message_blocks"
    __table_args__ = (
        Index("ix_message_blocks_message_id", "message_id"),
    )

    block_id: Mapped[str] = mapped_column(Text, primary_key=True)
    message_id: Mapped[str] = mapped_column(
        ForeignKey("conversation_messages.message_id", ondelete="CASCADE"),
        nullable=False,
    )
    block_index: Mapped[int] = mapped_column(Integer, nullable=False)
    block_type: Mapped[str] = mapped_column(Text, nullable=False)
    text_content: Mapped[str | None] = mapped_column(Text)
    tool_use_id: Mapped[str | None] = mapped_column(Text)
    tool_name: Mapped[str | None] = mapped_column(Text)
    tool_input_json: Mapped[str | None] = mapped_column(Text)
    tool_result_text: Mapped[str | None] = mapped_column(Text)
    is_error: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    message: Mapped[ConversationMessage] = relationship(back_populates="blocks")


class ConversationPlanRecord(ProvenanceMixin, OltpBase):
    __tablename__ = "conversation_plans"
    __table_args__ = (Index("ix_plans_conversation_id_timestamp", "conversation_id", "timestamp"),)

    plan_row_id: Mapped[str] = mapped_column(Text, primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.conversation_id", ondelete="CASCADE"),
        nullable=False,
    )
    plan_id: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    preview: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    model: Mapped[str | None] = mapped_column(Text)
    explanation: Mapped[str | None] = mapped_column(Text)
    steps_json: Mapped[str | None] = mapped_column(Text)

    conversation: Mapped[ConversationRecord] = relationship(back_populates="plans")


class ConversationSubagentRecord(ProvenanceMixin, OltpBase):
    __tablename__ = "conversation_subagents"
    __table_args__ = (Index("ix_subagents_conversation_id", "conversation_id"),)

    subagent_row_id: Mapped[str] = mapped_column(Text, primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.conversation_id", ondelete="CASCADE"),
        nullable=False,
    )
    agent_id: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    subagent_type: Mapped[str | None] = mapped_column(Text)
    nickname: Mapped[str | None] = mapped_column(Text)
    has_file: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    conversation: Mapped[ConversationRecord] = relationship(back_populates="subagents")


class ConversationTaskRecord(ProvenanceMixin, OltpBase):
    __tablename__ = "conversation_tasks"
    __table_args__ = (Index("ix_tasks_conversation_id", "conversation_id"),)

    task_row_id: Mapped[str] = mapped_column(Text, primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.conversation_id", ondelete="CASCADE"),
        nullable=False,
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    task_json: Mapped[str] = mapped_column(Text, nullable=False)

    conversation: Mapped[ConversationRecord] = relationship(back_populates="tasks")


class ContextBucketRecord(ProvenanceMixin, OltpBase):
    __tablename__ = "context_buckets"
    __table_args__ = (Index("ix_context_buckets_conversation_id", "conversation_id"),)

    bucket_row_id: Mapped[str] = mapped_column(Text, primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.conversation_id", ondelete="CASCADE"),
        nullable=False,
    )
    label: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_write_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_read_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    conversation: Mapped[ConversationRecord] = relationship(back_populates="context_buckets")


class ContextStepRecord(ProvenanceMixin, OltpBase):
    __tablename__ = "context_steps"
    __table_args__ = (Index("ix_context_steps_conversation_id_timestamp", "conversation_id", "timestamp"),)

    step_row_id: Mapped[str] = mapped_column(Text, primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.conversation_id", ondelete="CASCADE"),
        nullable=False,
    )
    message_id: Mapped[str] = mapped_column(Text, nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_write_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_read_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    conversation: Mapped[ConversationRecord] = relationship(back_populates="context_steps")
