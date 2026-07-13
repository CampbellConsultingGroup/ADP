---
spec_id: ADP-SPEC-015
title: Anthropic LLM Integration with Model Selection
status: implemented
version: 1.0.0
depends_on: [ADP-SPEC-006, ADP-SPEC-012, ADP-SPEC-014]
articles_engaged: [ART-V, ART-VI, ART-VII, ART-VIII]
quality_gates: [QG-05, QG-06, QG-08, QG-10]
owner: enterprise-architecture
---

# ADP-SPEC-015 — Anthropic LLM Integration with Model Selection

## Overview

Connect ADP to Anthropic's Claude family of models as the LLM provider for requirements extraction and architecture recommendations. Architects choose which Claude model to use for each pipeline (extraction vs. recommendations) via a settings panel in the workspace. The platform defaults to Claude Sonnet 4.6 but allows upgrading to Opus or downgrading to Haiku based on the task's complexity and cost requirements.

This feature also fixes the Vite development proxy (so the web canvas can reach the FastAPI backend through a single port) and repairs a database constraint violation that caused failures when confirming or rejecting multiple proposals in sequence.

## User Scenarios & Acceptance Criteria

- **Configure Anthropic.** Given `ADP_LLM_ENDPOINT=https://api.anthropic.com` and `ADP_LLM_API_KEY` set, when the platform starts, then the intake and recommendation pipelines call Claude models.
- **Choose model.** Given the architect opens the LLM Settings tab in the Requirements Intake screen, when they select a different model from the dropdown, then all subsequent extractions or recommendations use that model.
- **Extract requirements with Claude.** Given valid Anthropic credentials and bulk text submitted, when extraction completes, then Claude-extracted proposals appear in the UI with statements, kind, source excerpts, and confidence scores.
- **Web canvas reaches API.** Given the Vite dev server runs on :5173 and the API on :8001, when the canvas makes a relative `/api/` call, then Vite proxies it to the API server transparently.
- **Sequential confirm/reject.** Given multiple proposals from one extraction, when the architect confirms one and then rejects another, then both operations succeed without a database error.

## Functional Requirements

- **FR-001.** The platform MUST support Anthropic's Messages API (`/v1/messages`) in addition to OpenAI-compatible endpoints, detected automatically from the endpoint URL.
- **FR-002.** The platform MUST expose `GET /api/v1/config/models` returning all available Claude models with id, name, description, tier, and recommended use (extraction vs. recommendations).
- **FR-003.** The platform MUST expose `GET /api/v1/config/llm` returning the currently active models and API key status (configured: true/false) without revealing the key value.
- **FR-004.** The platform MUST expose `PUT /api/v1/config/llm` allowing independent selection of the extraction model and the recommendation model.
- **FR-005.** A `POST /api/v1/designs/{id}/intake` request MAY include a `model` field to override the globally configured extraction model for that single operation.
- **FR-006.** The intake screen MUST include a model selector inline with the Extract button and a dedicated LLM Settings tab showing connection status and per-pipeline model dropdowns.
- **FR-007.** The Vite development server MUST proxy all `/api/`, `/health`, and `/metrics` paths to the ADP API server so relative fetch calls work without CORS configuration or absolute URLs.
- **FR-008.** The platform MUST correctly handle sequential mutations (confirm + reject) on the same design without `UniqueViolationError` on audit entry IDs.

## Non-Functional Requirements

- **NFR-001.** The API key MUST NOT appear in any log, span attribute, API response body, or browser-accessible location.
- **NFR-002.** The LLM endpoint MUST gracefully degrade (return empty proposals, not error) when `ADP_LLM_API_KEY` is not configured.
- **NFR-003.** The Anthropic response parser MUST handle markdown code fences (`\`\`\`json...\`\`\``) that Claude sometimes wraps JSON responses in.

## Out of Scope

- LLM cost tracking and budget enforcement (future spec)
- Support for providers other than Anthropic and OpenAI-compatible endpoints
- Persistent model selection across server restarts (stored in-process for v1)

## Open Questions

None — all decisions resolved during implementation.
