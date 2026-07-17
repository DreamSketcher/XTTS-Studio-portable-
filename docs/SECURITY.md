# Security Policy

## Supported versions

Security fixes are provided for the latest published XTTS Studio release. Users should update to the latest release before reporting a reproducible issue.

## Reporting a vulnerability

Do **not** open a public GitHub issue for an unpatched vulnerability.

Use GitHub Private Vulnerability Reporting for this repository:

`Security` → `Advisories` → `Report a vulnerability`

Include:

- affected version and commit;
- Windows version and CPU/GPU configuration;
- minimal reproduction steps;
- impact and required attacker capabilities;
- logs with API keys, personal text, voice references and local paths removed;
- suggested remediation, if available.

The maintainer should acknowledge a report within 7 days. Disclosure should be coordinated until a fixed release is available. No guarantee of bounty or monetary compensation is made.

## Security boundaries

XTTS Studio processes voice references, generated audio and local models with the permissions of the current Windows user. Treat third-party `.pth`, `.index`, GGUF, ZIP and wheel files as untrusted.

- Only install models from sources you trust.
- A SHA-256 checksum proves integrity relative to a manifest; it does not prove the publisher's identity.
- Cloud AI providers receive the text sent to them. Local XTTS/RVC generation does not require sending voice or text to a cloud provider.
- Never attach `gpt_settings.json`, histories, voice references or generated private material to a public issue.

## Dependency vulnerability gate (pip-audit)

CI runs `tools/pip_audit_gate.py` over `requirements.txt`. `pip-audit` reports known advisories but not their severity, so the gate resolves each advisory's severity from OSV and applies this policy:

- **Critical / High** → fail the build, **unless** the advisory is listed in `.security/pip-audit-allowlist.yml`;
- **Medium / Low** → warning (does not fail);
- any **expired** allowlist entry → fail the build.

`.security/pip-audit-allowlist.yml` is the registry of documented exceptions. Every entry **must** carry `id`, `package`, `reason`, `expires_at` (and `issue_link`). `expires_at` is a quarterly re-evaluation trigger: on expiry CI turns red again until each entry is renewed or the advisory is resolved.

**Deviation from "Critical always fails".** The frozen ML stack that XTTS v2 and RVC depend on (`torch==2.2.2`, `transformers==4.38.2`) carries Critical CVEs with no compatible fix in the near term — bumping torch/transformers breaks the stack. Therefore a Critical advisory **is** suppressible via the allowlist, but **only** as an explicit, dated, justified exception, never silently. A new Critical CVE that is not in the allowlist still fails the build. The exceptions are recorded per-advisory with the specific reason the vulnerable code path is unreachable or mitigated in this project (e.g. `torch.load` trust model, unused model classes, eager-inference-only), and are mirrored in [SECURITY_BASELINE.md](./SECURITY_BASELINE.md).

## Release security requirements

A production release is expected to have:

1. a signed update manifest verified before update application;
2. path-confined updater operations;
3. a signed Windows artifact and published SHA-256 checksums;
4. a generated SBOM;
5. a `pip-audit` blocking gate for High/Critical CVE with an explicit allowlist (see "Dependency vulnerability gate");
6. Windows smoke tests;
7. no plaintext API credentials;
8. an explicit trust decision before loading unsigned pickle/PyTorch checkpoints.
