import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

SERVER_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER_DIR))

from session import ConversationSession
from response import LLMResponse, ToolCall
from providers.open_ai import OpenAIProvider

def test_openai_provider_generate_text():
    # Mock the OpenAI client
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_message = MagicMock()
    mock_usage = MagicMock()

    mock_message.content = "Hello, world!"
    mock_message.tool_calls = None
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    mock_usage.prompt_tokens = 10
    mock_usage.completion_tokens = 5
    mock_usage.total_tokens = 15
    mock_response.usage = mock_usage

    mock_client.chat.completions.create.return_value = mock_response

    with patch("providers.open_ai.OpenAI", return_value=mock_client):
        provider = OpenAIProvider(api_key="fake-key", model_name="gpt-4o-mini")
        
        session = ConversationSession(session_id="test_sess")
        session.add_user_message("Hi")
        
        response = provider.generate(session)
        
        assert response.text == "Hello, world!"
        assert response.prompt_tokens == 10
        assert response.candidates_tokens == 5
        assert response.total_tokens == 15
        assert response.model_name == "gpt-4o-mini"
        assert response.function_calls is None

        # Verify client arguments
        mock_client.chat.completions.create.assert_called_once_with(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Hi"}]
        )
        print("test_openai_provider_generate_text: PASSED")

def test_openai_provider_generate_tool_call():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_message = MagicMock()
    mock_usage = MagicMock()

    mock_message.content = None
    
    # Mock OpenAI tool call object
    mock_tool_call = MagicMock()
    mock_tool_call.type = "function"
    mock_tool_call.id = "call_abc123"
    mock_tool_call.function.name = "add"
    mock_tool_call.function.arguments = '{"a": 2, "b": 3}'
    
    mock_message.tool_calls = [mock_tool_call]
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    mock_response.usage = None

    mock_client.chat.completions.create.return_value = mock_response

    with patch("providers.open_ai.OpenAI", return_value=mock_client):
        provider = OpenAIProvider(api_key="fake-key", model_name="gpt-4o-mini")
        
        session = ConversationSession(session_id="test_sess")
        session.add_user_message("Compute 2+3")
        
        tools = [{
            "name": "add",
            "description": "Add numbers",
            "parameters": {
                "type": "object",
                "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
                "required": ["a", "b"]
            }
        }]
        
        response = provider.generate(session, tools=tools)
        
        assert response.text == ""
        assert len(response.function_calls) == 1
        assert response.function_calls[0].name == "add"
        assert response.function_calls[0].args == {"a": 2, "b": 3}
        assert response.function_calls[0].id == "call_abc123"

        # Verify client arguments had mapped tools
        mock_client.chat.completions.create.assert_called_once_with(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Compute 2+3"}],
            tools=[{
                "type": "function",
                "function": {
                    "name": "add",
                    "description": "Add numbers",
                    "parameters": {
                        "type": "object",
                        "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
                        "required": ["a", "b"]
                    }
                }
            }]
        )
        print("test_openai_provider_generate_tool_call: PASSED")

def test_openai_provider_message_translation():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_message = MagicMock()
    
    mock_message.content = "Done"
    mock_message.tool_calls = None
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    mock_response.usage = None
    mock_client.chat.completions.create.return_value = mock_response

    with patch("providers.open_ai.OpenAI", return_value=mock_client):
        provider = OpenAIProvider(api_key="fake-key", model_name="gpt-4o-mini")
        
        session = ConversationSession(session_id="test_sess")
        session.add_user_message("Hello")
        # Contiguous tool calls
        session.add_tool_call_message(tool_name="add", tool_call_id="call_1", args={"a": 1, "b": 2})
        session.add_tool_call_message(tool_name="multiply", tool_call_id="call_2", args={"a": 3, "b": 4})
        # Tool results
        session.add_tool_result_message(tool_call_id="call_1", tool_name="add", content='{"result": 3}')
        session.add_tool_result_message(tool_call_id="call_2", tool_name="multiply", content='{"result": 12}')
        
        provider.generate(session)
        
        # Verify message mapping
        expected_messages = [
            {"role": "user", "content": "Hello"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "add", "arguments": '{"a": 1, "b": 2}'}
                    },
                    {
                        "id": "call_2",
                        "type": "function",
                        "function": {"name": "multiply", "arguments": '{"a": 3, "b": 4}'}
                    }
                ]
            },
            {"role": "tool", "tool_call_id": "call_1", "name": "add", "content": '{"result": 3}'},
            {"role": "tool", "tool_call_id": "call_2", "name": "multiply", "content": '{"result": 12}'}
        ]
        
        mock_client.chat.completions.create.assert_called_once_with(
            model="gpt-4o-mini",
            messages=expected_messages
        )
        print("test_openai_provider_message_translation: PASSED")

if __name__ == "__main__":
    test_openai_provider_generate_text()
    test_openai_provider_generate_tool_call()
    test_openai_provider_message_translation()
    print("All OpenAIProvider tests passed!")
