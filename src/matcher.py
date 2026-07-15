"""
matcher.py
==========
Compara una oferta de trabajo analizada (JobOffer) contra el archivo
master_cv.yaml y ordena los elementos de cada sección del CV por relevancia.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from rapidfuzz import fuzz

from parser import (
    FUZZY_THRESHOLD,
    KNOWLEDGE_DIR,
    SPACY_MODEL,
    JobOffer,
    Normalizer,
    SkillDictionary,
)


@dataclass
class MatchResult:
    """Guarda un elemento del CV junto con su puntuación de relevancia."""
    score: float
    item: dict[str, Any]


@dataclass
class MatchResults:
    """Contenedor que agrupa los resultados ordenados por secciones del CV.

    Las secciones son las que confirmó el maintainer en el issue #4:
    experiencias/proyectos, formación, certificaciones, hard skills,
    soft skills e idiomas. El campo `skills` general de master_cv.yaml
    se omite a propósito (comentario del maintainer: "no tiene mucho
    sentido"), y los items de `software` se rankean junto a hard_skills
    en vez de tener su propia sección, ya que el maintainer no lo
    menciona como un apartado independiente del currículum final.

    NOTA: los nombres de estos campos siguen las claves reales de
    knowledge/master_cv.yaml (hard_skills, soft_skills), que no coinciden
    con las categorías de knowledge/skills.yaml (competencias/
    conocimientos/herramientas/softskills) usadas por JobOffer.
    Ver _extract_skill_ids: esa es la capa que traduce entre ambos
    vocabularios.
    """
    experiences: list[MatchResult]
    projects: list[MatchResult]
    education: list[MatchResult]
    certifications: list[MatchResult]
    hard_skills: list[MatchResult]
    soft_skills: list[MatchResult]
    languages: list[MatchResult]


class CVMatcher:
    def __init__(
        self,
        master_cv_path: Path,
        knowledge_dir: Path = KNOWLEDGE_DIR,
        normalizer: Normalizer | None = None,
    ):
        """Carga el archivo YAML del CV maestro al instanciar la clase.

        `normalizer` es opcional: si ya tienes uno creado (p. ej. el de
        JobOfferParser en main.py), pásalo aquí para no cargar el modelo
        de spaCy dos veces. Si no se indica, se crea uno propio.
        """
        with open(master_cv_path, encoding="utf-8") as f:
            self.cv_data = yaml.safe_load(f)

        # Reutilizamos el mismo diccionario de habilidades que usa el parser
        # para poder "etiquetar" el texto libre del CV con los mismos
        # skill_id canónicos que ya trae la oferta parseada. Así evitamos
        # reimplementar la normalización/fuzzy-matching de cero.
        self.normalizer = normalizer or Normalizer(SPACY_MODEL)
        self.skill_dict = SkillDictionary(
            knowledge_dir / "skills.yaml",
            knowledge_dir / "synonims.yaml",
            self.normalizer,
            fuzzy_threshold=FUZZY_THRESHOLD,
        )

    def match(self, offer: JobOffer) -> MatchResults:
        """
        Compara la oferta de trabajo parseada contra las entradas del CV maestro
        y las devuelve ordenadas por su nivel de relevancia.
        """
        return MatchResults(
            experiences=self._rank_section(
                "experiences", self.cv_data.get("experiences", []), offer
            ),
            projects=self._rank_section(
                "projects", self.cv_data.get("projects", []), offer
            ),
            education=self._rank_section(
                "education", self.cv_data.get("education", []), offer
            ),
            certifications=self._rank_section(
                "certifications", self.cv_data.get("certifications", []), offer
            ),
            hard_skills=self._rank_section(
                "hard_skills",
                self._as_items(self.cv_data.get("hard_skills", []))
                + self._flatten_software(self.cv_data.get("software", [])),
                offer,
            ),
            soft_skills=self._rank_section(
                "soft_skills", self._as_items(self.cv_data.get("soft_skills", [])), offer
            ),
            languages=self._rank_section(
                "languages", self.cv_data.get("languages", []), offer
            ),
        )

    # ------------------------------------------------------------------
    # Preprocesado: algunas secciones del YAML no son listas de dicts
    # ------------------------------------------------------------------

    @staticmethod
    def _as_items(values: list[str]) -> list[dict[str, Any]]:
        """Envuelve strings sueltos (skills, hard_skills, soft_skills) en
        dicts, para que _score_item pueda tratarlos igual que el resto."""
        return [{"text": v} for v in values]

    @staticmethod
    def _flatten_software(categories: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """'software' es una lista de {category, items: [...]}; la aplanamos
        a un item por herramienta individual para poder rankearlas por
        separado (p. ej. "Magento 2" debería poder superar a "Windows 11"
        en una oferta de e-commerce, aunque estén en la misma categoría)."""
        flattened = []
        for entry in categories:
            category = entry.get("category", "")
            for item_name in entry.get("items", []):
                flattened.append({"text": item_name, "category": category})
        return flattened

    # ------------------------------------------------------------------

    def _rank_section(
        self,
        section: str,
        items: list[dict[str, Any]],
        offer: JobOffer,
    ) -> list[MatchResult]:
        """Ordena los elementos de una sección específica de mayor a menor score."""
        scored = [
            MatchResult(score=self._score_item(item, offer, section), item=item)
            for item in items
        ]
        return sorted(scored, key=lambda r: r.score, reverse=True)

    def _score_item(
        self,
        item: dict[str, Any],
        offer: JobOffer,
        section: str,
    ) -> float:
        """Calcula la puntuación de un elemento individual basado en la oferta."""
        if section == "languages":
            return self._score_language(item, offer)

        text = self._item_text(item, section)
        item_skill_ids = self._extract_skill_ids(text)
        offer_skill_ids = set(offer.skills)  # unión de las 4 categorías ya detectadas
        overlap_score = self._overlap_score(item_skill_ids, offer_skill_ids)

        if section in ("experiences", "projects"):
            # Las tareas/proyectos describen trabajo real con vocabulario
            # libre que no siempre está en skills.yaml, así que además
            # comparamos por similitud difusa contra las funciones de la oferta.
            text_score = self._text_similarity(text, offer.funciones)
            return 0.6 * overlap_score + 0.4 * text_score

        if section in ("education", "certifications"):
            # La formación rara vez comparte vocabulario exacto con
            # skills.yaml; priorizamos similitud textual contra la
            # descripción y el sector de la oferta.
            text_score = self._text_similarity(text, [offer.descripcion, offer.sector])
            return 0.3 * overlap_score + 0.7 * text_score

        # hard_skills / soft_skills (incluye items de software aplanados): overlap directo.
        return overlap_score

    # ------------------------------------------------------------------
    # Utilidades de scoring
    # ------------------------------------------------------------------

    @staticmethod
    def _item_text(item: dict[str, Any], section: str) -> str:
        """Concatena los campos de texto relevantes de un item según su sección."""
        if "text" in item:  # skills / hard_skills / soft_skills / software (aplanados)
            return item["text"]

        if section == "experiences":
            parts = [item.get("job_title", ""), item.get("description", "")]
            parts += item.get("achievements_and_tasks", [])
            parts += item.get("competencias", [])
            return " ".join(parts)

        if section == "projects":
            parts = [item.get("name", ""), item.get("description", "")]
            parts += item.get("technologies", [])
            return " ".join(parts)

        if section == "education":
            return " ".join([item.get("degree", ""), item.get("details", "")])

        if section == "certifications":
            return item.get("name", "")

        return " ".join(str(v) for v in item.values())

    def _extract_skill_ids(self, text: str) -> set[str]:
        """Reutiliza el SkillDictionary del parser para etiquetar texto libre
        del CV con los mismos skill_id canónicos que usa la oferta."""
        found = self.skill_dict.extract_skills(text)
        ids: set[str] = set()
        for category_ids in found.values():
            ids |= category_ids
        return ids

    @staticmethod
    def _overlap_score(item_ids: set[str], offer_ids: set[str]) -> float:
        if not offer_ids:
            return 0.0
        return len(item_ids & offer_ids) / len(offer_ids)

    @staticmethod
    def _text_similarity(text: str, references: list[str]) -> float:
        """Similitud difusa máxima entre el texto del item y una lista de
        textos de referencia de la oferta (funciones, descripción...)."""
        references = [r for r in references if r]
        if not text.strip() or not references:
            return 0.0
        scores = [fuzz.token_set_ratio(text, ref) for ref in references]
        return max(scores) / 100  # normalizado a [0, 1]

    @staticmethod
    def _score_language(item: dict[str, Any], offer: JobOffer) -> float:
        """JobOffer todavía no extrae un campo `languages` explícito, así que
        de momento puntuamos por si el idioma se menciona en el texto crudo
        de la oferta. Si en el futuro el parser añade offer.languages, esto
        debería sustituirse por una comparación directa de niveles."""
        language = item.get("language", "")
        if not language:
            return 0.0
        haystack = " ".join(
            [offer.descripcion, offer.texto_requisitos, offer.texto_se_ofrece]
        )
        return 1.0 if language.lower() in haystack.lower() else 0.0
