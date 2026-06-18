"""Object storage (S3-compatible). Requires the `storage` extra (aioboto3).

Builds an S3 client from settings (endpoint / bucket / region / credentials — never
hard-coded), so it works against AWS S3 or any S3-compatible endpoint (MinIO, Cloudflare
R2, ...). `app.storage.client` is the single seam mocked in tests; the router exposes
presigned-URL upload/download plus list/delete and never proxies object bytes or sets a
public ACL. With tenancy, keys are prefixed per organization so tenants are isolated;
without it, keys are stored verbatim. `app.main.create_app` mounts the router under
`/orgs` (org-scoped) when tenancy is present, else under `/storage`.
"""

from __future__ import annotations
