from unittest.mock import MagicMock
from pathlib import Path
import sys

SERVER_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER_DIR))

from session import MongoSessionStore, ConversationSession

def test_mongo_session_store_mock():
    store = MongoSessionStore()
    
    mock_collection = MagicMock()
    mock_collection.find_one.return_value = None
    mock_client = MagicMock()
    mock_client.__getitem__.return_value.__getitem__.return_value = mock_collection
    store._client = mock_client

    # Get or create
    session = store.get_or_create("test-session-123")
    assert session.session_id == "test-session-123"
    
    # Save
    session.add_user_message("Hello")
    session.add_assistant_message("Hi there!")
    store.save(session)
    assert mock_collection.update_one.called
    print("MongoSessionStore Test Passed!")

if __name__ == "__main__":
    test_mongo_session_store_mock()
