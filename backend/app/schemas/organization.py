import uuid

from app.schemas.common import ORMBase


class OrganizationResponse(ORMBase):
    id: uuid.UUID
    name: str
