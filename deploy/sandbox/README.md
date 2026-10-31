# Reviewed laboratory sandbox deployment contract

The application intentionally does not ship an implicit host-process sandbox. A production deployment must bind ARTIFICIAL_SCIENTIST_LAB_EXECUTION_MODE to a reviewed adapter and enforce the controls below at the runtime layer.

## Mandatory controls

- non-root execution;
- read-only image/root filesystem;
- isolated ephemeral work directory;
- no host filesystem mounts;
- no host PID/IPC/UTS namespaces;
- network disabled by default;
- dropped Linux capabilities;
- no-new-privileges;
- seccomp/AppArmor/SELinux or equivalent syscall policy;
- CPU and memory quotas;
- process/PID limit;
- wall-clock timeout enforced by the orchestrator;
- output-size limit;
- automatic cleanup;
- no cloud instance metadata access;
- no service-account credentials in the sandbox;
- separate runtime identity from the API service;
- tenant-specific artifact namespace;
- immutable image digest.

## Kubernetes/container checklist

Use a dedicated namespace/service account, restricted Pod Security profile, read-only root filesystem, allowPrivilegeEscalation=false, runAsNonRoot=true, dropped capabilities, explicit seccomp, resource requests/limits, and an ephemeral workspace. NetworkPolicy should deny egress unless an explicit allowlist is required.

The API service must not share the sandbox service account or writable host volumes.

## Adapter boundary

The Python LabExecutionAdapter is deployment-neutral. A production adapter should submit an allowlisted operation to this runtime and return only a schema-validated result. It must not serialize arbitrary Python callables or accept user-supplied shell commands.

Until a concrete implementation has been reviewed and exercised against this contract, the external OS-sandbox gate remains open.
