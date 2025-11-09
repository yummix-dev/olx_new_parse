from pydantic import BaseModel

from app.models.post_sale_apartment import Repair
from app.models.post_sale_commerce import Purpose


class PostCommerce(BaseModel):
    rooms: int | None
    floor: int | None
    total_floor: int | None
    total_area_sqm: int | None
    land_area_sqm: int | None
    total_price: int | None
    has_furniture: bool | None
    repair: Repair | None
    purpose: Purpose | None
