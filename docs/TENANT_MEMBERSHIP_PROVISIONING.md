# Tenant membership provisioning

Tenant membership is not created from a client-supplied tenant header and is not
self-service. An operator must explicitly provision membership after confirming
the identity and tenant through an approved out-of-band process.

The backend includes an operator CLI:

```powershell
python -m artificial_scientist.authorization_admin --issuer "https://identity.example/" --subject "exact-oidc-subject" --tenant-key "internal-customer-key" --tenant-name "Customer Name" --role tenant_admin
```

Run it from the installed backend environment with the intended
`ARTIFICIAL_SCIENTIST_DB_PATH` configured. The issuer and subject must match
the validated OIDC token claims exactly. Use an internal, operator-controlled
tenant key; do not use a client-supplied tenant ID as the provisioning key.

Supported roles are `tenant_admin`, `researcher`, `viewer`, and `auditor`.
The CLI grants only the specified principal-to-tenant membership and prints
opaque IDs for operational reference. Re-running the command for the same
issuer, subject, tenant key, tenant name, and role is idempotent for membership.

## Security boundaries

- The command is an operator tool, not an HTTP endpoint.
- Do not run it automatically at application startup.
- Do not provision a membership merely because a user sends an `X-Tenant-ID`
  header or a valid bearer token.
- Keep the database path consistent with the API deployment.
- Tenant-scoped persistence primitives exist, but API routes must still enforce
  authenticated membership and role checks before tenant isolation is complete.
- Legacy records with a NULL tenant remain unowned and must not be silently
  assigned to a tenant.
