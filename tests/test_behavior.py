import pytest
from pydantic import ValidationError
from tools.behavior.schema import Action, Behavior

def test_action_schema_validation():
    # Valid tap action
    action = Action(action_type="tap", params={"x": 100, "y": 200})
    assert action.action_type == "tap"
    assert action.params == {"x": 100, "y": 200}
    
    # Valid wait action
    action = Action(action_type="wait", params={"duration": 1.5})
    assert action.action_type == "wait"
    
    # Invalid action type
    with pytest.raises(ValueError):
        Action(action_type="unknown")

def test_behavior_schema_validation():
    b = Behavior(
        name="test_behavior",
        preconditions=["screen_menu"],
        actions=[Action(action_type="tap", params={"x": 50, "y": 50})],
        postconditions=["screen_combat"]
    )
    assert b.name == "test_behavior"
    assert "screen_menu" in b.preconditions
    assert "screen_combat" in b.postconditions
    assert len(b.actions) == 1
    
    # Missing required fields should raise ValidationError
    with pytest.raises(ValidationError):
        Behavior(name="no_actions")
