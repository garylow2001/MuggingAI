from cerebras.cloud.sdk import Cerebras
from typing import List, Dict, Any, Optional
from app.core.config import settings
import json
import re
import logging
import os
from pathlib import Path
from datetime import datetime
import uuid
from app.services.prompts import (
    TopicExtractionPrompt,
    BatchNoteGenerationPrompt,
    clean_formatting,
)


# Get logger for this module
logger = logging.getLogger(__name__)


class NoteGenerator:
    def __init__(self, client: Optional[Cerebras] = None):
        # Lazy client: do not create the Cerebras client at import time to avoid warmup requests
        self._client = client
        self._extraction_temperature = 0.2
        self._extraction_top_p = 0.8
        self._note_generation_temperature = 0.2
        self._note_generation_top_p = 0.8

    def _get_client(self) -> Cerebras:
        if self._client is None:
            self._client = Cerebras(api_key=settings.cerebras_api_key)
        return self._client

    # Helpers
    def _extract_text_from_response(self, resp: Any) -> Optional[str]:
        """Extract text from the expected SDK response shape.

        This function only accepts the canonical shape: resp.choices[0].message.content
        and will raise a ValueError if the response does not conform. This makes
        upstream failures explicit instead of silently trying other shapes.
        Also extracts out the content from the json response that is wrapped in a fenced block.
        """
        if resp is None:
            raise ValueError("LLM response is None")

        # Expect the SDK response object where choices[0].message.content exists
        try:
            if not hasattr(resp, "choices"):
                raise ValueError('LLM response missing "choices" attribute')
            choices = resp.choices
            if not isinstance(choices, (list, tuple)) or len(choices) == 0:
                raise ValueError("LLM response has no choices")
            first = choices[0]
            if not hasattr(first, "message") or not hasattr(first.message, "content"):
                raise ValueError("LLM response choices[0] missing message.content")
            content = first.message.content
            if content is None:
                raise ValueError("LLM response message.content is None")

            # Normalize to string and strip surrounding whitespace
            text = str(content).strip()

            # More robust handling of multiple code block formats
            patterns = [
                r"```(?:json)\s*(.*?)\s*```",  # ```json ... ```
                r"```\s*([\{|\[].*?[\}|\]])\s*```",  # ``` {json} ``` or ``` [json] ```
                r"```(?:python|javascript|js)\s*({[\s\S]*?})\s*```",  # ```python/js/javascript {...} ```
                r"```\s*(.*?)\s*```",  # Any code block
            ]

            # Try to find and extract JSON from code blocks
            for pattern in patterns:
                m = re.search(pattern, text, flags=re.DOTALL | re.IGNORECASE)
                if m:
                    inner = m.group(1).strip()
                    if not inner:
                        continue  # Try next pattern if empty

                    # Additional cleaning for potential JSON formatting issues
                    if inner.startswith("{") or inner.startswith("["):
                        # Remove any markdown formatting that might have been included
                        inner = re.sub(r"^\s*```.*?\n", "", inner)
                        inner = re.sub(r"\n\s*```\s*$", "", inner)

                        # Log the extracted JSON for debugging
                        logger.debug("Extracted JSON from code block: %s", inner[:200])
                        return inner

            # If it looks like JSON but wasn't in a code block
            if (text.strip().startswith("{") and text.strip().endswith("}")) or (
                text.strip().startswith("[") and text.strip().endswith("]")
            ):
                logger.info("Found raw JSON without code block")
                return text.strip()

            # If no JSON or code block detected, return the trimmed content as-is
            # Clean any triple backticks at the beginning or end without content between them
            text = re.sub(r"^```.*?\n", "", text)
            text = re.sub(r"\n```\s*$", "", text)

            logger.debug("No code block or direct JSON found, returning raw text")
            return text
        except Exception as e:
            # propagate as ValueError so callers can detect and fail fast
            raise

    def _normalize_chapter_title(self, title: Optional[str]) -> str:
        if not title:
            return "Main Content"
        t = title.strip()
        # remove bracketed course codes and leading numbers
        t = re.sub(r"\[.*?\]", "", t)
        t = re.sub(r"^\d+\s*[-:\)]*", "", t)
        t = re.sub(r"\s{2,}", " ", t)
        t = t.strip(" -:[]()")
        return t or "Main Content"

    def _summarize_text(self, text: str, max_chars: int = 8000) -> str:
        if not text:
            return ""
        text = text.strip()
        if len(text) <= max_chars:
            return text
        sentences = re.split(r"(?<=[\.\?\!])\s+", text)
        out = []
        cur = 0
        for s in sentences:
            if cur + len(s) + 1 > max_chars:
                break
            out.append(s)
            cur += len(s) + 1
        return " ".join(out) if out else text[:max_chars]

    # --- LLM logging helpers -------------------------------------------------
    def _init_llm_log_for_run(self) -> Path:
        """Create a unique log file for the current run of process_course_content.

        Returns the path to the log file (which may be inside backend/llm_logs).
        """
        # place logs under the backend folder next to `app`
        base = Path(__file__).resolve().parents[2]
        logs_dir = base / "llm_logs"
        try:
            logs_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            # fallback to current working directory
            logs_dir = Path.cwd() / "llm_logs"
            logs_dir.mkdir(parents=True, exist_ok=True)

        name = (
            datetime.utcnow().strftime("llm_%Y%m%dT%H%M%S")
            + "_"
            + uuid.uuid4().hex[:8]
            + ".log"
        )
        return logs_dir / name

    def _log_llm_call(
        self,
        log_path: Path,
        call_index: int,
        call_name: str,
        prompt: str,
        resp_obj: Any,
    ) -> None:
        """Append a well-separated record of an LLM call to the provided log file.

        call_index: 1-based index for ordering multiple calls within a run.
        call_name: human-readable name like 'extraction' or 'batch_notes'.
        prompt: the text sent to the LLM.
        resp_obj: the raw response object returned by the SDK (may be dict or sdk object).
        """
        try:
            extracted = self._extract_text_from_response(resp_obj)
        except Exception:
            extracted = None

        header = f"--- LLM CALL #{call_index} [{call_name}] START ({datetime.utcnow().isoformat()} UTC) ---\n"
        prompt_section = "--- PROMPT ---\n" + (prompt or "") + "\n"
        response_section = (
            "--- RAW RESPONSE (repr) ---\n" + repr(resp_obj)[:10000] + "\n"
        )
        extracted_section = "--- EXTRACTED TEXT ---\n" + (extracted or "") + "\n"
        footer = f"--- LLM CALL #{call_index} [{call_name}] END ---\n\n"

        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(header)
                f.write(prompt_section)
                f.write(response_section)
                f.write(extracted_section)
                f.write(footer)
        except Exception:
            logger.exception("Failed to write LLM log to %s", log_path)

    def _build_extraction_prompt(self, text: str) -> str:
        return TopicExtractionPrompt(text)

    def _build_batch_notes_prompt(
        self,
        chapter_title: str,
        topics: List[Dict[str, Any]],
        chapter_summary: str,
        topic_snippets: Dict[str, str] | None = None,
    ) -> str:
        return BatchNoteGenerationPrompt(
            chapter_title, topics, chapter_summary, topic_snippets
        )

    def _find_relevant_snippets(
        self,
        topic_title: str,
        topic_desc: str,
        chunks: List[Dict[str, Any]],
        max_snippets: int = 5,
    ) -> List[str]:
        """Find content chunks that are most relevant to a given topic based on keyword matching.

        Args:
            topic_title: Title of the topic
            topic_desc: Description of the topic
            chunks: List of content chunks
            max_snippets: Maximum number of snippets to return

        Returns:
            List of relevant content snippets
        """
        # Create keywords from title and description
        # Extract words of at least 3 characters to use as keywords
        keywords = re.findall(r"\b\w{3,}\b", (topic_title + " " + topic_desc).lower())
        keywords = [
            k
            for k in keywords
            if k
            not in {
                "and",
                "the",
                "for",
                "with",
                "that",
                "this",
                "from",
                "what",
                "when",
                "where",
                "who",
                "how",
                "why",
            }
        ]

        # Score chunks by keyword matches
        scored_chunks = []
        for chunk in chunks:
            content = chunk.get("content", "").lower()
            # Base score: how many keywords appear in this chunk
            score = sum(1 for k in keywords if k in content)

            # Bonus points for title words (more significant)
            title_words = re.findall(r"\b\w{3,}\b", topic_title.lower())
            title_bonus = sum(3 for w in title_words if w in content and len(w) > 3)

            total_score = score + title_bonus
            if total_score > 0:
                scored_chunks.append((total_score, chunk.get("content", "")))

        # Sort by score (descending) and take top chunks
        scored_chunks.sort(reverse=True)
        result = [c for _, c in scored_chunks[:max_snippets]]

        # If we don't have enough relevant chunks, add the first few chunks as fallback
        if len(result) < 2:
            fallback = [
                c.get("content", "")
                for c in chunks[:3]
                if c.get("content") not in result
            ]
            result.extend(fallback[: 3 - len(result)])

        return result

    def _create_fallback_structure(self, text: str) -> Dict[str, Any]:
        lines = text.split("\n")
        chapters = []
        current_chapter = None
        current_content = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if (
                line.lower().startswith("chapter")
                or re.match(r"^\d+\.", line)
                or (line.isupper() and len(line) > 3)
            ):
                if current_chapter and current_content:
                    chapters.append(
                        {
                            "title": current_chapter,
                            "topics": [{"title": "Main Content", "description": ""}],
                        }
                    )
                current_chapter = line
                current_content = []
            else:
                current_content.append(line)

        if current_chapter and current_content:
            chapters.append(
                {
                    "title": current_chapter,
                    "topics": [{"title": "Main Content", "description": ""}],
                }
            )

        if not chapters:
            chapters.append(
                {
                    "title": "Main Content",
                    "topics": [{"title": "General", "description": ""}],
                }
            )

        logger.info("Fallback extractor produced %d chapters", len(chapters))
        return {"chapters": chapters}

    def generate_notes_for_topic(
        self, topic_title: str, topic_description: str, content: str
    ) -> str:
        # Clean the content first to remove formatting artifacts
        cleaned_content = clean_formatting(content)

        # Build focused prompt and log it; LLM call is commented out
        trimmed = self._summarize_text(cleaned_content, max_chars=3000)
        prompt = (
            f"Generate concise study notes for the topic '{topic_title}'.\nDescription: {topic_description}\n"
            f"Context:\n{trimmed}\n\nReturn readable bullet-point notes."
        )
        logger.info(
            "Prepared notes prompt for topic '%s' (len=%d) — LLM call commented out",
            topic_title,
            len(prompt),
        )
        logger.debug("Notes prompt for topic '%s':\n%s", topic_title, prompt)

        # If the content is very messy or unformatted, create a better fallback
        if "--- Page" in content or "\n" in content[:50]:
            # This appears to be raw lecture content - provide a cleaner fallback
            return (
                f"# {topic_title}\n\n"
                f"*This topic requires additional processing. Please regenerate notes for better content.*\n\n"
                f"## Summary\n{topic_description}\n\n"
                f"## Key Points\n- Important information about {topic_title}\n- Check source material for details"
            )

        # LLM invocation is commented out for testing; return extractive fallback with improved cleaning
        sentences = re.split(r"(?<=[\.!?])\s+", cleaned_content)
        bullets = []
        for s in sentences:
            s = s.strip()
            if not s or len(s) < 10:  # Skip very short snippets
                continue
            # Skip sentences with page markers or formatting artifacts
            if "Page" in s or "---" in s or "[ CS" in s:
                continue
            bullets.append(f"- {s}")
            if len(bullets) >= 8:
                break

        if not bullets:
            return (
                f"# {topic_title}\n\n"
                f"*Automated notes for this topic could not be generated.*\n\n"
                f"## Description\n{topic_description}"
            )

        return "\n".join(bullets)

    def process_course_content(
        self, chunks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        logger.info("Processing %d chunks into notes", len(chunks))

        # Create a per-run LLM log file so all LLM prompts/responses are captured
        llm_log = self._init_llm_log_for_run()
        logger.info("LLM log for this run: %s", llm_log)
        call_idx = 0

        structured_notes: List[Dict[str, Any]] = []

        # Process all chunks as a single unit
        logger.info("Processing %d chunks as single unit", len(chunks))
        content = " ".join([c.get("content", "") for c in chunks])
        content_summary = self._summarize_text(content, max_chars=8000)

        # Build extraction prompt
        extraction_prompt = self._build_extraction_prompt(content_summary)
        logger.info(
            "Prepared extraction prompt (len=%d)",
            len(extraction_prompt),
        )
        logger.debug(
            "Extraction prompt:\n%s",
            extraction_prompt,
        )

        # LLM extraction call: send extraction prompt and parse JSON response
        extractor_result = None
        try:
            logger.info(
                "Sending extraction prompt to LLM (len=%d)",
                len(extraction_prompt),
            )
            logger.debug("[LLM REQUEST][extraction] %s", extraction_prompt)
            client = self._get_client()
            extract_topic_resp = client.chat.completions.create(
                messages=[{"role": "user", "content": extraction_prompt}],
                model=getattr(settings, "cerebras_model", None),
                stream=False,
                max_completion_tokens=65536,
                temperature=self._extraction_temperature,
                top_p=self._extraction_top_p,
            )

            # Log LLM extraction call (prompt + raw response + extracted text)
            call_idx += 1
            try:
                self._log_llm_call(
                    llm_log,
                    call_idx,
                    "extraction",
                    extraction_prompt,
                    extract_topic_resp,
                )
            except Exception:
                logger.exception("Failed to record extraction LLM call to log")

            # Log raw response shape for debugging
            try:
                logger.debug(
                    "[LLM RAW RESPONSE][extraction] type=%s repr=%r",
                    type(extract_topic_resp),
                    extract_topic_resp,
                )
            except Exception:
                logger.debug(
                    "[LLM RAW RESPONSE][extraction] could not fully serialize response"
                )

            # extract text using helper
            text = self._extract_text_from_response(extract_topic_resp)
            if not text:
                raise ValueError("LLM returned no text for extraction")

            logger.info("Received extraction response (len=%d)", len(text))
            logger.debug("[LLM RESPONSE][extraction] %s", text)
            extractor_result = json.loads(text)
            if "chapters" not in extractor_result:
                raise ValueError("Extraction JSON missing chapters")
        except Exception as e:
            logger.exception(
                "Extraction LLM call failed or produced invalid JSON: %s", e
            )

            # Record the failed extraction prompt & exception to the per-run LLM log,
            # then re-raise so callers know extraction failed.
            try:
                with open(llm_log, "a", encoding="utf-8") as f:
                    f.write(
                        f"--- LLM CALL [extraction] FAILED ({datetime.utcnow().isoformat()} UTC) ---\n"
                    )
                    f.write("--- PROMPT ---\n" + extraction_prompt + "\n")
                    f.write("--- ERROR ---\n" + repr(e) + "\n\n")
            except Exception:
                logger.exception(
                    "Failed to append extraction failure to LLM log %s", llm_log
                )

            raise

        extracted_chapters = extractor_result.get("chapters", [])

        # Process extracted content (treating it as single unit)
        for ex in extracted_chapters:
            ex_title = ex.get("title") or "Main Content"
            topics = ex.get("topics") or [{"title": ex_title, "description": ""}]

            # Build topic -> supporting snippets map using improved retrieval method
            topic_snippets: Dict[str, str] = (
                {}
            )  # title -> summarized chunks related to topic
            for topic in topics:
                t_title = topic.get("title", "")
                t_desc = topic.get("description", "")

                # Use our new helper method to find relevant snippets based on topic title and description
                relevant_snippets = self._find_relevant_snippets(
                    topic_title=t_title,
                    topic_desc=t_desc,
                    chunks=chunks,
                    max_snippets=5,
                )

                # If we couldn't find any relevant snippets, fallback to the first few chunks
                if not relevant_snippets:
                    relevant_snippets = [c.get("content", "") for c in chunks[:3]]

                # Clean each snippet before combining them
                cleaned_snippets = [
                    clean_formatting(snippet) for snippet in relevant_snippets
                ]

                # Summarize the combined snippets to fit within character limit
                topic_snippets[t_title] = self._summarize_text(
                    " ".join(cleaned_snippets), max_chars=4000
                )

            # Build the batch prompt and log
            batch_prompt = self._build_batch_notes_prompt(
                ex_title, topics, content_summary, topic_snippets
            )
            logger.info(
                "Prepared batch notes prompt with %d topics (len=%d)",
                len(topics),
                len(batch_prompt),
            )
            logger.debug("Batch notes prompt:\n%s", batch_prompt)

            # LLM batch-note call: send single prompt and expect JSON array
            notes_json = None
            try:
                logger.info(
                    "Sending batch notes prompt to LLM (topics=%d len=%d)",
                    len(topics),
                    len(batch_prompt),
                )
                logger.debug("[LLM REQUEST][batch_notes] %s", batch_prompt)
                client = self._get_client()
                note_generation_resp = client.chat.completions.create(
                    messages=[{"role": "user", "content": batch_prompt}],
                    model=getattr(settings, "cerebras_model", "gpt-oss-120b"),
                    stream=False,
                    max_completion_tokens=65536,
                    temperature=self._note_generation_temperature,
                    top_p=self._note_generation_top_p,
                    response_format={"type": "json_object"},
                )

                # Log LLM batch-notes call
                call_idx += 1
                try:
                    self._log_llm_call(
                        llm_log,
                        call_idx,
                        "batch_notes",
                        batch_prompt,
                        note_generation_resp,
                    )
                except Exception:
                    logger.exception("Failed to record batch_notes LLM call to log")
                # Log raw response shape for debugging
                try:
                    logger.debug(
                        "[LLM RAW RESPONSE][batch_notes] type=%s repr=%r",
                        type(note_generation_resp),
                        note_generation_resp,
                    )
                except Exception:
                    logger.debug(
                        "[LLM RAW RESPONSE][batch_notes] could not fully serialize response"
                    )

                text2 = self._extract_text_from_response(note_generation_resp)
                if not text2:
                    raise ValueError("LLM returned no text for batch notes")

                logger.info("Received batch notes response (len=%d)", len(text2))
                logger.debug("[LLM RESPONSE][batch_notes] %s", text2)

                notes_json = json.loads(text2)

                try:
                    chapters = notes_json.get("chapters", [])
                    chapter = chapters[0]
                    chapter_title = chapter.get("title", "Main Content")
                    topics = chapter.get("topics", [])

                    for topic in topics:
                        # Transform the topic into the expected format
                        structured_note = {
                            "topic_title": topic.get("title", ""),
                            "chapter_title": chapter_title,
                            "notes_content": topic.get("notes", ""),
                        }
                        structured_notes.append(structured_note)
                except Exception:
                    logger.exception(
                        "Failed to extract topics from nested chapter structure"
                    )
            except Exception as e:
                logger.exception("Batch notes LLM call or JSON parse failed: %s", e)
        logger.info("Finished generating notes; total=%d", len(structured_notes))
        return structured_notes

    def extract_topics_and_chapters_for_logging(self, text: str) -> Dict[str, Any]:
        # Pre-summarize long text
        summary = self._summarize_text(text, max_chars=6000)
        prompt = self._build_extraction_prompt(summary)
        logger.info(
            "Prepared extraction prompt (len=%d) — LLM call commented out", len(prompt)
        )
        logger.debug("Extraction prompt:\n%s", prompt)

        # LLM call commented out for testing
        # client = self._get_client()
        # resp = client.chat.completions.create(...)

        # Use fallback extractor so downstream note generation proceeds (keeps behavior safe)
        return self._create_fallback_structure(summary)

    def log_prompts(self, chunks: List[Dict[str, Any]]) -> None:
        """Build and log extraction & batch-note prompts for the provided chunks.

        This method intentionally does not call the LLM; it logs the prompts (INFO and DEBUG)
        so you can inspect what would be sent, then returns None.
        """
        logger.info("Logging prompts for %d chunks", len(chunks))

        # Process all chunks as single unit
        logger.info("Processing %d chunks as single unit (prompt logging)", len(chunks))
        content = " ".join([c.get("content", "") for c in chunks])
        content_summary = self._summarize_text(content, max_chars=8000)

        # Extraction prompt (log full prompt)
        extraction_prompt = self._build_extraction_prompt(content_summary)
        logger.info(
            "[PROMPT][extraction] len=%d",
            len(extraction_prompt),
        )
        logger.debug(
            "[PROMPT][extraction]:\n%s",
            extraction_prompt,
        )

        # Use extractor (LLM disabled) to get the structure
        extractor_result = self.extract_topics_and_chapters_for_logging(content_summary)
        extracted_chapters = (
            extractor_result.get("chapters", [])
            if isinstance(extractor_result, dict)
            else []
        )

        for ex in extracted_chapters:
            ex_title = ex.get("title") or "Main Content"
            topics = ex.get("topics") or [{"title": ex_title, "description": ""}]

            # Batch prompt (would be a single LLM call per extracted section)
            batch_prompt = self._build_batch_notes_prompt(
                ex_title, topics, content_summary
            )
            logger.info(
                "[PROMPT][batch_notes] topics=%d len=%d",
                len(topics),
                len(batch_prompt),
            )
            logger.debug(
                "[PROMPT][batch_notes]:\n%s",
                batch_prompt,
            )

            # For each topic, build the focused notes prompt (but do not call the LLM)
            for topic in topics:
                t_title = topic.get("title")
                t_desc = topic.get("description", "")

                # Build topic-specific context the same way process_course_content does
                key = (t_title or "").lower()
                snippets = []
                for c in chunks:
                    ctext = c.get("content", "")
                    if key and key in ctext.lower():
                        snippets.append(ctext)
                    if len(snippets) >= 5:
                        break
                if not snippets:
                    snippets = [c.get("content", "") for c in chunks[:3]]

                context = " ".join(snippets)
                trimmed = self._summarize_text(context, max_chars=3000)

                # Build the exact per-topic prompt that would be sent to the LLM
                topic_prompt = (
                    f"Generate concise study notes for the topic '{t_title}'.\n"
                    f"Description: {t_desc}\n"
                    f"Context:\n{trimmed}\n\n"
                    "Return readable bullet-point notes."
                )

                logger.info(
                    "[PROMPT][topic] topic='%s' len=%d",
                    t_title,
                    len(topic_prompt),
                )
                logger.debug(
                    "[PROMPT][topic] for topic='%s':\n%s",
                    t_title,
                    topic_prompt,
                )

        logger.info("Finished logging prompts for chunks")
