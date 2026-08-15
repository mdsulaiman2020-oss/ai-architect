from tools.base import ValidatorRequest

class TopicValidator:
    def  __init__(self, request: ValidatorRequest):
        self.request = request
        self.assessment_data = request.assessment_data.get("assessment", {})

    def get_expected_topics(self) -> set[str]:
        """Returns the set of all topic names defined in the course."""
        topics = self.assessment_data.get("topics", [])
        return {topic.get("name") for topic in topics if topic.get("name")}

    def get_covered_topics(self) -> set[str]:
        """Returns the set of all topic names covered by the items and subitems."""
        covered = set()
        items = self.assessment_data.get("items", [])
        for item in items:
            # Check main item topics if any
            for topic in item.get("topics", []):
                if topic.get("name"):
                    covered.add(topic.get("name"))
            
            # Check subItems topics
            for sub_item in item.get("subItems", []):
                for topic in sub_item.get("topics", []):
                    if topic.get("name"):
                        covered.add(topic.get("name"))
        return covered

    def analyze_missing_topics(self) -> list[str]:
        """Returns a list of topics that are in the course but not covered by any item."""
        expected = self.get_expected_topics()
        covered = self.get_covered_topics()
        missing = expected - covered
        return sorted(list(missing))

    def analyze_invalid_topics(self) -> list[str]:
        """Returns a list of topics tagged in items that do not exist in the course."""
        expected = self.get_expected_topics()
        covered = self.get_covered_topics()
        invalid = covered - expected
        return sorted(list(invalid))

if __name__ == "__main__":
    from agents.assessment.mock_data import source
    request = ValidatorRequest(course_name="Test Course", assessment_data=source)
    validator = TopicValidator(request)
    missing = validator.analyze_missing_topics()
    
    print(f"Total Course Topics: {len(validator.get_expected_topics())}")
    print(f"Topics Covered by Items: {len(validator.get_covered_topics())}")
    print(f"Topics Missing: {len(missing)}")
    print("\nMissing Topics (Not covered in any question):")
    for t in missing:
        print(f"- {t}")