# RAG Enhancement Phases - Implementation Tracker
# ================================================
# Based on production RAG best practices analysis
# Created: 2026-02-28
#
# STATUS KEY: [ ] = TODO, [~] = IN PROGRESS, [x] = DONE
#
# [x] Phase 1: Hybrid Search (BM25) + Cross-Encoder Re-ranker ✅ DONE
#     - bm25_search.py: BM25 keyword search engine
#     - reranker.py: Cross-encoder re-ranking
#     - QueryProcessor.py: Integrate hybrid pipeline
#     - vectorstore.py: Return raw chunk text for re-ranker
#
# [x] Phase 2: Citation Enforcement (MODIFIED) ✅ DONE
#     - llm.py: Clear separation between doc-grounded answers vs general knowledge
#     - Keep general knowledge fallback but ALWAYS clearly label it
#     - Add citation_coverage score to each response
#
# [x] Phase 3: Token-based Chunking ✅ DONE
#     - chunker.py: Switch from character-based to token-based (tiktoken)
#     - Add sentence boundary awareness
#     - Target: 500-800 tokens, 100 token overlap
#
# [x] Phase 4: Monitoring & Observability ✅ DONE
#     - Add Langfuse tracing to every RAG pipeline step
#     - Track: latency per step, tokens used, cost
#     - Log to usage_logs table
#
# [x] Phase 5: Evaluation Framework (RAGAS) ✅ DONE
#     - Create golden_qa.json (50+ verified QA pairs)
#     - Offline evaluation script with RAGAS metrics
#     - Measure: faithfulness, answer_relevancy, context_precision
#
# [x] Phase 6: Prompt Versioning ✅ DONE
#     - Move all prompts to prompts/*.yaml config files
#     - Version control prompt templates
#     - Support A/B testing
