# Phase 6 — Execution Isolation Boundary and Deployment Gate

**Status: threat model and deployment requirements; a complete OS sandbox is not yet implemented.**

## Protected assets

- The API process, its credentials, source tree, environment variables, database, and host filesystem.
- Scientific run records, experiment inputs, attachments, and exported archives.
- Host and neighboring workloads: CPU, memory, disk, process table, network, and file descriptors.
- Integrity of recorded results and provenance.

## Threat model

Treat a lab step as potentially hostile even though current steps are selected from an allowlist. Inputs can still trigger expensive computation, dependency bugs, native-library faults, or parser vulnerabilities. Future generated code must be treated as arbitrary hostile code and must not run inside the API process or a worker that inherits API secrets and unrestricted host access.

Current spawned workers have hard wall-clock timeouts and, on POSIX, CPU, address-space, file-size, descriptor, and core-dump limits. These controls reduce denial-of-service exposure but do not block filesystem reads/writes, network access, access to inherited environment variables, or exploitation of the kernel and native dependencies. Windows does not receive the POSIX rlimits implemented here. Therefore the current worker is not a security boundary for untrusted generated code.

## Required production execution architecture

1. **Separate control plane and execution plane.** The API validates and stores a declarative job, then submits an immutable job envelope to a dedicated execution service. The API process must never execute generated source code.
2. **Use an OS-enforced isolation boundary.** A deployment-specific runner must use a hardened container or microVM profile with a read-only root filesystem, isolated scratch space, no host mounts, no container-runtime socket, no privileged mode, dropped Linux capabilities, no-new-privileges, seccomp/AppArmor/SELinux policy where available, and a non-root UID. A microVM may be required where container/kernel sharing is not acceptable.
3. **Deny network by default.** The worker has no outbound or inbound network route unless a narrowly scoped capability is explicitly approved. Do not expose cloud metadata endpoints, internal service networks, or the host gateway.
4. **Minimize secrets.** The worker receives only the validated job envelope and temporary artifact handles. It receives no API keys, database credentials, identity-provider secrets, or inherited environment by default.
5. **Constrain resources at multiple layers.** Enforce CPU quota, memory limit, process/PID limit, disk and output-size limit, file-descriptor limit, and wall-clock deadline at the OS/orchestrator layer. In-process checks and POSIX rlimits remain defense in depth.
6. **Use explicit artifact exchange.** Input artifacts are immutable and verified before mount/read. Output is written only to a dedicated bounded scratch directory; after completion, the control plane validates size, type, digest, and provenance before promoting it to durable storage.
7. **Make lifecycle bounded and observable.** Apply queue limits, per-job and per-tenant concurrency limits, cancellation, hard termination, cleanup of scratch data, and an operator-visible record for timeout, crash, policy denial, and runner loss.
8. **Pin and verify the execution image.** Use an immutable image digest, controlled dependency inventory, vulnerability scanning, signed build provenance where available, and a documented patch/rebuild process. A tag alone is not an immutable identity.
9. **Test isolation, not just functionality.** In a disposable CI or staging environment, prove that a job cannot read a canary host file, reach a canary network endpoint, access metadata/internal services, see API secrets, exceed CPU/memory/PID/disk limits, or persist scratch files across jobs. Test timeout, cancellation, worker crash, malformed output, and cleanup.
10. **Review before trust expansion.** Independently review the runner configuration and attack surface. Do not enable generated code or untrusted public submissions based solely on unit tests.

## Deployment profile decision

The repository must not silently assume that Docker, a particular container runtime, Linux namespaces, seccomp, or a microVM is available in every target environment. The production adapter should be selected per supported deployment target and fail closed if required isolation controls are unavailable. Local development can retain the existing allowlisted subprocess runner, clearly marked as development-only and not a hostile-code sandbox.

## Exit checklist

- [ ] Select and document a supported deployment target and sandbox runtime.
- [ ] Implement a separate execution adapter with immutable job envelopes and bounded artifact exchange.
- [ ] Enforce filesystem, network, identity, syscall/capability, and resource policies at the OS/orchestrator boundary.
- [ ] Prove the controls with adversarial integration tests in a disposable environment.
- [ ] Verify runtime/image provenance, patching, logging, cleanup, and incident response.
- [ ] Obtain independent security review and record accepted residual risks.
- [ ] Keep arbitrary/generated code disabled until all preceding checks are evidenced.

Passing ordinary unit tests or having POSIX rlimits does not satisfy this checklist. Phase 6 remains incomplete until these deployment-specific controls are implemented and independently reviewed.
