from tools.base import Tool

class AddTool(Tool):
    @property
    def name(self) -> str:
        return "add"

    @property
    def description(self) -> str:
        return "Add two numbers"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "a": {"type": "integer"},
                "b": {"type": "integer"},
            },
            "required": ["a", "b"],
        }

    def execute(self, **args) -> dict:
        return {"result": args["a"] + args["b"]}  