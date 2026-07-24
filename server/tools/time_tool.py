from tools.base import Tool
from tools.time import get_current_time_and_zone

class CurrentTimeTool(Tool):
    @property
    def name(self) -> str:
        return "current_time"

    @property
    def description(self) -> str:
        return "Get the current local time and timezone"    

    @property
    def parameters(self) -> dict:
        return {}

    def execute(self, **args):
        return get_current_time_and_zone()