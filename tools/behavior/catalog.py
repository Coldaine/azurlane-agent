from .schema import Behavior, Action

_CATALOG = {
    "navigate_to_menu": Behavior(
        name="navigate_to_menu",
        preconditions=[],
        actions=[
            Action(action_type="tap", params={"x": 50, "y": 50}), # back button or home button
            Action(action_type="wait", params={"duration": 2.0})
        ],
        postconditions=["screen_menu"]
    ),
    "start_sortie": Behavior(
        name="start_sortie",
        preconditions=["screen_menu"],
        actions=[
            Action(action_type="tap", params={"x": 800, "y": 450}), # Assuming sortie button coords
            Action(action_type="wait", params={"duration": 2.0})
        ],
        postconditions=["screen_sortie"]
    ),
    "collect_rewards": Behavior(
        name="collect_rewards",
        preconditions=["screen_menu"],
        actions=[
            Action(action_type="tap", params={"x": 700, "y": 500}), # Missions
            Action(action_type="wait", params={"duration": 1.0}),
            Action(action_type="tap", params={"x": 800, "y": 100}), # Collect All
            Action(action_type="wait", params={"duration": 2.0}),
            Action(action_type="tap", params={"x": 50, "y": 50})    # Back
        ],
        postconditions=["screen_menu"]
    ),
    "manage_dock": Behavior(
        name="manage_dock",
        preconditions=["screen_menu"],
        actions=[
            Action(action_type="tap", params={"x": 300, "y": 500}), # Dock
            Action(action_type="wait", params={"duration": 1.0})
        ],
        postconditions=["screen_dock"]
    )
}

def get_behavior(name: str) -> Behavior:
    if name not in _CATALOG:
        raise KeyError(f"Behavior '{name}' not found in catalog")
    return _CATALOG[name]

def list_behaviors() -> list[str]:
    return list(_CATALOG.keys())
