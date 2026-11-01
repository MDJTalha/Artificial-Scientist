"""Provision an initial tenant and explicit tenant-admin membership.

This operator command never runs during login and never grants a platform-wide role.
The OIDC subject is read with hidden terminal input and is not printed.
"""

from __future__ import annotations

import argparse
import getpass
from urllib.parse import urlsplit

from artificial_scientist.authorization import TenantDirectory


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a tenant and provision one explicit tenant membership."
    )
    parser.add_argument("--database", required=True, help="SQLite database path")
    parser.add_argument("--issuer", required=True, help="Exact HTTPS OIDC issuer")
    parser.add_argument("--tenant-key", required=True, help="Operator-controlled stable tenant key")
    parser.add_argument("--tenant-name", required=True, help="Display name for the tenant")
    parser.add_argument(
        "--role",
        choices=("tenant_admin", "researcher", "viewer", "auditor"),
        default="tenant_admin",
        help="Tenant-scoped role; no platform-wide superadmin role exists",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    issuer = args.issuer.strip()
    parsed_issuer = urlsplit(issuer)
    if (
        parsed_issuer.scheme != "https"
        or not parsed_issuer.hostname
        or parsed_issuer.username
        or parsed_issuer.password
        or parsed_issuer.fragment
    ):
        raise SystemExit("--issuer must be an exact HTTPS issuer URL.")

    subject = getpass.getpass("OIDC subject (input hidden): ").strip()
    if not subject or len(subject) > 255:
        raise SystemExit("OIDC subject must contain 1 to 255 characters.")

    directory = TenantDirectory(args.database)
    principal_id = directory.register_principal(issuer, subject)
    tenant_id = directory.create_tenant(args.tenant_key, args.tenant_name)
    directory.grant_membership(principal_id, tenant_id, args.role)

    print("Tenant membership provisioned.")
    print(f"Tenant ID: {tenant_id}")
    print(f"Role: {args.role}")
    print("The role applies only to this tenant.")
    print("No bearer token, issuer subject, or secret was printed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
