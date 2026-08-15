import logging
import asyncio
logger = logging.getLogger(__name__)
class ValidationOrchestrator:

    def __init__(self, validators):
        self.validators = validators

    async def run_validator(self, validator, course_name: str, assessment_data: dict):
        try:
            if asyncio.iscoroutinefunction(validator.validate):
                res = await validator.validate(course_name, assessment_data)
            else:
                res = await asyncio.to_thread(validator.validate, course_name, assessment_data)
            return {
                "status": "success",
                "validator_name": getattr(validator, 'category', 'unknown'),
                "data": res
            }
        except Exception as e:
            logger.error(f"Actual error in validator {getattr(validator, 'category', 'unknown')}: {e}", exc_info=True)
            return {
                "status": "failure",
                "validator_name": getattr(validator, 'category', 'unknown'),
                "error": "Validation failed due to an internal error."
            }

    async def run_validators(self, scope: str, course_name: str, assessment_data: dict):
        logger.info(f"DEBUG: run_validators started. scope='{scope}', course_name='{course_name}'")
        selected_validators = self._select_validators(scope)
        logger.info(f"DEBUG: selected {len(selected_validators)} validators: {[getattr(v, 'category', 'unknown') for v in selected_validators]}")
        validation_result  = {
            "status": "success",
            "results": [],
            "errors": []
        }
 
        results = await asyncio.gather(
            *[
                self.run_validator(validator, course_name, assessment_data) 
                for validator in selected_validators
            ]
        )
        logger.info(f"DEBUG: asyncio.gather returned: {results}")
        
        for res in results:
            if res["status"] == "success":
                validation_result["results"].append(res)
            else:
                validation_result["errors"].append(res)
                
        if validation_result["errors"]:
            validation_result["status"] = "partial_success" if validation_result["results"] else "failure"
            
        return validation_result

    def _select_validators(self, scope: str):
        scope = scope.lower()
        
        selected = []
        if scope == 'all':
            selected = self.validators
        else:
            for validator in self.validators:
                if getattr(validator, 'category', None) == scope:
                    selected.append(validator)
                    
        if not selected:
            raise ValueError(f"No validators found for scope: {scope}")
        return selected