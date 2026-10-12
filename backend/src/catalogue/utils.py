import re
import unicodedata


def normalize_title(title: str) -> str:
    normalized = unicodedata.normalize("NFKC", title).casefold()
    return " ".join(
        "".join(
            char if unicodedata.category(char)[0] in {"L", "N", "M"} else " " for char in normalized
        ).split()
    )


def title_identity(title: str) -> str:
    """Keep meaningful punctuation such as #Love distinct from Love."""
    return " ".join(unicodedata.normalize("NFKC", title).casefold().split())


def title_variants(title: str) -> list[str]:
    cleaned = title.translate(dict.fromkeys(map(ord, "\u200b\ufeff\u2060")))
    folded = []
    latin = False
    for char in unicodedata.normalize("NFD", cleaned):
        if unicodedata.category(char).startswith("M"):
            if latin:
                continue
        else:
            latin = "LATIN" in unicodedata.name(char, "")
        folded.append(char)
    bases = [cleaned, unicodedata.normalize("NFC", "".join(folded))]
    variants = []
    seen = {normalize_title(title)}
    for base in bases:
        core, separator, subtitle = base.partition(":")
        core = core.strip()
        descriptive = separator and len(core.split()) >= 3 and len(subtitle.split()) >= 6
        variants_for_base = [
            base,
            ".".join(base) if re.fullmatch(r"[A-Z]{2,8}", base) else base,
            re.sub(r"\s+I$", "", base),
            core if descriptive else base,
        ]
        for variant in variants_for_base:
            key = normalize_title(variant)
            if key and key not in seen:
                seen.add(key)
                variants.append(variant)
    return variants
