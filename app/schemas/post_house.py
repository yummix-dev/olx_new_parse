from pydantic import BaseModel

from ..models.post_sale_apartment import BuildingMaterial, Repair
from ..models.post_sale_house import HouseType


class PostHouse(BaseModel):
    rooms: int | None
    total_floor: int | None
    total_area_sqm: int | None
    land_area_sqm: int | None
    total_price: int | None
    has_furniture: bool | None
    building_material: BuildingMaterial | None
    repair: Repair | None
    house_type: HouseType | None
