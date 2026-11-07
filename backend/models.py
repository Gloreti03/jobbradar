"""Tabelle SQLite (BLUEPRINT sez. 5). Chi le cambia lo dice nel gruppo (owner: Gabriele).

Le colonne JSON contengono i dict dei modelli in schemas.py
(es. profiles.data = Profile, applications.cv = TailoredCV).
Nota: non ci sono migrazioni → se cambia una tabella, cancellare radar.db
e ricaricare gli annunci con `scripts/scan.py --load-seed`.
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ProfileRow(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON)
    extra_text: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class JobRow(Base):
    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("source", "source_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(32), index=True)
    source_id: Mapped[str] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(500))
    company: Mapped[str | None] = mapped_column(String(255))
    location: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str] = mapped_column(String(1000))
    apply_url: Mapped[str | None] = mapped_column(String(1000))
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    language: Mapped[str | None] = mapped_column(String(2))
    norwegian_required: Mapped[bool | None] = mapped_column(Boolean)


class MatchRow(Base):
    __tablename__ = "matches"

    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"), primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), primary_key=True)
    score: Mapped[int] = mapped_column(Integer)
    verdict: Mapped[str] = mapped_column(String(16))
    reasons: Mapped[list[str]] = mapped_column(JSON, default=list)
    gaps: Mapped[list[str]] = mapped_column(JSON, default=list)
    to_clarify: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ApplicationRow(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    language: Mapped[str] = mapped_column(String(2), default="en")
    cv: Mapped[dict[str, Any]] = mapped_column(JSON)
    cover_letter: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class InterviewRow(Base):
    __tablename__ = "interviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), index=True)
    mode: Mapped[str] = mapped_column(String(8), default="text")
    plan: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    transcript: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    feedback: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
