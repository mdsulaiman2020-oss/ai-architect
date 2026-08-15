import json
from tools.base import Tool
from tools.registry import ToolRegistry
from runtime import Runtime
from session import ConversationSession
from provider import get_provider

from agents.assessment.tools.validators import AssessmentTopicsValidator, AssessmentOutcomesValidator, AssessmentQuestionTopicAlignmentValidator, AssessmentQuestionOutcomeAlignmentValidator
from agents.assessment.mock_data import source

from agents.assessment.validationOrchestration import ValidationOrchestrator

class AssessmentAgent:
    def __init__(self):
        # Create a private tool registry for this agent
        self.registry = ToolRegistry()
        
        self.provider = get_provider()

    def analyze_validation_result(self, validation_result: dict) -> str:
        if validation_result.get("errors"):
            return "needs_deeper_review"
            
        for res in validation_result.get("results", []):
            data = res.get("data", {})
            if data.get("missing") or data.get("invalid"):
                return "needs_deeper_review"
                
        return "final_report"

    async def process(self, course_name: str, scope: str) -> dict:
        """Run the assessment agent and return both the response text and the internal session messages."""
        # Create a local session just for this agent's lifetime
        session = ConversationSession(session_id="internal-assessment-agent")
        
        system_instruction = (
            "You are an Assessment Validator Agent. "
            "The validation engine has already performed the requested checks. "
            f"The course in question is '{course_name}'. "
            " Your responsibility is to:"
            "1. Interpret the validation results."
            "2. Clearly explain successful validations."
            "3. Clearly identify missing and invalid items."
            "4. Clearly present questions with incorrect topic or outcome mappings, including the suggestions provided by the validation engine."
            "5. Explain partial/failure status when applicable."
            "6. Do not invent validation results."
            "7. Only report validation areas present in the supplied validation results. Never infer that an unexecuted validator passed."
            "8. Provide a highly detailed final report containing all missing items, formatting it beautifully in markdown."
        )
        
        session.add_user_message(f"SYSTEM INSTRUCTION: {system_instruction}\n\nUSER SCOPE: {scope}")

        orchestrator = ValidationOrchestrator([
            AssessmentTopicsValidator(), 
            AssessmentOutcomesValidator(),
            AssessmentQuestionTopicAlignmentValidator(),
            AssessmentQuestionOutcomeAlignmentValidator()
        ])
        results = await orchestrator.run_validators(scope, course_name, source)

        # decision = self.analyze_validation_result(results)

        serialized_results = json.dumps(results, indent=2)

        session.add_validation_result_message(name="assessment_validators", content=f"RESULTS: {serialized_results}")

        """  session.add_user_message(
            f"WORKFLOW DECISION: {decision}\n\n"
            "If the decision is 'final_report', generate the beautifully formatted final report. "
            "If the decision is 'needs_deeper_review', explain why and what aspects require deeper review based on the results."
        ) """

        
        runtime = Runtime(self.provider, session, self.registry)
        response, _ = await runtime.call_provider()
        
        return {
            "text": response.text,
            "_sub_agent_messages": session.messages
        }


class RunAssessmentAgentTool(Tool):
    @property
    def name(self) -> str:
        return "run_assessment_agent"

    @property
    def description(self) -> str:
        return "Use this tool to delegate assessment validation tasks (like checking missing topics or outcomes) to the specialized Assessment Agent. This agent will run independently and return a comprehensive report."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "course_name": {
                    "type": "string",
                    "description": "The name of the course. Use select_course tool first if you don't know it."
                },
                "scope": {
                    "type": "string",
                    "enum": [
                        "topics",
                        "outcomes",
                        "all"
                    ],
                    "description": "The assessment validation area to review."
                }
            },
            "required": ["course_name", "scope"]
        }

    async def execute(self, course_name: str, scope: str, **kwargs) -> dict:
        agent = AssessmentAgent()
        result = await agent.process(course_name, scope)
        return result

