---
spec_id: ADP-SPEC-014
title: Requirements Intake HTTP API and Web Screen
status: draft
version: 0.1.0
depends_on: [ADP-SPEC-001, ADP-SPEC-003, ADP-SPEC-006, ADP-SPEC-008, ADP-SPEC-009]
articles_engaged: [ART-I, ART-II, ART-IV, ART-VI, ART-VII, ART-VIII, ART-IX, ART-XIII]
quality_gates: [QG-01, QG-03, QG-04, QG-05, QG-09, QG-13, QG-14]
owner: enterprise-architecture
---

# ADP-SPEC-014 — Requirements Intake HTTP API and Web Screen

## Context

The requirements intake pipeline is fully implemented in Python (ADP-SPEC-006):
the `ExtractionOrchestrator` accepts text or structured form input, calls the LLM,
produces `ExtractedProposal` records, and writes confirmed `Requirement` records
to the canonical model. However, no HTTP routes are registered and no web screen
exists. This spec wires the existing Python pipeline to the API layer and builds
the intake screen in the C4 workspace web application.

## Overview

Wire the requirements intake pipeline (`adp.intake`) into the FastAPI application
as a set of REST endpoints, and build a React screen in the web workspace that lets
an architect submit requirements (as pasted text or structured form entries), review
AI-extracted proposals, and confirm or reject each one before it enters the canonical
model. The screen integrates into the existing workspace navigation.
