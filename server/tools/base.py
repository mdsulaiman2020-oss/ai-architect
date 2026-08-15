from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict

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

    @property
    def is_client_side(self) -> bool:
        """If True, this tool is executed by the client UI instead of the backend."""
        return False

    @abstractmethod
    def execute(self, **args):
        """ The execution handler of the tool."""
        pass

@dataclass
class ValidationResult:
    total_count: int
    covered_count: int
    missing: list[str]
    invalid: list[str]
    validator_name: str

    @property
    def missing_count(self) -> int:
        return len(self.missing)

    @property
    def invalid_count(self) -> int:
        return len(self.invalid)

    def to_dict(self) -> dict:
        return asdict(self) | {
            "missing_count": self.missing_count,
            "invalid_count": self.invalid_count,
        }

@dataclass
class ValidatorRequest:
    course_name: str
    assessment_data: dict