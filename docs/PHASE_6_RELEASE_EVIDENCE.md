# Phase 6 — Release Evidence Register

This register separates repository-verifiable implementation evidence from deployment evidence that must be produced by an operator or independent reviewer.

## Repository verification

| Evidence | Current state | Verification |
|---|---|---|
| Phase 6 implementation | Implemented | Completion matrix and regression suite |
| Production execution fallback | Blocked | `execution_adapter.py` fails closed unless development local-process mode is explicitly selected |
| Frontend CI | Must pass on the exact release candidate SHA | GitHub Actions exact-SHA check |
| Python 3.12 CI | Must pass on the exact release candidate SHA | GitHub Actions exact-SHA check |
| Python 3.13 CI | Must pass on the exact release candidate SHA | GitHub Actions exact-SHA check |

## Deployment evidence required before production release

### 1. Execution sandbox
Record:
- selected runtime and immutable image/runtime digest;
- filesystem, network, capability, syscall and identity policy;
- CPU, memory, PID, disk, file-descriptor and wall-clock limits;
- artifact input/output boundary;
- cancellation and cleanup evidence;
- host canary, network canary, metadata-service and secret-exposure adversarial test results;
- vulnerability/provenance scan results;
- independent security reviewer and sign-off date.

### 2. Identity provider
Record:
- issuer and audience;
- JWKS endpoint;
- successful validation against the real provider;
- key rotation and unknown-key refresh test;
- provider-specific claim semantics;
- reviewer and evidence timestamp.

### 3. Migration and recovery
Record:
- sanitized representative database snapshot identifier;
- backup checksum;
- restore checksum;
- WAL/recovery evidence;
- migration dry-run output;
- migration apply output;
- rollback result;
- record-count reconciliation;
- ownership manifest reconciliation;
- operator identity and approval.

### 4. Operations
Record:
- TLS termination;
- secret-management mechanism;
- filesystem/database least privilege;
- audit retention/monitoring;
- alerting;
- rate limiting;
- incident-response exercise;
- backup/restore rehearsal.

## Release rule

A successful CI run is necessary but insufficient. Any deployment evidence above that is absent remains **OPEN**. The system must not be represented as production-ready, independently security-reviewed, or OS-sandbox-certified until the corresponding evidence is attached and signed off.