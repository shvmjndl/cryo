import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from api.core.database import Base


class Upload(Base):
    __tablename__ = "uploads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # File metadata
    original_filename: Mapped[str] = mapped_column(String, nullable=False)
    stored_filename: Mapped[str] = mapped_column(String, nullable=False)      # uuid_originalname on disk
    server_path: Mapped[str] = mapped_column(Text, nullable=False)            # full path inside container
    file_size: Mapped[int] = mapped_column(BigInteger, default=0)             # bytes
    mime_type: Mapped[str | None] = mapped_column(String, nullable=True)
    file_ext: Mapped[str | None] = mapped_column(String, nullable=True)       # .csv, .h5ad, .bam …

    # Classification — what kind of data file is this
    data_type: Mapped[str | None] = mapped_column(String, nullable=True)      # rnaseq_counts, scrna, bam, fastq, ms_proteomics, sec, other
    suggested_command: Mapped[str | None] = mapped_column(String, nullable=True)  # /deseq, /scrna, /atac …

    # Usage tracking
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True)
    times_used: Mapped[int] = mapped_column(BigInteger, default=0)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Extra metadata (checksum, tags, notes)
    meta: Mapped[dict] = mapped_column(JSONB, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
