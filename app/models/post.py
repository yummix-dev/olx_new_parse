import enum
import uuid
from datetime import datetime, UTC
from typing import TYPE_CHECKING

from sqlalchemy import CHAR, TEXT, Enum, BIGINT, VARCHAR, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship, selectinload

from .base import Base

if TYPE_CHECKING:
    from models import (
        PostSaleApartment,
        PostSaleCommerce,
        PostSaleHouse,
        PostRentApartment,
        PostRentCommerce,
        PostRentHouse,
        Organization,
    )


class TypeOfService(str, enum.Enum):
    RENT = "rent"
    SALE = "sale"


class TypeOfProperty(str, enum.Enum):
    APARTMENT = "apartment"
    COMMERCE = "commerce"
    HOUSE = "house"


class Source(str, enum.Enum):
    OLX = "olx"
    UYBOR = "uybor"
    TELEGRAM = "telegram"


class Status(str, enum.Enum):
    ACTIVE = "active"
    VERIFIED = "verified"


class Post(Base):
    __tablename__ = "posts"
    id: Mapped[str] = mapped_column(CHAR(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    type_of_property: Mapped[TypeOfProperty] = mapped_column(
        Enum(TypeOfProperty, values_callable=lambda x: [i.value for i in x])
    )
    type_of_service: Mapped[TypeOfService] = mapped_column(
        Enum(TypeOfService, values_callable=lambda x: [i.value for i in x])
    )
    url: Mapped[str] = mapped_column(TEXT)
    title: Mapped[str] = mapped_column(TEXT)
    description: Mapped[str] = mapped_column(TEXT)
    source: Mapped[Source] = mapped_column(Enum(Source, values_callable=lambda x: [i.value for i in x]))
    status: Mapped[Status] = mapped_column(
        Enum(Status, values_callable=lambda x: [i.value for i in x]), default=Status.ACTIVE
    )
    external_id: Mapped[str] = mapped_column(VARCHAR(20))
    phone_number: Mapped[str | None] = mapped_column(VARCHAR(20), default=None)
    polygon_id: Mapped[int | None] = mapped_column(BIGINT, default=None)
    organization_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("organizations.id"))
    is_broker: Mapped[bool]
    added_at: Mapped[datetime] = mapped_column(default=datetime.now(UTC), server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.now(UTC), server_default=func.current_timestamp(), onupdate=func.current_timestamp()
    )

    # Relationship
    sale_apartment: Mapped["PostSaleApartment"] = relationship(back_populates="post")
    sale_commerce: Mapped["PostSaleCommerce"] = relationship(back_populates="post")
    sale_house: Mapped["PostSaleHouse"] = relationship(back_populates="post")
    rent_apartment: Mapped["PostRentApartment"] = relationship(back_populates="post")
    rent_commerce: Mapped["PostRentCommerce"] = relationship(back_populates="post")
    rent_house: Mapped["PostRentHouse"] = relationship(back_populates="post")
    organization: Mapped["Organization"] = relationship(back_populates="posts")

    @classmethod
    def get_options(cls):
        return (
            selectinload(cls.sale_apartment),
            selectinload(cls.sale_commerce),
            selectinload(cls.sale_house),
            selectinload(cls.rent_apartment),
            selectinload(cls.rent_commerce),
            selectinload(cls.rent_house),
            selectinload(cls.organization),
        )
