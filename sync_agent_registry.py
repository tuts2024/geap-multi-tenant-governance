import os
import json
import time
import vertexai
from vertexai import agent_engines
from google.cloud import bigquery
from google.cloud import datastore

# Configuration
PROJECT_ID = "acxiom-425322"
LOCATION = "us-central1"
DATASET_ID = "egnyte_demo"
TABLE_ID = "agent_platform_registry"

os.environ["GOOGLE_CLOUD_PROJECT"] = PROJECT_ID

# Initialize Clients
vertexai.init(project=PROJECT_ID, location=LOCATION)
bq_client = bigquery.Client(project=PROJECT_ID)
ds_client = datastore.Client(project=PROJECT_ID)

def get_live_engines():
    print("[1] Fetching live Reasoning Engines from GCP...")
    engines = list(agent_engines.list())
    print(f"    Found {len(engines)} live engines.")
    # Store full resource names and short IDs
    live_map = {}
    for eng in engines:
        # Standardize to full URN or extract ID depending on database usage
        # In this codebase, BQ URNs are often just the ID or full path.
        # Let's support both or extract ID consistently.
        engine_id = eng.name.split("/")[-1]
        live_map[engine_id] = eng
        print(f"    - {eng.display_name} ({engine_id})")
    return live_map

def cleanup_and_sync_datastore(live_map):
    print("\n[2] Synchronizing Datastore (Kind: Agent)...")
    
    # 1. Fetch existing Datastore keys
    query = ds_client.query(kind="Agent")
    query.keys_only()
    existing_entities = list(query.fetch())
    
    # 2. Delete stale entities
    deleted_count = 0
    for entity in existing_entities:
        key_name = entity.key.name
        # Check if key_name matches any live engine ID
        if key_name not in live_map:
            ds_client.delete(entity.key)
            print(f"    Deleted stale agent from Datastore: {key_name}")
            deleted_count += 1
    print(f"    Total Datastore records deleted: {deleted_count}")

    # 3. Upsert live engines
    upsert_count = 0
    for engine_id, engine in live_map.items():
        key = ds_client.key("Agent", engine_id)
        entity = datastore.Entity(key=key)
        
        # Default Synthetic Metadata
        entity["agent_name"] = engine.display_name
        entity["description"] = "Discovered from GCP Agent Registry"
        entity["model_config"] = "Gemini 2.5 Flash" # Default
        entity["thinking_enabled"] = False
        entity["thinking_tokens"] = "Disabled"
        entity["temperature"] = "0.2"
        entity["fallback_model"] = "Gemini 2.5 Pro"
        entity["runtime_group"] = "Shared Engine"
        entity["is_system"] = False
        entity["icon"] = "fa-robot"
        entity["spiffy_id"] = f"spiffe://acme.com/tenant/operator/agent-{engine_id}"
        entity["iam_policy"] = "roles/aiplatform.user"
        entity["status"] = "deployed"
        entity["skills"] = "[]"
        entity["tools"] = "[]"
        entity["tenant_overrides"] = "{}" # Overwritten/Cleared
        entity["owned_by"] = "Operator"
        entity["shared_with"] = "None"
        entity["shared_type"] = "private"
        
        entity.exclude_from_indexes = ("tenant_overrides", "description", "skills", "tools", "iam_policy", "icon")
        
        ds_client.put(entity)
        upsert_count += 1
        
    print(f"    Total Datastore records upserted: {upsert_count}")

def cleanup_and_sync_bigquery(live_map):
    print("\n[3] Synchronizing BigQuery (Table: agent_platform_registry)...")
    
    # 1. Fetch existing BQ agents
    QUERY_FETCH = f"SELECT agent_urn FROM `{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}`"
    query_job = bq_client.query(QUERY_FETCH)
    bq_agents = [row.agent_urn for row in query_job.result()]
    
    # 2. Identify stale URNs
    stale_urns = []
    for urn in bq_agents:
        # Extract ID from URN (could be full path or just ID)
        engine_id = urn.split("/")[-1]
        if engine_id not in live_map:
            stale_urns.append(urn)
            
    # 3. Delete stale agents
    if stale_urns:
        print(f"    Deleting {len(stale_urns)} stale agents from BigQuery...")
        # Need to handle potential quoting in URNs
        urns_str = ", ".join([f"'{u}'" for u in stale_urns])
        QUERY_DELETE = f"DELETE FROM `{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}` WHERE agent_urn IN ({urns_str})"
        bq_client.query(QUERY_DELETE).result()
        for u in stale_urns:
            print(f"    Deleted: {u}")
    else:
        print("    No stale agents to delete in BigQuery.")

    # 4. Upsert (Delete existing matched and re-insert or update)
    # Easiest approach for small table: Delete matched and insert all fresh.
    # Or just use UPDATE/INSERT. Let's do simple DELETE then INSERT for cleanliness.
    matched_ids = [id for id in live_map.keys()]
    # Convert IDs to potential stored URN formats (just ID or full path)
    # Let's delete anything that matches the short ID at the end of the URN
    
    # Actually, simpler: Just truncate/clear the table and rewrite it from live_map?
    # No, keep it surgical if possible.
    
    # Let's delete all existing records in BQ that match our live IDs to prepare for fresh insert
    # This fulfills the "overwrite everything" instruction.
    print("    Clearing existing matching records in BigQuery for fresh sync...")
    for engine_id in matched_ids:
        QUERY_DEL_MATCH = f"DELETE FROM `{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}` WHERE agent_urn LIKE '%{engine_id}'"
        bq_client.query(QUERY_DEL_MATCH).result()

    # 5. Insert fresh records
    print("    Inserting fresh records into BigQuery...")
    QUERY_INSERT = f"""
    INSERT INTO `{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}`
    (agent_urn, agent_name, description, owned_by, owner_group, shared_with, shared_type, 
     model_config, thinking_enabled, thinking_tokens, temperature, fallback_model, 
     runtime_group, is_system, icon, spiffy_id, iam_policy, status, skills, tools, tenant_overrides)
    VALUES
    (@urn, @name, @desc, 'Operator', 'operator', 'None', 'private', 
     'Gemini 2.5 Flash', false, 'Disabled', '0.2', 'Gemini 2.5 Pro', 
     'Shared Engine', false, 'fa-robot', @spiffy, 'roles/aiplatform.user', 'deployed', '[]', '[]', '{{}}')
    """
    
    insert_count = 0
    for engine_id, engine in live_map.items():
        # Use short ID as URN key for consistency if that's the pattern, or full name
        # Looking at previous logs, some are full paths, some are just IDs.
        # Let's use the full resource_name as the URN key to avoid ambiguity.
        urn = engine.name 
        spiffy = f"spiffe://acme.com/tenant/operator/agent-{engine_id}"
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("urn", "STRING", urn),
                bigquery.ScalarQueryParameter("name", "STRING", engine.display_name),
                bigquery.ScalarQueryParameter("desc", "STRING", "Discovered from GCP Agent Registry"),
                bigquery.ScalarQueryParameter("spiffy", "STRING", spiffy),
            ]
        )
        bq_client.query(QUERY_INSERT, job_config=job_config).result()
        insert_count += 1
        print(f"    Inserted: {engine.display_name} ({engine_id})")
        
    print(f"    Total BigQuery records inserted: {insert_count}")

if __name__ == "__main__":
    print("=== Agent Registry & Database Sync ===")
    live_engines = get_live_engines()
    cleanup_and_sync_datastore(live_engines)
    cleanup_and_sync_bigquery(live_engines)
    print("\n=== Sync Completed Successfully ===")
