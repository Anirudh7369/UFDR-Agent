from __future__ import annotations

import os
from typing import Optional, List
from dotenv import load_dotenv

from agents import Agent, Runner
from agents.extensions.models.litellm_model import LitellmModel
from utils.prompts.Forensic_agent import forensic_agent_instructions

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
        
        self.agent = Agent(
            name="ForensicAnalyst",
            instructions=forensic_agent_instructions,
            model=LitellmModel(model=self.model, api_key=self.api_key),
            tools=[],
        )
    
    async def analyze_forensic_data(self, user_query: str, data_chunks: Optional[List[str]] = None) -> str:
        """
        Process a forensic query by analyzing provided UFDR report data chunks.
        
        Args:
            user_query: The investigator's question
            data_chunks: Optional list of UFDR report data chunks to analyze
            
        Returns:
            The agent's forensic analysis response
        """
        if data_chunks is None:
            data_chunks = []
        
        # Prepare the query with forensic data context
        query_with_context = f"Query: {user_query}\nForensic Data: {len(data_chunks)} data chunks available for analysis"
        
        result = await Runner.run(self.agent, query_with_context)
        return result.final_output


async def create_forensic_agent() -> ForensicAgent:
    """
    Factory function to create a ForensicAgent instance.
    
    Returns:
        Configured ForensicAgent instance
    """
    return ForensicAgent()