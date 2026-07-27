-- Provision the privileged (BYPASSRLS) role the trusted cross-tenant flows connect as.
--
-- WHY THIS EXISTS: `DATABASE_URL_PRIVILEGED` falls back to `DATABASE_URL` when unset, which makes a
-- default local stack run "privileged" flows as the ordinary app role. Under FORCE RLS that role
-- sees nothing, so auth lookups, the admin panel, inbound webhooks and workers all read zero rows
-- locally while working in production — a divergence that is only ever discovered in production.
--
-- Postgres applies every file in /docker-entrypoint-initdb.d on FIRST boot of an empty data volume.
-- Re-running by hand against an existing database is safe: every statement below is idempotent.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_privileged') THEN
        -- BYPASSRLS is the point: this role is exempt from the row-level policies, which is what
        -- lets RLS be FORCE'd on the app role without breaking the legitimately cross-tenant paths.
        CREATE ROLE app_privileged LOGIN PASSWORD 'app_privileged' BYPASSRLS;
    ELSE
        ALTER ROLE app_privileged LOGIN PASSWORD 'app_privileged' BYPASSRLS;
    END IF;
END
$$;

-- The role needs the same object access as the app role; RLS exemption is not access.
GRANT USAGE ON SCHEMA public TO app_privileged;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO app_privileged;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO app_privileged;
-- Migrations create tables after this script runs, so future objects must be covered too.
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO app_privileged;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO app_privileged;

-- LOCAL DEVELOPMENT ONLY. In production this role is created by your DBA or IaC with a real secret,
-- and DATABASE_URL_PRIVILEGED points at it — never this password.
