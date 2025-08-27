import logging
from typing import List, Dict, Any

try:
    import torch
    from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
except Exception as e:
    # Defer import errors to runtime usage so the app can start even if transformers isn't installed yet.
    torch = None
    AutoTokenizer = None
    AutoModelForSeq2SeqLM = None


logger = logging.getLogger(__name__)


class Summarizer:
    """Light wrapper around a seq2seq summarization model (BART by default).

    This class loads the tokenizer and model on initialization. Summarization
    is synchronous; callers should run it in a thread if used from async code.
    """

    def __init__(self, model_name: str = "facebook/bart-large-cnn", max_input_tokens: int = 1024, max_summary_length: int = 150):
        if AutoTokenizer is None or AutoModelForSeq2SeqLM is None or torch is None:
            raise RuntimeError("transformers and torch are required for Summarizer")

        self.model_name = model_name
        self.max_input_tokens = max_input_tokens
        self.max_summary_length = max_summary_length
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        try:
            logger.info(f"Loading summarization model {model_name} on {self.device}")
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
            self.model.to(self.device)
            self.model.eval()
        except Exception as e:
            logger.exception("Failed to load summarization model: %s", e)
            raise

    def summarize_text(self, text: str) -> str:
        if not text or not text.strip():
            return ""

        # tokenization with truncation to model max
        inputs = self.tokenizer(text, max_length=self.max_input_tokens, truncation=True, return_tensors="pt")
        input_ids = inputs.input_ids.to(self.device)
        attention_mask = inputs.attention_mask.to(self.device)

        with torch.no_grad():
            summary_ids = self.model.generate(
                input_ids,
                attention_mask=attention_mask,
                max_length=self.max_summary_length,
                num_beams=4,
                length_penalty=2.0,
                early_stopping=True,
            )

        summary = self.tokenizer.decode(summary_ids[0], skip_special_tokens=True)
        return summary.strip()

    def summarize_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for c in chunks:
            content = c.get("content", "")
            try:
                summary = self.summarize_text(content)
            except Exception:
                logger.exception("Failed to summarize chunk")
                summary = ""

            results.append({
                "chunk_index": c.get("chunk_index"),
                "file_id": c.get("file_id"),
                "summary": summary,
            })

        return results
