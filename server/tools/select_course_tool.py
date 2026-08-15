from tools.base import Tool

class SelectCourseTool(Tool):
    @property
    def name(self) -> str:
        return "select_course"

    @property
    def description(self) -> str:
        return "Use this tool to ask the user to select a course from the UI. Call this when you need a course name to proceed."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "The reason why you need the user to select a course (e.g. 'To evaluate this assessment, I need to know which course it belongs to.')"
                }
            },
            "required": ["reason"]
        }
        
    @property
    def is_client_side(self) -> bool:
        return True

    def execute(self, **args):
        # This will not be executed by the backend runtime directly.
        # It serves as a placeholder or fallback.
        reason = args.get('reason', '')
        return f"Waiting for user to select a course. Reason: {reason}"
