from tools.base import Tool
from agents.schedule.exam_schedule_service import ExamSchedulingService
import re
import logging

logger = logging.getLogger(__name__)


def _should_clear_params(session_id: str) -> bool:
    """Deterministic check: did the user actually provide scheduling params, 
    or did the LLM hallucinate them from session history?
    
    Returns True if params should be cleared (user's message is vague,
    and no form submission tool-result has been received since then).
    """
    try:
        from session import MongoSessionStore
        session = MongoSessionStore().get_or_create(session_id)
        messages = session.messages
        
        if not messages:
            return False
        
        # Find the index of the last user message
        last_user_idx = -1
        last_user_content = ""
        for i in range(len(messages) - 1, -1, -1):
            if messages[i].role == "user":
                last_user_idx = i
                last_user_content = (messages[i].content or "").strip().lower()
                break
        
        if last_user_idx == -1:
            return False
        
        # Check if there are any tool-results AFTER the last user message.
        # If there are, it means a form was submitted and we should NOT clear params.
        for i in range(last_user_idx + 1, len(messages)):
            if messages[i].role == "tool-result":
                logger.info(f"Found tool-result after last user message — keeping params (form flow)")
                return False
        
        # No tool-results after user message. Check if the user's message
        # actually contains specific scheduling parameters.
        # Look for date patterns (YYYY-MM-DD, "august", "tomorrow", etc.), 
        # time patterns (HH:MM, "3 PM", etc.), or course identifiers.
        has_date = bool(re.search(r'\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}', last_user_content))
        has_time = bool(re.search(r'\d{1,2}:\d{2}|\d{1,2}\s*(am|pm)', last_user_content))
        has_duration = bool(re.search(r'\d+\s*(min|hour|minute)', last_user_content))
        
        # If the message has none of these specifics, the LLM likely hallucinated
        if not has_date and not has_time and not has_duration:
            logger.info(f"User message '{last_user_content}' has no scheduling specifics — clearing hallucinated params")
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"Error in _should_clear_params: {e}")
        return False


def _should_clear_reschedule_params(session_id: str) -> bool:
    """Stronger guard for reschedule: ALWAYS clear all params (exam_id, new_date, new_time)
    unless they came from a form submission (tool-result).
    
    exam_id MUST come from the client UI form dropdown — it can NEVER be inferred
    from conversation history, even if the user mentions a time or date.
    """
    try:
        from session import MongoSessionStore
        session = MongoSessionStore().get_or_create(session_id)
        messages = session.messages
        
        if not messages:
            return False
        
        # Find the index of the last user message
        last_user_idx = -1
        for i in range(len(messages) - 1, -1, -1):
            if messages[i].role == "user":
                last_user_idx = i
                break
        
        if last_user_idx == -1:
            return False
        
        # Check if there are any tool-results AFTER the last user message.
        # If there are, it means a form was submitted and we should NOT clear params.
        for i in range(last_user_idx + 1, len(messages)):
            if messages[i].role == "tool-result":
                logger.info(f"Found tool-result after last user message — keeping reschedule params (form flow)")
                return False
        
        # No tool-result after the last user message — always clear.
        # exam_id must always come from the client UI, never inferred from context.
        logger.info("No tool-result after user message — clearing all reschedule params (exam_id must come from UI form)")
        return True
        
    except Exception as e:
        logger.error(f"Error in _should_clear_reschedule_params: {e}")
        return False


class RunExamSchedulingTool(Tool): 
    """
    Schedule an exam. 
    Determines whether the required scheduling information is available,
    validates the request, checks conflicts, and prepares a schedule proposal.
    """
    @property
    def name(self) -> str:
        return "run_exam_scheduling"

    @property
    def description(self) -> str:
        return """Schedule an exam. 
            CRITICAL INSTRUCTION: DO NOT invent, guess, or assume ANY parameters.
            Schedule an exam by collecting the required scheduling information.
            If required information is missing, return the missing fields.
            If the tool returns a validation failure (status: validation_failed), you MUST inform the user of 
            the error message so they can correct it. DO NOT silently change any parameters 
            (like exam_type) to bypass the error.
            IMPORTANT: If the validation_failed message indicates that an exam is already scheduled for that 
            course and type, DO NOT attempt to schedule again. Instead, tell the user the exam is already 
            scheduled and suggest using the reschedule option if they want to change the date or time.
            If all information is provided, prepare the request for validation.
            On schedule preparation fail, do not guess, hallucinate, or suggest arbitrary alternative 
            exam types (e.g., Quiz or Final) unless explicitly provided by a tool.
            If the tool returns status "ready_for_user_confirmation",
            present the proposed schedule to the user and ask for confirmation.
            Only use action="confirm" after the user explicitly confirms the proposed schedule.
            When using action="confirm", you MUST provide the transaction_id returned from the prepare step.
            Never treat "ready_for_user_confirmation" itself as user confirmation.
            EXPLICIT CONFIRMATION RULES:
            These phrases ARE confirmations: "yes", "confirm", "confirm it", "go ahead", "schedule it", "do it".
            These phrases are NOT confirmations: "maybe", "change the time to 3 PM", "actually use tomorrow", "wait", "no", or any prompt changing the parameters.
            If the user's response is not a clear confirmation, DO NOT use action="confirm". Instead, use action="prepare" with the newly requested parameters, or ask for clarification.
            """

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "transaction_id": {
                    "type": "string",
                    "description": "The transaction ID provided during the prepare step. Required ONLY for action='confirm'."
                },
                "course_name": {
                    "type": "string",
                    "description": "The name of the course. Only used when action='prepare'."
                },
                "exam_type": {
                    "type": "string",
                    "description": "The type of exam to schedule. Only used when action='prepare'."
                },
                "date": {
                    "type": "string",
                    "description": "The date of the exam in YYYY-MM-DD format. Only used when action='prepare'."
                },
                "time": {
                    "type": "string",
                    "description": "The time of the exam in HH:MM format. Only used when action='prepare'."
                },
                "duration_minutes": {
                    "type": "integer",
                    "description": "Duration of the exam in minutes. Only used when action='prepare'."
                },
                "action": {
                    "type": "string",
                    "enum": ["prepare", "confirm"],
                    "description": "Use 'prepare' when collecting/validating schedule information. "
                                    "Use 'confirm' ONLY after the user explicitly confirms the proposed "
                                    "schedule returned by a previous prepare operation."
                }
            },
        }

    def execute(self, transaction_id: str = None, course_name: str = None, exam_type: str = None, date: str = None, time: str = None, duration_minutes: int = None, action:str = 'prepare', **kwargs) -> dict:
        
        # Deterministic guard: check if this is a fresh user request where the LLM 
        # may have hallucinated params from session history.
        if action == "prepare":
            session_id = kwargs.get("_context_session_id")
            if session_id and _should_clear_params(session_id):
                course_name = exam_type = date = time = duration_minutes = None


        if action == "prepare":
            request_params = {
                "course_name": course_name,
                "exam_type": exam_type,
                "date": date,
                "time": time,
                "duration_minutes": duration_minutes
            }
            request_parameter_validation_result = ExamSchedulingService().validate_request(request_params)

            if request_parameter_validation_result["status"] == "ready_for_validation":
                request_conflict_validation_result = ExamSchedulingService().check_conflicts(request_params)
                return request_conflict_validation_result
            
            return request_parameter_validation_result

        if action == "confirm":
            if not transaction_id:
                return {
                    "status": "validation_failed", 
                    "message": "transaction_id is required for confirmation. Please ensure you are confirming a proposed schedule."
                }
            return ExamSchedulingService().schedule_exam(transaction_id)

class RunExamReSchedulingTool(Tool):
    @property
    def name(self) -> str:
        return "run_exam_rescheduling"

    @property
    def description(self) -> str:
           return """Reschedule an exam. 
            CRITICAL INSTRUCTION: DO NOT invent, guess, or assume ANY parameters.
            ReSchedule an exam by collecting the required scheduling information.
            If required information is missing, return the missing fields.
            DO NOT silently change any parameters to bypass the error.
            If all information is provided, prepare the request for validation.
            On reschedule preparation fail, do not guess, hallucinate, or suggest arbitrary alternative 
            exam types (e.g., Quiz or Final) unless explicitly provided by a tool.
            If the tool returns status "ready_for_user_confirmation",
            present the proposed reschedule to the user and ask for confirmation.
            Only use action="confirm" after the user explicitly confirms the proposed schedule.
            When using action="confirm", you MUST provide the transaction_id returned from the prepare step.
            Never treat "ready_for_user_confirmation" itself as user confirmation.
            EXPLICIT CONFIRMATION RULES:
            These phrases ARE confirmations: "yes", "confirm", "confirm it", "go ahead", "schedule it", "do it".
            These phrases are NOT confirmations: "maybe", "change the time to 3 PM", "actually use tomorrow", "wait", "no", or any prompt changing the parameters.
            If the user's response is not a clear confirmation, DO NOT use action="confirm". Instead, use action="prepare" with the newly requested parameters, or ask for clarification.
            """

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "transaction_id": {
                    "type": "string",
                    "description": "The transaction ID provided during the prepare step. Required ONLY for action='confirm'."
                },
                "exam_id": {
                    "type": "string",
                    "description": "The unique MongoDB ID of the exam to reschedule. This MUST come from the client UI form dropdown — NEVER guess, infer, or use a course name. Leave empty to trigger the UI form."
                },
                "new_date": {
                    "type": "string",
                    "description": "The new date of the exam in YYYY-MM-DD format. Only used when action='prepare'."
                },
                "new_time": {
                    "type": "string",
                    "description": "The new time of the exam in HH:MM format. Only used when action='prepare'."
                },
                "action": {
                    "type": "string",
                    "enum": ["prepare", "confirm"],
                    "description": "Use 'prepare' when collecting/validating reschedule information. "
                                    "Use 'confirm' ONLY after the user explicitly confirms the proposed "
                                    "reschedule returned by a previous prepare operation."
                }
            },
        }    

    def execute(self, exam_id: str = "", new_date: str = "", new_time: str = "", action: str = 'prepare', transaction_id: str = None, **kwargs) -> dict:
        # Strict guard: for reschedule, exam_id MUST come from the client UI form.
        # Always clear ALL params on fresh user messages — even if they mention a time/date.
        # Only allow params through when they arrive via a tool-result (form submission).
        if action == "prepare":
            session_id = kwargs.get("_context_session_id")
            if session_id and _should_clear_reschedule_params(session_id):
                exam_id = new_date = new_time = ""
            
        service = ExamSchedulingService()
        result = service.reschedule_exam(exam_id, new_date, new_time, action, transaction_id)
        print(f"DEBUG: Tool result for {self.name}: {result}")
        return result