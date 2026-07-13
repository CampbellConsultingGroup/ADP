---
spec_id: ADP-SPEC-013
title: Playwright End-to-End Test Suite
status: draft
version: 0.1.0
depends_on: [ADP-SPEC-003, ADP-SPEC-009, ADP-SPEC-010, ADP-SPEC-011, ADP-SPEC-012]
articles_engaged: [ART-IV]
quality_gates: [QG-04, QG-05]
owner: enterprise-architecture
---

# ADP-SPEC-013 — Playwright End-to-End Test Suite

## Overview

Add a full Playwright end-to-end test suite that exercises the ADP application through its real user interfaces and HTTP API — not mocks. Tests run against the live API server (backend) and optionally the web canvas (frontend). The suite covers the critical user journeys: theme endpoint integrity, document generation, round-trip import/export, health and metrics, and the C4 canvas workspace interactions. Every test uses the Playwright CLI for browser automation and the Playwright API client for REST assertions.

## Goals

- Prove the ADP application works end-to-end after every code change
- Catch regressions that unit and contract tests (which use mocks) cannot catch
- Give developers a single command to verify the full stack

## Out of Scope

- Load/performance testing
- Cross-browser matrix (Chromium only for v1)
- Authentication integration (tests use a bypass header or skip auth-gated paths that require a real IdP)
