# Startup V2 marketplace search architecture

Updated: 2026-09-01

## Implemented request path

`POST /api/app/explore/search` is now the authority for authenticated marketplace
discovery. It loads public `intent_posts` projections only and applies membership,
owner, block, environment, lifecycle, capacity, Request, Community, Connection,
saved, type, location, date, tag, and freshness gates before bounded text and
freshness ranking. Responses include privacy-safe surfaced reasons and a 50-result
ceiling.

The browser no longer needs to download every public Post and decide discovery
authority locally. The API explicitly reports which retrieval layers were active.

## Google Cloud capability decision

Firestore Native mode supports K-nearest-neighbor vector search and documents
combining vector search with filters. Firestore does not generate embeddings.
Vertex AI supports `gemini-embedding-001`, including multilingual retrieval
embeddings and configurable output dimensions.

Primary references:

- [Firestore vector search](https://docs.cloud.google.com/firestore/native/docs/vector-search)
- [Firestore StructuredQuery `findNearest`](https://docs.cloud.google.com/firestore/docs/reference/rest/v1/StructuredQuery)
- [Vertex AI text embeddings](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/embeddings/get-text-embeddings)

## Why vectors are not marked complete

Production has no vector index, public-Post embedding field, or embedding backfill
history. Startup V2 therefore does not claim semantic retrieval yet. The API
returns `semantic_vector: false` and uses structured filters plus bounded text
relevance.

Candidate activation requires selecting the dimension, creating the candidate
index, generating public-only `RETRIEVAL_DOCUMENT` embeddings, recording model and
Post versions, idempotently backfilling, generating `RETRIEVAL_QUERY` embeddings,
fusing vector distance with deterministic compatibility, and accepting
multilingual quality, cost, latency, staleness, and failure behavior.

Private Intent data, chat, Memory, contact fields, and negotiation instructions
must never be embedded into the public search vector.

## Demo separation

The real marketplace excludes the demo namespace and explicitly labelled
synthetic Posts. It recognizes only affirmative labels such as `demo_data`,
controlled-demo titles/profiles, and known test-run markers. It does not guess
that an unlabelled account is synthetic. Remaining historical identities must be
classified from explicit seed/account evidence during migration.
