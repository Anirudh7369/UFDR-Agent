from __future__ import annotations

import os
from typing import Optional, List
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
from tools.vector_search import vector_search_tool

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
        print(f"  7. {vector_search_tool.name} - {vector_search_tool.description}")
        print("=" * 80)

        self.agent = Agent(
            name="ForensicAnalyst",
            instructions=forensic_agent_instructions,
            model=LitellmModel(model=self.model, api_key=self.api_key),
            tools=[location_tool, app_tool, call_log_tool, message_tool, browsing_history_tool, contact_tool, vector_search_tool],
        )

        # Debug: Verify tools were added
        print(f"Agent created with {len(self.agent.tools) if hasattr(self.agent, 'tools') else 'unknown'} tools")
        print("=" * 80)

    async def analyze_forensic_data(
        self,
        user_query: str,
        chat_history: str = "",
        data_chunks: Optional[List[str]] = None
    ) -> str:
        """
        Process a forensic query by analyzing provided UFDR report data chunks.

        Args:
            user_query: The investigator's question
            chat_history: Prior conversation for context
            data_chunks: Optional list of UFDR report data chunks to analyze

        Returns:
            The agent's forensic analysis response
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
        return result.final_output


async def create_forensic_agent() -> ForensicAgent:
    """
    Factory function to create a ForensicAgent instance.

    Returns:
        Configured ForensicAgent instance
    """
    return ForensicAgent()
