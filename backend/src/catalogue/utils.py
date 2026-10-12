import unicodedata


def title_identity(title: str) -> str:
    """Keep meaningful punctuation such as #Love distinct from Love."""
    return " ".join(unicodedata.normalize("NFKC", title).casefold().split())
