"""Validation de confort ; l'API reste l'autorité métier."""

import json

SUPPORTS = {
    "numerique": "Numérique",
    "dvd": "DVD",
    "blu-ray": "Blu-ray",
    "vhs": "VHS",
    "autre": "Autre",
}


def list_values(form, name, limit):
    """Recover unchanged line endings; hidden state never bypasses validation."""
    values = [value.replace("\r\n", "\n").replace("\r", "\n") for value in form.getlist(name)]
    encoded = form.getlist("_original_" + name)
    # An astral character occupies two six-character JSON Unicode escapes.
    if len(encoded) != 1 or len(encoded[0]) > 30 * (limit * 12 + 4) + 2:
        return values
    try:
        originals = json.loads(encoded[0])
        if (
            not isinstance(originals, list)
            or len(originals) > 30
            or len(originals) != len(values)
            or any(not isinstance(value, str) or len(value) > limit for value in originals)
        ):
            return values
        for value in originals:
            value.encode("utf-8")
    except (ValueError, RecursionError, UnicodeEncodeError):
        return values
    return [
        original
        if original.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "\ufffd") == value
        else value
        for original, value in zip(originals, values, strict=True)
    ]


def validate_names(values, limit):
    names = [value.strip() for value in values if value.strip()]
    return names, len(values) <= 30 and all(len(value) <= limit for value in names)


def validate(form):
    title = form.get("titre", "").strip()
    director = form.get("realisateur", "").strip()
    year = form.get("annee", "").strip()
    actors, valid_actors = validate_names(form.get("acteurs", []), 120)
    support = form.get("support", "")
    synopsis = form.get("synopsis", "").strip()
    errors = {}
    if not title or len(title) > 200:
        errors["titre"] = "Indiquez un titre de 1 à 200 caractères."
    if not director or len(director) > 120:
        errors["realisateur"] = "Indiquez un réalisateur de 1 à 120 caractères."
    if len(year) != 4 or not year.isascii() or not year.isdigit() or not 1888 <= int(year) <= 2100:
        errors["annee"] = "Indiquez une année entre 1888 et 2100."
    if not valid_actors:
        errors["acteurs"] = "Indiquez au plus 30 noms de 120 caractères."
    if support not in SUPPORTS:
        errors["support"] = "Choisissez un support."
    if len(synopsis) > 4000:
        errors["synopsis"] = "Le synopsis ne peut pas dépasser 4000 caractères."
    data = {
        "titre": title,
        "realisateur": director,
        "annee": int(year) if "annee" not in errors else None,
        "acteurs": actors,
        "support": support,
        "synopsis": synopsis,
    }
    return data, errors
