from pydantic import BaseModel
from models.post import Source, Status, TypeOfProperty, TypeOfService


class Post(BaseModel):
    type_of_service: TypeOfService
    type_of_property: TypeOfProperty
    url: str
    title: str
    description: str
    source: Source = Source.OLX
    status: Status = Status.ACTIVE
    organization_url: str
    external_id: str
    phone_number: str | None = None
    polygon_id: int
    organization_id: int
    is_broker: bool = False
