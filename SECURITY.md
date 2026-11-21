# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 1.x (latest release) | Yes |
| older | No |

## Reporting a vulnerability

Please do **not** open a public issue for a security problem.

Report it privately through GitHub: open the **Security** tab of this repository and choose **Report a vulnerability** (GitHub private vulnerability reporting). Only the maintainer can read the report.

Please include: what happens, the input or the steps that cause it, the version, and Python or Node.js version.

- You will get a first reply within 14 days.
- A confirmed problem will be fixed in a new release, and the report will be credited unless you prefer otherwise.

## What matters for this library

Nmahjong reads JSON files (tilesets, rulesets, walls, records, annotations) that may come from someone else, and game logs imported from other services.

- The library does not open network connections, does not run code taken from its input, and has no third-party dependencies.
- Things we treat as security problems: an input file that makes the library run code, read or write files outside what the caller asked for, or use time or memory without limit; and any way to make a record pass verification although it does not match its wall or its rule.
- A wrong score or a wrong judgement for a valid game is a bug, not a security problem. Please use an ordinary issue.
