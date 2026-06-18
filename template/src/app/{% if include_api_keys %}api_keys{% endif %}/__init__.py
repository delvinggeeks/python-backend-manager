"""Hashed, org-scoped API keys / service tokens. Requires the `db` + `users` extras.

`app.main.create_app` mounts the management router under `/orgs/{org_id}/api-keys` and the
identity router (`/whoami`) at the top level. The `get_principal` dependency in
`app.api_keys.dependencies` authenticates a request by EITHER a user JWT or an `X-API-Key`
header. The heavy imports (engine, ORM models) live in the submodules, so importing this
package is cheap and free of import-time side effects.
"""

from __future__ import annotations
