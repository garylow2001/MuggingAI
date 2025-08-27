from typing import Optional
import logging

from .summarizer import Summarizer

logger = logging.getLogger(__name__)

_SUMMARIZER: Optional[Summarizer] = None


def init_summarizer(
    model_name: str = "facebook/bart-large-cnn", **kwargs
) -> Summarizer:
    global _SUMMARIZER
    if _SUMMARIZER is None:
        logger.info("Initializing global Summarizer singleton")
        _SUMMARIZER = Summarizer(model_name=model_name, **kwargs)
    return _SUMMARIZER


def get_summarizer() -> Optional[Summarizer]:
    return _SUMMARIZER
