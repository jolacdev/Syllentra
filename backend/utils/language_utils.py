"""Normalize standard language identifiers without loading media or model dependencies."""

import re

# ISO 639-1 and legacy ISO 639-2 terminology/bibliographic codes for the model's languages.
LANGUAGE_ALIASES = {
    "en": ("eng",),
    "es": ("spa",),
    "fr": ("fra", "fre"),
    "de": ("deu", "ger"),
    "it": ("ita",),
    "pt": ("por",),
    "nl": ("nld", "dut"),
    "pl": ("pol",),
    "ru": ("rus",),
    "uk": ("ukr",),
    "ro": ("ron", "rum"),
    "cs": ("ces", "cze"),
    "sk": ("slk", "slo"),
    "bg": ("bul",),
    "hr": ("hrv",),
    "sv": ("swe",),
    "da": ("dan",),
    "fi": ("fin",),
    "et": ("est",),
    "lv": ("lav",),
    "lt": ("lit",),
    "hu": ("hun",),
    "sl": ("slv",),
    "mt": ("mlt",),
    "el": ("ell", "gre"),
}
LANGUAGE_CODES = {alias: code for code, aliases in LANGUAGE_ALIASES.items() for alias in (code, *aliases)}
# RFC 5646 syntax: extlangs, script, region, variants, extensions, and private use.
LANGUAGE_TAG = re.compile(
    r"[a-z]{2,3}(?:-[a-z]{3}){0,3}(?:-[a-z]{4})?(?:-(?:[a-z]{2}|[0-9]{3}))?"
    r"(?:-(?:[a-z0-9]{5,8}|[0-9][a-z0-9]{3}))*"
    r"(?:-[0-9a-wy-z](?:-[a-z0-9]{2,8})+)*(?:-x(?:-[a-z0-9]{1,8})+)?"
)


def normalize_language(value: str | None) -> str | None:
    """Match standard ISO codes and BCP 47 tags by base language; names and titles are not language tags."""
    if value is None:
        return None
    label = value.casefold()
    if LANGUAGE_TAG.fullmatch(label):
        return LANGUAGE_CODES.get(label.split("-", 1)[0])
    return None
