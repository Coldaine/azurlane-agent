from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Any

class Action(BaseModel):
    action_type: str = Field(..., description="Action type: tap, swipe, wait, etc.")
    params: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("action_type")
    @classmethod
    def validate_action_type(cls, value: str) -> str:
        valid_types = {"tap", "swipe", "wait"}
        if value not in valid_types:
            raise ValueError(f"action_type must be one of {valid_types}")
        return value

class Behavior(BaseModel):
    name: str = Field(..., description="Behavior identifier")
    preconditions: List[str] = Field(default_factory=list, description="Required screen states")
    actions: List[Action] = Field(..., description="Ordered list of actions to perform")
    postconditions: List[str] = Field(default_factory=list, description="Expected screen state after completion")
