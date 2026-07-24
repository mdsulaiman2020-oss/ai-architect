from pathlib import Path
import sys

SERVER_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER_DIR))

from tools.registry import ToolRegistry
from tools.time_tool import CurrentTimeTool
from tools.add_tool import AddTool
from tools.multiply_tool import MultiplyTool


def main():
    registry = ToolRegistry()

    registry.register(AddTool())
    registry.register(MultiplyTool())
    registry.register(CurrentTimeTool())

    print("Available tools:")
    for tool in registry.list_tools():
        print(f"- {tool['name']}: {tool['description']}")

    print()
    print("Tool results:")
    print("add:", registry.execute("add", a=2, b=3))
    print("multiply:", registry.execute("multiply", a=4, b=5))
    print("current_time:", registry.execute("current_time"))


if __name__ == "__main__":
    main()
