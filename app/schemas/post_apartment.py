from ..models.post_sale_apartment import BuildingMaterial, Repair
from .post import Post


class PostApartment(Post):
    rooms: int | None = None
    floor: int | None = None
    total_floor: int | None = None
    total_area_sqm: float | None = None
    total_price: int | None = None
    is_new_building: bool | None = None
    has_furniture: bool | None = None
    repair: Repair | None = None
    building_material: BuildingMaterial | None = None
