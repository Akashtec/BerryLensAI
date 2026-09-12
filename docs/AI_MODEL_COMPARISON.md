# AI Model Comparison

BerryLens should use the simplest technique that solves a real problem and can be measured.

## Classical ML

Examples:

- TF-IDF plus Logistic Regression
- simple relevance classifier
- source/noise classifier

Good for:

- fast baselines
- explainable feature-based classification
- cheap offline experiments

Weak at:

- deep semantic reasoning
- new entities or nuanced context
- long evidence passages

BerryLens status: optional/planned. `train_prior_classifier.py` is isolated and not part of production verification.

## Transformer Encoder Models

Examples:

- sentence-transformers
- NLI models
- relevance rerankers

Good for:

- semantic similarity
- entailment/contradiction/neutral classification
- embeddings and reranking

Weak at:

- explaining complex multi-source reasoning by itself
- temporal or source-quality policy without extra logic

BerryLens status: implemented for embeddings through Chroma. NLI is planned for benchmarked evidence classification.

## LLMs

Examples:

- Mistral through Hugging Face
- future Gemini or local Ollama provider

Good for:

- query planning
- summarizing evidence
- extracting structured fields from messy text
- explaining verdicts in readable language

Weak at:

- hallucination if not grounded
- inconsistent structured output without validation
- cost and latency

BerryLens status: partial. Query generation can use Mistral; structured analyst generation is not yet wired.

## NLI

What it does:

```text
claim + evidence passage -> entailment / contradiction / neutral
```

Good for:

- direct evidence stance classification
- reducing unsupported LLM judgment

Weak at:

- long documents
- claims requiring arithmetic, dates, or multiple-hop context
- domain mismatch

BerryLens status: planned. It must be benchmarked before production use.

## RAG

What it does:

```text
query -> retrieve context -> generate answer grounded in retrieved text
```

Good for:

- grounding model summaries
- reusing historical investigations
- reducing unsupported generation

Weak at:

- bad retrieval produces bad grounding
- stale retrieved context can mislead time-sensitive claims
- retrieved text can contain prompt injection

BerryLens status: partial. Chroma stores historical memory; fresh web evidence remains the primary source.

## Recommended Roles

| Task | Preferred first approach |
| --- | --- |
| Validate request | Pydantic schema |
| Generate search queries | deterministic fallback plus optional LLM |
| Retrieve evidence | Tavily/search adapter |
| Deduplicate sources | URL normalization plus text similarity |
| Historical lookup | embeddings plus Chroma |
| Evidence stance | benchmark NLI and structured LLM against fixtures |
| Final verdict | deterministic policy |
| User explanation | LLM or template grounded in structured evidence |
