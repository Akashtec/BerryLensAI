# Data Quality

BerryLens relies on evidence. Bad data creates bad verdicts.

## Data Types

- raw data: search results and retrieved page content before cleaning
- clean data: normalized text and metadata
- processed data: deduplicated source/evidence records
- training data: labeled examples used to train models
- evaluation data: held-out benchmark claims and evidence
- runtime evidence: evidence used for one verification
- historical investigations: previous BerryLens reports stored in SQLite/Chroma

Training data, evaluation data, runtime evidence, and historical memory must not be mixed silently.

## Checks

BerryLens should check:

- empty documents
- malformed URLs
- duplicate URLs
- near-duplicate passages
- missing source title/domain
- invalid or missing timestamps
- excessive text length
- encoding problems
- copied or syndicated content
- low-relevance snippets

## Current Implementation

Implemented:

- URL normalization in `evidence_quality.py`
- tracking-parameter removal
- domain extraction
- source-tier lookup
- exact URL and near-passage deduplication
- Pydantic URL validation through `Source`

Missing:

- full page extraction quality checks
- publication-date normalization
- content-length limits for retrieved documents
- source-independence scoring
- data-quality reports for evaluation runs

## Policy

One failed or low-quality source should not crash the investigation. It should be recorded, skipped or downgraded, and surfaced as uncertainty when it affects the final verdict.
