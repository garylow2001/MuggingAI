from typing import List, Dict, Any


def TopicExtractionPrompt(text: str) -> str:
    """Build a concise, deterministic prompt for extracting chapters and topics.

    The model should return strict JSON only: {"chapters": [{"title":..., "topics": [{"title":..., "description":...}, ...]}, ...]}
    """
    return (
        "You are an AI study assistant.\n"
        "Your task is to analyze the following texts from a source (lecture note/transcripts) and extract the main topics and subtopics.\n"
        "Return ONLY valid JSON with a single top-level object that has a 'chapters' array.\n"
        "Each chapter must be an object with 'title' (string) and 'topics' (array).\n"
        "Each topic must be an object with 'title' (string) and 'description' (short string).\n"
        "Do not include any extra explanation or text outside the JSON.\n\n"
        "Text:\n" + text
    )


def BatchNoteGenerationPrompt(chapter_title: str, topics: List[Dict[str, Any]], chapter_summary: str, topic_snippets: Dict[str, str] | None = None) -> str:
    """Build a single prompt to generate study notes for all topics in a chapter.

    topic_snippets is an optional dict mapping topic_title -> supporting context (string).
    The model should return a JSON array like: [{"title": "...", "notes": "- bullet1\n- bullet2"}, ...]
    """
    prompt = (
        f"You are an AI study assistant. Your task is to generate concise, student-friendly study notes for each topic in this chapter.\n"
        f"For the chapter: '{chapter_title}' produce a JSON array where each element is an object with 'title' and 'notes' (notes should be newline-separated bullet points).\n"
        f"Return ONLY valid JSON.\n\n"
    )

    prompt += "Chapter summary:\n" + (chapter_summary or "") + "\n\n"

    prompt += "Topics and context:\n"
    for t in topics:
        title = t.get("title") or "Untitled"
        desc = t.get("description", "")
        prompt += f"- Topic: {title}\n  Description: {desc}\n"
        if topic_snippets and title in topic_snippets:
            prompt += f"  Context snippets:\n{topic_snippets[title]}\n"

    prompt += "\nProduce the JSON array now. Do not include any extra explanation or text outside the JSON."
    return prompt
