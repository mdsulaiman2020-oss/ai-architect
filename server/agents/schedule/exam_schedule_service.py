import uuid
from datetime import datetime, timezone

class ExamSchedulingService:

    REQUIRED_FIELDS = ["course_name", "exam_type", "date", "time", "duration_minutes"]

    def _get_proposals_collection(self):
        from db import get_db
        return get_db()["agent_proposals"]

    def _get_schedule_collection(self):
        from db import get_db
        return get_db()["agent_schedule"]

    def _check_seat_availability(self, date: str):
        if date == "2026-12-25":
            return {
                "status": "validation_failed",
                "message": "There are no seats available for the selected date. Please choose another date."
            }
        return None

    def reschedule_exam(self, exam_id: str, new_date: str, new_time: str, action:str, transaction_id: str = None):
        """Update an existing exam schedule with a new date and time."""
        print(f"Rescheduling exam params: exam_id={exam_id}, new_date={new_date}, new_time={new_time}, action={action}, transaction_id={transaction_id}")
        
        # validate parameters for prepare action
        if action == 'prepare' and (not exam_id or not new_date or not new_time):
            fields = {
                "exam_id":  {"status": "provided" if exam_id  else "missing", "value": exam_id  or None},
                "new_date": {"status": "provided" if new_date else "missing", "value": new_date or None},
                "new_time": {"status": "provided" if new_time else "missing", "value": new_time or None},
            }
            return {"status": "needs_reschedule_input", "fields": fields, "message": "Please select the exam and provide the new date and time."}
        if action == 'confirm' and (not transaction_id):
            return {"status": "validation_failed", "message": "transaction_id is required for confirmation. Please ensure you are confirming a proposed reschedule."}

        proposal = {}
        
        # validate if exam exists for update action
        if action == 'prepare':
            exam = self.get_exam(exam_id)
        elif action == 'confirm':
            coll = self._get_proposals_collection()
            proposal = coll.find_one({"_id": transaction_id, "status": {"$ne": "confirmed"}})
            if not proposal:
                return {"status": "validation_failed", "message": "Transaction expired or invalid. Please prepare the schedule again."}
            exam = self.get_exam(proposal["params"]["exam_id"])

        if not exam:
            return {"status": "validation_failed", "message": "Exam not found."}
        
        if action == 'prepare':
            validation_result = self.validate_reschedule(exam, new_date, new_time)
            if validation_result.get("status") != "success":
                return validation_result
        elif action == 'confirm':
            validation_result = self.validate_reschedule(exam, new_date=proposal["params"]["new_date"], new_time=proposal["params"]["new_time"])
            if validation_result.get("status") != "success":
                return validation_result

        if action == "prepare":
            transaction_id = str(uuid.uuid4())
            coll = self._get_proposals_collection()
            coll.insert_one({
                "_id": transaction_id,
                "type": "reschedule",
                "status": "pending",
                "params": {
                    "exam_id": exam_id,
                    "new_date": new_date,
                    "new_time": new_time
                },
                "created_at": datetime.now(timezone.utc)
            })
            return {
                "status": "ready_for_user_confirmation",
                "message": "All required rescheduling information has been provided and validated successfully. Prompt the user to confirm the reschedule.",
                "transaction_id": transaction_id,
                "exam_schedule": {
                    "exam_id": exam_id,
                    "course_name": exam["course_name"],
                    "exam_type": exam["exam_type"],
                    "current": {
                        "date": exam["date"],
                        "time": exam["time"]
                    },
                    "proposed": {
                        "date": new_date,
                        "time": new_time
                    }
                }
            }
        elif action == "confirm":
            proposal_collection = self._get_proposals_collection()
            proposal = proposal_collection.find_one({"_id": transaction_id, "status": {"$ne": "confirmed"}, "type": "reschedule"})
            if not proposal:
                return {"status": "validation_failed", "message": "Transaction expired or invalid. Please prepare the schedule again."}
            proposal_collection.update_one({"_id": transaction_id , "type": "reschedule" }, {"$set": {"status": "confirmed", "updated_at": datetime.now(timezone.utc)}})
            
            schedule_collection = self._get_schedule_collection()
            
            update_data = {
                "date": proposal["params"]["new_date"],
                "time": proposal["params"]["new_time"],
                "updated_at": datetime.now(timezone.utc)
            }
        
            schedule_collection.update_one(
                {"_id": exam["_id"]},
                {"$set": update_data}
            )
            return {
                "status": "success",
                "message": "Exam has been successfully rescheduled.",
                "exam_schedule": {
                    "exam_id": exam_id,
                    "new_date": proposal["params"]["new_date"],
                    "new_time": proposal["params"]["new_time"]
                }
            }
        else:
            return {"status": "validation_failed", "message": "Invalid action. Please use 'prepare' or 'confirm'."}
        
        # update local object for returning
    def schedule_exam(self, transaction_id: str):
        """Finalize and schedule the exam in the system."""
        if not transaction_id:
            return {"status": "validation_failed", "message": "Missing transaction_id for confirmation."}
            
        coll = self._get_proposals_collection()
        proposal = coll.find_one({"_id": transaction_id, "status": {"$ne": "confirmed"}})
        
        if not proposal:
            return {"status": "validation_failed", "message": "Transaction expired or invalid. Please prepare the schedule again."}
            
        params = proposal.get("params", {})
        
        # TOCTOU Prevention: Re-validate and re-check conflicts
        val_result = self.validate_request(params)
        if val_result.get("status") != "ready_for_validation":
            return val_result
            
        conflict_result = self.check_conflicts(params, _is_recheck=True)
        if conflict_result.get("status") != "ready_for_user_confirmation":
            return conflict_result
            
        # Success! Mark the proposal as confirmed and schedule it
        coll.update_one({"_id": transaction_id}, {"$set": {"status": "confirmed", "updated_at": datetime.now(timezone.utc)}})
        
        schedule_coll = self._get_schedule_collection()
        schedule_coll.insert_one({
            "transaction_id": transaction_id,
            "course_name": params.get("course_name"),
            "exam_type": params.get("exam_type"),
            "date": params.get("date"),
            "time": params.get("time"),
            "duration_minutes": params.get("duration_minutes"),
            "created_at": datetime.now(timezone.utc)
        })
        
        return {
            "status": "success",
            "message": "Exam has been successfully confirmed and scheduled in the database.",
            "exam_schedule": {
                "course_name": params.get("course_name"),
                "exam_type": params.get("exam_type"),
                "date": params.get("date"),
                "time": params.get("time"),
                "duration_minutes": params.get("duration_minutes")
            }
        }

    def check_conflicts(self, params: dict, _is_recheck: bool = False):
        """Check for scheduling conflicts."""
        # 1. Check if an exam of this type is already scheduled for this course
        schedule_coll = self._get_schedule_collection()
        existing = schedule_coll.find_one({
            "course_name": params.get("course_name"),
            "exam_type": params.get("exam_type")
        })
        if existing:
            return {
                "status": "validation_failed",
                "message": (
                    f"A {params.get('exam_type')} exam is already scheduled for {params.get('course_name')} "
                    f"on {existing.get('date')} at {existing.get('time')}. "
                    "To change the date or time, please use the reschedule option instead."
                )
            }

        # 2. Seats not available (Mocked scenario)
        seat_check = self._check_seat_availability(params.get("date"))
        if seat_check:
            return seat_check

        if _is_recheck:
            return {
                "status": "ready_for_user_confirmation",
                "message": "All required scheduling information has been provided and validated successfully."
            }

        transaction_id = str(uuid.uuid4())
        coll = self._get_proposals_collection()
        coll.insert_one({
            "_id": transaction_id,
            "type": "schedule",
            "status": "pending",
            "params": {
                "course_name": params.get("course_name"),
                "exam_type": params.get("exam_type"),
                "date": params.get("date"),
                "time": params.get("time"),
                "duration_minutes": params.get("duration_minutes")
            },
            "created_at": datetime.now(timezone.utc)
        })

        return {
            "status": "ready_for_user_confirmation",
            "message": "All required scheduling information has been provided and validated successfully. Prompt the user to confirm the exam schedule.",
            "transaction_id": transaction_id,
            "exam_schedule": {
                "course_name": params.get("course_name"),
                "exam_type": params.get("exam_type"),
                "date": params.get("date"),
                "time": params.get("time"),
                "duration_minutes": params.get("duration_minutes")
            }
        }

    def validate_request(self, params: dict):
        fields = {}
        missing = False

        for field in self.REQUIRED_FIELDS:
            value = params.get(field)
            if value:
                fields[field] = {"status": "provided", "value": value}
            else:
                fields[field] = {"status": "missing", "value": None}
                missing = True
                
        # 1. Date passed validation
        date_val = params.get("date")
        if date_val:
            try:
                exam_date = datetime.strptime(date_val, "%Y-%m-%d").date()
                if exam_date < datetime.now().date():
                    return {
                        "status": "validation_failed",
                        "message": "The selected date has already passed. Please choose a future date.",
                        "fields": fields
                    }
            except ValueError:
                return {
                    "status": "validation_failed",
                    "message": "Invalid date. Please use YYYY-MM-DD format.",
                    "fields": fields
                }


        if missing:
            return {
                "status": "needs_schedule_input",
                "fields": fields
            }
            
        return {
            "status": "ready_for_validation",
            "message": "All required scheduling information has been provided and validated successfully.",
            "fields": fields
        }

    def get_exam(self, exam_id: str):
        from bson.objectid import ObjectId
        from bson.errors import InvalidId
        
        schedule_coll = self._get_schedule_collection()
        
        # 1. Try as MongoDB ObjectId
        try:
            doc = schedule_coll.find_one({"_id": ObjectId(exam_id)})
            if doc:
                return doc
        except (InvalidId, TypeError):
            pass

        # 2. Try as transaction_id UUID string (stored during schedule_exam)
        return schedule_coll.find_one({"transaction_id": exam_id})

    def validate_reschedule(self, exam: dict, new_date: str, new_time: str):
        """Validate an exam reschedule request."""
        if not exam:
            return {"status": "validation_failed", "message": "Exam not found."}
        fields = {}
        missing = False

        if new_date:
            fields["new_date"] = {"status": "provided", "value": new_date}
        else:
            fields["new_date"] = {"status": "missing", "value": None}
            missing = True

        if new_time:
            fields["new_time"] = {"status": "provided", "value": new_time}
        else:
            fields["new_time"] = {"status": "missing", "value": None}
            missing = True

        if missing:
            return {
                "status": "needs_reschedule_input",
                "fields": fields
            }

        if new_date == exam.get("date") and new_time == exam.get("time"):
            return {
                "status": "validation_failed",
                "message": "New date and time must be different from the current schedule."
            }

        # Date passed validation
        try:
            exam_date_obj = datetime.strptime(new_date, "%Y-%m-%d").date()
            if exam_date_obj < datetime.now().date():
                return {
                    "status": "validation_failed",
                    "message": "The selected date has already passed. Please choose a future date."
                }
        except ValueError:
            return {
                "status": "validation_failed",
                "message": "Invalid date. Please use YYYY-MM-DD format."
            }

        # Mocked availability check (same as check_conflicts)
        seat_check = self._check_seat_availability(new_date)
        if seat_check:
            return seat_check

        return {
            "status": "success",
            "message": "The new date and time are valid and available."
        }