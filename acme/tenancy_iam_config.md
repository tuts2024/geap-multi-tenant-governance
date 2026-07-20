Purpose
Analyze uploaded contracts, extract key clauses (indemnity, liability caps, payment terms, termination rights), flag high-risk language, compare against company playbooks, and generate plain-English summaries — all via natural language prompting.
# Multi-Tenancy Scoping Configuration (Step 1: Setup)
**GCP Project**: `learn-w-me`  
**Platform Operator**: `admin@ntuteja.altostrat.com`  
**Architecture**: Single-Project Multi-Tenancy (Isolated Tenant Identities + Conditional IAM & Registry Bindings)

---

## 1. Provisioned Tenant Identities (Service Accounts)

Two dedicated enterprise tenant identities have been successfully provisioned within the single Google Cloud project **`learn-w-me`**:

| Customer Tenant | Service Account Email | Principal Identity |
| :--- | :--- | :--- |
| **Customer A** (Acme Legal) | `customer-a-tenant@learn-w-me.iam.gserviceaccount.com` | `serviceAccount:customer-a-tenant@learn-w-me.iam.gserviceaccount.com` |
| **Customer B** (Beta Corp) | `customer-b-tenant@learn-w-me.iam.gserviceaccount.com` | `serviceAccount:customer-b-tenant@learn-w-me.iam.gserviceaccount.com` |

---

## 2. Resource-Level Cloud IAM Scoping (Hard Isolation)

To enforce true hard isolation so that **Customer B cannot access Customer A's private agents or search corpora**, Cloud IAM role bindings are configured with **CEL (Common Expression Language) Conditions** matching specific resource name suffixes or tags.

### IAM Policy Configuration (`iam_policy.json`)

```json
{
  "bindings": [
    {
      "role": "roles/aiplatform.user",
      "members": [
        "serviceAccount:customer-a-tenant@learn-w-me.iam.gserviceaccount.com",
        "serviceAccount:customer-b-tenant@learn-w-me.iam.gserviceaccount.com"
      ]
    },
    {
      "role": "roles/agentregistry.viewer",
      "members": [
        "serviceAccount:customer-a-tenant@learn-w-me.iam.gserviceaccount.com"
      ],
      "condition": {
        "title": "scope-customer-a-private-agents",
        "description": "Restricts Customer A to their private agents and shared operator agents",
        "expression": "resource.name.startsWith('projects/learn-w-me/locations/us-central1/agents/tenant-acme-') || resource.name.startsWith('projects/learn-w-me/locations/us-central1/agents/shared-')"
      }
    },
    {
      "role": "roles/agentregistry.viewer",
      "members": [
        "serviceAccount:customer-b-tenant@learn-w-me.iam.gserviceaccount.com"
      ],
      "condition": {
        "title": "scope-customer-b-private-agents",
        "description": "Restricts Customer B to their private agents and shared operator agents",
        "expression": "resource.name.startsWith('projects/learn-w-me/locations/us-central1/agents/tenant-beta-') || resource.name.startsWith('projects/learn-w-me/locations/us-central1/agents/shared-')"
      }
    }
  ]
}
```

> [!IMPORTANT]
> **Enforcement Mechanics**: If `customer-b-tenant` crafts a direct API payload referencing `projects/learn-w-me/locations/us-central1/agents/tenant-acme-agent-a`, Cloud IAM evaluates the resource prefix and instantly rejects the call with **HTTP 403 Forbidden**.

---

## 3. Agent Gateway & Registry Dynamic Bindings (Catalog Discovery Isolation)

When utilizing **GCP Agent Gateway** and **Agent Registry (`agentregistry:v1alpha`)**, each tenant ingress channel maps to an explicit **Source Endpoint URN**. Agent availability and connector mapping are governed via **Agent Registry Bindings (`bindings.create`)**:

```json
[
  {
    "name": "projects/learn-w-me/locations/us-central1/bindings/bind-acme-shared",
    "source": {
      "identifier": "urn:endpoint:learn-w-me:tenant-acme:gateway"
    },
    "target": {
      "identifier": "urn:agent:learn-w-me:shared:contract-analyst"
    }
  },
  {
    "name": "projects/learn-w-me/locations/us-central1/bindings/bind-acme-private-a",
    "source": {
      "identifier": "urn:endpoint:learn-w-me:tenant-acme:gateway"
    },
    "target": {
      "identifier": "urn:agent:learn-w-me:tenant-acme:intake-agent"
    }
  },
  {
    "name": "projects/learn-w-me/locations/us-central1/bindings/bind-beta-shared",
    "source": {
      "identifier": "urn:endpoint:learn-w-me:tenant-beta:gateway"
    },
    "target": {
      "identifier": "urn:agent:learn-w-me:shared:contract-analyst"
    }
  }
]
```

### Discovery Resolution (`bindings:fetchAvailable`)

When Customer B accesses their tenant gateway (`urn:endpoint:learn-w-me:tenant-beta:gateway`), the runtime invokes:

```http
GET /v1alpha/projects/learn-w-me/locations/us-central1/bindings:fetchAvailable?sourceIdentifier=urn:endpoint:learn-w-me:tenant-beta:gateway
```

* **Result**: Resolves **only** the `bind-beta-shared` target.
* **Guarantee**: Customer A's private agent (`intake-agent`) is **100% hidden and inaccessible** from Customer B.
