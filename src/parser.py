"""
parser.py
=========
Primer eslabón del pipeline de generación de CVs a medida.
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

KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "knowledge"
SKILLS_YAML = KNOWLEDGE_DIR / "skills.yaml"
SYNONIMS_YAML = KNOWLEDGE_DIR / "synonims.yaml"
SECTOR_YAML = KNOWLEDGE_DIR / "sector.yaml"

FUZZY_THRESHOLD = 85
SPACY_MODEL = "es_core_news_md"

# ---------------------------------------------------------------------------
# Modelo de datos
# ---------------------------------------------------------------------------

@dataclass
class JobOffer:
    empresa: str
    sector: str
    skills: List[str] = field(default_factory=list)
    funciones: List[str] = field(default_factory=list)

    competencias: List[str] = field(default_factory=list)
    conocimientos: List[str] = field(default_factory=list)
    herramientas: List[str] = field(default_factory=list)
    softskills: List[str] = field(default_factory=list)

    descripcion: str = ""
    texto_requisitos: str = ""
    texto_se_ofrece: str = ""

# ---------------------------------------------------------------------------
# 1. Limpieza de texto
# ---------------------------------------------------------------------------

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_MULTI_NEWLINE_RE = re.compile(r"\n{2,}")
_MULTI_SPACE_RE = re.compile(r"[ \t]{2,}")

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

_WEIRD_CHARS_RE = re.compile(r"[^\w\sáéíóúñüÁÉÍÓÚÑÜ.,;:()%/\-¿?¡!]")

def clean_text(raw_text: str) -> str:
    text = html.unescape(raw_text)
    text = _HTML_TAG_RE.sub(" ", text)
    text = _EMOJI_RE.sub("?", text) # Los emojis tipo check/bullet se transforman en ? a veces
    text = _WEIRD_CHARS_RE.sub(" ", text)
    text = _MULTI_NEWLINE_RE.sub("\n", text)
    text = _MULTI_SPACE_RE.sub(" ", text)

    lines = [ln.strip() for ln in text.split("\n")]
    lines = [ln for ln in lines if ln]
    return "\n".join(lines)

# ---------------------------------------------------------------------------
# 2. Normalización con spaCy
# ---------------------------------------------------------------------------

class Normalizer:
    def __init__(self, model: str = SPACY_MODEL):
        self.nlp = spacy.load(model)

    def normalize(self, text: str) -> str:
        doc = self.nlp(text.lower())
        tokens = [tok.lemma_ for tok in doc if not tok.is_space]
        return " ".join(tokens)

# ---------------------------------------------------------------------------
# 3. Detección de secciones
# ---------------------------------------------------------------------------

# Añadidos [¿\s]* y tolerancias para atrapar frases tipo "¿Qué hará que tu candidatura destaque?"
SECTION_PATTERNS: Dict[str, re.Pattern] = {
    "descripcion": re.compile(
        r"^[¿\s]*(descripci[oó]n|sobre\s+la\s+oferta|sobre\s+nosotros|el\s+puesto).*[?\s\:]*$",
        re.IGNORECASE,
    ),
    "funciones": re.compile(
        r"^[¿\s]*(funciones|responsabilidades|tareas|tu\s+misi[oó]n|qu[ée]\s+har[áa]s).*[?\s\:]*$",
        re.IGNORECASE,
    ),
    "requisitos": re.compile(
        r"^[¿\s]*(requisitos|se\s+requiere|perfil\s+buscado|perfil\s+ideal|qu[ée]\s+buscamos|qu[ée]\s+necesitamos|qu[ée]\s+har[áa]\s+que\s+tu\s+candidatura\s+destaque).*[?\s\:]*$",
        re.IGNORECASE,
    ),
    "se_ofrece": re.compile(
        r"^[¿\s]*(se\s+ofrece|ofrecemos|beneficios|condiciones|qu[ée]\s+(te\s+)?ofrecemos).*[?\s\:]*$",
        re.IGNORECASE,
    ),
}

def split_sections(text: str) -> Dict[str, str]:
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
            continue 
        sections[current].append(line)

    return {key: "\n".join(lines).strip() for key, lines in sections.items()}

# ---------------------------------------------------------------------------
# 4. Diccionario de skills
# ---------------------------------------------------------------------------

def load_yaml(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo de conocimiento: {path}")
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

_CHUNK_SPLIT_RE = re.compile(r"[.,;\n•\-–]+")

class SkillDictionary:
    CATEGORIES = ("competencias", "conocimientos", "herramientas", "softskills")

    def __init__(self, skills_path: Path, synonims_path: Path, normalizer: Normalizer, fuzzy_threshold: int = FUZZY_THRESHOLD):
        self.normalizer = normalizer
        self.fuzzy_threshold = fuzzy_threshold
        raw_skills = load_yaml(skills_path)
        self.synonyms: dict = load_yaml(synonims_path) if synonims_path.exists() else {}

        self.phrase_index: Dict[str, Tuple[str, str]] = {}

        for category in self.CATEGORIES:
            skill_map = raw_skills.get(category, {}) or {}
            for skill_id, phrases in skill_map.items():
                for phrase in phrases:
                    norm_phrase = normalizer.normalize(phrase)
                    self.phrase_index[norm_phrase] = (skill_id, category)

    def canonical(self, skill_id: str) -> str:
        return self.synonyms.get(skill_id, skill_id)

    def extract_skills(self, text: str) -> Dict[str, Set[str]]:
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

            best = process.extractOne(chunk, all_phrases, scorer=fuzz.token_set_ratio, score_cutoff=self.fuzzy_threshold)
            if best is not None:
                phrase, _score, _idx = best
                skill_id, category = self.phrase_index[phrase]
                found[category].add(self.canonical(skill_id))

        return found

# ---------------------------------------------------------------------------
# 5. Detección de sector
# ---------------------------------------------------------------------------

class SectorDetector:
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

_EMPRESA_RE = re.compile(r"(?:empresa|compañ[ií]a)\s*:\s*([^\n]+)", re.IGNORECASE)
# Se añadió [^\n] para prohibir que arrastre saltos de línea y destruya el nombre
_EMPRESA_NATURAL_RE = re.compile(r"en\s+([A-Z0-9][^\n]{1,35}?)\s+(?:buscamos|seleccionamos|queremos|necesitamos|estamos|te\s+estamos)", re.IGNORECASE)

def extract_empresa(text: str) -> str:
    match = _EMPRESA_RE.search(text)
    if match:
        return match.group(1).strip()
    
    match_natural = _EMPRESA_NATURAL_RE.search(text)
    if match_natural:
        return match_natural.group(1).strip()

    # Si todo falla, extrae la primera línea decente (ignora cabeceras o viñetas)
    ignore_words = {"sector", "descripción", "oferta", "puesto", "funciones", "requisitos"}
    for line in text.split("\n"):
        line_clean = line.strip()
        if not line_clean:
            continue
        if line_clean.lower() in ignore_words:
            continue
        if line_clean.startswith("¿") or line_clean.endswith("?"):
            continue
        if re.match(r"^[-•*?]", line_clean):
            continue
        return line_clean[:50]

    return "Desconocido"

# ---------------------------------------------------------------------------
# 7. Orquestador principal
# ---------------------------------------------------------------------------

class JobOfferParser:
    def __init__(self, knowledge_dir: Path = KNOWLEDGE_DIR, spacy_model: str = SPACY_MODEL, fuzzy_threshold: int = FUZZY_THRESHOLD):
        self.normalizer = Normalizer(spacy_model)
        self.skill_dict = SkillDictionary(
            knowledge_dir / "skills.yaml",
            knowledge_dir / "synonims.yaml",
            self.normalizer,
            fuzzy_threshold=fuzzy_threshold,
        )
        self.sector_detector = SectorDetector(knowledge_dir / "sector.yaml", self.normalizer)

    def parse(self, filepath: Union[str, Path]) -> JobOffer:
        path = Path(filepath)
        raw_text = path.read_text(encoding="utf-8", errors="ignore")

        cleaned = clean_text(raw_text)
        sections = split_sections(cleaned)

        empresa = extract_empresa(cleaned)
        sector = self.sector_detector.detect(cleaned)

        skills_por_categoria = self.skill_dict.extract_skills(sections.get("requisitos", ""))
        for extra_sec in ["descripcion", "funciones"]:
            extra = self.skill_dict.extract_skills(sections.get(extra_sec, ""))
            for categoria, valores in extra.items():
                skills_por_categoria[categoria] |= valores

        # Procesamiento avanzado de funciones
        raw_funciones = sections.get("funciones", "")
        funciones = []
        for line in raw_funciones.split("\n"):
            # Limpiamos viñetas (ahora incluye '?' por si los emojis se corrompieron)
            line_clean = line.lstrip(" -•*?¿¡!").strip()
            if len(line_clean) < 4:
                continue
                
            # Si el texto es un párrafo descriptivo masivo (>100 chars) y no es viñeta clara, 
            # delegamos en SpaCy para que separe las oraciones gramaticales.
            if len(line_clean) > 100 and not re.match(r"^\s*[-•*?]", line):
                doc = self.normalizer.nlp(line_clean)
                for sent in doc.sents:
                    sent_text = sent.text.lstrip(" -•*?¿¡!").strip()
                    if len(sent_text) > 4:
                        funciones.append(sent_text)
            else:
                funciones.append(line_clean)

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
    if len(sys.argv) != 2:
        print("Uso: python parser.py ruta/a/oferta.txt")
        sys.exit(1)

    parser = JobOfferParser()
    oferta = parser.parse(sys.argv[1])

    print("Empresa   :", oferta.empresa)
    print("Sector    :", oferta.sector)
    print("Skills    :", oferta.skills)
    print("Funciones :")
    for f in oferta.funciones:
        print(f"  - {f}")
    print("Categorías:")
    print("  competencias :", oferta.competencias)
    print("  conocimientos:", oferta.conocimientos)
    print("  herramientas :", oferta.herramientas)
    print("  softskills   :", oferta.softskills)