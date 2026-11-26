# -*- coding: utf-8 -*-
"""
aelf.py — L'ÉVANGILE DU JOUR (source : AELF — aelf.org) — ajouté en v7.18.4.

Un seul geste pour la cellule Communication : le bouton « ✨ Évangile du jour
(AELF) » de l'onglet 🙏 Prière / Méditation appelle `evangile_du_jour()` et
pré-remplit Titre et Contenu :

  Titre    → « Évangile du Jour – jeudi 26 novembre 2026 »
  Contenu  → le sous-titre (« Évangile de Jésus Christ selon saint Luc »),
             la référence convertie (« Lc 21, 20-28 » → « Luc 21, 20-28 »),
             le texte biblique, puis la ligne de source © AELF.

La source est l'API officielle AELF (api.aelf.org) — la même maison que le
site consulté jusqu'ici à la main. Si AELF est injoignable, AelfError porte
un message clair : la saisie manuelle reste la porte de secours, rien ne
casse et rien n'est publié automatiquement (le diocèse garde son SAS).

Textes liturgiques © AELF — aelf.org (Association Épiscopale Liturgique pour
les pays de Francophonie).
"""
import datetime
import html
import re

import requests

URL_API = "https://api.aelf.org/v1/messes/{date}"
ENTETES = {"User-Agent": "GestionnaireEquipesRosaire/7.18.4 (priere des equipes du rosaire)"}
DELAI = 15  # secondes

JOURS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
           "août", "septembre", "octobre", "novembre", "décembre"]

# Abréviations bibliques (celles qu'AELF met dans « ref ») → noms longs.
# Une abréviation inconnue reste telle quelle : jamais de référence fausse.
NOMS_LIVRES = {
    "Mt": "Matthieu", "Mc": "Marc", "Lc": "Luc", "Jn": "Jean",
    "Ac": "Actes des Apôtres",
    "Rm": "Romains", "1Co": "1 Corinthiens", "2Co": "2 Corinthiens",
    "Ga": "Galates", "Ep": "Éphésiens", "Ph": "Philippiens", "Phm": "Philémon",
    "Col": "Colossiens", "1Th": "1 Thessaloniciens", "2Th": "2 Thessaloniciens",
    "1Tm": "1 Timothée", "2Tm": "2 Timothée", "Tt": "Tite",
    "He": "Hébreux", "Jc": "Jacques", "1P": "1 Pierre", "2P": "2 Pierre",
    "1Jn": "1 Jean", "2Jn": "2 Jean", "3Jn": "3 Jean", "Jude": "Jude",
    "Ap": "Apocalypse", "Sg": "Sagesse", "Sir": "Sirac", "Bar": "Baruch",
    "Is": "Isaïe", "Jr": "Jérémie", "Lm": "Lamentations", "Ez": "Ézéchiel",
    "Dn": "Daniel", "Os": "Osée", "Jl": "Joël", "Am": "Amos", "Ab": "Abdias",
    "Jon": "Jonas", "Mi": "Michée", "Na": "Nahum", "Ha": "Habacuc",
    "So": "Sophonie", "Ag": "Aggée", "Za": "Zacharie", "Ml": "Malachie",
    "Gn": "Genèse", "Ex": "Exode", "Lv": "Lévitique", "Nb": "Nombres",
    "Dt": "Deutéronome", "Jos": "Josué", "Jg": "Juges", "Rt": "Ruth",
    "1S": "1 Samuel", "2S": "2 Samuel", "1R": "1 Rois", "2R": "2 Rois",
    "1Ch": "1 Chroniques", "2Ch": "2 Chroniques", "Es": "Esdras",
    "Ne": "Néhémie", "Tb": "Tobie", "Jdt": "Judith", "Est": "Esther",
    "Jb": "Job", "Ps": "Psaumes", "Pr": "Proverbes", "Qo": "Qohéleth",
    "Ct": "Cantique", "Dt2": "Deutéronome",
}

SOURCE_TEXTES = "Textes liturgiques © AELF — aelf.org"

_ACCLAMATION_FINALE = re.compile(
    r"^\s*[–—-]\s*(Acclamons la Parole de Dieu\.?|Parole du Seigneur\.?)\s*$")


class AelfError(Exception):
    """Erreur attendue (réseau, réponse vide…) avec un message clair pour la cellule."""


def reference_longue(reference_courte):
    """« Lc 21, 20-28 » → « Luc 21, 20-28 ». Abréviation inconnue → inchangée."""
    if not reference_courte:
        return ""
    propre = re.sub(r"\s+", " ", str(reference_courte).replace("\u00a0", " ")).strip()
    morceaux = propre.split(None, 1)
    if not morceaux:
        return propre
    livre, reste = morceaux[0], (morceaux[1].strip() if len(morceaux) > 1 else "")
    nom = NOMS_LIVRES.get(livre)
    if nom is None:
        return propre
    return (nom + (" " + reste if reste else "")).strip()


def date_en_francais(date_):
    """datetime.date → « jeudi 26 novembre 2026 » (sans dépendre des locales)."""
    return "{jour} {quantieme} {mois} {annee}".format(
        jour=JOURS_FR[date_.weekday()],
        quantieme=date_.day,
        mois=MOIS_FR[date_.month - 1],
        annee=date_.year,
    )


def _nettoyer_contenu(texte):
    """Le HTML d'AELF (balises <p>, <br>, &nbsp;) → texte propre, lignes poétiques gardées."""
    if not texte:
        return ""
    t = str(texte)
    t = re.sub(r"<br\s*/?>", "\n", t, flags=re.IGNORECASE)
    t = re.sub(r"</p\s*>", "\n", t, flags=re.IGNORECASE)
    t = re.sub(r"<[^>]+>", "", t)
    t = html.unescape(t)
    t = t.replace("\u00a0", " ")
    lignes = [ligne.rstrip() for ligne in t.splitlines()]
    lignes = [ligne for ligne in lignes if ligne.strip()]
    # la dernière ligne d'AELF est l'acclamation (« – Acclamons la Parole de
    # Dieu. ») : la cellule la retire de sa saisie à la main — idem ici.
    while lignes and _ACCLAMATION_FINALE.match(lignes[-1]):
        lignes.pop()
    return "\n".join(lignes).strip()


def _appeler_api(date_iso):
    reponse = requests.get(URL_API.format(date=date_iso),
                           headers=ENTETES, timeout=DELAI)
    reponse.raise_for_status()
    return reponse.json()


def _extraire_evangile(donnees):
    """La lecture « evangile » de la Messe du jour → (sous_titre, reference, texte)."""
    messes = (donnees or {}).get("messes") or []
    # « Messe du jour » d'abord (les jours de fête peuvent en lister plusieurs)
    messes_triees = sorted(messes,
                           key=lambda m: 0 if "du jour" in str(m.get("nom", "")).lower() else 1)
    for messe in messes_triees:
        for lecture in messe.get("lectures") or []:
            if str(lecture.get("type", "")).lower() != "evangile":
                continue
            sous_titre = (lecture.get("intro_lue") or "").strip()
            reference = re.sub(r"\s+", " ", str(lecture.get("ref") or "")
                               .replace("\u00a0", " ")).strip()
            texte = _nettoyer_contenu(lecture.get("contenu"))
            if not sous_titre and reference:
                # repli : dériver le sous-titre du livre (« Luc »)
                livre = reference.split(None, 1)[0]
                nom = NOMS_LIVRES.get(livre)
                if nom:
                    sous_titre = "Évangile de Jésus Christ selon saint " + nom
            return {"sous_titre": sous_titre, "reference": reference, "texte": texte}
    return None


def evangile_du_jour(date=None):
    """L'Évangile du jour, prêt à coller dans la méditation.

    `date` : datetime.date/datetime/« AAAA-MM-JJ » (par défaut : aujourd'hui).
    Renvoie un dict : date, date_longue, titre, sous_titre, reference_courte,
    reference, texte, contenu. Lève AelfError (message clair) si AELF est
    injoignable ou silencieux — la saisie manuelle reste la porte de secours.
    """
    if date is None:
        date_ = datetime.date.today()
    elif isinstance(date, datetime.datetime):
        date_ = date.date()
    elif isinstance(date, datetime.date):
        date_ = date
    else:
        try:
            date_ = datetime.date.fromisoformat(str(date).strip())
        except ValueError:
            raise AelfError("Date invalide (« " + str(date) + " ») — "
                            "l'Évangile du jour attend le format AAAA-MM-JJ.")
    date_iso = date_.isoformat()
    try:
        donnees = _appeler_api(date_iso)
    except requests.exceptions.Timeout:
        raise AelfError("🕊️ AELF ne répond pas (délai de " + str(DELAI) + " s dépassé). "
                        "Réessayez dans un instant, ou saisissez l'Évangile à la main "
                        "comme d'habitude.")
    except requests.exceptions.RequestException:
        raise AelfError("🕊️ AELF est injoignable pour le moment. Réessayez plus tard, "
                        "ou saisissez l'Évangile à la main comme d'habitude.")
    except ValueError:
        raise AelfError("🕊️ Réponse illisible d'AELF. Saisissez l'Évangile à la main "
                        "comme d'habitude.")

    morceaux = _extraire_evangile(donnees)
    if not morceaux or not morceaux.get("texte") or not morceaux.get("reference"):
        raise AelfError("🕊️ AELF n'a pas renvoyé d'Évangile pour le "
                        + date_en_francais(date_) + ". Saisissez-le à la main "
                        "comme d'habitude.")

    date_longue = date_en_francais(date_)
    sous_titre = morceaux["sous_titre"]
    reference_courte = morceaux["reference"]
    reference = reference_longue(reference_courte)
    texte = morceaux["texte"]

    titre = "Évangile du Jour – " + date_longue
    contenu = "\n".join([sous_titre, reference, "", texte, "",
                         SOURCE_TEXTES])

    return {
        "date": date_iso,
        "date_longue": date_longue,
        "titre": titre,
        "sous_titre": sous_titre,
        "reference_courte": reference_courte,
        "reference": reference,
        "texte": texte,
        "contenu": contenu,
    }
