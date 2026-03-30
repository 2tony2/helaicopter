from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class OlapBase(DeclarativeBase):
    pass


class DimDate(OlapBase):
    __tablename__ = "dim_dates"

    date_key: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    calendar_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    day: Mapped[int] = mapped_column(Integer, nullable=False)
    iso_week: Mapped[int] = mapped_column(Integer, nullable=False)
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)


class DimProject(OlapBase):
    __tablename__ = "dim_projects"

    project_id: Mapped[str] = mapped_column(Text, primary_key=True)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    project_path: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    project_name: Mapped[str] = mapped_column(Text, nullable=False)


class DimModel(OlapBase):
    __tablename__ = "dim_models"

    model_id: Mapped[str] = mapped_column(Text, primary_key=True)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    model_name: Mapped[str] = mapped_column(Text, nullable=False)


class DimTool(OlapBase):
    __tablename__ = "dim_tools"

    tool_id: Mapped[str] = mapped_column(Text, primary_key=True)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    tool_name: Mapped[str] = mapped_column(Text, nullable=False)


class DimSubagentType(OlapBase):
    __tablename__ = "dim_subagent_types"

    subagent_type_id: Mapped[str] = mapped_column(Text, primary_key=True)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    subagent_type: Mapped[str] = mapped_column(Text, nullable=False)


class FactConversation(OlapBase):
    __tablename__ = "fact_conversations"

    conversation_id: Mapped[str] = mapped_column(Text, primary_key=True)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    session_id: Mapped[str] = mapped_column(Text, nullable=False)
    project_id: Mapped[str] = mapped_column(ForeignKey("dim_projects.project_id"), nullable=False)
    model_id: Mapped[str | None] = mapped_column(ForeignKey("dim_models.model_id"))
    started_date_key: Mapped[int] = mapped_column(ForeignKey("dim_dates.date_key"), nullable=False)
    ended_date_key: Mapped[int] = mapped_column(ForeignKey("dim_dates.date_key"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    first_message: Mapped[str] = mapped_column(Text, nullable=False)
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_cache_write_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_cache_read_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_reasoning_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tool_use_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    subagent_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    task_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_total_cost: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False, default=0)
    estimated_input_cost: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False, default=0)
    estimated_output_cost: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False, default=0)
    estimated_cache_write_cost: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False, default=0)
    estimated_cache_read_cost: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False, default=0)


class FactDailyUsage(OlapBase):
    __tablename__ = "fact_daily_usage"

    daily_usage_id: Mapped[str] = mapped_column(Text, primary_key=True)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    date_key: Mapped[int] = mapped_column(ForeignKey("dim_dates.date_key"), nullable=False)
    model_id: Mapped[str | None] = mapped_column(ForeignKey("dim_models.model_id"))
    conversation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_write_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_read_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reasoning_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tool_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_total_cost: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False, default=0)


class FactToolUsage(OlapBase):
    __tablename__ = "fact_tool_usage"

    tool_usage_id: Mapped[str] = mapped_column(Text, primary_key=True)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    date_key: Mapped[int] = mapped_column(ForeignKey("dim_dates.date_key"), nullable=False)
    project_id: Mapped[str] = mapped_column(ForeignKey("dim_projects.project_id"), nullable=False)
    tool_id: Mapped[str] = mapped_column(ForeignKey("dim_tools.tool_id"), nullable=False)
    conversation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tool_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class FactSubagentUsage(OlapBase):
    __tablename__ = "fact_subagent_usage"

    subagent_usage_id: Mapped[str] = mapped_column(Text, primary_key=True)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    date_key: Mapped[int] = mapped_column(ForeignKey("dim_dates.date_key"), nullable=False)
    project_id: Mapped[str] = mapped_column(ForeignKey("dim_projects.project_id"), nullable=False)
    subagent_type_id: Mapped[str] = mapped_column(
        ForeignKey("dim_subagent_types.subagent_type_id"),
        nullable=False,
    )
    conversation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    subagent_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

