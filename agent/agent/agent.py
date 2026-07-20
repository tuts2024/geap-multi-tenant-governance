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
from google.genai import types as genai_types
from google.cloud import datastore
import json
from . import config
from .tools import build_drive_tools, build_spotify_tools, build_confluence_tools

INSTRUCTION = """\
You are a contract analyst assistant. You help the current user review and \
analyze contracts stored in their own Google Drive. You also have access to Spotify tools to fetch the user's private playlists to demonstrate 3-legged OAuth (3LO) capabilities, and Confluence tools to search wiki pages for contract documentation.

Rules:
- Only ever search and read documents belonging to the CURRENTLY LOGGED-IN \
  user. You have no ability to access any other customer's documents, and \
  you must never claim otherwise or attempt to bypass this.
- When asked to analyze a contract or list files, you MUST use the `search_contract_documents` tool to find the files first.
- To read the content of a file, you MUST use the `fetch_document_text` tool.
- Do not assume file contents or existence without calling tools.
- Cite which Drive file name each finding comes from.
- If the user asks about Spotify or wants to see their playlists, call your Spotify playlist tool.
- If the user asks about Confluence or wants to search wiki pages, call your Confluence search pages tool. To read the full text of a page, call your Confluence get page content tool.
"""


async def before_model_callback(callback_context, llm_request):
    """
    ADK runtime callback to dynamically inject tenant-specific model configurations 
    and thinking token budgets directly into the LLM request at execution time.
    """
    session = callback_context.session
    user_id = getattr(session, "user_id", "unknown")
    print(f"[ADK_CALLBACK] 🔄 Intercepted LLM request for User ID: {user_id}", flush=True)
    
    # Default agent URN to look up
    agent_urn = None
    
    # Safely inspect the latest user message to see if it carries an agent URN envelope
    if hasattr(llm_request, "contents") and llm_request.contents:
        try:
            latest_content = llm_request.contents[-1]
            if hasattr(latest_content, "parts") and latest_content.parts and latest_content.parts[0].text:
                text = latest_content.parts[0].text
                if text.startswith("[agent_urn:"):
                    end_idx = text.find("]")
                    if end_idx != -1:
                        agent_urn = text[11:end_idx].strip()
                        # Clean the message so the LLM doesn't see the technical envelope
                        latest_content.parts[0].text = text[end_idx+1:].strip()
                        print(f"[ADK_CALLBACK] 📨 Parsed dynamic agent URN envelope: '{agent_urn}'", flush=True)
        except Exception as e:
            print(f"[ADK_CALLBACK] Warning parsing message envelope: {e}", flush=True)

    print("[ADK_CALLBACK] >>> Entering before_model_callback (Depth 2)", flush=True)
    try:
        user_id = callback_context.state.get("user_id")
        
        # Connect to Datastore to fetch latest tenant self-service configurations
        client = datastore.Client(project=config.PROJECT_ID)
        
        entity = None
        if agent_urn:
            key = client.key("Agent", agent_urn)
            entity = client.get(key)
            print(f"[ADK_CALLBACK] 📡 Dispatching dynamic Datastore lookup for URN: {agent_urn}", flush=True)
        else:
            query = client.query(kind="Agent")
            query.add_filter("agent_name", "=", "Contract Analyst Agent")
            results = list(query.fetch(limit=1))
            if results:
                entity = results[0]
            print("[ADK_CALLBACK] 📡 Dispatching default Datastore lookup for Contract Analyst Agent", flush=True)
        
        if entity:
            model_config = entity.get("model_config")
            thinking_enabled = entity.get("thinking_enabled")
            thinking_tokens = entity.get("thinking_tokens")
            tenant_overrides_val = entity.get("tenant_overrides")
            
            # Resolve tenant name from user ID dynamically via Datastore
            tenant_name = None
            try:
                user_key = client.key("UserConfiguration", user_id)
                user_config = client.get(user_key)
                if user_config and user_config.get("tenant_name"):
                    tenant_name = user_config.get("tenant_name")
                    print(f"[ADK_CALLBACK] Resolved Tenant Name: {tenant_name} for User ID: {user_id}", flush=True)
                else:
                    print(f"[ADK_CALLBACK] [WARNING] Unknown User ID: {user_id}. Blocking access or using generic sandbox.", flush=True)
                    # For strict isolation, you could raise an exception here:
                    # raise ValueError(f"Access Denied: Unrecognized User ID {user_id}")
                    tenant_name = "Generic Sandbox" # Safe fallback or stop execution
            except Exception as e:
                print(f"[ADK_CALLBACK] Error resolving tenant name from Datastore: {e}", flush=True)
                tenant_name = "Generic Sandbox" # Safe fallback on error
            
            custom_instruction = None
            if tenant_overrides_val:
                try:
                    overrides_dict = json.loads(tenant_overrides_val)
                    tenant_specific = overrides_dict.get(tenant_name, {})
                    custom_instruction = tenant_specific.get("custom_instruction")
                    if "model_config" in tenant_specific:
                        model_config = tenant_specific["model_config"]
                    if "thinking_enabled" in tenant_specific:
                        thinking_enabled = tenant_specific["thinking_enabled"]
                    if "thinking_tokens" in tenant_specific:
                        thinking_tokens = tenant_specific["thinking_tokens"]
                except Exception as e:
                    print(f"[ADK_CALLBACK] Error parsing tenant overrides JSON: {e}", flush=True)

            # Map user-friendly model configs to official model strings
            model_mapping = {
                "Claude 3.5 Sonnet": "anthropic/claude-sonnet-4-20250514",
                "Gemini 2.5 Pro": "gemini-2.5-pro",
                "Gemini 2.5 Flash": "gemini-2.5-flash",
                "Gemini 3.0 Enterprise (Thinking 8k)": "gemini-2.5-pro"
            }
            
            official_model = model_mapping.get(model_config, model_config)
            
            # Override model
            if official_model:
                llm_request.model = official_model
                
            # Override thinking budget
            if thinking_enabled and thinking_tokens:
                try:
                    budget_val = int(thinking_tokens.split()[0].replace(",", ""))
                    if not llm_request.config:
                        llm_request.config = genai_types.GenerateContentConfig()
                    llm_request.config.thinking_config = genai_types.ThinkingConfig(
                        thinking_budget=budget_val
                    )
                except Exception as e:
                    print(f"[ADK_CALLBACK] Warning parsing thinking budget: {e}", flush=True)
            elif thinking_enabled is False:
                if llm_request.config:
                    llm_request.config.thinking_config = None
            
            # Override system instructions (custom tenant skill prompt)
            if custom_instruction:
                if not llm_request.config:
                    llm_request.config = genai_types.GenerateContentConfig()
                llm_request.config.system_instruction = custom_instruction
                print(f"[ADK_CALLBACK] 💡 Dynamic Skill Instruction Override Enforced for {tenant_name}: '{custom_instruction}'", flush=True)
                    
            print(f"[ADK_CALLBACK] 🧠 Dynamic Model Override Enforced: Model='{llm_request.model}' | Thinking Budget='{thinking_tokens}'", flush=True)
    except Exception as e:
        import traceback
        print(f"[ADK_CALLBACK] ❌ Error in before_model_callback (Depth 3): {e}", flush=True)
        traceback.print_exc()


root_agent = Agent(
    model=config.GEMINI_MODEL,
    name="contract_analyst_agent",
    instruction=INSTRUCTION,
    tools=[*build_drive_tools(), *build_spotify_tools(), *build_confluence_tools()],
    before_model_callback=before_model_callback,
)
