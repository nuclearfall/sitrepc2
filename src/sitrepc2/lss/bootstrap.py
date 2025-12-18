# holmes/bootstrap.py
import holmes_extractor as holmes
from dataclasses import dataclass
from typing import Any


@dataclass
class HolmesSettings:
    model: str = "en_core_web_lg"
    overall_similarity_threshold: float = 1.0
    embedding_based_matching_on_root_words: bool = False
    ontology: Any = None
    perform_coreference_resolution: bool | None = None

def build_manager(settings: HolmesSettings | None = None) -> holmes.Manager:
    s = settings or HolmesSettings()
    return holmes.Manager(
        model=s.model,
        ontology=s.ontology,
        overall_similarity_threshold=s.overall_similarity_threshold,
        embedding_based_matching_on_root_words=s.embedding_based_matching_on_root_words,
        perform_coreference_resolution=s.perform_coreference_resolution,
    )
