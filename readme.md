# MinimAIze (learning build)

A personal, from-scratch rebuild of the **MinimAIze** project — an AI-powered Data Product
Health & Minimization Copilot. The goal here is **learning**: understand every moving part
(databases, metadata, scoring, AI explanations, dashboards, and Git) before doing the real
thing.

## What it does (in one sentence)
Looks at *metadata* about an organization's data products, scores how healthy vs. wasteful
each one is, estimates cost and potential savings, and uses AI to explain its reasoning —
while a human always makes the final call.

## Tech stack
- **Python** — all the logic
- **SQLite/DuckDB** — a local stand-in for Snowflake/Databricks metadata
- **Claude API** — natural-language explanations and recommendations
- **Streamlit** — a simple dashboard (later phases)

## Project status
🚧 Phase 0: setup & Git foundations.

## Build roadmap
0. Setup & Git foundations
1. Fake "data warehouse" (synthetic metadata)
2. Data product + asset inventory
3. Usage analysis (inactivity, query counts)
4. Cost & savings analysis
5. Health Score + MinimAIze Score
6. AI recommendation & explanation engine
7. Dashboard + conversational queries
8. Demo polish
