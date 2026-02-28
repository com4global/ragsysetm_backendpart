"""
LLM Module with Citation Enforcement + Prompt Versioning
=========================================================
Phase 2: Strict citation enforcement
Phase 6: Prompts loaded from YAML config files (prompts/ directory)

To edit prompts: modify prompts/rag_query_en.yaml — no Python changes needed!
"""

import os
import re
import logging
from dotenv import load_dotenv
from openai import OpenAI
from typing import Dict, Optional

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = "gpt-4o-mini"

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# PROMPT LOADING — YAML first, hardcoded fallback
# ──────────────────────────────────────────────────────────────

def _load_prompt_from_yaml(name: str) -> str:
    """Try to load a prompt from YAML config. Returns empty string if not found."""
    try:
        from prompt_loader import get_system_prompt
        prompt = get_system_prompt(name)
        if prompt and prompt.strip():
            return prompt
    except Exception as e:
        logger.debug(f"YAML prompt '{name}' not available: {e}")
    return ""

# Hardcoded fallbacks (used if YAML files are missing/broken)
_FALLBACK_PROMPT_EN = (
    "You are an intelligent document Q&A assistant. Your PRIMARY job is to answer questions using the provided context blocks.\n\n"
    "CITATION RULES (STRICT):\n"
    "1. For EVERY claim or fact that comes from the provided context, you MUST cite the source inline using this exact format: [DocumentName.pdf, Page X]\n"
    "2. Place citations immediately after the relevant sentence or claim, not at the end of the entire answer.\n"
    "3. If multiple documents support the same point, cite all of them: [Doc1.pdf, Page 2] [Doc2.pdf, Page 5]\n"
    "4. NEVER fabricate citations — only cite documents that actually appear in the context.\n\n"
    "ANSWER STRUCTURE:\n"
    "- If the context FULLY answers the question: Answer entirely from documents with inline citations.\n"
    "- If the context PARTIALLY answers the question: First give the document-based answer with citations, "
    "then add: '\\n\\n📌 *Additional information (not from your documents):*\\n' followed by supplementary general knowledge.\n"
    "- If the context does NOT answer the question at all: Start with: "
    "'📌 *This information was not found in your uploaded documents. Here\\'s what I know from general knowledge:*\\n' "
    "then provide a helpful answer from your general knowledge.\n\n"
    "QUALITY RULES:\n"
    "- Be thorough and helpful — never refuse to answer.\n"
    "- Always prefer document-based answers when context is available.\n"
    "- Keep the same friendly, professional tone regardless of source."
)

_FALLBACK_PROMPT_TA = (
    "\n\nCRITICAL LANGUAGE INSTRUCTION: You MUST respond in THANGLISH style. "
    "Use Tamil script (தமிழ்) as the primary language, but mix in English words "
    "naturally for technical terms, greetings, and common phrases. "
    "Use everyday conversational Tamil, NOT formal literary Tamil. "
    "Example: '[HRPolicy.pdf, Page 3] படி, இந்த policy-ன் main point என்னன்னா...' "
    "Document names, technical terms, and citation brackets can stay in English. "
    "For general knowledge prefix, use: '📌 *இந்த information உங்க documents-ல இல்ல. General knowledge-லிருந்து:*' "
    "Keep the tone friendly and easy to understand like daily Tamil conversation."
)

# Also keep old names as aliases for backward compatibility
SYSTEM_PROMPT_EN = _FALLBACK_PROMPT_EN
SYSTEM_PROMPT_TA_ADDON = _FALLBACK_PROMPT_TA


# ──────────────────────────────────────────────────────────────
# MAIN QUERY FUNCTION
# ──────────────────────────────────────────────────────────────

def query_llm_with_context(question: str, context: str, language: str = "en") -> str:
    """
    Query the LLM with retrieved context. Enforces citation format.
    
    Prompt loading priority:
    1. YAML config file (prompts/rag_query_en.yaml) — editable without code changes
    2. Hardcoded fallback (above) — always available as safety net
    
    Args:
        question: User's question
        context: Retrieved document chunks formatted as context string
        language: Response language ("en" for English, "ta" for Tamil/Thanglish)
        
    Returns:
        LLM-generated answer with inline citations
    """
    # Try YAML config first, fall back to hardcoded
    system_prompt = _load_prompt_from_yaml("rag_query_en") or _FALLBACK_PROMPT_EN
    
    # Add Tamil language instruction when requested
    if language == "ta":
        ta_addon = _load_prompt_from_yaml("rag_query_ta") or _FALLBACK_PROMPT_TA
        system_prompt += "\n\n" + ta_addon

    # Load user prompt template (or use default)
    try:
        from prompt_loader import get_user_prompt_template
        template = get_user_prompt_template("rag_query_en")
        user_prompt = template.format(context=context, question=question)
    except Exception:
        user_prompt = f"CONTEXT:\n{context}\n\nUSER QUESTION:\n{question}"

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
    )
    return response.choices[0].message.content


# ──────────────────────────────────────────────────────────────
# CITATION COVERAGE SCORING — Phase 2 Enhancement
# ──────────────────────────────────────────────────────────────

def compute_citation_coverage(answer: str, sources: list) -> Dict:
    """
    Compute how well the answer is grounded in cited sources.
    
    Returns:
        {
            "citation_coverage": 0.0-1.0 (% of answer from documents),
            "citations_found": ["HRPolicy.pdf", ...],
            "is_grounded": True/False (majority from documents),
            "has_general_knowledge": True/False
        }
    """
    if not answer:
        return {
            "citation_coverage": 0.0,
            "citations_found": [],
            "is_grounded": False,
            "has_general_knowledge": False
        }
    
    # Find all citations in the answer [DocName.pdf, Page X]
    citation_pattern = r'\[([^\]]+\.(?:pdf|docx|doc|txt|csv|xlsx|pptx|xml|epub|json|md))\s*(?:,\s*Page\s*\w+)?\]'
    citations_found = re.findall(citation_pattern, answer, re.IGNORECASE)
    unique_citations = list(set(citations_found))
    
    # Check for general knowledge markers
    general_knowledge_markers = [
        "not from your documents",
        "not found in your uploaded documents",
        "general knowledge",
        "documents-ல இல்ல",  # Tamil marker
        "📌"
    ]
    has_general_knowledge = any(marker.lower() in answer.lower() for marker in general_knowledge_markers)
    
    # Calculate coverage
    # Split answer into sentences
    sentences = [s.strip() for s in re.split(r'[.!?]\s+', answer) if s.strip()]
    if not sentences:
        sentences = [answer]
    
    cited_sentences = 0
    for sentence in sentences:
        # Check if this sentence has a citation nearby
        if re.search(citation_pattern, sentence, re.IGNORECASE):
            cited_sentences += 1
    
    # If we found general knowledge marker, check what % is before vs after
    if has_general_knowledge and "📌" in answer:
        parts = answer.split("📌")
        doc_part_len = len(parts[0].strip()) if parts[0].strip() else 0
        total_len = len(answer)
        coverage = doc_part_len / total_len if total_len > 0 else 0.0
    elif citations_found and not has_general_knowledge:
        coverage = 1.0  # All from documents
    elif not citations_found and has_general_knowledge:
        coverage = 0.0  # All from general knowledge
    else:
        # Mixed — estimate based on cited sentences
        coverage = cited_sentences / len(sentences) if sentences else 0.0
    
    return {
        "citation_coverage": round(min(coverage, 1.0), 2),
        "citations_found": unique_citations,
        "is_grounded": coverage >= 0.5,
        "has_general_knowledge": has_general_knowledge
    }
