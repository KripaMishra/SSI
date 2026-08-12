# ADR-005: PII redaction pipeline for unstructured documents

## Status

Accepted (implemented; see ARTEFACT.md).

## Context

The knowledge base includes 30 unstructured `.txt` files (emails, notes,
circulars) containing personal data: phone numbers, email addresses, and names.
These documents are embedded into a vector store (ChromaDB), sent to an external
LLM for retrieval and citation, and surfaced verbatim in answers. Personal data
must not leave the pipeline to the model or the vector store.

## Decision

Run every document through a deterministic PII redaction pipeline before
ingestion (APPROACH.md §3):

1. **Phones**: `+91XXXXXXXXXX` → `<REDACTED_PHONE>` (4 redactions).
2. **Emails**: `name@domain.com` → `<REDACTED_EMAIL>` (4 redactions).
3. **Names**: `From:` header plus action-verb context (`spoke`, `said`,
   `reported`, …) → `<REDACTED_NAME>` (4 redactions).
4. **Chunking**: one chunk per document — the documents are short notes/emails,
   no semantic splitting needed.
5. **Metadata**: category, ref, tags, attributes, and redaction counts per
   document. Redacted documents live in `cleaned/cleaned_docs.jsonl`; the original
   plain-text files remain in `Data/docs/`.

## Consequences

- **Positive**: 12 redactions across 30 documents; PII never reaches the LLM
  context or the vector store; the pipeline is deterministic and auditable via
  redaction counts; original files are preserved for access-controlled access.
- **Negative**: name detection is regex/context-based and will miss paraphrased
  references (e.g., a first name without an action verb); originals remain on disk
  and need separate access control; no NER model, so coverage depends on pattern
  quality.

## Alternatives considered

- **Full NER model for redaction**: rejected — overkill for 30 short documents;
  adds model dependency and nondeterminism to a security-relevant step.
- **Drop the documents**: rejected — loses the unstructured knowledge the
  assistant must answer questions over.
- **Manual redaction**: rejected — not reproducible or auditable.
