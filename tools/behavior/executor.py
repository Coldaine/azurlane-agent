import time
from typing import List, Protocol
from .schema import Behavior, Action

class MCPClient(Protocol):
    def call_tool(self, name: str, kwargs: dict) -> any:
        pass

class BehaviorError(Exception):
    pass

class BehaviorExecutor:
    def __init__(self, mcp_client: MCPClient):
        self.mcp = mcp_client

    def get_screen_state(self) -> str:
        result = self.mcp.call_tool("get_screen_state", {})
        return result.get("observed_state", "unknown")

    def execute(self, behavior: Behavior) -> None:
        if behavior.preconditions:
            state = self.get_screen_state()
            if state not in behavior.preconditions:
                raise BehaviorError(f"Precondition failed for {behavior.name}: expected one of {behavior.preconditions}, got {state}")

        for action in behavior.actions:
            self._execute_action(action)

        if behavior.postconditions:
            state = self.get_screen_state()
            if state not in behavior.postconditions:
                raise BehaviorError(f"Postcondition failed for {behavior.name}: expected one of {behavior.postconditions}, got {state}")

    def _execute_action(self, action: Action):
        if action.action_type == "tap":
            self.mcp.call_tool("adb_tap", action.params)
        elif action.action_type == "swipe":
            self.mcp.call_tool("adb_swipe", action.params)
        elif action.action_type == "wait":
            self.mcp.call_tool("wait", action.params)
        else:
            raise BehaviorError(f"Unknown action type: {action.action_type}")

    def execute_chain(self, behaviors: List[Behavior]) -> None:
        for b in behaviors:
            self.execute(b)
