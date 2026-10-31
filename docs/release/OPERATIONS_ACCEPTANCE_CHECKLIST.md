# Production Operations Acceptance Checklist

Before production traffic is enabled, the operator must record evidence for every item.

- [ ] TLS certificate chain, hostname and renewal tested.
- [ ] HTTP-to-HTTPS behavior and secure headers verified.
- [ ] Secrets are supplied by an approved secret manager; no secrets in images, repository or logs.
- [ ] API and sandbox identities use least privilege and are distinct.
- [ ] Network segmentation/firewall rules deny unnecessary ingress and egress.
- [ ] Health and readiness endpoints are wired to the deployment controller.
- [ ] Structured application logs and security audit logs are collected and retained.
- [ ] Monitoring covers latency, error rate, saturation, authentication failures, authorization denials and sandbox failures.
- [ ] Alerts have tested routing and ownership.
- [ ] Rate limits and tenant quotas are configured and tested at production values.
- [ ] Backups are scheduled, encrypted and immutable where supported.
- [ ] Restore has been rehearsed from a real sanitized snapshot.
- [ ] Rollback has been rehearsed.
- [ ] Configuration drift is detectable.
- [ ] Incident-response contacts and escalation paths are documented.
- [ ] Deployment restart/recovery has been tested.
- [ ] Capacity and concurrency limits are documented.
- [ ] External OIDC, sandbox, recovery and security evidence is attached to the release record.

A checked item must have an operator timestamp and evidence reference. CI success alone does not check these items.
