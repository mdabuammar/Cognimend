# Trust Engine

The Cognimend Trust Engine is the verification layer behind the document assistant. It is designed to make answer quality visible without changing the simple user flow of uploading documents and asking questions.

## What It Checks

- Whether answer claims are supported by uploaded documents
- Whether citations actually back the answer
- Whether retrieved documents disagree with each other
- Whether the available documents are missing required information
- Whether source dates or versions affect the answer
- Whether quality is drifting over time

## Main Signals

- Claim Passport: claim-level support results for an answer
- Strict Evidence Mode: conservative mode that refuses unsupported answers
- Citation Truth Score: citation support score for cited chunks
- Conflict Detection: visible warning when sources disagree
- Evidence Gap Detection: identifies missing source material
- Freshness Awareness: warns when date or version metadata matters
- RAG Health Timeline: live timeline of quality events

## Repair Safety

Cognimend can suggest evidence-aware repair candidates when quality signals degrade. Failed repairs are rejected, and stable configuration can be restored through rollback-safe configuration handling.

The repair workflow is intentionally conservative. Missing evidence should lead to user action, such as uploading a better document, rather than a blind configuration change.
