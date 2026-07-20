"""
The contract analyst agent.

This agent is intentionally tenant-agnostic: there is exactly one Agent
definition, used for both Customer A and Customer B. Per-customer isolation
is enforced entirely at the tool layer (drive_tool.py), where Agent
Identity resolves a credential scoped to the active session's authenticated
user - never to a value embedded in the prompt.

Operator responsibility: build and `adk deploy` this agent once.
Customer responsibility: nothing here - they only interact via the
frontend, which creates a session under their own user_id.

NOTE: Confluence support has been removed for now. The repo previously
included a confluence_tool.py and a second 3LO auth provider for it - see
git history if you want to bring it back. Removing it meant: deleting
tools/confluence_tool.py, dropping CONFLUENCE_AUTH_PROVIDER from config.py,
and removing the confluence-3lo auth provider / binding from the setup
scripts (setup/02-04).
"""

from google.adk.agents import Agent
from . import config
from .tools import build_drive_tools

INSTRUCTION = """\
You are a contract analyst assistant. You help the current user review and \
analyze contracts stored in their own Google Drive.

Rules:
- Only ever search and read documents belonging to the CURRENTLY LOGGED-IN \
  user. You have no ability to access any other customer's documents, and \
  you must never claim otherwise or attempt to bypass this.
- When asked to analyze a contract, first search Drive for relevant \
  documents, fetch the full text of the most relevant ones, then \
  summarize: parties involved, key obligations, term/renewal dates, \
  termination clauses, and any unusual or risky clauses.
- If you can't find a requested document, say so plainly rather than \
  guessing at its contents.
- Cite which Drive file name each finding comes from.
"""

root_agent = Agent(
    model=config.GEMINI_MODEL,
    name="contract_analyst_agent",
    instruction=INSTRUCTION,
    tools=[*build_drive_tools()],
)
