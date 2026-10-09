# JUDICIAL2 Gate Pipeline Runbook

## Local batch evaluation

```powershell
python -m pipeline.evaluate
```

The evaluator reads only the two local cleaned JSON files. It emits aggregate
counts and never writes or sends case text.

## Local web adapter

```powershell
python -m pipeline.web
```

The service binds to `127.0.0.1` and exposes `GET /health` and `POST /api/gates`.
The request may contain a raw text string or a record with `gate1_fields`.
To use a local OpenAI-compatible model, set `JUDICIAL2_LOCAL_LLM_ENDPOINT` to
a loopback URL and send `use_model: true`. Non-loopback endpoints are rejected.
The model may extract facts only; it cannot select a route or offence.

MCP is reserved for public-law data construction. Case text, names, identifiers,
reports and investigation material must never be included in an MCP query.

## Legal-data boundary

Gate 2 only returns candidates whose exact `article_no` exists in the local
SQLite law table. Missing articles and missing explicit offence labels remain
`UNKNOWN`; the system does not infer a chapter from keywords. Additional law
rows require separately supplied and human-approved source output.
