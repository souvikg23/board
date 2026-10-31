# Security

Board runs entirely in your browser. It has no server, no login and no tracking, and your lectures never leave your device.

**Found a vulnerability?** Please report it privately: repo → **Security** tab → **Report a vulnerability**. Don't open a public issue.

How Board protects you:
- Lecture text and backup files are treated as untrusted input and escaped before display.
- A Content-Security-Policy blocks inline and third-party scripts.
- Every change runs the security tests in `tests/` and a CodeQL scan before it can go green.
