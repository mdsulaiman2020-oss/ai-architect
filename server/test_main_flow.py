import asyncio
import json
import logging
import sys
from pymongo import MongoClient

# Reconfigure stdout to use UTF-8 to prevent Windows terminal encoding crashes
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from provider import get_provider
from session import MongoSessionStore
from tools.registry import ToolRegistry
from tools.select_course_tool import SelectCourseTool
from agents.assessment.assessment_agent import RunAssessmentAgentTool
from runtime import Runtime
from config import Config

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

async def test_main_flow():
    # 1. Setup session store and database
    sessions = MongoSessionStore()
    session_id = "test_main_session"
    
    # Reset session for clean run
    sessions.reset(session_id)
    session = sessions.get_or_create(session_id)
    
    # 2. Setup tools registry
    registry = ToolRegistry()
    registry.register(SelectCourseTool())
    registry.register(RunAssessmentAgentTool())
    
    # 3. Setup runtime
    provider = get_provider()
    runtime = Runtime(provider, session, registry)
    
    # --- TURN 1: Normal User Query ---
    user_prompt_1 = "Hi! Can you briefly explain what assessment validation means in education?"
    print(f"\n[TURN 1 - USER] Sending message: {user_prompt_1}\n")
    session.add_user_message(user_prompt_1)
    sessions.save(session)
    
    print("[TURN 1 - MAIN AGENT] Running provider loop...")
    response_1, metadata_1 = await runtime.call_provider()
    session.add_assistant_message(response_1.text, metadata=metadata_1)
    sessions.save(session)
    
    print(f"[TURN 1 - MAIN AGENT] Response: {response_1.text}\n")
    print("-" * 50)
    
    # Wait for rate limit safety before Turn 2
    print("Waiting 12s for rate limit safety...")
    await asyncio.sleep(12)
    
    # --- TURN 2: Assessment Query ---
    user_prompt_2 = (
        "Awesome. Now run the assessment agent to validate topics and learning outcomes "
        "for the course 'DOS 326'. Please return the validation report."
    )
    print(f"\n[TURN 2 - USER] Sending message: {user_prompt_2}\n")
    session.add_user_message(user_prompt_2)
    sessions.save(session)
    
    print("[TURN 2 - MAIN AGENT] Running provider loop (this will delegate to assessment agent)...")
    response_2, metadata_2 = await runtime.call_provider()
    session.add_assistant_message(response_2.text, metadata=metadata_2)
    sessions.save(session)
    
    print("\n[TURN 2 - MAIN AGENT] Finished! Final Response:\n")
    print(response_2.text)
    print("\n" + "="*50 + "\n")
    
    # 6. Fetch directly from MongoDB to verify nesting
    print("[DATABASE] Querying MongoDB to verify the nested structure...")
    client = MongoClient(Config.MONGODB_URI)
    db = client[Config.MONGODB_DB_NAME]
    doc = db["agent_sessions"].find_one({"session_id": session_id})
    
    if not doc:
        print("[ERROR] No session document found in MongoDB.")
        return
        
    print("\nVerified Session Document in DB:")
    # We will print the messages, showing the nested children of the run_assessment_agent tool_call
    for msg in doc.get("messages", []):
        role = msg.get("role")
        tool_name = msg.get("tool_name", "")
        print(f"\n- Role: {role} | Tool Name: {tool_name}")
        
        # If there are children, show them nested
        if "children" in msg and msg["children"]:
            print(f"  +-- Contains {len(msg['children'])} nested children messages:")
            for child in msg["children"]:
                child_role = child.get("role")
                child_tool = child.get("tool_name", "")
                child_content = (child.get("content") or "")[:80].replace('\n', ' ')
                print(f"     |-- [{child_role}] {child_tool}: {child_content}...")
                
if __name__ == "__main__":
    asyncio.run(test_main_flow())
