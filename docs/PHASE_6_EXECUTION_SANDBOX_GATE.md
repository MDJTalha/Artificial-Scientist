# Phase 6 — Execution Sandbox Implementation Gate

**Status: specification and acceptance gate; not a claim that an OS sandbox is deployed.**

## Security boundary

The current Python worker is a process-isolation and resource-limiting mechanism. It is not a security boundary for hostile code. The lab currently accepts allowlisted operations and must continue to reject arbitrary Python, shell commands, generated code, and user-selected callables. A future feature that executes untrusted code must not reuse the current worker as its only boundary.

## Required production architecture

Use a separately maintained, disposable execution boundary (for example, a hardened container runtime or dedicated execution service) with an explicit policy. The API process must never mount the host filesystem, Docker socket, credentials, or application secrets into a worker.

Required controls:

- Run as a non-root, unprivileged identity; drop Linux capabilities and prohibit privilege escalation.
- Enforce seccomp and mandatory access control (AppArmor/SELinux where available); use a read-only root filesystem and a small, size-limited temporary workspace.
- Deny network egress by default. Any required network access must be explicit, destination-restricted, and separately reviewed.
- Do not mount host paths or the container-runtime socket. Do not pass environment secrets into the worker.
- Apply CPU, memory, process/PID, file-size, open-file, output-size, and wall-clock limits at the runtime boundary, not only in Python.
- Use a disposable worker per execution; terminate the full process group/container on timeout and confirm cleanup.
- Keep input and output schemas allowlisted and bounded. Treat all worker output as untrusted data and validate it before persistence or display.
- Pin and scan the worker image/runtime dependencies; rebuild on security updates and record image digests in execution provenance.
- Separate the API identity from the worker identity and use least-privilege access to storage.

## Fail-closed rollout requirements

1. Keep arbitrary-code execution disabled. The existing allowlisted mathematical operations may run only through the current documented contract while this sandbox gate is open.
2. Do not advertise the existing spawned process as a complete sandbox.
3. Before enabling untrusted or multi-tenant code execution, require a separately reviewed sandbox adapter and an explicit production configuration switch. Missing or invalid sandbox configuration must prevent the untrusted execution path from starting.
4. The deployment owner must record the runtime type, pinned image digest, policy version, resource limits, network policy, and test evidence. Never store credentials in that record.

## Required acceptance tests

The sandbox adapter must demonstrate, in an isolated CI or disposable test environment:

- A worker cannot read a deliberately withheld host file or application secret.
- A worker cannot reach the public network or an unapproved internal endpoint.
- A worker cannot create privileged processes, access the container runtime socket, or escape its workspace.
- Memory, CPU, PID, file-size, output-size, and wall-clock limits are enforced by the runtime.
- Timeout and crash paths remove the worker and its descendants and do not leave reservations or temporary files behind.
- Malformed, oversized, or unexpected worker output is rejected safely.
- Concurrent tenant workloads cannot access each other's files, artifacts, credentials, or execution state.
- The policy is tested against the exact pinned runtime/image used in deployment, with the test report tied to its digest.

Unit tests for the Python process helper alone do not satisfy these acceptance criteria.

## Evidence and sign-off

Attach the CI run, runtime/image digest, policy configuration, negative-test report, and independent security-review finding references to the Phase 6 release record. Record unresolved failures as open blockers. Production identity-provider validation, migration rehearsal, and operational deployment checks remain separate release gates.
