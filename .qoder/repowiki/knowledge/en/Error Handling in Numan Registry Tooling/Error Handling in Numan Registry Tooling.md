---
kind: error_handling
name: Error Handling in Numan Registry Tooling
category: error_handling
scope:
    - '**'
source_files:
    - scripts/add-package.py
    - scripts/lifecycle-prove.py
    - scripts/ci-sign.py
    - scripts/nu_version_constraint.py
    - tools/numan-parser-check/src/main.rs
---

The Numan registry repository uses a pragmatic, script-oriented error handling approach across its Python tooling and Rust parser-check utility. Errors are primarily communicated through structured exit codes, explicit exception types, and stderr messages rather than a centralized error type system.

**Python Scripts Pattern:**
The Python scripts (`add-package.py`, `lifecycle-prove.py`, `ci-sign.py`) follow consistent patterns:
- Validation functions raise specific exceptions (`ValueError` for malformed input, `FileNotFoundError` for missing executables) with descriptive messages
- The `nu_version_constraint.py` module returns error strings from `lifecycle_evidence_error()` rather than raising exceptions, allowing callers to decide how to handle validation failures
- Scripts use `sys.exit(1)` for fatal errors after printing diagnostic messages to `sys.stderr`
- Optional dependencies (like `jsonschema` and `cryptography`) are handled with try/except ImportError blocks that print warnings and continue gracefully when unavailable
- Exit codes follow conventions: 0 for success, 1 for general errors, 2 for configuration/environment issues

**Rust Parser Check:**
The `tools/numan-parser-check/src/main.rs` uses idiomatic Rust error handling:
- Returns `Result<(), Box<dyn Error>>` from main
- Uses `std::io::Error` with specific `ErrorKind` variants (`InvalidInput`, `InvalidData`) for different error categories
- Propagates errors using the `?` operator throughout the call chain
- Provides clear error messages for usage violations and unsupported schema versions

**Key Conventions Observed:**
- No centralized error types or custom error enums - each script handles its own domain-specific errors
- Input validation happens early with clear error messages before any side effects
- External dependencies fail gracefully with warnings rather than hard failures
- Filesystem and network operations use try/catch blocks with meaningful error context
- The lifecycle-prove script demonstrates comprehensive error propagation through subprocess calls, returning specific exit codes for different failure modes
- Security-sensitive operations (like signing) validate input sizes and formats immediately

**Notable Absences:**
- No panic/recover patterns in Python code
- No logging framework - all diagnostics go to stderr
- No retry logic for transient failures
- No structured error logging or monitoring integration