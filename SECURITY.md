# Security Policy

## Supported Versions

ContextOS is pre-1.0. Security fixes target the latest released version.

| Version | Supported |
| ------- | --------- |
| 0.1.x   | Yes       |

## Reporting a Vulnerability

Please do not open public issues for suspected vulnerabilities.

Report security concerns by emailing the project maintainer or by opening a
private GitHub security advisory if available for this repository. Include:

- A clear description of the issue.
- Steps to reproduce or a minimal proof of concept.
- The affected version or commit.
- Any known impact on secret handling, filesystem access, or generated context packs.

The maintainer will acknowledge reports as soon as practical and coordinate a
fix before public disclosure.

## Security Model

ContextOS is designed to run locally. It does not make network calls by default.
Optional integrations, such as compression providers, must be explicitly enabled
by the user.

When reporting issues, please pay special attention to:

- Secret leakage into context packs or exports.
- Unsafe symlink or path traversal behavior.
- Unexpected writes outside user-requested output paths.
- Behavior that sends repository content to external services without explicit opt-in.
