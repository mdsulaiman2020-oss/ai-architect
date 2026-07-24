from tools.base import Tool

class ToolRegistry:
    def __init__(self):
        self._tools = {}

    def register(self, tool: Tool):
        self._tools[tool.name] = tool

    def list_tools(self) -> list[dict]:
        return [
            {
                "name": name,
                "description": tool.description,
                "parameters": tool.parameters,
            }
            for name, tool in self._tools.items()
        ]

    def execute(self, name: str, **arguments):
        if name not in self._tools:
            raise ValueError(f"Unknown tool: {name}")

        return self._tools[name].execute(**arguments)
