"""
EdTech AI Teaching Service
Transforms PDF chunks into interactive AI teacher dialogues.
Uses LLM to generate topic-wise discussions between two AI teachers.

CRITICAL: ALL content MUST be strictly grounded in the user's actual documents.
No generic/hallucinated topics allowed.
"""

import os
import json
import logging
from typing import List, Dict, Optional
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = "gpt-4o-mini"
logger = logging.getLogger(__name__)

# ── Teacher Pair Pool ────────────────────────────────────────────────
# Each pair has unique names, emojis, roles, personalities, and OpenAI TTS voices.
# Voices: alloy, echo, fable, onyx, nova, shimmer
TEACHER_PAIRS = [
    {
        "a": {"name": "Priya", "emoji": "👩‍🏫", "role": "Concept Explorer", "personality": "Enthusiastic, uses real-world analogies, asks thought-provoking questions", "voice": "nova"},
        "b": {"name": "Arjun", "emoji": "🧑‍🔬", "role": "Deep Diver", "personality": "Analytical, provides deep explanations from the document, uses examples", "voice": "onyx"},
    },
    {
        "a": {"name": "Maya", "emoji": "🌟", "role": "Storyteller", "personality": "Turns every concept into a memorable story or narrative, engaging and dramatic", "voice": "shimmer"},
        "b": {"name": "Ravi", "emoji": "📚", "role": "Scholar", "personality": "Precise and methodical, breaks down complex ideas into structured steps", "voice": "echo"},
    },
    {
        "a": {"name": "Zara", "emoji": "🎯", "role": "Challenger", "personality": "Loves to challenge assumptions, asks 'what if' questions, provocative thinker", "voice": "alloy"},
        "b": {"name": "Dev", "emoji": "💡", "role": "Innovator", "personality": "Creative problem-solver, connects concepts to cutting-edge applications", "voice": "fable"},
    },
    {
        "a": {"name": "Ananya", "emoji": "🦋", "role": "Simplifier", "personality": "Makes complex topics feel effortless, uses everyday examples students love", "voice": "nova"},
        "b": {"name": "Kabir", "emoji": "🔭", "role": "Explorer", "personality": "Curious and wide-ranging, connects topics to broader themes and discoveries", "voice": "echo"},
    },
    {
        "a": {"name": "Diya", "emoji": "✨", "role": "Motivator", "personality": "Energetic and encouraging, celebrates every learning moment, builds confidence", "voice": "shimmer"},
        "b": {"name": "Sai", "emoji": "🧠", "role": "Analyst", "personality": "Logical thinker, loves data and evidence, provides structured breakdowns", "voice": "onyx"},
    },
    {
        "a": {"name": "Isha", "emoji": "🎨", "role": "Visualizer", "personality": "Thinks in pictures and diagrams, paints vivid mental images of concepts", "voice": "alloy"},
        "b": {"name": "Vikram", "emoji": "⚡", "role": "Energizer", "personality": "Fast-paced and exciting, makes even dry topics feel thrilling", "voice": "fable"},
    },
    {
        "a": {"name": "Neha", "emoji": "🌍", "role": "Connector", "personality": "Links topics to real-world events and global contexts, culturally aware", "voice": "nova"},
        "b": {"name": "Rohit", "emoji": "🔬", "role": "Experimenter", "personality": "Hands-on thinker, suggests experiments and practical demonstrations", "voice": "echo"},
    },
    {
        "a": {"name": "Kavya", "emoji": "🎭", "role": "Performer", "personality": "Dramatic and expressive, makes lessons feel like a show, uses humor", "voice": "shimmer"},
        "b": {"name": "Aditya", "emoji": "📐", "role": "Architect", "personality": "Builds understanding brick by brick, systematic and thorough", "voice": "onyx"},
    },
]


def get_random_teacher_pair(topic: str) -> dict:
    """
    Pick a teacher pair deterministically based on the topic string.
    Same topic always gets the same pair for consistency.
    Different topics get different pairs for variety.
    """
    import hashlib
    topic_hash = int(hashlib.md5(topic.lower().strip().encode()).hexdigest(), 16)
    idx = topic_hash % len(TEACHER_PAIRS)
    return TEACHER_PAIRS[idx]


def extract_topics(chunks_text: str, language: str = "en", doc_names: Optional[List[str]] = None) -> List[Dict]:
    """
    Extract key topics STRICTLY from the provided document chunks.
    No hallucination — only topics explicitly present in the content.
    """
    lang_instruction = ""
    if language == "ta":
        lang_instruction = "\nIMPORTANT: Generate all topic titles and descriptions in Tamil (தமிழ்). Keep document names in English."

    doc_list = ""
    if doc_names:
        doc_list = f"\nThe content comes from these documents: {', '.join(doc_names)}"

    prompt = f"""You are a curriculum designer. Your job is to extract TEACHING TOPICS from the document content below.

CRITICAL RULES:
1. ONLY extract topics that are EXPLICITLY discussed in the provided content below.
2. DO NOT invent topics, DO NOT use your general knowledge, DO NOT add topics that aren't in the content.
3. Every topic title must directly reference a concept, term, or subject found in the text.
4. The description must use ONLY information from the document chunks.
5. Key concepts must be actual terms/phrases found in the content.
6. Include the source document name for each topic.
7. If the content is about HR policies, the topics should be about HR policies. If it's about science, the topics should be about science. Match the actual content.
{doc_list}
{lang_instruction}

Return as JSON:
{{
  "topics": [
    {{
      "title": "Topic title from the document content",
      "description": "1-2 sentence description using ONLY content from the documents",
      "key_concepts": ["actual term from doc", "another term from doc", "third term"],
      "difficulty": "beginner|intermediate|advanced",
      "source_document": "filename.pdf"
    }}
  ]
}}

Extract 3-8 topics. For large textbooks or multi-chapter books, try to cover different chapters/sections.
Every topic MUST be traceable to specific content in the chunks below.

DOCUMENT CONTENT:
{chunks_text[:15000]}"""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You extract teaching topics STRICTLY from provided document content. You NEVER invent or hallucinate topics. Every topic must be traceable to the provided text. Return valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        result = json.loads(response.choices[0].message.content)
        if isinstance(result, dict) and "topics" in result:
            return result["topics"]
        if isinstance(result, list):
            return result
        return result.get("topics", [])
    except Exception as e:
        logger.error(f"Topic extraction failed: {e}")
        return []


def generate_teacher_dialogue(topic: str, content: str, language: str = "en") -> Dict:
    """
    Generate an engaging dialogue between two AI teachers about a topic.
    The dialogue MUST be grounded in the actual document content provided.
    Teachers are randomly selected from the pool based on the topic.
    """
    # Pick a random teacher pair for this topic
    pair = get_random_teacher_pair(topic)
    teacher_a = pair["a"]
    teacher_b = pair["b"]

    lang_instruction = ""
    if language == "ta":
        lang_instruction = """
CRITICAL: Generate the ENTIRE dialogue in Tamil (தமிழ்). 
Teacher names can stay in English, but ALL dialogue text MUST be in Tamil.
Use simple, conversational Tamil that students can easily understand."""

    prompt = f"""You are a script writer for an EdTech platform. Create an engaging dialogue between two AI teachers.

TOPIC: {topic}

REFERENCE CONTENT FROM USER'S DOCUMENTS:
{content[:8000]}

CRITICAL RULES:
1. The dialogue MUST be based ONLY on the reference content above.
2. DO NOT add information that is NOT in the reference content.
3. Use real-world analogies to explain the concepts, but the core facts must come from the documents.
4. Every explanation must be traceable to the provided content.
5. Teachers should quote or paraphrase actual content from the documents.

TEACHER ROLES:
- Teacher A ({teacher_a['emoji']} {teacher_a['name']}): {teacher_a['personality']}
- Teacher B ({teacher_b['emoji']} {teacher_b['name']}): {teacher_b['personality']}

DIALOGUE RULES:
- 8-12 exchanges long
- Include at least one "aha moment" where a complex concept becomes simple
- End with quiz questions BASED ON the document content
- Make it conversational and fun, NOT a lecture
{lang_instruction}

Return as JSON:
{{
  "title": "Lesson title based on the document topic",
  "teachers": [
    {{"name": "{teacher_a['name']}", "emoji": "{teacher_a['emoji']}", "role": "{teacher_a['role']}"}},
    {{"name": "{teacher_b['name']}", "emoji": "{teacher_b['emoji']}", "role": "{teacher_b['role']}"}}
  ],
  "dialogue": [
    {{"speaker": "{teacher_a['name']}", "text": "...", "type": "question"}},
    {{"speaker": "{teacher_b['name']}", "text": "...", "type": "explanation"}}
  ],
  "quiz": [
    {{
      "question": "First quiz question from the document content",
      "options": ["A) ...", "B) ...", "C) ...", "D) ..."],
      "correct": 0,
      "explanation": "Explanation from the document"
    }},
    {{
      "question": "Second quiz question from the document content",
      "options": ["A) ...", "B) ...", "C) ...", "D) ..."],
      "correct": 2,
      "explanation": "Explanation from the document"
    }},
    {{
      "question": "Third quiz question from the document content",
      "options": ["A) ...", "B) ...", "C) ...", "D) ..."],
      "correct": 1,
      "explanation": "Explanation from the document"
    }}
  ],
  "key_takeaways": ["Takeaway from document", "Another takeaway", "Third takeaway"]
}}

Type can be: "question", "explanation", "analogy", "story", "aha_moment", "summary"
"""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You create engaging teacher dialogues STRICTLY based on provided document content. Never add information not found in the source documents. Return valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            response_format={"type": "json_object"}
        )
        result = json.loads(response.choices[0].message.content)
        # Attach voice mappings so frontend can use them for TTS
        result["voice_map"] = {
            teacher_a["name"]: teacher_a["voice"],
            teacher_b["name"]: teacher_b["voice"]
        }
        return result
    except Exception as e:
        logger.error(f"Dialogue generation failed: {e}")
        return {"error": str(e)}


def generate_lesson_from_chunks(
    chunks: List[str],
    topic: Optional[str] = None,
    language: str = "en"
) -> Dict:
    """
    Main entry point: takes chunks, optionally a topic,
    and generates a full interactive lesson with AI teacher dialogue.
    """
    combined_text = "\n\n".join(chunks)

    if not topic:
        topics = extract_topics(combined_text, language)
        if topics:
            topic = topics[0].get("title", "General Overview")
        else:
            topic = "Document Overview"

    lesson = generate_teacher_dialogue(topic, combined_text, language)
    lesson["source_chunks_count"] = len(chunks)

    return lesson
