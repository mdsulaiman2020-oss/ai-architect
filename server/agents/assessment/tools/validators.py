from tools.base import ValidationResult, ValidatorRequest
from agents.assessment.validators.topic_validator import TopicValidator
from agents.assessment.validators.outcome_validator import OutcomeValidator

class AssessmentTopicsValidator:
    category = "topics"

    def validate(self, course_name: str, assessment: dict) -> dict:
        request = ValidatorRequest(course_name=course_name, assessment_data=assessment)
        validator = TopicValidator(request)
        missing = validator.analyze_missing_topics()
        invalid = validator.analyze_invalid_topics()
        
        return ValidationResult(
            total_count=len(validator.get_expected_topics()),   
            covered_count=len(validator.get_covered_topics()),
            missing=missing,
            invalid=invalid,
            validator_name=self.category
        ).to_dict()
   
class AssessmentOutcomesValidator:
    category = "outcomes"

    def validate(self, course_name: str, assessment: dict) -> dict:
        request = ValidatorRequest(course_name=course_name, assessment_data=assessment)
        validator = OutcomeValidator(request)
        missing = validator.analyze_missing_outcomes()
        invalid = validator.analyze_invalid_outcomes()
        
        return ValidationResult(
            total_count=len(validator.get_expected_outcomes()),
            covered_count=len(validator.get_covered_outcomes()),
            missing=missing,
            invalid=invalid,
            validator_name=self.category
        ).to_dict()

from agents.assessment.validators.question_topic_alignment_validator import QuestionTopicAlignmentValidator

class AssessmentQuestionTopicAlignmentValidator:
    category = "topics"

    async def validate(self, course_name: str, assessment: dict) -> dict:
        request = ValidatorRequest(course_name=course_name, assessment_data=assessment)
        validator = QuestionTopicAlignmentValidator(request)
        
        misaligned = await validator.analyze_alignment()
        
        total_questions = len(request.assessment_data.get("assessment", {}).get("items", []))
        
        return ValidationResult(
            total_count=total_questions,
            covered_count=total_questions - len(misaligned),
            missing=[],
            invalid=misaligned,
            validator_name=self.category
        ).to_dict()

from agents.assessment.validators.question_outcome_alignment_validator import QuestionOutcomeAlignmentValidator

class AssessmentQuestionOutcomeAlignmentValidator:
    category = "outcomes"

    async def validate(self, course_name: str, assessment: dict) -> dict:
        request = ValidatorRequest(course_name=course_name, assessment_data=assessment)
        validator = QuestionOutcomeAlignmentValidator(request)
        
        misaligned = await validator.analyze_alignment()
        
        total_questions = len(request.assessment_data.get("assessment", {}).get("items", []))
        
        return ValidationResult(
            total_count=total_questions,
            covered_count=total_questions - len(misaligned),
            missing=[],
            invalid=misaligned,
            validator_name=self.category
        ).to_dict()
