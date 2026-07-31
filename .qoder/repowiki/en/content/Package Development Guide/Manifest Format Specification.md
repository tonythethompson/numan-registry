# Manifest Format Specification

<cite>
**Referenced Files in This Document**
- [index-v1.json](file://schemas/index-v1.json)
- [index.json](file://registry/index.json)
- [FMotalleb-nu_plugin_desktop_notifications-0.114.1.json](file://specs/FMotalleb-nu_plugin_desktop_notifications-0.114.1.json)
- [SuaveIV-nu_script_wttr-0.1.0-main.json](file://specs/SuaveIV-nu_script_wttr-0.1.0-main.json)
- [lint-manifest-index.py](file://scripts/lint-manifest-index.py)
- [validate.py](file://scripts/validate.py)
- [add-package.py](file://scripts/add-package.py)
</cite>

## Table of Contents
1. [Introduction](#introduction)
2. [Project Structure](#project-structure)
3. [Core Components](#core-components)
4. [Architecture Overview](#architecture-overview)
5. [Detailed Component Analysis](#detailed-component-analysis)
6. [Dependency Analysis](#dependency-analysis)
7. [Performance Considerations](#performance-considerations)
8. [Troubleshooting Guide](#troubleshooting-guide)
9. [Conclusion](#conclusion)
10. [Appendices](#appendices)

## Introduction

This document specifies the package manifest format used by the Nushell package registry system. The manifest defines metadata, dependencies, and versioning information for packages distributed through the registry. It serves as the contract between package authors and the registry infrastructure, ensuring consistency and reliability across all published packages.

The manifest format supports multiple package types including plugins, scripts, and custom configurations, each with specific field requirements and validation rules.

## Project Structure

The manifest system consists of several key components:

```mermaid
graph TB
subgraph "Schema Layer"
Schema["JSON Schema<br/>index-v1.json"]
end
subgraph "Registry Layer"
Index["Registry Index<br/>index.json"]
Signature["Index Signature<br/>index.json.sig"]
end
subgraph "Package Specs"
PluginSpec["Plugin Manifest<br/>*.json"]
ScriptSpec["Script Manifest<br/>*.json"]
CustomSpec["Custom Package<br/>*.json"]
end
subgraph "Validation Tools"
Linter["Manifest Linter<br/>lint-manifest-index.py"]
Validator["Package Validator<br/>validate.py"]
Adder["Package Adder<br/>add-package.py"]
end
Schema --> Index
PluginSpec --> Schema
ScriptSpec --> Schema
CustomSpec --> Schema
Index --> Linter
Index --> Validator
Index --> Adder
```

**Diagram sources**
- [index-v1.json:1-200](file://schemas/index-v1.json#L1-L200)
- [index.json:1-100](file://registry/index.json#L1-L100)
- [lint-manifest-index.py:1-50](file://scripts/lint-manifest-index.py#L1-L50)

**Section sources**
- [index-v1.json:1-200](file://schemas/index-v1.json#L1-L200)
- [index.json:1-100](file://registry/index.json#L1-L100)

## Core Components

### Manifest Schema Definition

The manifest schema defines the structure and validation rules for package manifests. Key components include:

- **Package Identification**: Unique identifiers and naming conventions
- **Version Management**: Semantic versioning with pre-release support
- **Dependency Declaration**: External package requirements and constraints
- **Metadata Fields**: Author information, descriptions, and licensing
- **File References**: Archive locations and integrity checks

### Registry Index Structure

The registry index maintains a centralized catalog of all available packages with their versions and metadata. It provides quick lookup capabilities and ensures package availability across the distribution network.

**Section sources**
- [index-v1.json:1-200](file://schemas/index-v1.json#L1-L200)
- [index.json:1-100](file://registry/index.json#L1-L100)

## Architecture Overview

The manifest system follows a layered architecture that separates concerns between definition, validation, and distribution:

```mermaid
sequenceDiagram
participant Author as "Package Author"
participant Linter as "Manifest Linter"
participant Schema as "JSON Schema"
participant Registry as "Registry Index"
participant Validator as "Package Validator"
Author->>Linter : Submit manifest
Linter->>Schema : Validate structure
Schema-->>Linter : Validation result
Linter->>Author : Feedback/errors
Author->>Validator : Submit package
Validator->>Registry : Update index
Registry-->>Validator : Confirmation
Validator-->>Author : Success notification
```

**Diagram sources**
- [lint-manifest-index.py:1-100](file://scripts/lint-manifest-index.py#L1-L100)
- [validate.py:1-100](file://scripts/validate.py#L1-L100)
- [add-package.py:1-100](file://scripts/add-package.py#L1-L100)

## Detailed Component Analysis

### Manifest Field Specifications

#### Required Fields

| Field | Type | Description | Validation Rules |
|-------|------|-------------|------------------|
| `name` | string | Unique package identifier | Must follow naming conventions, no spaces or special characters |
| `version` | string | Semantic version number | Must comply with semver specification |
| `description` | string | Human-readable package description | Non-empty string, reasonable length limits |
| `authors` | array | List of package authors | Array of strings with valid email formats |
| `license` | string | License identifier | SPDX-compliant license identifier |
| `homepage` | string | Package homepage URL | Valid HTTP/HTTPS URL |
| `repository` | string | Source code repository URL | Valid Git repository URL |
| `archive` | object | Package archive information | Contains filename and checksum fields |

#### Optional Fields

| Field | Type | Description | Default Value |
|-------|------|-------------|---------------|
| `keywords` | array | Search keywords | Empty array |
| `categories` | array | Package categories | Empty array |
| `dependencies` | object | External dependencies | Empty object |
| `nushell_version` | string | Minimum Nushell version | No minimum requirement |
| `readme` | string | Path to README file | None |
| `examples` | array | Example script paths | Empty array |

### Package Type Variations

#### Plugin Packages
Plugin manifests include additional fields for plugin-specific configuration:
- `plugin_type`: Specifies the type of Nushell plugin (external, internal)
- `entry_point`: Entry point function or executable path
- `capabilities`: Declares plugin capabilities and permissions

#### Script Packages
Script manifests focus on execution context and environment:
- `script_type`: Type of script (shell, python, etc.)
- `interpreter`: Required interpreter or runtime
- `environment`: Environment variables and settings

**Section sources**
- [FMotalleb-nu_plugin_desktop_notifications-0.114.1.json:1-100](file://specs/FMotalleb-nu_plugin_desktop_notifications-0.114.1.json#L1-L100)
- [SuaveIV-nu_script_wttr-0.1.0-main.json:1-100](file://specs/SuaveIV-nu_script_wttr-0.1.0-main.json#L1-L100)

### Versioning Strategy

The manifest system implements semantic versioning with support for pre-release and build metadata:

```mermaid
flowchart TD
Start([Version Bump]) --> CheckType{"Version Type?"}
CheckType --> |Major| MajorBump["Increment Major Version<br/>Reset Minor/Patch"]
CheckType --> |Minor| MinorBump["Increment Minor Version<br/>Reset Patch"]
CheckType --> |Patch| PatchBump["Increment Patch Version"]
MajorBump --> PreRelease{"Pre-release?"}
MinorBump --> PreRelease
PatchBump --> PreRelease
PreRelease --> |Yes| AddPreRelease["Add Pre-release Tag"]
PreRelease --> |No| Finalize["Finalize Version"]
AddPreRelease --> Finalize
Finalize --> Validate["Validate Against Schema"]
Validate --> Success{"Valid?"}
Success --> |Yes| Publish["Publish to Registry"]
Success --> |No| FixErrors["Fix Validation Errors"]
FixErrors --> Validate
Publish --> End([Complete])
```

**Diagram sources**
- [nu_version_constraint.py:1-100](file://scripts/nu_version_constraint.py#L1-L100)

### Dependency Management

Dependencies are declared using a flexible constraint system:

- **Exact Versions**: Pin to specific versions using `=` operator
- **Version Ranges**: Specify acceptable ranges with comparison operators
- **Wildcard Support**: Use `*` for flexible matching
- **Transitive Dependencies**: Automatic resolution of nested dependencies

**Section sources**
- [nu_version_constraint.py:1-100](file://scripts/nu_version_constraint.py#L1-L100)

## Dependency Analysis

The manifest system has well-defined dependency relationships:

```mermaid
graph LR
subgraph "Core Dependencies"
JSONSchema["JSON Schema Parser"]
SemVer["Semantic Version Parser"]
Crypto["Cryptographic Verification"]
end
subgraph "Validation Pipeline"
Linter["Manifest Linter"]
Validator["Package Validator"]
Resolver["Dependency Resolver"]
end
subgraph "Registry Operations"
IndexManager["Index Manager"]
Archiver["Archive Handler"]
Publisher["Package Publisher"]
end
JSONSchema --> Linter
SemVer --> Validator
Crypto --> Validator
Linter --> Resolver
Validator --> Resolver
Resolver --> IndexManager
IndexManager --> Archiver
Archiver --> Publisher
```

**Diagram sources**
- [lint-manifest-index.py:1-100](file://scripts/lint-manifest-index.py#L1-L100)
- [validate.py:1-100](file://scripts/validate.py#L1-L100)
- [add-package.py:1-100](file://scripts/add-package.py#L1-L100)

**Section sources**
- [lint-manifest-index.py:1-100](file://scripts/lint-manifest-index.py#L1-L100)
- [validate.py:1-100](file://scripts/validate.py#L1-L100)

## Performance Considerations

### Schema Validation Optimization
- Implement lazy loading for large schema definitions
- Cache parsed schema objects to avoid repeated parsing
- Use streaming validation for large manifest files

### Registry Index Performance
- Implement indexing strategies for fast lookups
- Use compression for archived packages
- Optimize concurrent access patterns

### Memory Management
- Process manifests in chunks for large registries
- Implement garbage collection for temporary objects
- Monitor memory usage during batch operations

## Troubleshooting Guide

### Common Manifest Errors

#### Schema Validation Failures
- **Invalid JSON syntax**: Ensure proper JSON formatting and escaping
- **Missing required fields**: Verify all mandatory fields are present
- **Type mismatches**: Check data types match schema expectations
- **Constraint violations**: Validate values against defined constraints

#### Version Resolution Issues
- **Unresolvable dependencies**: Check version constraints and availability
- **Circular dependencies**: Identify and break dependency cycles
- **Incompatible versions**: Ensure compatibility with target Nushell version

#### Archive and Integrity Problems
- **Checksum mismatches**: Verify archive integrity matches manifest
- **Missing archives**: Ensure referenced archives exist and are accessible
- **Permission issues**: Check file permissions and access rights

### Debugging Techniques

1. **Enable verbose logging** during validation processes
2. **Use schema validation tools** to identify structural issues
3. **Check network connectivity** for remote resource access
4. **Verify cryptographic signatures** for security validation

**Section sources**
- [lint-manifest-index.py:1-200](file://scripts/lint-manifest-index.py#L1-L200)
- [validate.py:1-200](file://scripts/validate.py#L1-L200)

## Conclusion

The manifest format specification provides a robust foundation for package management in the Nushell ecosystem. By following these guidelines, package authors can create reliable, maintainable packages that integrate seamlessly with the registry infrastructure. The combination of strict validation, flexible dependency management, and comprehensive error handling ensures a smooth experience for both authors and consumers.

Key benefits of this specification include:
- **Consistency**: Standardized format across all package types
- **Reliability**: Comprehensive validation and error handling
- **Flexibility**: Support for various package types and use cases
- **Security**: Cryptographic verification and integrity checking

## Appendices

### A. Complete Field Reference

A comprehensive reference of all manifest fields with detailed descriptions, examples, and validation rules.

### B. Migration Guide

Step-by-step instructions for migrating from older manifest formats to the current specification.

### C. Best Practices

Recommended practices for package organization, documentation, and maintenance.

### D. API Reference

Technical reference for programmatic access to manifest validation and manipulation APIs.