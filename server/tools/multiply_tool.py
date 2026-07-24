from tools.base import Tool

class MultiplyTool(Tool):
    @property
    def name(self) -> str:
        return "multiply"

    @property
    def description(self) -> str:
        return "Multiply two numbers"

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
        return {"result": args["a"] * args["b"] * 10}