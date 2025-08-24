from typing import List, Dict, Any
import re

# Text cleaning functions
def clean_formatting(text: str) -> str:
    """Clean up OCR/formatting artifacts from text content."""
    if not text:
        return ""
    # Replace 'n' markers with newlines when they appear between words
    text = re.sub(r'(?<=[a-zA-Z0-9])n(?=[A-Z])', '\n', text)
    # Replace 'q' markers with bullet points
    text = re.sub(r'(?<=\n)q', '• ', text)
    # Remove slide markers and page numbers
    text = re.sub(r'--- Page \d+ ---', '\n', text)
    text = re.sub(r'\bPage \d+\b', '', text)
    # Remove slide footers like [ CS2106 L1 - AY2526 S1 ]
    text = re.sub(r'\[\s*CS\d+.*?\]', '', text)
    # Fix OCR artifacts for bullet points
    text = re.sub(r'(?<=\n)([oO•\*\-]) ', '• ', text)
    # Fix common OCR errors
    text = re.sub(r'(?<=\w)l(?=\w)', 'i', text)  # Fix 'l' mistaken for 'i'
    text = re.sub(r'(?<=\w)0(?=\w)', 'o', text)  # Fix '0' mistaken for 'o'
    # Remove repeated punctuation
    text = re.sub(r'([.,;:!?])\1+', r'\1', text)
    # Fix multiple spaces and newlines
    text = re.sub(r'\s{2,}', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

# Reusable prompt fragments
STRICT_INSTRUCTIONS = (
    "STRICT INSTRUCTIONS (follow exactly):\n"
    "1) Return ONLY valid JSON and nothing else.\n"
    "2) Wrap the JSON response in a fenced code block with the language tag: ```json\\n{...}\\n``` (this helps with extraction).\n"
    "3) The top-level object must be: {\"chapters\": [...]}. Each chapter is an object with 'title' (string) and 'topics' (array).\n"
    "4) Each topic must be an object with 'title' (string) and 'description' (string).\n"
    "5) Consolidate and MERGE similar or duplicate lines into broader canonical topics. Do not create many micro-topics.\n"
    "6) Use concise Title Case for topic titles (no prefixes like 'Illustration:' or trailing question marks).\n"
    "7) Return at most 6 topics per chapter (prefer 3-5).\n"
    "8) Escape internal double-quotes in strings (use \\\" for a double-quote inside values).\n"
    "9) After producing the JSON, validate it is parseable with a strict JSON parser. If you cannot produce valid JSON, return this exact JSON: {\"error\":\"cannot_produce_valid_json\",\"notes\":\"brief reason\"} wrapped in the same fenced block.\n"
)

# Guidance for what 'topic' and 'description' should contain
TOPIC_DEFINITION = (
    "TOPIC & DESCRIPTION GUIDELINES:\n"
    "- Topic: a concise, high-level summary of a specific aspect of the chapter content. Use Title Case and keep the title short (3-6 words when possible).\n"
    "- Description: provide a DETAILED explanation (4-6 sentences) covering:\n"
    "  * Definition and core concepts specific to this topic (avoid generic descriptions)\n"
    "  * Key features or components unique to this concept\n"
    "  * Practical applications or concrete examples (use real-world scenarios)\n"
    "  * Relationships to other topics in the chapter\n"
    "  Package the description in an easy-to-learn format for students.\n"
    "- IMPORTANT: Each topic description must be DISTINCT and SPECIFIC to that topic - do not reuse content across topics.\n"
)


def TopicExtractionPrompt(text: str) -> str:
    """Build a concise, deterministic prompt for extracting chapters and topics.

    The model should return strict JSON only: {"chapters": [{"title":..., "topics": [{"title":..., "description":...}, ...]}, ...]}
    """
    # Compose prompt from reusable fragments so instructions are consistent and testable
    return (
        "You are an AI study assistant.\n"
        "Your task is to analyze the following texts from a source (lecture note/transcripts) and extract the main topics and subtopics.\n\n"
        + STRICT_INSTRUCTIONS + "\n"
        + TOPIC_DEFINITION + "\n"
        "Example output (exact shape expected):\n"
        "```json\n{\"chapters\":[{\"title\":\"Introduction to Operating Systems\",\"topics\":[{\"title\":\"Introduction to Operating Systems\",\"description\":\"...\"}]}]}\n```\n\n"
        "Text:\n" + text
    )


def BatchNoteGenerationPrompt(chapter_title: str, topics: List[Dict[str, Any]], chapter_summary: str, topic_snippets: Dict[str, str] | None = None) -> str:
    """Build a single prompt to generate study notes for all topics in a chapter.

    topic_snippets is an optional dict mapping topic_title -> supporting context (string).
    The model should return a JSON array like: [{"title": "...", "notes": "- bullet1\n- bullet2"}, ...]
    """
    prompt = (
        f"You are an AI study assistant. Your task is to generate comprehensive, student-friendly study notes for each topic in this chapter.\n\n"
        + STRICT_INSTRUCTIONS + "\n"
        + TOPIC_DEFINITION + "\n"
        f"NOTE GENERATION INSTRUCTIONS:\n"
        f"1. For each topic, create a JSON object with 'title' and 'notes' fields\n"
        f"2. The 'notes' field should contain 5-8 detailed bullet points as an array of strings\n"
        f"3. Each bullet point should be comprehensive and informative\n" 
        f"4. Include examples, definitions, and practical applications in your notes\n"
        f"5. If topics are similar, merge them and create combined, thorough notes\n"
        f"6. Return at most 6 topic objects\n\n"
        f"CRITICAL REQUIREMENTS:\n"
        f"1. Each topic's notes MUST be UNIQUE and DIRECTLY RELEVANT to that specific topic\n"
        f"2. DO NOT reuse the same content across different topics\n"
        f"3. Use the 'Relevant context' provided for each topic to tailor your notes\n"
        f"4. Focus on topic-specific information rather than generic information\n"
        f"5. Include concrete examples and practical applications specific to each topic\n\n"
        f"FORMAT REQUIREMENTS:\n"
        f"1. IMPORTANT: Return ONLY a flat JSON array of topic objects, not a nested structure\n"
        f"2. Format: [{{'title': 'Topic Name', 'notes': ['Point 1', 'Point 2', ...]}}]\n"
        f"3. Do NOT wrap the response in {{'chapters': [...]}}\n\n"
    )

    # Only include a brief chapter overview to save context space
    brief_summary = chapter_summary
    if len(chapter_summary) > 500:
        brief_summary = chapter_summary[:500] + "..."
    
    prompt += f"Chapter: {chapter_title}\nOverview: {clean_formatting(brief_summary)}\n\n"

    # For each topic, provide clean, relevant context
    prompt += "Topics to cover:\n"
    for t in topics:
        title = t.get("title") or "Untitled"
        desc = t.get("description", "")
        prompt += f"- Topic: {title}\n  Description: {desc}\n"
        if topic_snippets and title in topic_snippets:
            # Clean the context and limit length to avoid repetition
            clean_context = clean_formatting(topic_snippets[title])
            if len(clean_context) > 800:
                clean_context = clean_context[:800] + "..."
            prompt += f"  Relevant context:\n{clean_context}\n\n"

    prompt += "\nProduce the JSON array now. Do not include any extra explanation or text outside the fenced JSON block. If you cannot produce valid JSON, return {\"error\":\"cannot_produce_valid_json\",\"notes\":\"brief reason\"} inside the fenced block."
    return prompt
