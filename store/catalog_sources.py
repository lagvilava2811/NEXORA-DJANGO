from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal
from itertools import zip_longest
from urllib.parse import unquote, urlparse

from PIL import Image


@dataclass(frozen=True)
class CatalogSource:
    slug: str
    name_en: str
    name_ka: str
    name_ru: str
    class_id: str
    candidate_limit: int
    min_price: int
    max_price: int


CATEGORY_SOURCES = (
    CatalogSource("smartphones", "Smartphones", "სმარტფონები", "Смартфоны", "Q19723451", 520, 399, 4999),
    CatalogSource("cameras", "Cameras", "კამერები", "Камеры", "Q20741022", 720, 499, 14999),
    CatalogSource("laptops", "Laptops", "ლეპტოპები", "Ноутбуки", "Q73343954", 80, 999, 9999),
    CatalogSource("tablets", "Tablets", "ტაბლეტები", "Планшеты", "Q113990168", 24, 399, 4999),
    CatalogSource("gaming", "Gaming", "გეიმინგი", "Игры", "Q56682555", 42, 299, 4999),
    CatalogSource("wearables", "Wearables", "ჭკვიანი აქსესუარები", "Носимые устройства", "Q19799938", 34, 149, 2999),
    CatalogSource("graphics-cards", "Graphics Cards", "ვიდეობარათები", "Видеокарты", "Q122760264", 15, 499, 9999),
    CatalogSource("monitors", "Monitors", "მონიტორები", "Мониторы", "Q136260412", 12, 299, 6999),
    CatalogSource("processors", "Processors", "პროცესორები", "Процессоры", "Q122967152", 74, 199, 4999),
    CatalogSource("microphones", "Microphones", "მიკროფონები", "Микрофоны", "Q83178864", 13, 99, 2999),
    CatalogSource("keyboards", "Keyboards", "კლავიატურები", "Клавиатуры", "Q128558307", 39, 59, 1499),
    CatalogSource("printers", "Printers", "პრინტერები", "Принтеры", "Q128493564", 27, 199, 3999),
    CatalogSource("mice", "Computer Mice", "კომპიუტერის მაუსები", "Компьютерные мыши", "Q135902762", 74, 39, 999),
)

SOURCE_BY_SLUG = {source.slug: source for source in CATEGORY_SOURCES}

BRAND_HINTS = {
    "iphone": "Apple",
    "ipad": "Apple",
    "macbook": "Apple",
    "apple watch": "Apple",
    "galaxy": "Samsung",
    "pixel": "Google",
    "xperia": "Sony",
    "playstation": "Sony",
    "xbox": "Microsoft",
    "surface": "Microsoft",
    "thinkpad": "Lenovo",
    "lumia": "Nokia",
    "redmi": "Xiaomi",
    "mi ": "Xiaomi",
    "rog ": "ASUS",
    "geforce": "NVIDIA",
    "radeon": "AMD",
    "ryzen": "AMD",
}


def build_sparql(source: CatalogSource) -> str:
    """Build one bounded exact-item query for a Wikidata product-model class."""
    return f'''SELECT ?item ?itemLabel
        (SAMPLE(?imageValue) AS ?image)
        (SAMPLE(?manufacturerName) AS ?manufacturer)
        (SAMPLE(?descriptionValue) AS ?description)
        (SAMPLE(?websiteValue) AS ?website)
        (MAX(?dateValue) AS ?released)
    WHERE {{
      ?item wdt:P31 wd:{source.class_id};
            wdt:P18 ?imageValue;
            rdfs:label ?itemLabel.
      FILTER(LANG(?itemLabel) = "en")
      OPTIONAL {{
        ?item wdt:P176 ?manufacturerItem.
        ?manufacturerItem rdfs:label ?manufacturerName.
        FILTER(LANG(?manufacturerName) = "en")
      }}
      OPTIONAL {{
        ?item schema:description ?descriptionValue.
        FILTER(LANG(?descriptionValue) = "en")
      }}
      OPTIONAL {{ ?item wdt:P856 ?websiteValue. }}
      OPTIONAL {{
        {{ ?item wdt:P577 ?dateValue. }}
        UNION
        {{ ?item wdt:P571 ?dateValue. }}
      }}
    }}
    GROUP BY ?item ?itemLabel
    ORDER BY DESC(?released) ?itemLabel
    LIMIT {source.candidate_limit}'''


def entity_id(entity_url: str) -> str:
    value = entity_url.rstrip("/").rsplit("/", 1)[-1].upper()
    if not re.fullmatch(r"Q\d+", value):
        raise ValueError(f"Invalid Wikidata entity URL: {entity_url}")
    return value


def commons_filename(image_url: str) -> str:
    parsed = urlparse(image_url)
    marker = "/Special:FilePath/"
    if marker not in parsed.path:
        raise ValueError(f"Not a Wikimedia file URL: {image_url}")
    return unquote(parsed.path.split(marker, 1)[1]).replace("_", " ")


GENERIC_MEDIA_TOKENS = {
    "file", "image", "photo", "product", "sample", "front", "back", "view",
    "official", "device", "model", "series", "camera", "phone", "laptop", "the",
    "and", "with", "from", "webp", "jpeg", "jpg", "png", "tiff",
}


def media_tokens(value: str) -> list[str]:
    normalized = unicodedata.normalize("NFKD", unquote(value)).encode("ascii", "ignore").decode("ascii")
    return [token for token in re.findall(r"[a-z0-9]+", normalized.casefold()) if token not in GENERIC_MEDIA_TOKENS]


def model_match_score(product_name: str, filename: str) -> float:
    """Conservatively verify that a Commons filename names the same model.

    The Wikidata P18 claim supplies the semantic link; this lexical gate catches bad
    or family-level claims such as a Core Ultra 9 item pointing at a Core Ultra 7 file.
    """
    wanted = media_tokens(product_name)
    actual = media_tokens(filename)
    if not wanted or not actual:
        return 0.0
    actual_set = set(actual)
    compact = "".join(actual)
    identifiers = [token for token in wanted if any(char.isdigit() for char in token)]
    if identifiers and any(token not in actual_set and token not in compact for token in identifiers):
        return 0.0
    matched = sum(token in actual_set or token in compact for token in wanted)
    score = matched / len(wanted)
    if "".join(wanted) in compact:
        score = max(score, 0.95)
    return score


def model_media_matches(product_name: str, filename: str, threshold: float = 0.68) -> bool:
    return model_match_score(product_name, filename) >= threshold

def normalise_file_title(value: str) -> str:
    value = unquote(value).replace("_", " ").strip()
    if value.lower().startswith("file:"):
        value = value[5:]
    return " ".join(value.split()).casefold()


def safe_brand(name: str, manufacturer: str | None) -> str:
    manufacturer = (manufacturer or "").strip()
    if manufacturer and not re.fullmatch(r"Q\d+", manufacturer):
        return manufacturer[:80]
    lowered = f"{name.strip().lower()} "
    for prefix, brand in BRAND_HINTS.items():
        if lowered.startswith(prefix) or f" {prefix}" in lowered:
            return brand
    token = re.split(r"[\s\-/]+", name.strip())[0]
    return (token or "Independent")[:80]


def deterministic_int(key: str, low: int, high: int) -> int:
    if high < low:
        raise ValueError("high must be greater than or equal to low")
    number = int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:12], 16)
    return low + (number % (high - low + 1))


def deterministic_price(key: str, source: CatalogSource) -> Decimal:
    raw = deterministic_int(f"price:{key}", source.min_price, source.max_price)
    rounded = max(source.min_price, int(round(raw / 10.0) * 10) - 1)
    return Decimal(f"{rounded}.00")


def image_dhash(image: Image.Image) -> str:
    pixels = list(image.convert("L").resize((9, 8), Image.Resampling.LANCZOS).getdata())
    bits = []
    for row in range(8):
        offset = row * 9
        bits.extend(pixels[offset + column] > pixels[offset + column + 1] for column in range(8))
    value = 0
    for bit in bits:
        value = (value << 1) | int(bit)
    return f"{value:016x}"


def hamming_distance(left: str, right: str) -> int:
    return (int(left, 16) ^ int(right, 16)).bit_count()


def round_robin(groups: dict[str, list[dict]]) -> list[dict]:
    """Interleave categories so a large source cannot crowd out smaller categories."""
    ordered_groups = [groups[source.slug] for source in CATEGORY_SOURCES if groups.get(source.slug)]
    output: list[dict] = []
    for row in zip_longest(*ordered_groups):
        output.extend(item for item in row if item is not None)
    return output


def variant_blueprints(category_slug: str) -> tuple[dict, ...]:
    if category_slug in {"smartphones", "tablets"}:
        return (
            {"name": "128 GB", "storage": "128 GB", "ram": "8 GB", "price_delta": 0},
            {"name": "256 GB", "storage": "256 GB", "ram": "8 GB", "price_delta": 180},
            {"name": "512 GB", "storage": "512 GB", "ram": "12 GB", "price_delta": 420},
        )
    if category_slug == "laptops":
        return (
            {"name": "16 GB / 512 GB", "ram": "16 GB", "storage": "512 GB", "price_delta": 0},
            {"name": "32 GB / 1 TB", "ram": "32 GB", "storage": "1 TB", "price_delta": 650},
            {"name": "64 GB / 2 TB", "ram": "64 GB", "storage": "2 TB", "price_delta": 1450},
        )
    if category_slug == "cameras":
        return (
            {"name": "Body", "size": "Body", "price_delta": 0},
            {"name": "Creator Kit", "size": "Creator Kit", "price_delta": 480},
            {"name": "Pro Kit", "size": "Pro Kit", "price_delta": 980},
        )
    return (
        {"name": "Standard", "size": "Standard", "price_delta": 0},
        {"name": "Premium", "size": "Premium", "price_delta": 240},
    )