from unittest.mock import MagicMock
from pathlib import Path
import sys

SERVER_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER_DIR))

from tools.student_search_tool import StudentSearchTool

def test_student_search_mock():
    tool = StudentSearchTool()
    
    mock_collection = MagicMock()
    mock_collection.find.return_value.limit.return_value = [
        {
            "academicNo": "S101", 
            "name": {"first": "Alice", "middle": "M.", "last": "Smith"}, 
            "gender": "Female", 
            "username": "alice@example.com"
        }
    ]
    mock_client = MagicMock()
    mock_client.__getitem__.return_value.__getitem__.return_value = mock_collection
    tool._client = mock_client

    result = tool.execute(query="Alice")
    assert "result" in result
    assert "Alice M. Smith" in result["result"]
    print("Mock Test passed! Result:\n", result["result"])


if __name__ == "__main__":
    test_student_search_mock()


