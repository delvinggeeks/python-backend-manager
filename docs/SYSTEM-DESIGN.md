# SYSTEM-DESIGN.md — C4 + sequence + ER diagrams (diagrams-as-code)

> The platform's design rendered as **versioned diagrams-as-code** (Mermaid, so they review in PRs and
> render on GitHub). Follows the **C4 model** (Context → Container → Component) + key **sequence** flows
> + an **ER** overview. This is the *platform-level* design; **every ROADMAP phase ships its own
> phase-level C4-component + sequence + ER-delta diagrams** in the same notation (enforced by the
> per-phase template in [SDLC.md](SDLC.md), traced in [TRACEABILITY.md](TRACEABILITY.md)). Deployment /
> networking topology lives in [INFRA-TOPOLOGY.md](INFRA-TOPOLOGY.md). Inherits
> [PRINCIPLES.md](PRINCIPLES.md); catalog in [ARCHITECTURE.md](ARCHITECTURE.md).

**Diagram conventions.** Mermaid in markdown is the default (zero-tooling, PR-reviewable, GitHub-native).
For a navigable model-as-a-whole, the **Structurizr DSL** (one model → many auto-consistent views) is
the documented upgrade seam; PlantUML is the heavier alternative. One source of truth per diagram; no
binary/Visio. Diagram types per the C4 model + UML sequence/state + ER.

---

## C4 L1 — System context

Who/what uses the platform and what it depends on.

```mermaid
flowchart TB
    enduser([End user / SMB customer]):::person
    admin([Superuser / ops]):::person
    aiclient([AI client - Claude / IDE / agent]):::person
    mobile([Mobile / PWA app]):::person

    subgraph PLATFORM[" SaaS Platform (this backend) "]
      core[[FastAPI modular monolith\n+ Postgres + Redis]]:::sys
    end

    pay[Payments: Razorpay/Stripe\n+ crypto BTCPay/Beldex]:::ext
    llm[LLM providers\nAnthropic/OpenAI via LiteLLM]:::ext
    notif[Email/SMS/WhatsApp/Push\nSES/MSG91/Gupshup/FCM-APNs]:::ext
    store[Object storage\nCloudflare R2 / S3]:::ext
    obs[Observability backend\nOTLP → Grafana/Axiom/Sentry]:::ext
    idp[Enterprise IdP\nAuthentik/WorkOS - OIDC/SAML]:::ext

    enduser -->|HTTPS REST / WS| core
    mobile -->|HTTPS REST / WS / push| core
    admin -->|/admin| core
    aiclient -->|MCP /mcp| core
    core -->|charge / webhook| pay
    core -->|tokens metered| llm
    core -->|send| notif
    core -->|put/get presign| store
    core -->|OTLP spans/metrics/logs| obs
    core -->|federated login| idp

    classDef person fill:#08427b,color:#fff,stroke:#052e56;
    classDef sys fill:#1168bd,color:#fff,stroke:#0b4884;
    classDef ext fill:#999,color:#fff,stroke:#6b6b6b;
```

---

## C4 L2 — Containers

The deployable/runtime units. The monolith is one process; the dashed boxes are the logical planes
from [ARCHITECTURE.md](ARCHITECTURE.md).

```mermaid
flowchart TB
    client([Clients: web / mobile / AI / admin]):::person

    subgraph RT[" Runtime "]
      api[API container\nFastAPI/uvicorn\napp.main:app]:::c
      worker[Worker container\narq + DBOS workflows]:::c
      mcp[MCP server\nFastMCP @ /mcp]:::c
      rt[Realtime\nWS/SSE + Redis pub/sub]:::c
    end

    subgraph DATA[" Stateful "]
      pg[(Postgres\n+ pgvector + RLS\nsystem of record)]:::db
      redis[(Redis\ncache · queue · pubsub · denylist)]:::db
      blob[(Object storage\nR2 / S3, tenant-prefixed)]:::db
    end

    subgraph EXT[" External (behind ports) "]
      prov[Payments · LLM · Notify · IdP · KMS]:::ext
      obsx[OTLP collector → backend]:::ext
    end

    client --> api
    client -. websocket .-> rt
    client -. MCP .-> mcp
    api --> pg
    api --> redis
    api --> blob
    api -->|enqueue| redis
    worker --> redis
    worker --> pg
    rt --> redis
    mcp --> pg
    api & worker -->|ports| prov
    api & worker & rt & mcp -->|spans| obsx
    api -->|outbox row| pg
    worker -->|outbox relay → webhooks/notify/metering| prov

    classDef person fill:#08427b,color:#fff,stroke:#052e56;
    classDef c fill:#1168bd,color:#fff,stroke:#0b4884;
    classDef db fill:#2e7d32,color:#fff,stroke:#1b5e20;
    classDef ext fill:#999,color:#fff,stroke:#6b6b6b;
```

---

## C4 L3 — Component view: the request pipeline

The middleware/port chain a mutating request traverses (mirrors ARCHITECTURE §2). Each box is a
component owned by a capability module + its phase.

```mermaid
flowchart LR
    req([HTTPS request]) --> mw1[request-id / correlation\ncore.logging]
    mw1 --> mw2[tenant context\ncontextvars → RLS GUC]
    mw2 --> mw3[AuthnPort\nJWT + refresh/denylist]
    mw3 --> mw4[AuthorizationPort\ncheck subject,action,resource]
    mw4 --> mw5[IdempotencyPort\nreplay or proceed]
    mw5 --> mw6[RateLimitPort\nper-tenant/plan + quota]
    mw6 --> h[Route handler\ndomain logic]
    h --> sess[(tenant-scoped session\nRLS backstop)]
    h --> ob[outbox_events\nsame txn]
    ob -. relay .-> sx[webhooks SSRF-guarded /\nnotifications / metering]
    h --> resp([response + OTel span + structlog])

    classDef c fill:#1168bd,color:#fff,stroke:#0b4884;
    class mw1,mw2,mw3,mw4,mw5,mw6,h,sx c;
```

---

## Sequence — authenticated, tenant-isolated request (with RLS backstop)

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant API as FastAPI
    participant A as AuthnPort
    participant Z as AuthorizationPort
    participant DB as Postgres (RLS)
    C->>API: request + JWT
    API->>A: validate token (denylist check)
    A-->>API: user, tenant_id, roles
    API->>API: set contextvar tenant_id
    API->>Z: check(user, action, resource)
    Z-->>API: allow
    API->>DB: BEGIN; SET LOCAL app.current_tenant = tenant_id
    API->>DB: SELECT ... (app-level WHERE org_id) 
    Note over DB: RLS policy independently filters by current_tenant<br/>(defense-in-depth — leak-proof even if WHERE is missed)
    DB-->>API: rows (this tenant only)
    API-->>C: 200 + OTel span + structlog(trace_id)
```

## Sequence — usage-metered LLM call → billing (the AI unit-economics path)

```mermaid
sequenceDiagram
    autonumber
    participant Ag as Agent/Handler
    participant L as LLMPort (LiteLLM)
    participant Ca as Cache (prompt/semantic)
    participant P as Provider (Anthropic)
    participant M as MeteringPort
    participant B as BillingPort
    Ag->>L: complete(prompt, tenant)
    L->>Ca: lookup (semantic/prompt cache)
    alt cache hit
        Ca-->>L: cached completion (skip provider)
    else miss
        L->>P: request (cache_control)
        P-->>L: completion + usage{in,out,cache_read}
    end
    L->>M: record(tenant, model, tokens, cost)
    M->>M: budget check
    alt over budget
        M-->>Ag: 429 spend cap
    else ok
        M-->>L: ok
        L-->>Ag: completion
    end
    Note over M,B: nightly: MeteringPort.aggregate → BillingPort.invoice → PaymentsPort.charge
```

## Sequence — reliable side-effect via transactional outbox + SSRF-guarded webhook

```mermaid
sequenceDiagram
    autonumber
    participant H as Handler
    participant DB as Postgres
    participant R as Outbox relay (worker)
    participant G as SSRF egress guard
    participant EP as Tenant endpoint
    H->>DB: BEGIN; write state + INSERT outbox_events; COMMIT
    Note over H,DB: single transaction — no dual-write loss
    R->>DB: poll unpublished outbox rows
    R->>G: resolve+pin target URL
    alt private/metadata IP
        G-->>R: REJECT (logged)
    else public
        G-->>R: ok
        R->>EP: POST signed (HMAC) payload
        EP-->>R: 2xx
        R->>DB: mark published (idempotent on event_id)
    end
```

## Sequence — agent tool call gated by AgentPolicy + human-in-the-loop (P29)

```mermaid
sequenceDiagram
    autonumber
    participant Ag as Agent
    participant Pol as AgentPolicy
    participant T as MCPToolPort
    participant Ap as Approval (HITL)
    participant Au as Audit (immutable)
    Ag->>Pol: request tool(name,args)
    Pol->>Pol: capability check (allow/deny, tenant scope, budget)
    alt tool not allowed
        Pol-->>Ag: deny
    else allowed
        Pol->>T: validate (signature, arg schema, SSRF)
        alt destructive/high-risk
            T->>Ap: propose action (plan-then-execute)
            Ap-->>T: human approves (2FA)
        end
        T->>T: execute (sandboxed) + redact output
        T->>Au: append(agent_id, tool, cost, risk, injection_score)
        T-->>Ag: result
    end
```

---

## ER overview — core data model (representative; per-capability deltas ship with each phase)

```mermaid
erDiagram
    ORGANIZATION ||--o{ MEMBERSHIP : has
    USER ||--o{ MEMBERSHIP : in
    ORGANIZATION ||--o{ API_KEY : owns
    ORGANIZATION ||--o| SUBSCRIPTION : billed
    ORGANIZATION ||--o{ USAGE_EVENT : meters
    ORGANIZATION ||--o{ WEBHOOK_ENDPOINT : registers
    ORGANIZATION ||--o{ AUDIT_LOG : records
    ORGANIZATION ||--o{ OUTBOX_EVENT : emits
    ORGANIZATION ||--o{ THREAD : owns
    THREAD ||--o{ MESSAGE : contains
    SUBSCRIPTION ||--o{ INVOICE : generates
    USAGE_EVENT ||--o| INVOICE : rated_into
    ORGANIZATION ||--o{ CUSTOMER_WALLET : prepays

    USER {
      uuid id PK
      string email
      string hashed_password "redacted in admin"
      bool is_superuser
    }
    ORGANIZATION {
      uuid id PK
      string slug
      string payments_customer_id "secret"
    }
    USAGE_EVENT {
      uuid id PK
      string metric
      numeric qty
      string idempotency_key "unique"
    }
    OUTBOX_EVENT {
      uuid id PK
      string event_type
      jsonb payload
      timestamp published_at
    }
    AUDIT_LOG {
      uuid id PK
      string actor
      string action
      jsonb meta "append-only"
    }
```

---

## How phases extend this

Every ROADMAP phase delivers, in this same notation (gated by [SDLC.md](SDLC.md) Definition-of-Done):
a **C4 component** diagram for its module, a **sequence** diagram for its primary flow, and an **ER
delta** for any new tables — each cross-linked from its [TRACEABILITY.md](TRACEABILITY.md) rows. The
platform diagrams above are the always-current "you are here"; phase diagrams are the granular detail.
No phase is "done" until its diagrams + traceability rows merge with the code.
