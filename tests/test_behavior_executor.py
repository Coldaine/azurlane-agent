import pytest
from tools.behavior.schema import Action, Behavior
from tools.behavior.executor import BehaviorExecutor, BehaviorError

@pytest.fixture
def mock_mcp():
    class MockMCP:
        def __init__(self):
            self.calls = []
            self.screen_state = 'screen_menu'
        def call_tool(self, name, kwargs):
            self.calls.append((name, kwargs))
            if name == 'get_screen_state':
                return {'observed_state': self.screen_state}
            return 'ok'
    return MockMCP()

def test_behavior_executor_runs_actions(mock_mcp):
    b = Behavior(
        name='test_behavior',
        actions=[
            Action(action_type='tap', params={'x': 50, 'y': 60}),
            Action(action_type='wait', params={'duration': 1.0}),
            Action(action_type='swipe', params={'x1': 10, 'y1': 10, 'x2': 20, 'y2': 20})
        ]
    )
    executor = BehaviorExecutor(mcp_client=mock_mcp)
    executor.execute(b)
    
    assert len(mock_mcp.calls) == 3
    assert mock_mcp.calls[0] == ('adb_tap', {'x': 50, 'y': 60})
    assert mock_mcp.calls[1] == ('wait', {'duration': 1.0})
    assert mock_mcp.calls[2] == ('adb_swipe', {'x1': 10, 'y1': 10, 'x2': 20, 'y2': 20})

def test_behavior_chaining(mock_mcp):
    b1 = Behavior(name='b1', actions=[Action(action_type='tap', params={'x': 1, 'y': 1})])
    b2 = Behavior(name='b2', actions=[Action(action_type='tap', params={'x': 2, 'y': 2})])
    
    executor = BehaviorExecutor(mcp_client=mock_mcp)
    executor.execute_chain([b1, b2])
    
    assert len(mock_mcp.calls) == 2
    assert mock_mcp.calls[0] == ('adb_tap', {'x': 1, 'y': 1})
    assert mock_mcp.calls[1] == ('adb_tap', {'x': 2, 'y': 2})

def test_behavior_precondition_check(mock_mcp):
    b = Behavior(
        name='needs_menu',
        preconditions=['screen_menu'],
        actions=[Action(action_type='tap', params={'x': 1, 'y': 1})]
    )
    executor = BehaviorExecutor(mcp_client=mock_mcp)
    
    # Should pass since mock_mcp.screen_state is 'screen_menu'
    executor.execute(b)
    assert ('adb_tap', {'x': 1, 'y': 1}) in mock_mcp.calls
    
    mock_mcp.calls.clear()
    mock_mcp.screen_state = 'screen_combat'
    
    with pytest.raises(BehaviorError, match='needs_menu'):
        executor.execute(b)
    assert len(mock_mcp.calls) == 1 # Only get_screen_state was called
    assert mock_mcp.calls[0][0] == 'get_screen_state'
