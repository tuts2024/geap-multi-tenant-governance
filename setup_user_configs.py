from google.cloud import datastore
import os

os.environ["GOOGLE_CLOUD_PROJECT"] = "acxiom-425322"

client = datastore.Client()

# Define user configurations
users = [
    {
        "id": "HfV08Bu3n4YPXgrPvAms1i9RzwK2", # Customer A Firebase UID (Old?)
        "email": "customera@example.com",
        "tenant_name": "Customer A",
        "auth_strategy": "DWD",
        "dwd_service_account": "customer-a-tenant@acxiom-425322.iam.gserviceaccount.com"
    },
    {
        "id": "lKK7PPM62QYpdtCzrqrDcEm1aNs1", # Customer A Firebase UID (Current)
        "email": "customera@example.com",
        "tenant_name": "Customer A",
        "auth_strategy": "DWD",
        "dwd_service_account": "customer-a-tenant@acxiom-425322.iam.gserviceaccount.com"
    },
    {
        "id": "loWmDyexCjMFhGkqV7MPZYwMnEf1", # Customer B Firebase UID (Old?)
        "email": "customerb@example.com",
        "tenant_name": "Customer B",
        "auth_strategy": "3LO",
        "dwd_service_account": None
    },
    {
        "id": "JqK87Kh2tUVntVvSurw33gdqJZj2", # Customer B Firebase UID (Current)
        "email": "customerb@example.com",
        "tenant_name": "Customer B",
        "auth_strategy": "3LO",
        "dwd_service_account": None
    },
    # Also creating records keyed by email just in case the identifier flips
    {
        "id": "customera@example.com",
        "email": "customera@example.com",
        "tenant_name": "Customer A",
        "auth_strategy": "DWD",
        "dwd_service_account": "customer-a-tenant@acxiom-425322.iam.gserviceaccount.com"
    },
    {
        "id": "customerb@example.com",
        "email": "customerb@example.com",
        "tenant_name": "Customer B",
        "auth_strategy": "3LO",
        "dwd_service_account": None
    }
]

print("Populating User Configurations in Datastore...")
for user in users:
    key = client.key("UserConfiguration", user["id"])
    entity = datastore.Entity(key=key)
    entity.update(user)
    client.put(entity)
    print(f"Created/Updated config for: {user['id']} ({user['tenant_name']}) -> Strategy: {user['auth_strategy']}")

print("Done.")
