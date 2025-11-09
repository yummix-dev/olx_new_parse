from typing import TYPE_CHECKING

from sqlalchemy import CHAR, SMALLINT, BIGINT, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .post_sale_apartment import Repair, BuildingMaterial

if TYPE_CHECKING:
    from models import Post


class PostRentApartment(Base):
    __tablename__ = "post_rent_apartments"
    post_id: Mapped[str] = mapped_column(CHAR(32), ForeignKey("posts.id"), primary_key=True)
    rooms: Mapped[int | None] = mapped_column(SMALLINT)
    floor: Mapped[int | None] = mapped_column(SMALLINT)
    total_floor: Mapped[int | None] = mapped_column(SMALLINT)
    total_area_sqm: Mapped[int | None] = mapped_column(BIGINT)
    total_price: Mapped[int | None] = mapped_column(BIGINT)
    is_new_building: Mapped[bool | None]
    has_furniture: Mapped[bool | None]
    repair: Mapped[Repair | None] = mapped_column(Enum(Repair, values_callable=lambda x: [i.value for i in x]))
    building_material: Mapped[BuildingMaterial | None] = mapped_column(
        Enum(BuildingMaterial, values_callable=lambda x: [i.value for i in x])
    )

    # Relationship
    post: Mapped["Post"] = relationship(back_populates="rent_apartment")
