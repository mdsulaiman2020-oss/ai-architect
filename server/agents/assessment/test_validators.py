from agents.assessment.assessment_agent import AssessmentAgent
import asyncio
import json
import sys

# Reconfigure stdout to use UTF-8 to prevent Windows terminal encoding crashes
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

async def test_agent():
    print("Initializing Assessment Agent...")
    agent = AssessmentAgent()
    
    print("\nRequesting full assessment validation for 'DOS 326 Pre-Clinical Oral Surgery'...\n")
    result = await agent.process(
        course_name="DOS 326 Pre-Clinical Oral Surgery", 
        task="Validate both topics and learning outcomes. Please give me a detailed markdown report."
    )
    
    report_text = result["text"]
    sub_agent_messages = result["_sub_agent_messages"]
    
    print("=================== AGENT REPORT ===================")
    print(report_text)
    print("====================================================\n")
    
    print("=========== SUB-AGENT INTERNAL MESSAGES =============")
    for msg in sub_agent_messages:
        role = msg.role
        name = msg.tool_name or ""
        content_preview = (msg.content or "")[:120]
        print(f"  [{role}] {name}: {content_preview}...")
    print("====================================================")

if __name__ == "__main__":
    asyncio.run(test_agent())
