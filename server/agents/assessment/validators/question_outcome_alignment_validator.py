import json
import logging
from tools.base import ValidatorRequest
from provider import get_provider
from session import ConversationSession

logger = logging.getLogger(__name__)

class QuestionOutcomeAlignmentValidator:
    def __init__(self, request: ValidatorRequest):
        self.request = request
        self.assessment_data = request.assessment_data.get("assessment", {})
        self.provider = get_provider()

    async def analyze_alignment(self) -> list[dict]:
        """
        Uses an LLM to check if items align with their assigned course learning outcomes.
        Returns a list of misaligned items.
        """
        misaligned = []
        items = self.assessment_data.get("items", [])
        
        # Build a lookup for learning outcome descriptions from the course
        course_outcomes = {
            lo.get("name"): lo.get("description", "")
            for lo in self.assessment_data.get("learningOutcomes", [])
            if lo.get("name")
        }
        
        questions_to_check = []
        for item in items:
            stem = item.get("stem", "")
            outcomes = item.get("learningOutcomes", [])
            
            if outcomes:
                outcome_details = [
                    f"{o.get('name')}: {course_outcomes.get(o.get('name'), '')}" 
                    for o in outcomes if o.get("name")
                ]
                questions_to_check.append({
                    "id": item.get("id"),
                    "stem": stem,
                    "learningOutcomes": outcome_details
                })
                
            for sub in item.get("subItems", []):
                sub_stem = sub.get("stem", "")
                sub_outcomes = sub.get("learningOutcomes", [])
                if sub_outcomes:
                    sub_outcome_details = [
                        f"{o.get('name')}: {course_outcomes.get(o.get('name'), '')}" 
                        for o in sub_outcomes if o.get("name")
                    ]
                    questions_to_check.append({
                        "id": sub.get("id"),
                        "stem": f"Context: {stem}\nQuestion: {sub_stem}",
                        "learningOutcomes": sub_outcome_details
                    })
                    
        if not questions_to_check:
            return []

        prompt = (
            "You are a Question Alignment Validator. Your task is to determine if each of the following questions "
            "semantically aligns with its assigned course learning outcomes.\n\n"
            "Return EXACTLY a JSON array of objects for ANY question that is MISALIGNED. "
            "If all questions are perfectly aligned, return an empty array [].\n\n"
            "Format of response array objects:\n"
            '{"id": "item_id", "aligned": false, "confidence": 0.92, "reason": "Detailed explanation of why it does not align.", "suggestedOutcomes": ["Correct Outcome Name"]}\n\n'
            f"Questions to evaluate:\n{json.dumps(questions_to_check, indent=2)}"
        )

        session = ConversationSession(session_id="batch-outcome-align-check")
        session.add_user_message(prompt)
        
        try:
            response = await self.provider.generate(session)
            text = response.text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            text = text.removesuffix("```").strip()
            
            result = json.loads(text)
            
            if isinstance(result, list):
                for invalid in result:
                    q_id = invalid.get("id")
                    q_obj = next((q for q in questions_to_check if q["id"] == q_id), None)
                    if q_obj:
                        misaligned.append({
                            "id": q_id,
                            "stem": q_obj["stem"],
                            "assigned_outcomes": q_obj["learningOutcomes"],
                            "aligned": invalid.get("aligned", False),
                            "confidence": invalid.get("confidence", 1.0),
                            "reason": invalid.get("reason", "No reason provided"),
                            "suggestedOutcomes": invalid.get("suggestedOutcomes", [])
                        })
        except Exception as e:
            logger.error(f"Error checking outcome alignment batch: {e}", exc_info=True)
            raise RuntimeError("Validation failed due to an internal error calling the LLM.") from e
            
        return misaligned
