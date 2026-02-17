"""
Legal Document Analyzer Service — Enhanced with Chunked Analysis

Handles large legal documents by splitting into chunks, analyzing each independently,
then synthesizing a comprehensive structured report.
"""
import os
import json
import math
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = "gpt-4o-mini"

# Max chars per chunk for individual analysis
CHUNK_SIZE = 8000
# Max chars for a single-pass analysis (small documents)
SINGLE_PASS_LIMIT = 12000


def _build_analysis_prompt(language="en"):
    """The master system prompt for structured legal analysis."""
    tamil_instruction = ""
    if language == "ta":
        tamil_instruction = """\n\nCRITICAL LANGUAGE INSTRUCTION: You MUST respond in Tamil (தமிழ்).
- ALL text values in your JSON response (summary, descriptions, findings, plain_english, impact, notes, suggestions, titles, document_type, finding, description, clause_name, original_text, issue, suggestion) MUST be written in Tamil (தமிழ்).
- The risk_breakdown keys MUST be in Tamil: use "நிதி" instead of "Financial", "சட்டம்" instead of "Legal", "இணக்கம்" instead of "Compliance", "செயல்பாட்டு" instead of "Operational".
- Keep only JSON structural keys (like "summary", "risk_score", "issues") in English.
- Keep proper nouns, company names, and specific legal terms of art in English.
- EVERYTHING ELSE must be in Tamil script. This is mandatory."""
    return """You are an expert Legal AI Assistant specializing in contract analysis, regulatory compliance, risk assessment, and financial auditing.

Analyze the provided legal document text thoroughly and return a SINGLE valid JSON object with this EXACT structure:

{
  "summary": "3-5 sentence overview of what this document is, its purpose, and key terms",
  "document_type": "Type of document (e.g. Employment Contract, NDA, Insurance Policy, Lease Agreement, Terms of Service, Corporate Bylaws, etc.)",
  "risk_score": 0-100 integer (0=no risk, 100=extremely risky. Score based on missing protections, unfair terms, ambiguity, and liability exposure),
  "risk_breakdown": {
    "Financial": 0-100,
    "Legal": 0-100,
    "Compliance": 0-100,
    "Operational": 0-100
  },
  "critical_findings": [
    {
      "id": 1,
      "finding": "One-sentence description of the most important finding",
      "impact": "Why this matters to the reader",
      "severity": "high|medium|low"
    }
  ],
  "issues": [
    {
      "id": 1,
      "title": "Short issue title",
      "description": "Detailed explanation of the issue and its implications",
      "severity": "high|medium|low",
      "category": "Category (e.g. Liability, Termination, IP Rights, Payment Terms, Privacy, Compliance, Warranty, Indemnification)",
      "page_reference": "Section or page reference if identifiable"
    }
  ],
  "key_clauses": [
    {
      "id": 1,
      "clause_name": "Name of the clause (e.g. Limitation of Liability, Non-Compete, Indemnification)",
      "original_text": "Brief quote or paraphrase from the document",
      "plain_english": "What this clause means in simple, everyday language",
      "risk_level": "high|medium|low",
      "notes": "Any concerns or things to watch out for"
    }
  ],
  "financial_issues": [
    {
      "id": 1,
      "title": "Short title (e.g. Late Payment Penalty, Uncapped Liability)",
      "description": "Details about the financial term, amount, or exposure",
      "amount": "Dollar amount or percentage if specified, otherwise 'Not specified'",
      "risk_level": "high|medium|low"
    }
  ],
  "actions": [
    {
      "id": 1,
      "title": "Specific recommended action",
      "description": "Why this action is needed and what to do",
      "priority": "urgent|important|recommended"
    }
  ],
  "conflicts": [
    {
      "id": 1,
      "title": "Short conflict title",
      "description": "Explanation of the contradiction or inconsistency",
      "sections": ["Section A reference", "Section B reference"]
    }
  ],
  "spelling_grammar_issues": [
    {
      "id": 1,
      "text": "The problematic text or phrase",
      "issue": "What is wrong (typo, grammar, ambiguous wording, inconsistent terminology)",
      "suggestion": "Suggested correction",
      "location": "Where in the document this appears"
    }
  ],
  "entities": [
    {
      "name": "Party or entity name",
      "role": "Their role in the document (e.g. Employer, Contractor, Insurer, Landlord)"
    }
  ]
}

RULES:
- Return ONLY valid JSON. No markdown formatting, no ```json blocks.
- Every array must have at least one item if applicable, or be empty [].
- Be thorough: identify ALL issues, not just obvious ones.
- For risk_score: consider missing standard protections, one-sided terms, ambiguity, potential for disputes.
- For financial_issues: identify ALL monetary amounts, fees, penalties, caps, thresholds, payment schedules.
- For spelling_grammar_issues: look for typos, grammatical errors, inconsistent use of defined terms, ambiguous pronouns, missing commas that change meaning.
- For key_clauses: explain EVERY significant clause in plain English.
- For critical_findings: identify the 3-5 MOST IMPORTANT things a non-lawyer should know about this document.
- Severity/priority should reflect real legal impact, not just formality.""" + tamil_instruction


def _build_chunk_prompt(language="en"):
    """Prompt for analyzing individual chunks of a large document."""
    tamil_instruction = ""
    if language == "ta":
        tamil_instruction = """\n\nCRITICAL LANGUAGE INSTRUCTION: You MUST respond in Tamil (தமிழ்). ALL text values in your JSON (summaries, descriptions, notes, titles, plain_english, issue, suggestion) MUST be in Tamil (தமிழ்). Keep only JSON structural keys in English. Keep proper nouns in English. Everything else MUST be Tamil."""
    return """You are an expert Legal AI Assistant. You are analyzing ONE SECTION of a larger legal document.

Extract ALL findings from this section and return a JSON object with:

{
  "section_summary": "Brief summary of what this section covers",
  "issues": [{"title": "...", "description": "...", "severity": "high|medium|low", "category": "...", "page_reference": "..."}],
  "key_clauses": [{"clause_name": "...", "original_text": "...", "plain_english": "...", "risk_level": "high|medium|low", "notes": "..."}],
  "financial_issues": [{"title": "...", "description": "...", "amount": "...", "risk_level": "high|medium|low"}],
  "conflicts_hints": ["Any terms that might conflict with other sections"],
  "spelling_grammar_issues": [{"text": "...", "issue": "...", "suggestion": "...", "location": "..."}],
  "entities": [{"name": "...", "role": "..."}],
  "risk_indicators": ["List of risk factors found in this section"]
}

Return ONLY valid JSON. Be thorough — identify everything relevant.""" + tamil_instruction


def _build_synthesis_prompt(chunk_count, language="en"):
    """Prompt for synthesizing multiple chunk analyses into a final report."""
    return f"""You are an expert Legal AI Assistant. You have analyzed {chunk_count} sections of a legal document separately. 
Now SYNTHESIZE all the section analyses below into ONE comprehensive final report.

{_build_analysis_prompt(language)}

ADDITIONAL SYNTHESIS RULES:
- Merge duplicate issues — if the same issue appears in multiple sections, combine them into one with the most complete description.
- Identify cross-section conflicts by comparing terms from different sections.
- Calculate overall risk_score by weighing all section findings.
- Generate critical_findings for the TOP 3-5 most important takeaways across ALL sections.
- Assign sequential IDs to all items.
- De-duplicate entities.
- Merge and de-duplicate spelling/grammar issues."""


def _call_llm(system_prompt, user_content, temperature=0.15):
    """Make an LLM call with error handling."""
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            temperature=temperature,
            response_format={"type": "json_object"}
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"LLM call error: {e}")
        raise


def _split_into_chunks(text, chunk_size=CHUNK_SIZE):
    """Split text into overlapping chunks, trying to break at paragraph boundaries."""
    if len(text) <= chunk_size:
        return [text]
    
    chunks = []
    start = 0
    overlap = 500  # chars of overlap between chunks
    
    while start < len(text):
        end = min(start + chunk_size, len(text))
        
        # Try to break at a paragraph or sentence boundary
        if end < len(text):
            # Look for paragraph break near the end
            para_break = text.rfind('\n\n', start + chunk_size // 2, end)
            if para_break > start:
                end = para_break + 2
            else:
                # Try sentence break
                sent_break = max(
                    text.rfind('. ', start + chunk_size // 2, end),
                    text.rfind('.\n', start + chunk_size // 2, end)
                )
                if sent_break > start:
                    end = sent_break + 2
        
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        
        if end >= len(text):
            break
        start = end - overlap
    
    return chunks


def analyze_legal_document(text_content: str, page_count: int = None, language: str = "en") -> dict:
    """
    Analyze a legal document using LLM with intelligent chunking for large documents.
    
    Args:
        text_content: The full text content of the document
        page_count: Number of pages in the original document (optional)
        
    Returns:
        Dictionary with structured analysis results
    """
    if not text_content or not text_content.strip():
        return {
            "error": "No text content provided",
            "summary": "No content to analyze",
            "risk_score": 0,
            "issues": [],
            "actions": [],
            "conflicts": [],
            "key_clauses": [],
            "financial_issues": [],
            "critical_findings": [],
            "spelling_grammar_issues": [],
            "entities": [],
            "risk_breakdown": {"Financial": 0, "Legal": 0, "Compliance": 0, "Operational": 0}
        }

    text = text_content.strip()
    estimated_pages = page_count or max(1, math.ceil(len(text) / 3000))

    try:
        if len(text) <= SINGLE_PASS_LIMIT:
            # Small document — single pass
            print(f"Legal analysis: single pass ({len(text)} chars, ~{estimated_pages} pages)")
            result_str = _call_llm(
                _build_analysis_prompt(language),
                f"Analyze this legal document (~{estimated_pages} pages):\n\n{text}"
            )
            result = json.loads(result_str)
        else:
            # Large document — chunked analysis + synthesis
            chunks = _split_into_chunks(text)
            print(f"Legal analysis: chunked ({len(text)} chars, {len(chunks)} chunks, ~{estimated_pages} pages)")
            
            # Phase 1: Analyze each chunk
            chunk_analyses = []
            for i, chunk in enumerate(chunks):
                print(f"  Analyzing chunk {i+1}/{len(chunks)}...")
                try:
                    chunk_result_str = _call_llm(
                        _build_chunk_prompt(language),
                        f"Section {i+1} of {len(chunks)} from a legal document:\n\n{chunk}"
                    )
                    chunk_analyses.append(chunk_result_str)
                except Exception as e:
                    print(f"  Chunk {i+1} analysis failed: {e}")
                    chunk_analyses.append(json.dumps({"section_summary": f"Analysis failed for section {i+1}", "issues": [], "key_clauses": [], "financial_issues": [], "entities": []}))
            
            # Phase 2: Synthesize all chunk results
            print(f"  Synthesizing {len(chunk_analyses)} chunk analyses...")
            combined_input = f"Document info: ~{estimated_pages} pages, {len(chunks)} sections analyzed.\n\n"
            for i, analysis in enumerate(chunk_analyses):
                combined_input += f"=== SECTION {i+1} ANALYSIS ===\n{analysis}\n\n"
            
            result_str = _call_llm(
                _build_synthesis_prompt(len(chunks), language),
                combined_input
            )
            result = json.loads(result_str)

        # Ensure all expected fields exist with defaults
        result.setdefault("summary", "Analysis completed")
        result.setdefault("document_type", "Legal Document")
        result.setdefault("risk_score", 0)
        result.setdefault("risk_breakdown", {"Financial": 0, "Legal": 0, "Compliance": 0, "Operational": 0})
        result.setdefault("critical_findings", [])
        result.setdefault("issues", [])
        result.setdefault("key_clauses", [])
        result.setdefault("financial_issues", [])
        result.setdefault("actions", [])
        result.setdefault("conflicts", [])
        result.setdefault("spelling_grammar_issues", [])
        result.setdefault("entities", [])
        result["total_pages"] = estimated_pages

        # Assign IDs if missing
        for field in ["critical_findings", "issues", "key_clauses", "financial_issues", "actions", "conflicts", "spelling_grammar_issues"]:
            for i, item in enumerate(result.get(field, []), 1):
                if isinstance(item, dict):
                    item.setdefault("id", i)

        print(f"Legal analysis complete: risk_score={result['risk_score']}, "
              f"issues={len(result['issues'])}, clauses={len(result['key_clauses'])}, "
              f"financial={len(result['financial_issues'])}, critical={len(result['critical_findings'])}")
        
        return result
        
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
        print(f"Raw response: {result_str[:500] if 'result_str' in dir() else 'N/A'}")
        return {
            "error": f"Failed to parse analysis: {e}",
            "summary": "Analysis completed but results could not be parsed",
            "risk_score": 0,
            "issues": [],
            "actions": [],
            "conflicts": [],
            "key_clauses": [],
            "financial_issues": [],
            "critical_findings": [],
            "spelling_grammar_issues": [],
            "entities": [],
            "risk_breakdown": {"Financial": 0, "Legal": 0, "Compliance": 0, "Operational": 0}
        }
    except Exception as e:
        print(f"Legal analysis error: {e}")
        return {
            "error": f"Failed to analyze document: {str(e)}",
            "summary": "Analysis failed",
            "risk_score": 0,
            "issues": [],
            "actions": [],
            "conflicts": [],
            "key_clauses": [],
            "financial_issues": [],
            "critical_findings": [],
            "spelling_grammar_issues": [],
            "entities": [],
            "risk_breakdown": {"Financial": 0, "Legal": 0, "Compliance": 0, "Operational": 0}
        }
