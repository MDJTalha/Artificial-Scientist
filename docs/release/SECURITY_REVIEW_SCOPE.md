# Independent Security Review Scope

The reviewer should independently assess the exact release commit and deployed configuration.

## Required scope
- OIDC/JWKS signature, issuer, audience, expiry and rotation behavior;
- endpoint-by-endpoint authentication and authorization;
- tenant isolation and object ownership;
- privilege escalation and confused-deputy paths;
- request-size, quota and concurrency abuse;
- secret exposure and credential inheritance;
- dependency and CI supply-chain controls;
- audit-log integrity and failure behavior;
- sandbox/container escape resistance;
- database/network/TLS deployment;
- logging, monitoring and incident response.

## Evidence requested
Record commit SHA, deployed image digest, configuration fingerprint without secrets, test methodology, findings by severity, exploitability, remediation, residual risk, and signed reviewer approval.

Repository tests are supporting evidence only; this document does not constitute an independent review.
