"""Provision one ASDS tenant membership for a Cognito user after identity verification.

Run only from a trusted operator workstation/container with access to the same
database used by the API. The Cognito subject must come from the verified User Pool.
Never pass an ID/access token or password to this script.
"""

from __future__ import annotations

import argparse

from artificial_scientist.authorization import TenantDirectory


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, help="Path to the API authorization SQLite database")
    parser.add_argument("--issuer", required=True, help="Exact Cognito User Pool issuer URL")
    parser.add_argument("--subject", required=True, help="Verified Cognito user sub claim")
    parser.add_argument("--tenant-key", required=True, help="Operator-controlled stable tenant key")
    parser.add_argument("--tenant-name", required=True, help="Display name for the tenant")
    parser.add_argument("--role", choices=("tenant_admin", "researcher", "viewer", "auditor"), default="tenant_admin")
    args = parser.parse_args()

    directory = TenantDirectory(args.database)
    principal_id = directory.register_principal(args.issuer, args.subject)
    tenant_id = directory.create_tenant(args.tenant_key, args.tenant_name)
    directory.grant_membership(principal_id, tenant_id, args.role)
    print(f"principal_id={principal_id}")
    print(f"tenant_id={tenant_id}")
    print(f"role={args.role}")


if __name__ == "__main__":
    main()
