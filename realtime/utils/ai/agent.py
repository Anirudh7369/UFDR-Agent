from agents import Agent
from ..prompts.Forensic_agent import forensic_agent_instructions


def get_agent(
    model
) -> Agent:
    """
    Create and return a Forensic Agent with specified model.
    
    Args:
        model: The model to use for the agent
        
    Returns:
        Agent: Configured Forensic Agent instance
    """
    return Agent(
        name="Forensic_agent",
        model=model,
        instructions=forensic_agent_instructions
    )