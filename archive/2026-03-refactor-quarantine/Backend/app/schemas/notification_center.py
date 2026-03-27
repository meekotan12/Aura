from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class NotificationOut(BaseModel):
    id: int
    user_id: int
    school_id: int
    title: str
    message: str
    type: str
    related_id: Optional[int] = None
    is_read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationListResponse(BaseModel):
    unread_count: int
    items: list[NotificationOut]


class NotificationMarkReadRequest(BaseModel):
    ids: list[int] = Field(default_factory=list, min_length=1)
