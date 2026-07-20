from vertexai.agent_engines import AdkApp
from agent.agent import root_agent

agent = AdkApp(agent=root_agent, enable_tracing=True)
agent_runtime = agent
root_agent = agent
