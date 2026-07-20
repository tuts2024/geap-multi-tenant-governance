#!/usr/bin/env python3
"""
Step 2: Deploy Shared Agent — Verification Runner
Demonstrates that both Customer A (Acme Legal) and Customer B (Beta Corp)
can see and invoke the operator-level shared Contract Analyst Agent from their respective contexts.

Each tenant interacts with the agent using their own identity and their own data —
the agent itself is shared, but every invocation is strictly scoped to the calling tenant.
"""

import sys
import os
import json
import logging

# Add workspace directory to Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from contract_analyst_agent.agent import fetch_google_drive_contracts, search_confluence_cloud


class MockTenantToolContext:
    """Simulates per-tenant runtime ToolContext injection during shared agent inference."""
    def __init__(self, tenant_principal: str):
        self.principal = tenant_principal


def verify_shared_agent_tenancy():
    print("==============================================================================")
    print("STEP 2: DEPLOY SHARED AGENT — TENANCY & CONNECTOR VERIFICATION")
    print("Agent: Contract Analyst Agent (Shared / Operator-owned)")
    print("==============================================================================\n")

    tenants = [
        {"name": "Customer A (Acme Legal)", "principal": "tenant-user-a@acmelegal.com", "storage": "Google Drive (Workspace MCP)"},
        {"name": "Customer B (Beta Corp)", "principal": "tenant-user-b@betacorp.com", "storage": "Confluence Cloud (Custom MCP)"}
    ]

    for t in tenants:
        print(f"++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
        print(f"INVOCATION CONTEXT: {t['name']} [{t['principal']}]")
        print(f"++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
        
        ctx = MockTenantToolContext(tenant_principal=t["principal"])

        print(f"\n--- 1. Executing Primary Connector: Google Drive (Workspace MCP) ---")
        print(f"Auth Mode: Implicit (User's existing session; no separate login required)")
        gdrive_res = fetch_google_drive_contracts(tool_context=ctx, query="indemnity and liability cap")
        print(f"Extracted Payload:\n{gdrive_res}")
        
        # Verify strict scoping
        payload = json.loads(gdrive_res)
        assert payload["tenant_context"] == t["principal"], "Data leakage detected in Google Drive connector!"
        print(f"[✓ PASS] Google Drive connector successfully scoped exactly to {t['name']}.")

        print(f"\n--- 2. Executing Supplementary Connector: Confluence (Custom MCP) ---")
        print(f"Auth Mode: Delegated OAuth 2.0 (Confluence)")
        confluence_res = search_confluence_cloud(tool_context=ctx, search_term="payment terms and termination playbook")
        print(f"Extracted Payload:\n{confluence_res}")
        
        payload = json.loads(confluence_res)
        assert payload["tenant_context"] == t["principal"], "Data leakage detected in Confluence connector!"
        print(f"[✓ PASS] Confluence connector successfully scoped exactly to {t['name']}.\n")

    print("==============================================================================")
    print("[✓ SUCCESS] Shared Contract Analyst Agent successfully verified for both tenants.")
    print("==============================================================================")


if __name__ == "__main__":
    verify_shared_agent_tenancy()
