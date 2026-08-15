from tools.base import ValidatorRequest

class OutcomeValidator:
    def __init__(self, request: ValidatorRequest):
        self.request = request
        self.assessment_data = request.assessment_data.get("assessment", {})

    def get_expected_outcomes(self) -> set[str]:
        """Returns the set of all outcome names defined in the course."""
        outcomes = self.assessment_data.get("learningOutcomes", [])
        return {outcome.get("name") for outcome in outcomes if outcome.get("name")}

    def get_covered_outcomes(self) -> set[str]:
        """Returns the set of all outcome names covered by the items and subitems."""
        covered = set()
        items = self.assessment_data.get("items", [])
        for item in items:
            # Check main item outcomes if any
            for outcome in item.get("learningOutcomes", []):
                if outcome.get("name"):
                    covered.add(outcome.get("name"))
            
            # Check subItems outcomes
            for sub_item in item.get("subItems", []):
                for outcome in sub_item.get("learningOutcomes", []):
                    if outcome.get("name"):
                        covered.add(outcome.get("name"))
        return covered

    def analyze_missing_outcomes(self) -> list[str]:
        """Returns a list of outcomes that are in the course but not covered by any item."""
        expected = self.get_expected_outcomes()
        covered = self.get_covered_outcomes()
        missing = expected - covered
        return sorted(list(missing))

    def analyze_invalid_outcomes(self) -> list[str]:
        """Returns a list of outcomes tagged in items that do not exist in the course."""
        expected = self.get_expected_outcomes()
        covered = self.get_covered_outcomes()
        invalid = covered - expected
        return sorted(list(invalid))
