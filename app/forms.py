"""Validation de confort ; l'API reste l'autorité métier."""
SUPPORTS = {'numerique': 'Numérique', 'dvd': 'DVD', 'blu-ray': 'Blu-ray', 'vhs': 'VHS', 'autre': 'Autre'}


def validate(form):
    title = form.get('titre', '').strip()
    director = form.get('realisateur', '').strip()
    year = form.get('annee', '').strip()
    actors = [x.strip() for x in form.get('acteurs', '').split(',') if x.strip()]
    support = form.get('support', '')
    synopsis = form.get('synopsis', '').strip()
    errors = {}
    if not title or len(title) > 200:
        errors['titre'] = 'Indiquez un titre de 1 à 200 caractères.'
    if not director or len(director) > 120:
        errors['realisateur'] = 'Indiquez un réalisateur de 1 à 120 caractères.'
    if not year.isascii() or not year.isdigit() or not 1888 <= int(year) <= 2100:
        errors['annee'] = 'Indiquez une année entre 1888 et 2100.'
    if len(actors) > 30 or any(len(x) > 120 for x in actors):
        errors['acteurs'] = 'Indiquez au plus 30 noms de 120 caractères.'
    if support not in SUPPORTS:
        errors['support'] = 'Choisissez un support.'
    if len(synopsis) > 4000:
        errors['synopsis'] = 'Le synopsis ne peut pas dépasser 4000 caractères.'
    data = {'titre': title, 'realisateur': director, 'annee': int(year) if 'annee' not in errors else None, 'acteurs': actors, 'support': support, 'synopsis': synopsis}
    return data, errors
