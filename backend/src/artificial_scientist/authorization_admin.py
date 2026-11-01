"""Operator-only CLI for explicitly provisioning tenant membership.

Run this command from an installed backend environment. It does not expose a
network endpoint and never grants membership based on an API request.
"""

from __future__ import annotations

import argparse

from artificial_scientist.authorization import TenantDirectory
from artificial_scientist.config import get_settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Provision a tenant and explicitly grant a principal membership."
    )
    parser.add_argument("--issuer", required=True, help="Exact trusted OIDC issuer URL.")
    parser.add_argument(
        "--subject",
        required=True,
        help="Exact subject claim from the validated identity.",
    )
    parser.add_argument(
        "--tenant-key", required=True, help="Operator-controlled stable tenant key."
    )
    parser.add_argument("--tenant-name", required=True, help="Human-readable tenant name.")
    parser.add_argument(
        "--role",
        required=True,
        choices=("tenant_admin", "researcher", "viewer", "auditor"),
        help="Role to grant to this principal in this tenant.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    directory = TenantDirectory(get_settings().database_url or get_settings().database_path)
    principal_id = directory.register_principal(args.issuer, args.subject)
    tenant_id = directory.create_tenant(args.tenant_key, args.tenant_name)
    directory.grant_membership(principal_id, tenant_id, args.role)
    print(f"Principal ID: {principal_id}")
    print(f"Tenant ID: {tenant_id}")
    print(f"Granted role: {args.role}")
    print("Membership provisioning completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
