---
kind: logging_system
name: No Centralized Logging System
category: logging_system
scope:
    - '**'
source_files:
    - tools/numan-parser-check/src/main.rs
    - .github/workflows/production.yml
---

This repository does not implement a centralized logging system. The only log-like output in the codebase is ad-hoc `println!` usage in the Rust tool `tools/numan-parser-check/src/main.rs`, which prints a single status line to stdout after parsing the registry index. Python scripts throughout the repo use standard `print()` and `echo` statements for CLI output rather than structured logging. There is no logging framework, logger initialization, log-level configuration, or structured log format anywhere in the project. The `.github/workflows/production.yml` workflow explicitly guards against debug logging by failing if GitHub Actions debug flags are enabled, but this is a security guard, not a logging system. In short, logging is not a concern addressed by this repository — it relies on simple stdout/stderr output from scripts and tools.