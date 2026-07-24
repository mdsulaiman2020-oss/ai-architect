from abc import ABC, abstractmethod

class Tool(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """The name of the tool exposed to the LLM (e.g., 'current_time')."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """The description of the tool, explaining what it does to the LLM."""
        pass

    @property
    @abstractmethod
    def parameters(self) -> dict:
        """The parameters of the tool."""
        pass

    @abstractmethod
    def execute(self, **args):
        """ The execution handler of the tool."""
        pass