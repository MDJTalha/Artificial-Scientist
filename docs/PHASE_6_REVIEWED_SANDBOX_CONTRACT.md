# Phase 6 — Reviewed Sandbox Deployment Contract

This document is the concrete deployment contract for the remaining Phase 6 execution-isolation gate.

## Required worker profile

The execution worker must run as a non-root UID with:

- read-only root filesystem;
- one empty writable scratch directory;
- no host filesystem mounts;
- no container runtime socket;
- no host PID, IPC, or network namespace sharing;
- all Linux capabilities dropped;
- no-new-privileges enabled;
- seccomp profile denying dangerous syscalls;
- AppArmor/SELinux policy where supported;
- PID, CPU, memory, file-size, file-count, descriptor and wall-clock limits;
- network namespace with no routes by default;
- no cloud metadata route;
- no inherited application environment or credentials;
- immutable image digest and dependency inventory;
- bounded output promotion through the control plane only.

## Admission contract

A worker is admitted only when the deployment reports all required controls as active. If any control is unknown, unavailable, or degraded, the execution adapter must reject the job.

## Adversarial acceptance cases

A disposable test environment must attempt:

1. reading a host canary file;
2. writing outside scratch;
3. connecting to a canary network endpoint;
4. accessing cloud metadata/internal service addresses;
5. reading an injected secret;
6. spawning beyond the PID limit;
7. exceeding memory and CPU limits;
8. filling scratch beyond the output quota;
9. surviving cancellation/timeout;
10. retaining files after worker cleanup.

Every case must record expected denial, observed outcome, worker/image identity, and cleanup result.

## Evidence rule

This contract is not a sandbox implementation and does not certify a deployment. Phase 6 becomes externally release-complete only after a supported runtime is deployed, these cases pass in that disposable environment, image/dependency provenance is recorded, and an independent reviewer signs off.
