# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.x     | ✅ Supported       |
| < 1.0   | ❌ Not Supported   |

## 🛡️ Security Posture

Code Intelligence takes security seriously. As a tool that parses local codebases and interacts with local LLMs (Ollama), we prioritize the following:

- **AST-Aware Parsing**: We use hardened Tree-sitter grammars.
- **Path Isolation**: Strict path containment logic to prevent directory traversal.
- **Safe Serialization**: Rejection of dangerous deserialization patterns (no `pickle`).
- **Secret Scanning**: Gitleaks is integrated into our CI pipeline.

## 🪲 Reporting a Vulnerability

**Please do not open a public issue.**

If you discover a potential security vulnerability, please report it privately by emailing [INSERT SECURITY EMAIL or GitHub Security Advisory].

We follow a Responsible Disclosure policy:
1.  **Acknowledgment**: We will acknowledge your report within 48 hours.
2.  **Assessment**: We will provide an initial assessment and timeline for a fix.
3.  **Remediation**: Once fixed, we will release a security update.
4.  **Disclosure**: Public disclosure will follow after a reasonable period to allow users to update.

Thank you for helping keep our code intelligence secure!
