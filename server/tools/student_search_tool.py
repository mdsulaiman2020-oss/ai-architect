import re
from pymongo import MongoClient
from tools.base import Tool
from config import Config

class StudentSearchTool(Tool):
    def __init__(self):
        self._client = None

    @property
    def client(self) -> MongoClient:
        if self._client is None:
            self._client = MongoClient(
                Config.MONGODB_URI,
                serverSelectionTimeoutMS=2000
            )
        return self._client

    @property
    def name(self) -> str:
        return "student_search"

    @property
    def description(self) -> str:
        return "Search for student records in MongoDB by name or student ID."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The student name or student ID to search for."
                },
            },
            "required": ["query"],
        }

    def execute(self, **args) -> dict:
        query_str = args.get("query", "").strip()
        if not query_str:
            return {"error": "Please provide a query."}

        try:
            db = self.client[Config.MONGODB_DB_NAME]
            collection = db["users_old"]

            safe_query = re.escape(query_str)
            regex = {"$regex": safe_query, "$options": "i"}

            cursor = collection.find({
                "$or": [
                    {"name.first": regex},
                    {"name.middle": regex},
                    {"name.last": regex},
                    {"name": regex},
                    {"academicNo": regex}
                ]
            }, {'username': 1, 'gender': 1, 'academicNo': 1, 'name': 1}).limit(10)

            results = list(cursor)

            if not results:
                return {"result": "No results found."}

            formatted_results = []
            for s in results:
                name_val = s.get('name')
                if isinstance(name_val, dict):
                    full_name = " ".join(filter(None, [
                        name_val.get('first', '').strip(),
                        name_val.get('middle', '').strip(),
                        name_val.get('last', '').strip()
                    ])) or "N/A"
                elif isinstance(name_val, str):
                    full_name = name_val.strip() or "N/A"
                else:
                    full_name = "N/A"

                formatted_results.append(
                    f"ID: {s.get('academicNo', 'N/A')}, Name: {full_name}, Gender: {s.get('gender', 'N/A')}, Email: {s.get('username', 'N/A')}"
                )
            return {"result": "\n".join(formatted_results)}

        except Exception as e:
            return {"error": f"MongoDB query error: {str(e)}"}

