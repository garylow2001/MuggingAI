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
from app.services.prompts import TopicExtractionPrompt, BatchNoteGenerationPrompt


# Get logger for this module
logger = logging.getLogger(__name__)


class NoteGenerator:
    def __init__(self, client: Optional[Cerebras] = None):
        # Lazy client: do not create the Cerebras client at import time to avoid warmup requests
        self._client = client

    def _get_client(self) -> Cerebras:
        if self._client is None:
            self._client = Cerebras(api_key=settings.cerebras_api_key)
        return self._client

    # Helpers
    def _extract_text_from_response(self, resp: Any) -> Optional[str]:
        """Try several common response shapes from the Cerebras SDK to extract the text content."""
        try:
            if resp is None:
                return None
            # direct attribute
            if hasattr(resp, 'text') and resp.text:
                return resp.text

            # choices -> message -> content
            choices = None
            if hasattr(resp, 'choices'):
                choices = resp.choices
            elif isinstance(resp, dict):
                choices = resp.get('choices')

            if choices:
                # try multiple shapes
                first = choices[0]
                # object with .message.content
                if hasattr(first, 'message') and getattr(first.message, 'content', None):
                    return first.message.content
                # dict shape
                if isinstance(first, dict):
                    msg = first.get('message')
                    if isinstance(msg, dict) and msg.get('content'):
                        return msg.get('content')
                    # delta/content (streaming)
                    delta = first.get('delta')
                    if isinstance(delta, dict) and delta.get('content'):
                        return delta.get('content')
                    # old text field
                    if first.get('text'):
                        return first.get('text')

            # fallback to str()
            return str(resp)
        except Exception:
            return None

    def _normalize_chapter_title(self, title: Optional[str]) -> str:
        if not title:
            return 'Main Content'
        t = title.strip()
        # remove bracketed course codes and leading numbers
        t = re.sub(r'\[.*?\]', '', t)
        t = re.sub(r'^\d+\s*[-:\)]*', '', t)
        t = re.sub(r'\s{2,}', ' ', t)
        t = t.strip(' -:[]()')
        return t or 'Main Content'

    def _summarize_text(self, text: str, max_chars: int = 4000) -> str:
        if not text:
            return ''
        text = text.strip()
        if len(text) <= max_chars:
            return text
        sentences = re.split(r'(?<=[\.\?\!])\s+', text)
        out = []
        cur = 0
        for s in sentences:
            if cur + len(s) + 1 > max_chars:
                break
            out.append(s)
            cur += len(s) + 1
        return ' '.join(out) if out else text[:max_chars]

    # --- LLM logging helpers -------------------------------------------------
    def _init_llm_log_for_run(self) -> Path:
        """Create a unique log file for the current run of process_course_content.

        Returns the path to the log file (which may be inside backend/llm_logs).
        """
        # place logs under the backend folder next to `app`
        base = Path(__file__).resolve().parents[2]
        logs_dir = base / 'llm_logs'
        try:
            logs_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            # fallback to current working directory
            logs_dir = Path.cwd() / 'llm_logs'
            logs_dir.mkdir(parents=True, exist_ok=True)

        name = datetime.utcnow().strftime('llm_%Y%m%dT%H%M%S') + '_' + uuid.uuid4().hex[:8] + '.log'
        return logs_dir / name

    def _log_llm_call(self, log_path: Path, call_index: int, call_name: str, prompt: str, resp_obj: Any) -> None:
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
        prompt_section = "--- PROMPT ---\n" + (prompt or '') + "\n"
        response_section = "--- RAW RESPONSE (repr) ---\n" + repr(resp_obj)[:10000] + "\n"
        extracted_section = "--- EXTRACTED TEXT ---\n" + (extracted or '') + "\n"
        footer = f"--- LLM CALL #{call_index} [{call_name}] END ---\n\n"

        try:
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(header)
                f.write(prompt_section)
                f.write(response_section)
                f.write(extracted_section)
                f.write(footer)
        except Exception:
            logger.exception("Failed to write LLM log to %s", log_path)

    def _build_extraction_prompt(self, text: str) -> str:
        return TopicExtractionPrompt(text)

    def _build_batch_notes_prompt(self, chapter_title: str, topics: List[Dict[str, Any]], chapter_summary: str, topic_snippets: Dict[str, str] | None = None) -> str:
        return BatchNoteGenerationPrompt(chapter_title, topics, chapter_summary, topic_snippets)

    # Public methods
    def extract_topics_and_chapters(self, text: str) -> Dict[str, Any]:
        # Pre-summarize long text
        summary = self._summarize_text(text, max_chars=6000)
        prompt = self._build_extraction_prompt(summary)
        logger.info("Prepared extraction prompt (len=%d) — LLM call commented out", len(prompt))
        logger.debug("Extraction prompt:\n%s", prompt)

        # LLM call commented out for testing
        # client = self._get_client()
        # resp = client.chat.completions.create(...)

        # Use fallback extractor so downstream note generation proceeds (keeps behavior safe)
        return self._create_fallback_structure(summary)

    def _create_fallback_structure(self, text: str) -> Dict[str, Any]:
        lines = text.split('\n')
        chapters = []
        current_chapter = None
        current_content = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if (line.lower().startswith('chapter') or re.match(r'^\d+\.', line) or (line.isupper() and len(line) > 3)):
                if current_chapter and current_content:
                    chapters.append({'title': current_chapter, 'topics': [{'title': 'Main Content', 'description': ''}]})
                current_chapter = line
                current_content = []
            else:
                current_content.append(line)

        if current_chapter and current_content:
            chapters.append({'title': current_chapter, 'topics': [{'title': 'Main Content', 'description': ''}]})

        if not chapters:
            chapters.append({'title': 'Main Content', 'topics': [{'title': 'General', 'description': ''}]})

        logger.info("Fallback extractor produced %d chapters", len(chapters))
        return {'chapters': chapters}

    def generate_notes_for_topic(self, topic_title: str, topic_description: str, content: str) -> str:
        # Build focused prompt and log it; LLM call is commented out
        trimmed = self._summarize_text(content, max_chars=3000)
        prompt = (f"Generate concise study notes for the topic '{topic_title}'.\nDescription: {topic_description}\n"
                  f"Context:\n{trimmed}\n\nReturn readable bullet-point notes.")
        logger.info("Prepared notes prompt for topic '%s' (len=%d) — LLM call commented out", topic_title, len(prompt))
        logger.debug("Notes prompt for topic '%s':\n%s", topic_title, prompt)

        # LLM invocation is commented out for testing; return extractive fallback
        sentences = re.split(r'(?<=[\.!?])\s+', content)
        bullets = []
        for s in sentences:
            s = s.strip()
            if not s:
                continue
            bullets.append(f"- {s}")
            if len(bullets) >= 8:
                break
        return '\n'.join(bullets) if bullets else content[:800]

    def process_course_content(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        logger.info("Processing %d chunks into notes (batched per chapter)", len(chunks))

        # Create a per-run LLM log file so all LLM prompts/responses are captured
        llm_log = self._init_llm_log_for_run()
        logger.info("LLM log for this run: %s", llm_log)
        call_idx = 0

        # Merge chunks by normalized chapter title
        chapters_map: Dict[str, List[Dict[str, Any]]] = {}
        for chunk in chunks:
            raw = chunk.get('chapter_title') or ''
            norm = self._normalize_chapter_title(raw)
            chapters_map.setdefault(norm, []).append(chunk)

        structured_notes: List[Dict[str, Any]] = []

        for chapter_title, chapter_chunks in chapters_map.items():
            logger.info("Chapter '%s' has %d chunks", chapter_title, len(chapter_chunks))
            chapter_content = ' '.join([c.get('content', '') for c in chapter_chunks])
            chapter_summary = self._summarize_text(chapter_content, max_chars=8000)

            # Build extraction prompt and (in future) call LLM once per chapter
            extraction_prompt = self._build_extraction_prompt(chapter_summary)
            logger.info("Prepared extraction prompt for chapter '%s' (len=%d)", chapter_title, len(extraction_prompt))
            logger.debug("Extraction prompt for chapter '%s':\n%s", chapter_title, extraction_prompt)

            # LLM extraction call: send extraction prompt and parse JSON response
            extractor_result = None
            try:
                logger.info("Sending extraction prompt to LLM for chapter '%s' (len=%d)", chapter_title, len(extraction_prompt))
                logger.debug("[LLM REQUEST][extraction] %s", extraction_prompt)
                client = self._get_client()
                resp = client.chat.completions.create(
                    messages=[{"role": "user", "content": extraction_prompt}],
                    model=getattr(settings, 'cerebras_model', None),
                    stream=False,
                    max_completion_tokens=65536,
                    temperature=1,
                    top_p=1,
                )

                # Log LLM extraction call (prompt + raw response + extracted text)
                call_idx += 1
                try:
                    self._log_llm_call(llm_log, call_idx, 'extraction', extraction_prompt, resp)
                except Exception:
                    logger.exception("Failed to record extraction LLM call to log")

                # Log raw response shape for debugging
                try:
                    logger.debug("[LLM RAW RESPONSE][extraction] type=%s repr=%r", type(resp), resp)
                    if isinstance(resp, dict):
                        logger.debug("[LLM RAW RESPONSE][extraction][dict] %s", json.dumps(resp, default=str)[:10000])
                    elif hasattr(resp, '__dict__'):
                        logger.debug("[LLM RAW RESPONSE][extraction].__dict__ keys=%s", list(getattr(resp, '__dict__', {}).keys()))
                except Exception:
                    logger.debug("[LLM RAW RESPONSE][extraction] could not fully serialize response")

                # extract text using helper
                text = self._extract_text_from_response(resp)
                if not text:
                    raise ValueError('LLM returned no text for extraction')

                logger.info("Received extraction response (len=%d)", len(text))
                logger.debug("[LLM RESPONSE][extraction] %s", text)
                extractor_result = json.loads(text)
                if 'chapters' not in extractor_result:
                    raise ValueError('Extraction JSON missing chapters')
            except Exception as e:
                logger.exception("Extraction LLM call failed or produced invalid JSON: %s", e)
                extractor_result = self._create_fallback_structure(chapter_summary)

                # Attempt to record the failed extraction prompt & exception to log
                try:
                    with open(llm_log, 'a', encoding='utf-8') as f:
                        f.write(f"--- LLM CALL [extraction] FAILED ({datetime.utcnow().isoformat()} UTC) ---\n")
                        f.write("--- PROMPT ---\n" + extraction_prompt + "\n")
                        f.write("--- ERROR ---\n" + repr(e) + "\n\n")
                except Exception:
                    logger.exception("Failed to append extraction failure to LLM log %s", llm_log)

            extracted_chapters = extractor_result.get('chapters', [])

            # For each extracted chapter (usually one per input chapter), batch-generate notes in a SINGLE call
            for ex in extracted_chapters:
                ex_title = ex.get('title') or chapter_title
                topics = ex.get('topics') or [{'title': ex_title, 'description': ''}]

                # Build topic -> supporting snippets map using retrieval heuristics (local)
                topic_snippets: Dict[str, str] = {}
                for topic in topics:
                    t_title = topic.get('title')
                    key = (t_title or '').lower()
                    snippets = []
                    for c in chapter_chunks:
                        ctext = c.get('content', '')
                        if key and key in ctext.lower():
                            snippets.append(ctext)
                        if len(snippets) >= 5:
                            break
                    if not snippets:
                        snippets = [c.get('content', '') for c in chapter_chunks[:3]]
                    topic_snippets[t_title] = self._summarize_text(' '.join(snippets), max_chars=2000)

                # Build the batch prompt and log
                batch_prompt = self._build_batch_notes_prompt(ex_title, topics, chapter_summary, topic_snippets)
                logger.info("Prepared batch notes prompt for chapter '%s' with %d topics (len=%d)", ex_title, len(topics), len(batch_prompt))
                logger.debug("Batch notes prompt for chapter '%s':\n%s", ex_title, batch_prompt)

                # LLM batch-note call: send single prompt per extracted chapter and expect JSON array
                notes_json = None
                try:
                    logger.info("Sending batch notes prompt to LLM for chapter '%s' (topics=%d len=%d)", ex_title, len(topics), len(batch_prompt))
                    logger.debug("[LLM REQUEST][batch_notes] %s", batch_prompt)
                    client = self._get_client()
                    resp2 = client.chat.completions.create(
                        messages=[{"role": "user", "content": batch_prompt}],
                        model=getattr(settings, 'cerebras_model', None),
                        stream=False,
                        max_completion_tokens=65536,
                        temperature=1,
                        top_p=1,
                    )

                    # Log LLM batch-notes call
                    call_idx += 1
                    try:
                        self._log_llm_call(llm_log, call_idx, 'batch_notes', batch_prompt, resp2)
                    except Exception:
                        logger.exception("Failed to record batch_notes LLM call to log")

                    # Log raw response shape for debugging
                    try:
                        logger.debug("[LLM RAW RESPONSE][batch_notes] type=%s repr=%r", type(resp2), resp2)
                        if isinstance(resp2, dict):
                            logger.debug("[LLM RAW RESPONSE][batch_notes][dict] %s", json.dumps(resp2, default=str)[:10000])
                        elif hasattr(resp2, '__dict__'):
                            logger.debug("[LLM RAW RESPONSE][batch_notes].__dict__ keys=%s", list(getattr(resp2, '__dict__', {}).keys()))
                    except Exception:
                        logger.debug("[LLM RAW RESPONSE][batch_notes] could not fully serialize response")

                    text2 = self._extract_text_from_response(resp2)
                    if not text2:
                        raise ValueError('LLM returned no text for batch notes')

                    logger.info("Received batch notes response (len=%d)", len(text2))
                    logger.debug("[LLM RESPONSE][batch_notes] %s", text2)

                    notes_json = json.loads(text2)
                    if not isinstance(notes_json, list):
                        raise ValueError('Batch notes response is not a JSON array')
                except Exception as e:
                    logger.exception("Batch notes LLM call failed or produced invalid JSON: %s", e)
                    notes_json = None

                # If notes JSON valid, use it; otherwise, fallback to local extractive generation per topic
                if notes_json:
                    for item in notes_json:
                        title = item.get('title')
                        notes_text = item.get('notes') or item.get('notes_content') or ''

                        # Normalize notes_text to a string for DB storage
                        try:
                            if isinstance(notes_text, list):
                                notes_text = '\n'.join(map(str, notes_text))
                            elif isinstance(notes_text, dict):
                                # convert dicts to compact JSON
                                notes_text = json.dumps(notes_text, ensure_ascii=False)
                            elif not isinstance(notes_text, str):
                                notes_text = str(notes_text)
                        except Exception:
                            notes_text = str(notes_text)

                        logger.info("Created note for topic '%s' (chapter '%s') from LLM", title, ex_title)
                        structured_notes.append({
                            'chapter_title': ex_title,
                            'topic_title': title,
                            'topic_description': next((t.get('description','') for t in topics if t.get('title')==title), ''),
                            'notes_content': notes_text,
                            'chunks': chapter_chunks
                        })
                else:
                    for topic in topics:
                        t_title = topic.get('title')
                        t_desc = topic.get('description', '')
                        context = topic_snippets.get(t_title, '')
                        notes_text = self.generate_notes_for_topic(t_title, t_desc, context)
                        logger.info("Created note for topic '%s' (chapter '%s') [fallback]", t_title, ex_title)
                        structured_notes.append({
                            'chapter_title': ex_title,
                            'topic_title': t_title,
                            'topic_description': t_desc,
                            'notes_content': notes_text,
                            'chunks': chapter_chunks
                        })

        logger.info("Finished generating notes; total=%d", len(structured_notes))
        return structured_notes

    def log_prompts(self, chunks: List[Dict[str, Any]]) -> None:
        """Build and log extraction & batch-note prompts for the provided chunks.

        This method intentionally does not call the LLM; it logs the prompts (INFO and DEBUG)
        so you can inspect what would be sent, then returns None.
        """
        logger.info("Logging prompts for %d chunks", len(chunks))

        # Merge chunks by normalized chapter title (same as process_course_content)
        chapters_map: Dict[str, List[Dict[str, Any]]] = {}
        for chunk in chunks:
            raw = chunk.get('chapter_title') or ''
            norm = self._normalize_chapter_title(raw)
            chapters_map.setdefault(norm, []).append(chunk)

        # For each chapter, build extraction prompt, batch prompt, and per-topic prompts
        for chapter_title, chapter_chunks in chapters_map.items():
            logger.info("Chapter '%s' has %d chunks (prompt logging)", chapter_title, len(chapter_chunks))
            chapter_content = ' '.join([c.get('content', '') for c in chapter_chunks])
            chapter_summary = self._summarize_text(chapter_content, max_chars=8000)

            # Extraction prompt (log full prompt)
            extraction_prompt = self._build_extraction_prompt(chapter_summary)
            logger.info("[PROMPT][extraction] chapter='%s' len=%d", chapter_title, len(extraction_prompt))
            logger.debug("[PROMPT][extraction] for chapter '%s':\n%s", chapter_title, extraction_prompt)

            # Use extractor (LLM disabled) to get the structure
            extractor_result = self.extract_topics_and_chapters(chapter_summary)
            extracted_chapters = extractor_result.get('chapters', []) if isinstance(extractor_result, dict) else []

            for ex in extracted_chapters:
                ex_title = ex.get('title') or chapter_title
                topics = ex.get('topics') or [{'title': ex_title, 'description': ''}]

                # Batch prompt (would be a single LLM call per extracted chapter)
                batch_prompt = self._build_batch_notes_prompt(ex_title, topics, chapter_summary)
                logger.info("[PROMPT][batch_notes] chapter='%s' topics=%d len=%d", ex_title, len(topics), len(batch_prompt))
                logger.debug("[PROMPT][batch_notes] for chapter '%s':\n%s", ex_title, batch_prompt)

                # For each topic, build the focused notes prompt (but do not call the LLM)
                for topic in topics:
                    t_title = topic.get('title')
                    t_desc = topic.get('description', '')

                    # Build topic-specific context the same way process_course_content does
                    key = (t_title or '').lower()
                    snippets = []
                    for c in chapter_chunks:
                        ctext = c.get('content', '')
                        if key and key in ctext.lower():
                            snippets.append(ctext)
                        if len(snippets) >= 5:
                            break
                    if not snippets:
                        snippets = [c.get('content', '') for c in chapter_chunks[:3]]

                    context = ' '.join(snippets)
                    trimmed = self._summarize_text(context, max_chars=3000)

                    # Build the exact per-topic prompt that would be sent to the LLM
                    topic_prompt = (
                        f"Generate concise study notes for the topic '{t_title}'.\n"
                        f"Description: {t_desc}\n"
                        f"Context:\n{trimmed}\n\n"
                        "Return readable bullet-point notes."
                    )

                    logger.info("[PROMPT][topic] chapter='%s' topic='%s' len=%d", ex_title, t_title, len(topic_prompt))
                    logger.debug("[PROMPT][topic] for chapter='%s' topic='%s':\n%s", ex_title, t_title, topic_prompt)

        logger.info("Finished logging prompts for chunks")
