"""
parser.py
=========
Primer eslabón del pipeline de generación de CVs a medida.

Flujo de este módulo:
    archivo .txt (oferta)
        -> limpieza de texto (regex)
        -> normalización con spaCy (minúsculas + lematización)
        -> detección de secciones (Descripción / Funciones / Requisitos / Se ofrece)
        -> extracción de skills usando knowledge/skills.yaml
        -> desambiguación de duplicados usando knowledge/synonims.yaml
        -> detección de sector usando knowledge/sector.yaml
        -> construcción del objeto JobOffer

Dependencias externas:
    pip install spacy rapidfuzz pyyaml
    python -m spacy download es_core_news_md

Uso:
    from parser import JobOfferParser
    parser = JobOfferParser()
    oferta = parser.parse("ofertas/spar.txt")
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set, Tuple, Union

import spacy
import yaml
from rapidfuzz import fuzz, process

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

# knowledge/ se asume como carpeta hermana de src/
KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "knowledge"
SKILLS_YAML = KNOWLEDGE_DIR / "skills.yaml"
SYNONIMS_YAML = KNOWLEDGE_DIR / "synonims.yaml"
SECTOR_YAML = KNOWLEDGE_DIR / "sector.yaml"

# Puntuación mínima (0-100) para aceptar un match por similitud con RapidFuzz
FUZZY_THRESHOLD = 85

SPACY_MODEL = "es_core_news_md"


# ---------------------------------------------------------------------------
# Modelo de datos
# ---------------------------------------------------------------------------

@dataclass
class JobOffer:
    empresa: str
    sector: str
    skills: List[str] = field(default_factory=list)       # unión de las 4 categorías
    funciones: List[str] = field(default_factory=list)

    # Desglose por categoría (útil para ATS.py y selector.py)
    competencias: List[str] = field(default_factory=list)
    conocimientos: List[str] = field(default_factory=list)
    herramientas: List[str] = field(default_factory=list)
    softskills: List[str] = field(default_factory=list)

    # Texto crudo de cada sección, por si algún módulo posterior lo necesita
    descripcion: str = ""
    texto_requisitos: str = ""
    texto_se_ofrece: str = ""


# ---------------------------------------------------------------------------
# 1. Limpieza de texto
# ---------------------------------------------------------------------------

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_MULTI_NEWLINE_RE = re.compile(r"\n{2,}")
_MULTI_SPACE_RE = re.compile(r"[ \t]{2,}")

# Rango amplio de emojis y pictogramas comunes
_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000026FF"
    "\U00002700-\U000027BF"
    "\U0001F1E6-\U0001F1FF"
    "\U00002190-\U000021FF"
    "\uFE0F"
    "]+",
    flags=re.UNICODE,
)

# Cualquier carácter que no sea letra (con acentos/ñ), número, espacio o
# puntuación básica se considera "raro" y se elimina
_WEIRD_CHARS_RE = re.compile(r"[^\w\sáéíóúñüÁÉÍÓÚÑÜ.,;:()%/\-]")


def clean_text(raw_text: str) -> str:
    """Limpia el texto crudo de la oferta antes de cualquier procesamiento NLP."""
    text = html.unescape(raw_text)
    text = _HTML_TAG_RE.sub(" ", text)
    text = _EMOJI_RE.sub("", text)
    text = _WEIRD_CHARS_RE.sub(" ", text)
    text = _MULTI_NEWLINE_RE.sub("\n", text)
    text = _MULTI_SPACE_RE.sub(" ", text)

    # quitamos líneas vacías sobrantes y espacios al principio/fin de línea
    lines = [ln.strip() for ln in text.split("\n")]
    lines = [ln for ln in lines if ln]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 2. Normalización con spaCy
# ---------------------------------------------------------------------------

class Normalizer:
    """Envuelve el pipeline de spaCy para minúsculas + lematización."""

    def __init__(self, model: str = SPACY_MODEL):
        self.nlp = spacy.load(model)

    def normalize(self, text: str) -> str:
        """
        'ATENCIÓN AL CLIENTE' -> 'atención al cliente' (lematizado).
        Se conservan las stopwords para no romper frases compuestas
        como 'atención al cliente' o 'trabajo en equipo'.
        """
        doc = self.nlp(text.lower())
        tokens = [tok.lemma_ for tok in doc if not tok.is_space]
        return " ".join(tokens)

    def extract_nouns(self, text: str) -> List[str]:
        """Extrae sustantivos lematizados y únicos, útil para 'funciones'."""
        doc = self.nlp(text.lower())
        nouns: List[str] = []
        for tok in doc:
            if tok.pos_ in {"NOUN", "PROPN"} and not tok.is_stop:
                lemma = tok.lemma_.strip()
                if lemma and lemma not in nouns:
                    nouns.append(lemma)
        return nouns


# ---------------------------------------------------------------------------
# 3. Detección de secciones
# ---------------------------------------------------------------------------

# Cada clave es el nombre interno de la sección; el valor es un patrón regex
# que debe matchear una línea completa (posiblemente con ":" al final) para
# considerarla una cabecera de esa sección.
SECTION_PATTERNS: Dict[str, re.Pattern] = {
    "descripcion": re.compile(
        r"^\s*descripci[oó]n(\s+de\s+la\s+oferta|\s+del\s+puesto)?\s*:?\s*$",
        re.IGNORECASE,
    ),
    "funciones": re.compile(
        r"^\s*(funciones|responsabilidades|tareas)\s*:?\s*$",
        re.IGNORECASE,
    ),
    "requisitos": re.compile(
        r"^\s*(requisitos|se\s+requiere|perfil\s+buscado|qu[ée]\s+buscamos)\s*:?\s*$",
        re.IGNORECASE,
    ),
    "se_ofrece": re.compile(
        r"^\s*(se\s+ofrece|ofrecemos|beneficios|condiciones)\s*:?\s*$",
        re.IGNORECASE,
    ),
}


def split_sections(text: str) -> Dict[str, str]:
    """
    Recorre el texto línea a línea y separa el contenido en las 4 secciones
    conocidas. Todo lo que aparezca antes de la primera cabecera se asigna
    a 'descripcion' (suele ser el resumen inicial de la oferta).
    """
    sections: Dict[str, List[str]] = {key: [] for key in SECTION_PATTERNS}
    current = "descripcion"

    for line in text.split("\n"):
        header_found = None
        for key, pattern in SECTION_PATTERNS.items():
            if pattern.match(line):
                header_found = key
                break
        if header_found:
            current = header_found
            continue  # no añadimos la línea de cabecera al contenido
        sections[current].append(line)

    return {key: "\n".join(lines).strip() for key, lines in sections.items()}


# ---------------------------------------------------------------------------
# 4. Diccionario de skills (skills.yaml + synonims.yaml)
# ---------------------------------------------------------------------------

def load_yaml(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo de conocimiento: {path}"
        )
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


_CHUNK_SPLIT_RE = re.compile(r"[.,;\n•\-–]+")


class SkillDictionary:
    """
    Estructura skills.yaml esperada:

        competencias:
          atencion_cliente:
            - "atención al público"
            - "trato con clientes"
            - "servicio al cliente"
          trabajo_equipo:
            - "trabajo en equipo"
            - "colaboración"
        conocimientos:
          ...
        herramientas:
          ...
        softskills:
          ...

    Estructura synonims.yaml esperada (id detectado -> id canónico):

        atencion_publico: atencion_cliente
        trabajo_colaborativo: trabajo_equipo
    """

    CATEGORIES = ("competencias", "conocimientos", "herramientas", "softskills")

    def __init__(
        self,
        skills_path: Path,
        synonims_path: Path,
        normalizer: Normalizer,
        fuzzy_threshold: int = FUZZY_THRESHOLD,
    ):
        self.normalizer = normalizer
        self.fuzzy_threshold = fuzzy_threshold
        raw_skills = load_yaml(skills_path)
        self.synonyms: dict = load_yaml(synonims_path) if synonims_path.exists() else {}

        # frase_normalizada -> (skill_id, categoria)
        self.phrase_index: Dict[str, Tuple[str, str]] = {}

        for category in self.CATEGORIES:
            skill_map = raw_skills.get(category, {}) or {}
            for skill_id, phrases in skill_map.items():
                for phrase in phrases:
                    norm_phrase = normalizer.normalize(phrase)
                    self.phrase_index[norm_phrase] = (skill_id, category)

    def canonical(self, skill_id: str) -> str:
        """Aplica synonims.yaml para evitar duplicados tipo 'atencion_publico'
        y 'atencion_cliente' conviviendo como si fueran distintos."""
        return self.synonyms.get(skill_id, skill_id)

    def extract_skills(self, text: str) -> Dict[str, Set[str]]:
        """
        Devuelve un dict {categoria: {skill_id, ...}} a partir de un texto
        (normalmente la sección de requisitos, aunque puede aplicarse a
        cualquier sección).

        Estrategia:
          1. Coincidencia por substring contra el diccionario (rápida y exacta).
          2. Si no hay coincidencia exacta, se recurre a RapidFuzz
             (token_set_ratio) contra todas las frases del diccionario.
        """
        found: Dict[str, Set[str]] = {cat: set() for cat in self.CATEGORIES}
        if not text.strip():
            return found

        normalized_text = self.normalizer.normalize(text)
        chunks = [c.strip() for c in _CHUNK_SPLIT_RE.split(normalized_text) if c.strip()]
        all_phrases = list(self.phrase_index.keys())

        for chunk in chunks:
            matched_exact = False
            for phrase, (skill_id, category) in self.phrase_index.items():
                if phrase in chunk or chunk in phrase:
                    found[category].add(self.canonical(skill_id))
                    matched_exact = True

            if matched_exact:
                continue

            # Fallback: similitud léxica con RapidFuzz
            best = process.extractOne(
                chunk,
                all_phrases,
                scorer=fuzz.token_set_ratio,
                score_cutoff=self.fuzzy_threshold,
            )
            if best is not None:
                phrase, _score, _idx = best
                skill_id, category = self.phrase_index[phrase]
                found[category].add(self.canonical(skill_id))

        return found


# ---------------------------------------------------------------------------
# 5. Detección de sector (sector.yaml)
# ---------------------------------------------------------------------------

class SectorDetector:
    """
    Estructura sector.yaml esperada (sector -> palabras clave asociadas):

        Retail:
          - "spar"
          - "supermercado"
          - "reposición"
        Hostelería:
          - "camarero"
          - "restaurante"
    """

    def __init__(self, sector_path: Path, normalizer: Normalizer):
        self.normalizer = normalizer
        raw = load_yaml(sector_path) if sector_path.exists() else {}
        self.keywords_by_sector: Dict[str, List[str]] = {
            sector: [normalizer.normalize(kw) for kw in keywords]
            for sector, keywords in raw.items()
        }

    def detect(self, text: str) -> str:
        normalized = self.normalizer.normalize(text)
        best_sector, best_hits = "desconocido", 0
        for sector, keywords in self.keywords_by_sector.items():
            hits = sum(1 for kw in keywords if kw in normalized)
            if hits > best_hits:
                best_sector, best_hits = sector, hits
        return best_sector


# ---------------------------------------------------------------------------
# 6. Extracción de la empresa
# ---------------------------------------------------------------------------

_EMPRESA_RE = re.compile(r"(?:empresa|compañ[ií]a)\s*:\s*(.+)", re.IGNORECASE)


def extract_empresa(text: str) -> str:
    """
    Intenta extraer el nombre de la empresa buscando primero un patrón
    explícito 'Empresa: X'. Si no existe, recurre a la primera línea no
    vacía del documento como heurística (suele ser el título del anuncio).
    """
    match = _EMPRESA_RE.search(text)
    if match:
        return match.group(1).strip()

    for line in text.split("\n"):
        if line.strip():
            return line.strip()

    return "Desconocido"


# ---------------------------------------------------------------------------
# 7. Orquestador principal
# ---------------------------------------------------------------------------

class JobOfferParser:
    def __init__(
        self,
        knowledge_dir: Path = KNOWLEDGE_DIR,
        spacy_model: str = SPACY_MODEL,
        fuzzy_threshold: int = FUZZY_THRESHOLD,
    ):
        self.normalizer = Normalizer(spacy_model)
        self.skill_dict = SkillDictionary(
            knowledge_dir / "skills.yaml",
            knowledge_dir / "synonims.yaml",
            self.normalizer,
            fuzzy_threshold=fuzzy_threshold,
        )
        self.sector_detector = SectorDetector(
            knowledge_dir / "sector.yaml", self.normalizer
        )

    def parse(self, filepath: Union[str, Path]) -> JobOffer:
        path = Path(filepath)
        raw_text = path.read_text(encoding="utf-8", errors="ignore")

        cleaned = clean_text(raw_text)
        sections = split_sections(cleaned)

        empresa = extract_empresa(cleaned)
        sector = self.sector_detector.detect(cleaned)

        # Los requisitos son la fuente principal de skills, pero a veces
        # aparecen mezclados dentro de la descripción, así que revisamos ambas.
        skills_por_categoria = self.skill_dict.extract_skills(
            sections.get("requisitos", "")
        )
        extra = self.skill_dict.extract_skills(sections.get("descripcion", ""))
        for categoria, valores in extra.items():
            skills_por_categoria[categoria] |= valores

        funciones = self.normalizer.extract_nouns(sections.get("funciones", ""))

        todas_las_skills = sorted(
            skills_por_categoria["competencias"]
            | skills_por_categoria["conocimientos"]
            | skills_por_categoria["herramientas"]
            | skills_por_categoria["softskills"]
        )

        return JobOffer(
            empresa=empresa,
            sector=sector,
            skills=todas_las_skills,
            funciones=funciones,
            competencias=sorted(skills_por_categoria["competencias"]),
            conocimientos=sorted(skills_por_categoria["conocimientos"]),
            herramientas=sorted(skills_por_categoria["herramientas"]),
            softskills=sorted(skills_por_categoria["softskills"]),
            descripcion=sections.get("descripcion", ""),
            texto_requisitos=sections.get("requisitos", ""),
            texto_se_ofrece=sections.get("se_ofrece", ""),
        )


# ---------------------------------------------------------------------------
# Uso directo por línea de comandos (debug rápido)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    print(KNOWLEDGE_DIR)
    if len(sys.argv) != 2:
        print("Uso: python parser.py ruta/a/oferta.txt")
        sys.exit(1)

    parser = JobOfferParser()
    oferta = parser.parse(sys.argv[1])

    print("Empresa   :", oferta.empresa)
    print("Sector    :", oferta.sector)
    print("Skills    :", oferta.skills)
    print("Funciones :", oferta.funciones)
    print("  competencias :", oferta.competencias)
    print("  conocimientos:", oferta.conocimientos)
    print("  herramientas :", oferta.herramientas)
    print("  softskills   :", oferta.softskills)
