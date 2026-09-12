# AI Engineering Guide

This guide explains the AI concepts through BerryLens, not as a generic textbook.

## AI

What it does: AI is the broad field of building systems that perform tasks requiring judgment, language understanding, prediction, or decision support.

Why BerryLens uses it: BerryLens needs to understand claims, find evidence, compare text, and explain verdicts.

Where it appears: `verification_service.py` coordinates AI-adjacent stages; `agents/` contains current model/search adapters.

## Machine Learning

What it does: ML learns patterns from data instead of relying only on handwritten rules.

Why BerryLens may use it: ML can benchmark claim classification, source ranking, duplicate detection, or evidence relevance.

Where it appears: `train_prior_classifier.py` is an optional training utility. No classical ML model is currently in the production verification path.

## Deep Learning

What it does: Deep learning uses neural networks with many layers, often for language, vision, speech, and representation learning.

Why BerryLens uses it: Sentence-transformer embeddings and LLM inference are deep-learning components.

Where it appears: `rag_memory.py` uses sentence-transformer embeddings through Chroma; `agents/claim_agent.py` can use Hugging Face/Mistral.

## NLP

What it does: NLP processes human language: sentences, entities, dates, claims, meaning, and relationships.

Why BerryLens needs it: Better claim analysis helps produce better searches and classify evidence more accurately.

Where it appears: `agents/analyst_agent.py` currently uses lightweight token overlap. A richer NLP layer is planned.

## Transformers

What it does: Transformers are neural architectures that power many modern embeddings, NLI models, and LLMs.

Why BerryLens uses them: They can represent semantic meaning and help compare claims with evidence.

Where it appears: `rag_memory.py` uses `all-MiniLM-L6-v2`; `agents/claim_agent.py` uses Mistral through Hugging Face when configured.

## Embeddings

What it does: Embeddings turn text into vectors so semantically similar text can be found by distance.

Why BerryLens uses it: Previous investigations can be found even when wording changes.

Where it appears: `rag_memory.py` stores claims in Chroma with sentence-transformer embeddings.

## Vector Database

What it does: A vector database stores embeddings and retrieves nearest neighbors.

Why BerryLens uses it: Chroma powers historical semantic memory.

Where it appears: `data/chroma_db` stores the current runtime Chroma data; `rag_memory.py` manages it.

## RAG

What it does: Retrieval-Augmented Generation gives a model retrieved context before it generates an answer.

Why BerryLens uses it: RAG can help reuse prior context and eventually ground summaries in retrieved evidence.

Where it appears: Current RAG is historical memory only. Fresh web evidence still drives verification.

## LLMs

What it does: LLMs generate and interpret language.

Why BerryLens uses them: LLMs can help generate search queries, classify evidence, and summarize results.

Where it appears: `agents/claim_agent.py` has optional Mistral query generation. `agents/analyst_agent.py` has a placeholder for structured generation but currently uses safe deterministic fallback.

## Agents

What it does: Agents combine reasoning steps with tools.

Why BerryLens uses them carefully: BerryLens benefits from logical roles, but uncontrolled autonomous loops would be risky and expensive.

Where it appears: `agents/claim_agent.py`, `agents/research_agent.py`, and `agents/analyst_agent.py` are stage adapters, not free-running agents.

## Tools

What it does: Tools are bounded actions an agent or service can call, such as search, database save, or memory lookup.

Why BerryLens needs them: Search and evidence retrieval must be observable, limited, and testable.

Where it appears: Tavily search in `agents/research_agent.py`, Chroma memory in `rag_memory.py`, SQLite persistence in `db_manager.py/db_manager.py`.

## Inference

What it does: Inference means running a trained model to produce outputs.

Why BerryLens uses it: Query generation and embeddings are inference tasks.

Where it appears: Hugging Face inference in `agents/claim_agent.py`; embedding inference in `rag_memory.py`.

## Training

What it does: Training fits model parameters from data.

Why BerryLens separates it: Training should not happen inside the web server.

Where it appears: `train_prior_classifier.py` is isolated from the production app.

## Fine-Tuning

What it does: Fine-tuning adapts a pretrained model to a specific dataset.

Why BerryLens may use it later: Evidence stance or claim-type classification might benefit if there is enough labeled data.

Where it appears: Not implemented.

## Evaluation

What it does: Evaluation measures whether a component works.

Why BerryLens needs it: Fact-checking quality cannot be trusted from demos alone.

Where it appears: `tests/` covers software contracts. AI evaluation datasets and metrics are planned.

## MLOps

What it does: MLOps manages datasets, models, prompts, evaluation, deployment, and monitoring over time.

Why BerryLens needs it: Claims, models, and evidence sources change. The system must know what model and policy produced a result.

Where it appears: Not implemented yet beyond pinned dependencies and documentation.
