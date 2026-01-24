# HANA Service Documentation

## Overview
HANA is a local Windows desktop assistant that uses OpenRouter as its LLM backend. The LLM only returns structured JSON; a local Python agent validates and executes actions.

## Architecture
- UI: PySide6 main window with chat and confirmation dialog.
- Core: Agent for OpenRouter requests, Safety for validation and risk detection, Executor for action dispatch and logging.
- Tools: File and system actions with safe delete to a local trash folder.
- Storage: SQLite actions log in hana.db.

## Safety
- Path validation blocks protected directories.
- Destructive actions require user confirmation.
- All actions are logged with timestamp, status, and args.

## Configuration
- OPENROUTER_API_KEY is required in .env or environment.
- OPENROUTER_MODEL optional; defaults to openrouter/auto.
- OPENROUTER_API_URL optional; defaults to OpenRouter chat completions endpoint.
