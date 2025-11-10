import enum
from typing import TYPE_CHECKING

from sqlalchemy import CHAR, BIGINT, SMALLINT, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .post_sale_apartment import Repair


class Purpose(str, enum.Enum):
    shop = "магазины/бутики"
    recreation_base = "базы отдыха"
    salon = "салоны"
    industrial = "помещения промышленного назначения"
    restaurant_cafe_bar = "рестораны/кафе/бары"
    free_purpose = "помещения свободного назначения"
    office = "офисы"
    small_architectural_form = "маф (малая архитектурная форма)"
    warehouse = "склады"
    part_of_building = "часть здания"
    standalone_building = "отдельно стоящее здание"
    uninhabitable = "нежилое помещение"
    other = "другое"


if TYPE_CHECKING:
    from models import Post


class PostSaleCommerce(Base):
    __tablename__ = "post_sale_commerces"
    post_id: Mapped[str] = mapped_column(CHAR(32), ForeignKey("posts.id"), primary_key=True)
    rooms: Mapped[int | None] = mapped_column(SMALLINT)
    floor: Mapped[int | None] = mapped_column(SMALLINT)
    total_floor: Mapped[int | None] = mapped_column(SMALLINT)
    total_area_sqm: Mapped[int | None] = mapped_column(BIGINT)
    land_area_sqm: Mapped[int | None] = mapped_column(BIGINT)
    total_price: Mapped[int | None] = mapped_column(BIGINT)
    has_furniture: Mapped[bool | None]
    repair: Mapped[Repair | None] = mapped_column(Enum(Repair, values_callable=lambda x: [i.value for i in x]))
    purpose: Mapped[Purpose | None] = mapped_column(Enum(Purpose, values_callable=lambda x: [i.value for i in x]))

    # Relationship
    post: Mapped["Post"] = relationship(back_populates="sale_commerce")
