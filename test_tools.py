import os
import sys

# Ensure parent directory is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mcp_server import search_strategy_guide, search_game_config

def test_search_guide():
    print("=== TEST: search_strategy_guide ===")
    query = "Specialist build"
    result = search_strategy_guide(query)
    print(f"Query: '{query}'")
    print(f"Result (truncated):\n{result[:800]}...\n")
    assert "SOURCE" in result or "No tactical advice" in result
    print("SUCCESS: Guide search test passed.\n")

def test_search_config():
    print("=== TEST: search_game_config ===")
    query = "Music"
    result = search_game_config(query)
    print(f"Query: '{query}'")
    print(f"Result (truncated):\n{result[:800]}...\n")
    assert "Line" in result or "No configuration" in result
    print("SUCCESS: Config search test passed.\n")

if __name__ == "__main__":
    try:
        test_search_guide()
        test_search_config()
        print("ALL TESTS PASSED SUCCESSFULLY!")
    except Exception as e:
        print(f"TEST FAILURE: {str(e)}")
        sys.exit(1)
