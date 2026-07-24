from fastapi import HTTPException
import logging

logger = logging.getLogger(__name__)

class Runtime:
    def __init__(self, provider, session, registry):
        self.session = session
        self.provider = provider
        self.registry = registry

    def call_provider(self):
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
                response = self.provider.generate(self.session, tools=self.registry.list_tools())
            except Exception:
                logger.exception("Failed to generate response")
                raise HTTPException(status_code=500, detail="Failed to generate response")

            # Accumulate metadata
            total_latency_ms += response.latency_ms
            total_prompt_tokens += response.prompt_tokens
            total_candidates_tokens += response.candidates_tokens
            total_total_tokens += response.total_tokens
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
            for fc in response.function_calls:
                logger.info(f"Executing tool call: {fc.name} (id: {fc.id}) with args {fc.args}")
                try:
                    result = self.registry.execute(fc.name, **fc.args)
                except Exception as e:
                    logger.error(f"Error executing tool {fc.name}: {e}")
                    result = f"Error: {e}"
                
                tool_calls.append(fc)
                tool_results.append((fc.id, fc.name, str(result)))
            
            # Add all tool calls to session first
            for fc in tool_calls:
                self.session.add_tool_call_message(
                    tool_name=fc.name,
                    tool_call_id=fc.id,
                    args=fc.args,
                    thought_signature=fc.thought_signature
                )
            
            # Add all tool results to session next
            for fc_id, name, res in tool_results:
                self.session.add_tool_result_message(
                    tool_call_id=fc_id,
                    tool_name=name,
                    content=res
                )

        raise HTTPException(
            status_code=500,
            detail="Tool execution loop exceeded maximum allowed iterations"
        )