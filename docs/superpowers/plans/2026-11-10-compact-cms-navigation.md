# Compact CMS Navigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make CMS page navigation compact, polished, accessible, and usable at existing responsive breakpoints.

**Architecture:** Keep routing and Jinja page ownership unchanged. Improve the shared CMS shell markup and its existing responsive CSS, with HTTP-level layout tests protecting semantic and active-state behavior.

**Tech Stack:** FastAPI, Jinja2, plain CSS, Python `unittest`.

**Spec:** `docs/superpowers/specs/2026-11-10-compact-cms-navigation-design.md`

## Global Constraints

- Preserve `/cms/articles`, `/cms/users`, and `/cms/logout` behavior.
- Add no JavaScript, frontend build step, or dependency.
- Keep current desktop, collapsed-tablet, and phone layout modes at 780px and 560px.

## Review Focus

- Articles must be the sole current link on its page and editor errors.
- Administrators must be the sole current link on its page.
- Collapsed icon links must keep accessible names and tooltips.
- Phone navigation must retain labels and a reachable sign-out control.
- Keyboard focus must remain visible against active and inactive surfaces.

---

### Task 1: Shared CMS navigation

**Files:**
- Modify: `tests/test_cms_layout.py`
- Modify: `tests/test_cms_editor_open.py`
- Modify: `app/templates/cms/base.html.j2`
- Modify: `app/static/cms.css`

**Interfaces:**
- Consumes: existing `active_page`, `page_title`, and `/cms/*` routes.
- Produces: named navigation links, exact `aria-current` state, semantic breadcrumb, compact responsive styles.

- [ ] **Step 1: Write failing HTTP-level assertions** for exact current/inactive links, accessible link names, the linked breadcrumb home, and editor-error Articles state.
- [ ] **Step 2: Run focused tests and confirm RED** with missing accessible names and breadcrumb navigation.
- [ ] **Step 3: Update the shared Jinja shell** with the two replacement SVG symbols, persistent link names/tooltips, semantic breadcrumb markup, and mobile-reachable logout structure.
- [ ] **Step 4: Update navigation CSS** with shorter borderless rows, restrained active indicator, refined icons, and responsive label/logout behavior.
- [ ] **Step 5: Run focused tests and confirm GREEN.**
- [ ] **Step 6: Run the complete test suite, Ruff, and compileall.**
- [ ] **Step 7: Verify both pages visually** at desktop, 780px, 560px, and 320px; confirm navigation, focus, and sign-out visibility.

### Task 2: Neutral navigation polish

**Files:**
- Modify: `app/templates/cms/base.html.j2`
- Modify: `app/static/cms.css`
- Test: `tests/test_cms_layout.py`

**Interfaces:**
- Consumes: the existing shared navigation markup and CMS design tokens.
- Produces: a neutral active state, ID-card administrator glyph, and tighter shared radius scale.

- [ ] **Step 1: Add a failing static-asset contract test** for the ID-card symbol, graphite active navigation, removed colored indicator, and 10px/12px/16px radius tokens.
- [ ] **Step 2: Run the focused test and confirm RED.**
- [ ] **Step 3: Replace the administrator symbol and update only the shared CSS tokens and navigation/shell radius rules.**
- [ ] **Step 4: Run the focused test and confirm GREEN.**
- [ ] **Step 5: Run the complete test suite, Ruff, compileall, and diff checks.**
