import pytest
from tools.behavior.catalog import get_behavior
from tools.behavior.executor import BehaviorExecutor

class MockPipelineMCP:
    def __init__(self, initial_state="screen_menu"):
        self.calls = []
        self.state = initial_state
        
    def call_tool(self, name, kwargs):
        self.calls.append((name, kwargs))
        if name == "get_screen_state":
            return {"observed_state": self.state}
        elif name == "adb_screenshot":
            return "mock_image_binary"
        return "ok"

def test_full_pipeline_happy_path():
    b = get_behavior("start_sortie")
    
    class MockStateChangingMCP(MockPipelineMCP):
        def call_tool(self, name, kwargs):
            self.calls.append((name, kwargs))
            if name == "get_screen_state":
                return {"observed_state": self.state}
            
            # Simulate game screen changing after tapping sortie
            # The start_sortie action taps at 800,450
            if name == "adb_tap" and kwargs.get("x") == 800 and kwargs.get("y") == 450:
                self.state = "screen_sortie"
            return "ok"

    mcp = MockStateChangingMCP(initial_state="screen_menu")
    executor = BehaviorExecutor(mcp_client=mcp)
    executor.execute(b)
    
    assert len(mcp.calls) == 4
    assert mcp.calls[0][0] == "get_screen_state"
    assert mcp.calls[1] == ("adb_tap", {"x": 800, "y": 450})
    assert mcp.calls[2] == ("wait", {"duration": 2.0})
    assert mcp.calls[3][0] == "get_screen_state"
