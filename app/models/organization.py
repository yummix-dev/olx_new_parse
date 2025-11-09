import enum
from typing import TYPE_CHECKING
from sqlalchemy import BIGINT, Enum, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base

if TYPE_CHECKING:
    from .post import Post


class Platform(str, enum.Enum):
    OLX = "olx"
    UYBOR = "uybor"
    TELEGRAM = "telegram"


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    platform: Mapped[Platform] = mapped_column(Enum(Platform, values_callable=lambda x: [i.value for i in x]))
    is_broker: Mapped[bool] = mapped_column(default=False)
    url: Mapped[str | None] = mapped_column(VARCHAR(255))
    code: Mapped[str | None] = mapped_column(VARCHAR(255))

    # Relationship
    posts: Mapped[list["Post"]] = relationship(back_populates="organization")
