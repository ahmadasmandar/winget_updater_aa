# 🌟 SOUL.md — Project Ethos & Engineering Philosophy

> **Project**: Winget Package Manager (GUI)  
> **Core Mission**: Provide a reliable, beautiful, and transparent desktop graphical interface for Windows Package Manager (`winget`) without compromising performance, stability, or control.

---

## 🧭 Core Principles

### 1. The Code is the Single Source of Truth
- Documentation and tests describe what **is**, never what is merely planned or wished for.
- Interfaces, contracts, and behaviors are rooted directly in repository evidence.

### 2. High-Contrast, Modern Aesthetics (Never Settle for Default)
- Desktop applications must look and feel first-class.
- Dark mode must maintain high contrast (never dark text on dark surfaces).
- Every visual state—idle, loading, updating, succeeded, skipped, failed—must have immediate, clear visual feedback with curated color tokens.

### 3. Transparent, Informative Feedback Over Black Boxes
- Never hide what the underlying package manager is doing.
- Stream every subprocess command line, status transition, exit code, and stdout/stderr output directly into the developer-friendly activity log.
- Color-code log levels distinctly (Green `[INFO]`, Yellow `[WARN]`, Red `[ERROR]`) using monospace developer fonts (Fira Code / Fira Mono).

### 4. Non-Blocking, Responsive Execution
- All heavy operations (catalog discovery, multi-package upgrades, detail queries) MUST execute on asynchronous background threads (`QThread`) with cooperative cancellation tokens (`CancelMixin`).
- The UI main loop must remain 100% responsive with live progress updates and elapsed timers.

### 5. Safe, Atomic State Management
- Configuration changes (exclusions, preferences) must write atomically (write-to-temporary + atomic replace) to prevent corruption.
- If corrupt configuration is detected, create an automatic timestamped backup and gracefully fallback to safe defaults.

### 6. Minimal, Purposeful Changes
- Preserve existing working interfaces and architecture.
- Do not introduce bloat, unnecessary dependencies, or speculative features.
- Test proportionally after every change.
