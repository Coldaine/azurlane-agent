import pytest
from tools.behavior.catalog import get_behavior

def test_catalog_entries_exist():
    menu = get_behavior("navigate_to_menu")
    assert menu.name == "navigate_to_menu"
    assert "screen_menu" in menu.postconditions

    sortie = get_behavior("start_sortie")
    assert sortie.name == "start_sortie"
    assert "screen_sortie" in sortie.postconditions

    rewards = get_behavior("collect_rewards")
    assert rewards.name == "collect_rewards"
    
    dock = get_behavior("manage_dock")
    assert dock.name == "manage_dock"

def test_catalog_unknown_behavior():
    with pytest.raises(KeyError):
        get_behavior("unknown_action")
