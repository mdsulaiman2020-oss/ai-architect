from fastapi import HTTPException
import logging
import json
import inspect

logger = logging.getLogger(__name__)

class Runtime:
    def __init__(self, provider, session, registry):
        self.session = session
        self.provider = provider
        self.registry = registry

    async def call_provider(self):
        # Accumulate stats
        total_latency_ms = 0.0
        total_prompt_tokens = 0
        total_candidates_tokens = 0
        total_total_tokens = 0
        used_model_name = ""

        max_iterations = 5
        iterations = 0

        while iterations < max_iterations:
            iterations += 1
            try:
                response = await self.provider.generate(self.session, tools=self.registry.list_tools())
            except Exception:
                logger.exception("Failed to generate response")
                raise HTTPException(status_code=500, detail="Failed to generate response")

            # Accumulate metadata
            total_latency_ms += response.latency_ms or 0.0
            total_prompt_tokens += response.prompt_tokens or 0
            total_candidates_tokens += response.candidates_tokens or 0
            total_total_tokens += response.total_tokens or 0
            used_model_name = response.model_name

            # If there are no tool calls, we're done
            if not response.function_calls:
                metadata = {
                    "latency_ms": total_latency_ms,
                    "prompt_tokens": total_prompt_tokens,
                    "candidates_tokens": total_candidates_tokens,
                    "total_tokens": total_total_tokens,
                    "model_name": used_model_name,
                }
                return response, metadata

            # Collect tool calls and run executions
            tool_calls = []
            tool_results = []
            client_side_tool_called = False
            client_side_fc = None
            
            for fc in response.function_calls:
                tool_calls.append(fc)
                tool = self.registry._tools.get(fc.name)
                if tool and getattr(tool, 'is_client_side', False):
                    logger.info(f"Client-side tool call requested: {fc.name} (id: {fc.id})")
                    client_side_tool_called = True
                    client_side_fc = fc
                    break
                    
                logger.info(f"Executing tool call: {fc.name} (id: {fc.id}) with args {fc.args}")
                try:
                    res = self.registry.execute(fc.name, **fc.args, _context_session_id=self.session.session_id)
                    if inspect.iscoroutine(res):
                        result = await res
                    else:
                        result = res
                except Exception as e:
                    logger.error(f"Error executing tool {fc.name}: {e}")
                    result = "An internal server error occurred during tool execution. Please inform the user gracefully without revealing technical details."
                
                if isinstance(result, dict) and result.get("status") == "needs_schedule_input":
                    logger.info(f"Dynamic UI requested by tool: {fc.name} (id: {fc.id})")
                    client_side_tool_called = True
                    client_side_fc = fc
                    fc.args.update(result)
                    break

                # Check if the result contains sub-agent messages to nest as children
                children = None
                if isinstance(result, dict) and "_sub_agent_messages" in result:
                    children = result["_sub_agent_messages"]
                    result_text = str(result.get("text", ""))
                else:
                    result_text = str(result)
                
                tool_results.append((fc.id, fc.name, result_text, children))
            
            # Build a lookup of children by tool_call_id
            children_map = {}
            for fc_id, name, res_text, children in tool_results:
                if children:
                    children_map[fc_id] = children
            
            # Add all tool calls to session first (with children if any)
            for fc in tool_calls:
                self.session.add_tool_call_message(
                    tool_name=fc.name,
                    tool_call_id=fc.id,
                    args=fc.args,
                    thought_signature=fc.thought_signature,
                    children=children_map.get(fc.id)
                )
            
            # Add all tool results to session next
            for fc_id, name, res, children in tool_results:
                self.session.add_tool_result_message(
                    tool_call_id=fc_id,
                    tool_name=name,
                    content=res
                )
                
            if client_side_tool_called:
                metadata = {
                    "latency_ms": total_latency_ms,
                    "prompt_tokens": total_prompt_tokens,
                    "candidates_tokens": total_candidates_tokens,
                    "total_tokens": total_total_tokens,
                    "model_name": used_model_name,
                    "ui_event": True,
                    "tool_call_id": client_side_fc.id,
                    "tool_name": client_side_fc.name,
                    "tool_args": client_side_fc.args
                }
                return response, metadata

        raise HTTPException(
            status_code=500,
            detail="Tool execution loop exceeded maximum allowed iterations"
        )

    async def call_provider_stream(self):
        max_iterations = 5
        iterations = 0
        
        while iterations < max_iterations:
            iterations += 1
            has_tool_calls = False
            tool_calls = []
            
            try:
                # Consume the provider's generator
                async for chunk in self.provider.generate_stream(self.session, tools=self.registry.list_tools()):
                    if chunk["type"] == "text":
                        yield chunk["content"]
                    elif chunk["type"] == "tool_calls":
                        has_tool_calls = True
                        tool_calls = chunk["content"]
            except Exception:
                logger.exception("Failed to generate response stream")
                raise HTTPException(status_code=500, detail="Failed to generate response stream")
            
            if not has_tool_calls:
                return  # Streaming finished completely

            # Run tool executions
            tool_results = []
            client_side_tool_called = False
            client_side_fc = None
            
            for fc in tool_calls:
                tool = self.registry._tools.get(fc.name)
                if tool and getattr(tool, 'is_client_side', False):
                    logger.info(f"Client-side tool call requested (stream): {fc.name} (id: {fc.id})")
                    client_side_tool_called = True
                    client_side_fc = fc
                    # Since we append tool calls to the session down below, we still need to process this fc 
                    # but we won't execute it, and we will break.
                    break
                    
                logger.info(f"Executing tool call (stream): {fc.name} (id: {fc.id}) with args {fc.args}")
                try:
                    res = self.registry.execute(fc.name, **fc.args, _context_session_id=self.session.session_id)
                    if inspect.iscoroutine(res):
                        result = await res
                    else:
                        result = res
                except Exception as e:
                    logger.error(f"Error executing tool {fc.name}: {e}")
                    result = "An internal server error occurred during tool execution. Please inform the user gracefully without revealing technical details."
                
                if isinstance(result, dict):
                    print(f"DEBUG: Tool result for {fc.name}: {result.get('status')}")
                if isinstance(result, dict) and (result.get("status") == "needs_schedule_input" or result.get("status") == "needs_reschedule_input"):
                    logger.info(f"Dynamic UI requested by tool (stream): {fc.name} (id: {fc.id})")
                    client_side_tool_called = True
                    client_side_fc = fc
                    fc.args.update(result)
                    break

                # Check if the result contains sub-agent messages to nest as children
                children = None
                if isinstance(result, dict) and "_sub_agent_messages" in result:
                    children = result["_sub_agent_messages"]
                    result_text = str(result.get("text", ""))
                else:
                    result_text = str(result)
                
                tool_results.append((fc.id, fc.name, result_text, children))

            # Build a lookup of children by tool_call_id
            children_map = {}
            for fc_id, name, res_text, children in tool_results:
                if children:
                    children_map[fc_id] = children
            
            # Update session messages
            for fc in tool_calls:
                self.session.add_tool_call_message(
                    tool_name=fc.name, tool_call_id=fc.id, args=fc.args,
                    thought_signature=fc.thought_signature,
                    children=children_map.get(fc.id)
                )
            for fc_id, name, res, children in tool_results:
                self.session.add_tool_result_message(
                    tool_call_id=fc_id, tool_name=name, content=res
                )
                
            if client_side_tool_called:
                self.session.add_client_ui_message(
                    component=client_side_fc.name,
                    tool_call_id=client_side_fc.id,
                    args=client_side_fc.args
                )
                # Yield the special UI event
                yield {
                    "type": "ui",
                    "component": client_side_fc.name,
                    "tool_call_id": client_side_fc.id,
                    "args": client_side_fc.args
                }
                return # Stop streaming completely

        raise HTTPException(
            status_code=500,
            detail="Tool execution loop exceeded maximum allowed iterations in stream"
        )