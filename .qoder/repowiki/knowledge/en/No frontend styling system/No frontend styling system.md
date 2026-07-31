---
kind: frontend_style
name: No frontend styling system
category: frontend_style
scope:
    - '**'
---

This repository is a Nushell package registry focused on publishing signed JSON indexes, per-package specs, and operational tooling. It contains no CSS, SCSS, Tailwind configuration, theme files, design tokens, or any other frontend styling assets. The only style-related references are Rust dependency names (anstyle) in the Cargo.lock for a CLI parser-check tool, which is unrelated to UI styling. There is no web interface, component library, or visual design system in this codebase.