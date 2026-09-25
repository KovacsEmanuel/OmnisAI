"""Persistent singleton guarding future instance admissions."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, SmallInteger, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class InstanceControl(Base):
    __tablename__ = "instance_control"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_instance_control_singleton"),
        CheckConstraint("generation >= 0", name="ck_instance_control_generation"),
    )

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    instance_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, unique=True, server_default=text("gen_random_uuid()")
    )
    admission_open: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    shutdown_command_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    generation: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    quiesced_generation: Mapped[int | None] = mapped_column(BigInteger)
    quiesced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
