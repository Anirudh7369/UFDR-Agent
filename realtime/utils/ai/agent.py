from __future__ import annotations

import os
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

from agents import Agent, Runner
from agents.extensions.models.litellm_model import LitellmModel
from utils.prompts.Forensic_agent import forensic_agent_instructions
from tools.location import location_tool
from tools.apps import app_tool
from tools.call_logs import call_log_tool
from tools.messages import message_tool
from tools.browsing_history import browsing_history_tool
from tools.contacts import contact_tool
from tools.case import case_tool

load_dotenv()

class ForensicAgent:
    def __init__(self):
        """
        Initialize the Forensic Agent with Gemini model via LiteLLM.
        Uses environment variables for API key and model configuration.
        """
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.model = os.getenv("GEMINI_MODEL", "gemini/gemini-1.5-flash")

        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")

        # Debug: Print tool information
        print("=" * 80)
        print("FORENSIC AGENT INITIALIZATION")
        print("=" * 80)
        print(f"Tools being added:")
        print(f"  1. {location_tool.name} - {location_tool.description}")
        print(f"  2. {app_tool.name} - {app_tool.description}")
        print(f"  3. {call_log_tool.name} - {call_log_tool.description}")
        print(f"  4. {message_tool.name} - {message_tool.description}")
        print(f"  5. {browsing_history_tool.name} - {browsing_history_tool.description}")
        print(f"  6. {contact_tool.name} - {contact_tool.description}")
        print(f"  7. {case_tool.name} - {case_tool.description}")
        print("=" * 80)

        self.agent = Agent(
            name="ForensicAnalyst",
            instructions=forensic_agent_instructions,
            model=LitellmModel(model=self.model, api_key=self.api_key),
            tools=[location_tool, app_tool, call_log_tool, message_tool, browsing_history_tool, contact_tool, case_tool],
        )

        # Debug: Verify tools were added
        print(f"Agent created with {len(self.agent.tools) if hasattr(self.agent, 'tools') else 'unknown'} tools")
        print("=" * 80)

    async def analyze_forensic_data(
        self,
        user_query: str,
        chat_history: str = "",
        data_chunks: Optional[List[str]] = None
    ) -> tuple[str, List[Dict[str, Any]]]:
        """
        Process a forensic query by analyzing provided UFDR report data chunks.

        Args:
            user_query: The investigator's question
            chat_history: Prior conversation for context
            data_chunks: Optional list of UFDR report data chunks to analyze

        Returns:
            Tuple of (agent's forensic analysis response, list of tool executions)
        """
        if data_chunks is None:
            data_chunks = []

        # Build a structured prompt so chat history is actually used
        sections: List[str] = []
        if chat_history:
            sections.append(
                "Prior Chat Context (use this for follow-ups, pronouns, and continuity):\n"
                + chat_history
            )
        sections.append("Current User Query:\n" + user_query)
        sections.append(f"Forensic Data Summary: {len(data_chunks)} data chunks available for analysis.")

        query_with_context = "\n\n".join(sections)

        result = await Runner.run(self.agent, query_with_context)

        # Debug: Print result structure
        print("\n" + "=" * 80)
        print("🔍 RUNNER RESULT DEBUG")
        print("=" * 80)
        print(f"Result type: {type(result)}")
        print(f"Result attributes: {dir(result)}")
        print(f"Has messages: {hasattr(result, 'messages')}")
        print(f"Has final_output: {hasattr(result, 'final_output')}")

        # Extract tool execution details from the result
        tool_executions = []

        if hasattr(result, 'messages'):
            print(f"Messages count: {len(result.messages)}")
            for i, message in enumerate(result.messages):
                print(f"\n--- Message {i} ---")
                print(f"Message type: {type(message)}")
                print(f"Message attributes: {dir(message)}")
                print(f"Has tool_calls: {hasattr(message, 'tool_calls')}")
                print(f"Has tool_result: {hasattr(message, 'tool_result')}")

                if hasattr(message, 'tool_calls') and message.tool_calls:
                    print(f"Tool calls count: {len(message.tool_calls)}")
                    for tool_call in message.tool_calls:
                        print(f"  Tool call type: {type(tool_call)}")
                        print(f"  Tool call attributes: {dir(tool_call)}")
                        tool_exec = {
                            "tool_name": tool_call.name if hasattr(tool_call, 'name') else "unknown",
                            "tool_input": tool_call.arguments if hasattr(tool_call, 'arguments') else {},
                            "tool_call_id": tool_call.id if hasattr(tool_call, 'id') else None
                        }
                        tool_executions.append(tool_exec)
                        print(f"  Extracted: {tool_exec}")

                # Match tool outputs to tool calls
                if hasattr(message, 'tool_result'):
                    print(f"Tool result found: {message.tool_result}")
                    for exec_item in tool_executions:
                        if exec_item.get('tool_call_id') == getattr(message.tool_result, 'tool_call_id', None):
                            exec_item['tool_output'] = getattr(message.tool_result, 'output', None)
        else:
            print("No messages attribute found in result")

        print(f"\nTotal tool executions extracted: {len(tool_executions)}")
        print("=" * 80 + "\n")

        return result.final_output, tool_executions


async def create_forensic_agent() -> ForensicAgent:
    """
    Factory function to create a ForensicAgent instance.

    Returns:
        Configured ForensicAgent instance
    """
    return ForensicAgent()
