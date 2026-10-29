# ====================================================================
# view_espace_membre.py — VERSION 7.8.11 (mise en page du feuillet)
# v7.8.11 : ① MISE EN PAGE TYPOGRAPHIQUE des pages du livret (demande n°4) :
#   marqueurs R./T./1./2./3+T. en gras, réponses « T. »/« 3+T. » en gras,
#   section « À l'écoute de la Parole de Dieu » en gras (sauf le titre du
#   passage, en italique), Salve Regina en gras, interligne entre marqueurs,
#   légende des rôles et puce « Accueil » de « Célébrons en équipe », titres
#   de rubrique en police manuscrite (Caveat, Google Fonts ; repli local
#   Segoe Print / Comic Sans MS) ;
# ② CADRE PHOTO sous chaque titre de section (image encadrée façon photo
#   papier, ou emplacement pointillé si pas d'image) + POSITION de la photo
#   au choix : haut / droite / gauche avec habillage du texte (demande n°3,
#   nouvelle colonne feuillet_sections.pos_image) ;
# ③ ALERTE feuillet : elle annonce le DERNIER MOIS PASTORAL publié (et non la
#   dernière publication en date) — republier septembre après octobre ne
#   renvoie plus l'alerte sur septembre (demande n°2) ; une publication à
#   date illisible est annoncée sans mention de date (auto-réparation) ;
# ④ Photos de Prière/Méditation du fil : préfixe [droite]/[gauche] du lien
#   (choisi à la soumission) → image flottante dans la carte du jour.
# (lecteur compagnon — musique en continu, v7.8.9)
# v7.8.9 : ① le bouton 🎧 ouvre l'onglet d'écoute en FENÊTRE COMPAGNON nommée
# sur PC (réutilisée à chaque clic) et dans le MÊME onglet sur téléphone ;
# ② la page d'écoute porte une barre « ◀️ Revenir à l'appli » (sur téléphone,
# un tap ramène à l'espace et la musique suit) ; ③ MINI-BARRE COMPAGNON
# flottante sur toutes les pages de l'espace : reprise automatique de la
# musique là où elle s'était arrêtée (sessionStorage) — on prie dans
# « 📿 Rosaire » ou le livret pendant que la musique continue ; ④ contrôles
# Media Session (écran verrouillé / notifications) + vignette flottante 📺
# (Picture-in-Picture, si supporté).
# v7.8.5 : ① la carte « 📝 Éditorial » est RETIRÉE de la vitrine — retour au
# duo Sommaire + « Ouvrir le livret » ; les archives suivent donc
# IMMÉDIATEMENT le bouton ; ② sommaire du livret en présentation UNIQUE
# (les entrées cliquables « 📖 N — Titre » remplacent la liste statique
# doublonnée et les boutons « ▶ » pris pour des expanders) ; ③ « ✕ Fermer
# le livret » ramène à 🕯️ Thème → 🔭 Vue d'ensemble ; ④ l'emplacement des
# archives est ANNONCÉ même sans feuillet précédent.
# v7.8.4 : ③ le clic sur l'alerte « Nouveau feuillet » OUVRE DIRECTEMENT le
# livret du feuillet annoncé via le lien profond ?flt=1&fa=ANNÉE&fm=MOIS
# (même mécanisme que les liens d'archive), au lieu de mener à la vitrine.
# v7.8.3 : ① vitrine du feuillet — la PREMIÈRE section (Éditorial) est lue
# directement dans la vitrine de Vue d'ensemble, sous le Sommaire (demande h :
# le clic de l'alerte mène à « Sommaire / Éditorial du feuillet ») ;
# ② blindage alerte — aucune alerte si le feuillet annoncé n'a aucune
# section saisie (sinon le clic mènerait à « pas encore publié »).
# v7.8.2 : ① e — RETOUR EN HAUT DE PAGE à chaque tour de page du livret
# (script scrollé avec nonce → ré-exécuté à chaque page, fini le scroll
# manuel vers le titre) ; ② h — l'alerte « 📖 Nouveau feuillet » du fil
# mène à 🕯️ Thème → 🔭 Vue d'ensemble (Sommaire du feuillet) ;
# ③ i — archivage des feuillets précédents EN EXPANDERS avec liens dans
# Vue d'ensemble (la sous-rubrique Archives → 📖 Feuillets est retirée).
# Hérite de v7.8.1 : correctif navigation (sandbox sans allow-top-navigation).
# Hérite de v7.8 : feuillets mensuels (vitrine, livret autonome, alerte fil).
# Hérite de v7.6 : menu liens HTML purs + ruban hover + ☰ mobile,
# navigation ?r=&s=, mesure autocorrigée, QR paroissial, lecteur complet.
# Marqueurs : Ctrl+F → "VERSION 7.6", "_liens_meme_onglet", "_VERSION_APPLI".
# ====================================================================
import os
import re
import html
import unicodedata
import base64
import urllib.parse
import json
import streamlit as st
from datetime import date
# v7.6.8 — Migration st.iframe : l'API st.components.v1.html est dépréciée
# (suppression annoncée). On utilise st.iframe si disponible ; repli
# automatique sur l'ancienne API sinon.
# POUR REVENIR EN ARRIÈRE : remplacez tout ce bloc par la ligne commentée.
# from streamlit.components.v1 import html as _comp_html
# v7.8 — CORRECTIF : st.iframe (Streamlit 1.66+) REFUSE height=0
# (StreamlitInvalidHeightError) et, les appels étant blindés par
# try/except, TOUS les scripts (mesure entête, scroll top, liens même
# onglet) mouraient en silence. On passe donc par st.iframe avec une
# hauteur minimale de 1 px (les scripts y exécutent bien
# window.parent.document) ; repli components.html sur les anciennes
# versions de Streamlit dépourvues de st.iframe.
# v7.8.16 — ce mécanisme est CENTRALISÉ dans stcompat.py (même code pour
# app.py, components.py et cette vue) : les avertissements « Please replace
# st.components.v1.html with st.iframe » disparaissent des journaux Cloud.
from stcompat import comp_html as _comp_html
from database import (c, commit_and_sync, verifier_reparer_intentions,
                      intention_du_prochain, intention_du_prochain_detail,
                      intentions_reserve_surplus,
                      contact_en_priere, date_intention_en_priere,
                      prise_en_charge_automatique, verser_intention_du_jour,
                      pointer_dizaine, dizaine_deja_pointee, compteur_dizaines_mois,
                      marquer_carte_vue, carte_deja_vue, dizaine_visiteur_pointee,
                      feuillet_questions_lister, feuillet_reponses_enregistrer,
                      feuillet_reponses_de_cle, importer_dizaines_hors_ligne)
from services import safe_date, compter_visite, lien_whatsapp, urls_galerie
from mysteres import get_mysteres_du_jour, COULEURS_TYPES, MYSTERES, get_mystere, get_theme_actif, get_sous_theme_du_mois, get_lien_mystere

# v7.9.8 — UNE SEULE version pour TOUTE la vue : la carte d'accueil affichait
# encore « v7.6 » (jamais suivie à chaque livraison) — désormais la carte et
# le pied de page lisent la MÊME constante, mise à jour à chaque version.
_VERSION_APPLI = "v7.10.1"

# v7.9.9 — la page Facebook du Mouvement / du diocèse : renseignée, l'icône
# apparaît dans la barre de copyright du pied de page (même disposition que
# le site du Mouvement) ; vide, elle reste discrètement absente.
LIEN_FACEBOOK = ""

# v7.9.17 — LA VIDÉO À LA DEMANDE : la vidéo YouTube de la chaîne
# « Équipes du Rosaire Grand-Bassam » s'affiche JUSTE AVANT LE PIED DE PAGE
# (v7.9.19 — elle a quitté la tête du fil d'actualité, à la demande :
# « s'il doit s'ouvrir, c'est juste avant le pied de page » ; v7.9.20 —
# la date du pèlerinage est passée, la carte porte son nom d'aujourd'hui :
# la vidéo reste disponible à la demande), avec le lecteur incorporé et un
# lien d'ouverture. Mettre "" dans la constante pour retirer la carte d'un
# seul geste, sans toucher au reste.
LIEN_YOUTUBE_VIDÉO_A_LA_DEMANDE = "https://youtu.be/RHrIgEeepO8?si=Dg0P8YHE0K3PYNo3"

# v7.9.19 — L'ADRESSE DE LA CHAÎNE YOUTUBE (demande : « le lien de la
# chaîne youtube.com à ajouter comme adresse dans le pied de page ») :
# elle apparaît dans la colonne centrale du pied, sous le contact du
# responsable paroissial. Vide, elle reste discrètement absente.
LIEN_YOUTUBE_CHAINE = "https://www.youtube.com/channel/UCK3pN76H1lTlIyjsIrYMTXw"


# ====================================================================
# NAVIGATION
# ====================================================================
RUBRIQUES_MEMBRE = ["🏠 Actualités", "🕯️ Thème", "📿 Rosaire", "📅 Mes évènements", "🖼️ Galerie +", "📖 Archives"]
RUBRIQUES_PUBLIC = ["🏠 Actualités", "📿 Rosaire", "🕯️ Thème", "🖼️ Galerie +", "📖 Archives"]
SOUS_RUBRIQUES = {
    "🕯️ Thème": ["🔭 Vue d'ensemble", "🎓 Enseignements", "💬 Discussions"],
    "📿 Rosaire": ["Le Rosaire chez les Équipiers", "Le Rosaire thématique"],
    # v7.9.2 — « 🖼️ Galerie + » déplacée ENTRE « 📅 Mes évènements » et
    # « 📖 Archives » (demande user). Le public garde son ordre d'origine.
    # Les liens codés en dur ?r=1 (🕯️ Thème) restent valables : l'index
    # de Thème ne bouge pas dans les deux listes.
    "🖼️ Galerie +": ["Souvenirs", "Témoignages"],
    "📖 Archives": ["🙏 Prières", "📖 Méditations", "🎵 Musiques"],
}

# v7.9.3 — FIL D'ACTUALITÉ ALLÉGÉ : l'Accueil ne garde qu'UNE section, celle
# qui correspond à nos attentes — la prière/méditation DU JOUR (couronnée de
# l'alerte feuillet). « 🙏 Vos intentions à une équipe » est REMONTÉE juste
# avant « 🕯️ Un jour, une dizaine » (harmonisée avec cette dernière) et les
# blocs 📣 Coin Affiche, 📰 Actualités de la Paroisse et 📰 Actualités du
# diocèse quittent le fil. METTRE À False pour réafficher l'ancien fil
# complet (tout le code d'origine est conservé, rien n'est supprimé).
FIL_ALLEGEE = True

def _lire_nav(rubriques):
    """Rubrique/sous-rubrique lues dans l'URL (?r=..&s=..). Navigation par
    LIENS HTML purs : aucun pont JS fragile."""
    rub = rubriques[0]
    try:
        i = int(str(st.query_params.get("r", "")))
        if 0 <= i < len(rubriques):
            rub = rubriques[i]
    except (ValueError, TypeError):
        pass
    sous = SOUS_RUBRIQUES.get(rub)
    sub = None
    if sous:
        sub = sous[0]
        try:
            j = int(str(st.query_params.get("s", "")))
            if 0 <= j < len(sous):
                sub = sous[j]
        except (ValueError, TypeError):
            pass
    return rub, sub

# ====================================================================
# HELPERS
# ====================================================================
# v7.9.15 — LE LOGO PARTOUT : le fichier images/logo.png est désormais LIVRÉ
# dans le paquet (c'est le chapelet doré des Équipes du Rosaire). Il est
# cherché à plusieurs adresses certaines : à côté du module (où que
# l'application soit installée), puis depuis le dossier de lancement ; en
# dernier recours, le chapelet livré dans static/ prend le relais. Pour
# passer au logo officiel du Mouvement, il suffira de déposer la nouvelle
# image sous le même nom — aucun code à modifier.
_CHEMINS_LOGO = (
    os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir,
                 "images", "logo.png"),
    os.path.join("images", "logo.png"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir,
                 "static", "logo_equipes_rosaire.png"),
    os.path.join("static", "logo_equipes_rosaire.png"),
)


@st.cache_data
def _logo_base64():
    for _chemin in _CHEMINS_LOGO:
        try:
            with open(_chemin, "rb") as f:
                return base64.b64encode(f.read()).decode()
        except Exception:
            continue
    return None


PDF_URL_RE = re.compile(r'href="(https://res\.cloudinary\.com/[^"]+\.pdf)"')
DIV_PDF_RE = re.compile(r'<div[^>]*1px dashed #4527a0.*?</div>\s*', re.DOTALL)


def _extraire_pdf_legacy(contenu):
    if not contenu or ("cloudinary" not in contenu and "data:application/pdf" not in contenu):
        return contenu, None
    m = PDF_URL_RE.search(contenu)
    url = m.group(1) if m else None
    return DIV_PDF_RE.sub("", contenu).strip(), url


def _scroll_top(cle):
    """v7.8.2-e — RETOUR EN HAUT DE PAGE à chaque tour de page : à l'ouverture
    d'une nouvelle page, la lecture reprend TOUJOURS en haut (là où se trouve
    le titre), sans devoir scroller vers le haut.
    Double correctif :
    ① CONTENEUR : Streamlit 1.66 ne scrolle PAS la fenêtre (window.scrollTo
      reste inopérant) mais la section <section class="main"> ; on remet à
      zéro le scrollTop de TOUS les conteneurs possibles (main, appView,
      documentElement, body, window) pour rester compatible.
    ② NONCE : le `cle` (page affichée) est injecté dans le script → chaque
      page produit un script DIFFÉRENT → Streamlit recharge l'iframe → le
      scroll s'exécute (sans nonce, l'iframe identique était réutilisée).
    Un 2e passage à 400 ms passe au-dessus de la restauration interne."""
    nonce = re.sub(r"[^0-9A-Za-z_-]", "", str(cle) or "x")
    _js = ("var d=window.parent.document;"
           "var els=d.querySelectorAll('section.main,[data-testid=\"stMain\"],"
           "[data-testid=\"stAppViewContainer\"]');"
           "for(var i=0;i<els.length;i++){els[i].scrollTop=0;}"
           "d.documentElement.scrollTop=0;d.body.scrollTop=0;"
           "try{window.parent.scrollTo(0,0);}catch(e){};")
    try:
        _comp_html("<script>/*" + nonce + "*/"
                   "try{" + _js + "}catch(e){}"
                   "setTimeout(function(){try{" + _js + "}catch(e){}},400);"
                   "</script>", height=0)
    except Exception:
        pass


def _scroll_top_si_nouvelle_page(cle, rub, sub):
    """v7.9.3 — LES PAGES REMONTENT À LEUR OUVERTURE (comme nous l'avons
    fait pour les feuillets) : quand la rubrique/sous-rubrique affichée
    CHANGE — c'est-à-dire à l'ouverture d'une page — la lecture repart DU
    HAUT (même mécanisme « nonce » que _scroll_top). Les interactions DANS
    la page (expander, bouton, formulaire) ne repositionnent PAS l'écran :
    seul le changement de page déclenche le retour en haut."""
    _cle_prec = "nav_page_prec_" + str(cle)
    _actuel = (str(rub), str(sub or ""))
    if st.session_state.get(_cle_prec) != _actuel:
        st.session_state[_cle_prec] = _actuel
        _scroll_top("nav" + str(cle) + re.sub(r"\W", "", str(rub))
                    + re.sub(r"\W", "", str(sub or "")))


def _liens_meme_onglet(cle):
    """v7.6 — LES LIENS DU MENU NAVIGUENT DANS L'ONGLET COURANT.
    Constat terrain : Streamlit force certains liens vers un nouvel onglet
    (10 clics = 10 onglets). Parade : target="_self" écrit dans le HTML
    des ancres + intercepteur qui reprend le clic et navigue le document
    parent. Ré-attaché à chaque run (le DOM est recréé).
    v7.8.1 — CORRECTIF MAJEUR : Streamlit 1.66 sandboxe ses iframes SANS
    « allow-top-navigation » → `window.top.location.href=…` lève
    SecurityError. L'ancien code appelait d'abord e.preventDefault() PUIS
    tentait la nav JS : celle-ci échouait en silence et le clic ne faisait
    PLUS RIEN (tous les liens du menu et des sous-rubriques morts).
    Stratégie « essai sans risque » :
      ① tenter la nav JS (top) ;
      ② si elle RÉUSSIT → preventDefault() (évite le double chargement) ;
      ③ si elle ÉCHOUE → ne RIEN annuler : le navigateur suit l'ancre
        nativement (target="_self" garantit l'onglet courant)."""
    script = (
        "<script>(function(){var d=window.parent.document;var essais=0;"
        "var t=setInterval(function(){essais++;"
        "var as=d.querySelectorAll('.menu-ligne a,.mob-panneau a,.pdr-v910 a');var n=0;"
        "for(var i=0;i<as.length;i++){"
        "if(!as[i].getAttribute('data-self76')){"
        "as[i].setAttribute('data-self76','1');as[i].setAttribute('target','_self');"
        "(function(a){a.addEventListener('click',function(e){"
        "var nav=false;"
        "try{window.top.location.href=a.href;nav=true;}catch(err){}"
        "if(nav&&e&&e.preventDefault){e.preventDefault();}"
        "});})(as[i]);}"
        "n++;}"
        "if(n>0&&essais>2){clearInterval(t);}"
        "else if(essais>20){clearInterval(t);}"
        "},300);})();</script>")
    try:
        _comp_html(script, height=0)
    except Exception:
        pass


def _fixer_liens_ecoute():
    """v7.8.9 — CORRECTIF SANITISEUR pour les liens du lecteur compagnon.
    Constat (test navigateur) : Streamlit 1.66 injecte target="_blank" +
    rel="noopener noreferrer" dans TOUTES les ancres de st.markdown → les
    boutons 🎧 / ◀️ Revenir ouvraient un NOUVEL onglet au lieu de naviguer
    dans l'onglet courant (la mémoire sessionStorage suivait l'ancien
    onglet : musique perdue de vue). Parade (motif éprouvé _liens_meme_onglet,
    v7.8.1) : après rendu, on réécrit `target` en JS sur le DOM vivant et on
    attache un intercepteur « essai sans risque » :
      ① tenter la nav JS du document parent (top) ;
      ② si elle réussit → preventDefault() ;
      ③ si SecurityError (sandbox) → ne RIEN annuler : l'ancre native suit
        (target="_self" réécrit garantit l'onglet courant).
    Cibles : « 🎧 Écouter en priant » (mobile, _self), « ◀️ Revenir à
    l'appli » (_self). Le bouton PC n'est PAS intercepté : on lui rend
    seulement son nom de fenêtre « rosaire_ecoute » (onglet réutilisé,
    window.name sert à la détection compagnon côté page d'écoute).
    `rel` est RETIRÉ sur les trois : le rel=noopener imposé empêche la
    réutilisation d'un onglet nommé (2e clic = 2e onglet).
    Boucle durable : le DOM est recréé à chaque rerun Streamlit."""
    script = (
        "<script>(function(){var d=window.parent.document;"
        "var t=setInterval(function(){"
        "var cibles=[['a.btn-eco.mob','_self',true],"
        "['a.btn-rv','_self',true],"
        "['a.btn-eco.pc','rosaire_ecoute',false]];"
        "for(var j=0;j<cibles.length;j++){"
        "var as=d.querySelectorAll(cibles[j][0]);"
        "for(var i=0;i<as.length;i++){var a=as[i];"
        "if(!a.getAttribute('data-eco89')){"
        "a.setAttribute('data-eco89','1');"
        "a.setAttribute('target',cibles[j][1]);"
        "a.removeAttribute('rel');"
        "if(cibles[j][2]){(function(an){"
        "an.addEventListener('click',function(e){"
        "var nav=false;"
        "try{window.top.location.href=an.href;nav=true;}catch(err){}"
        "if(nav&&e&&e.preventDefault){e.preventDefault();}"
        "});})(a);}}"
        "}}"
        "},350);})();</script>")
    try:
        _comp_html(script, height=0)
    except Exception:
        pass


def _compter_bandes(membre=False, pid=None):
    """Compte les bandes RÉELLEMENT affichées. v7.6 : accès par INDEX
    (jamais d'unpack) — blindé contre tout décalage de colonnes.
    LOT C5 : compte selon le même filtre que l'affichage."""
    cond, prm = ("AND (paroisse_cible IS NULL OR paroisse_cible = ?)", [pid]) if pid \
        else ("AND paroisse_cible IS NULL", [])
    try:
        bandes = c.execute(f"""SELECT contenu_texte, fichier_url FROM espace_spirituel
                              WHERE type_contenu='annonce_defilante' {cond}
                              ORDER BY date_publication DESC, id DESC LIMIT 3""", prm).fetchall()
    except Exception:
        return 0
    # 🔎 Diagnostic (s'affiche avec &debug=1)
    if st.query_params.get("debug") == "1":
        st.caption(f"🔎 DEBUG bandes — pid={pid} | {len(bandes)} ligne(s) : "
                   + " || ".join(f"«{(b[0] or '')[:25]}» cible_stockée={b[1]}" for b in bandes))
    n = 0
    for ligne in bandes:
        if len(ligne) < 1:
            continue
        texte = ligne[0]
        cible = ligne[1] if len(ligne) > 1 else None
        if cible == "membre" and not membre:
            continue
        if not texte:
            continue
        n += 1
    return n


def _mesure_entete(cle):
    """Mesure AUTOCORRIGÉE : revérifie toutes les 400 ms, n'écrit que si la
    hauteur a changé (l'entête se dessine en plusieurs fois).
    v7.8-e : compte aussi la barre de titre du livret (.flt-barre) — posée
    sous l'entête fixe, contenu poussé de la hauteur totale."""
    script = (
        "<script>(function(){var d0=-1;var a=function(){try{"
        "var d=window.parent.document;var h=d.querySelector('.sticky-header');"
        "var b=d.querySelector('.block-container');"
        "var bar=d.querySelector('.flt-barre');"
        "if(h&&b){var t=h.offsetHeight;"
        "if(bar){bar.style.top=t+'px';t+=bar.offsetHeight;}"
        "if(t!==d0){d0=t;"
        "b.style.setProperty('padding-top',t+'px','important');}}}catch(e){}};"
        "a();setInterval(a,400);window.parent.addEventListener('resize',a);})();</script>")
    try:
        _comp_html(script, height=0)
    except Exception:
        pass

def _render_theme(compact=False):
    """CSS de l'espace. CONCATÉNATION (jamais de f-string avec du CSS)."""
    if compact:
        secours_1, secours_2, secours_3 = 260, 240, 230
    else:
        secours_1, secours_2, secours_3 = 380, 330, 310
    regle_contenu = (
        ".block-container { padding-top: " + str(secours_1)
        + "px !important; padding-bottom: 4rem !important; max-width: 1050px !important; }"
    )
    st.markdown(
        '<style>'
        # v7.8.11 — police manuscrite des titres de section du livret
        # (@import DOIT précéder toute règle CSS) ; repli local si hors-ligne.
        + "@import url('https://fonts.googleapis.com/css2?family=Caveat:wght@600;700&display=swap');\n"
        + regle_contenu +
        """
    [data-testid="stHeader"] { display: none !important; }
    .stApp, [data-testid="stAppViewContainer"] { background-color: #0a0f2c !important; }
    .stApp .stMarkdown, .stApp .stMarkdown p, .stApp .stMarkdown li, .stApp .stMarkdown span,
    .stApp .stMarkdown h1, .stApp .stMarkdown h2, .stApp .stMarkdown h3, .stApp .stMarkdown h4,
    .stApp .stMarkdown strong, .stApp .stMarkdown em { color: #e8eaf6 !important; }
    .stApp .stMarkdown a { color: #b39ddb !important; }
    [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p { color: #9fa6d8 !important; }
    [data-testid="stExpander"] { background-color: #121a45 !important; border: 1px solid #27306b !important; border-radius: 12px !important; }
    details, [data-testid="stExpanderDetails"] { background-color: transparent !important; }
    summary, [data-testid="stExpander"] p { color: #e8eaf6 !important; }
    [data-baseweb="tab-list"] { border-bottom-color: #27306b !important; }
    [data-baseweb="tab"] p { color: #e8eaf6 !important; font-weight: 600 !important; }
    [data-baseweb="tab"][aria-selected="true"] p { color: #ffffff !important; }
    [data-baseweb="tab-highlight"] { background-color: #7b1fa2 !important; }
    .stButton > button { background-color: #1a2150 !important; color: #e8eaf6 !important; border: 1px solid #2a3160 !important; }
    .stButton > button[kind="primary"] { background-color: #4527a0 !important; border-color: #5e35b1 !important; color: #ffffff !important; }
    [data-testid="stAlert"] { background-color: #151b3d !important; }
    [data-testid="stAlert"] p { color: #e8eaf6 !important; }
    [data-testid="stPopover"] { width: fit-content !important; max-width: 260px !important; margin-left: 0 !important; }
    [data-testid="stPopover"] button { background-color: #4527a0 !important; color: #ffffff !important; border: 1px solid #5e35b1 !important; border-radius: 20px !important; font-weight: 600 !important; }
    [data-testid="stPopover"] button:hover { background-color: #5e35b1 !important; }
    [data-testid="stNumberInput"] { max-width: 220px !important; margin-left: auto !important; margin-right: auto !important; }
    [data-testid="stNumberInputStepUp"], [data-testid="stNumberInputStepDown"] { display: none !important; }
    .menu-ligne { display:flex; flex-wrap:wrap; gap:6px; justify-content:center; margin:8px auto 0 auto; max-width:1200px; }
    .menu-item { position:relative; }
    .menu-lien { display:block; background-color:#1a2150; color:#e8eaf6; border:1px solid #2a3160; border-radius:20px; padding:6px 14px; font-weight:600; font-size:0.85rem; text-decoration:none; white-space:nowrap; cursor:pointer; }
    .menu-item.actif .menu-lien { background-color:#4527a0; border-color:#5e35b1; color:#ffffff; }
    .menu-item:hover .menu-lien { background-color:#5e35b1; color:#ffffff; }
    .sous-ruban { display:none; position:absolute; top:100%; left:50%; transform:translateX(-50%); z-index:10001; background:#121a45; border:1px solid #27306b; border-radius:10px; padding:6px; min-width:210px; box-shadow:0 6px 18px rgba(0,0,0,0.5); }
    .menu-item:hover .sous-ruban { display:flex; flex-direction:column; gap:4px; }
    .menu-sub { display:block; background:#1a2150; color:#e8eaf6; border:1px solid #2a3160; border-radius:14px; padding:6px 12px; font-size:0.82rem; font-weight:600; text-decoration:none; white-space:nowrap; }
    .menu-sub.actif { background:#4527a0; border-color:#5e35b1; color:#ffffff; }
    .menu-sub:hover { background:#5e35b1; color:#ffffff; }
    .menu-mobile { display:none; }
    @media (max-width:640px) {
        .menu-ligne { display:none; }
        .menu-mobile { display:block; position:relative; margin:6px auto 0 auto; width:fit-content; }
        .menu-mobile summary { list-style:none; background:#4527a0; color:#ffffff; border:1px solid #5e35b1; border-radius:20px; padding:6px 22px; font-size:1.1rem; font-weight:bold; cursor:pointer; }
        .menu-mobile summary::-webkit-details-marker { display:none; }
        .menu-mobile[open] summary { background:#5e35b1; }
        .mob-panneau { position:absolute; top:calc(100% + 6px); left:50%; transform:translateX(-50%); width:250px; max-height:60vh; overflow-y:auto; background:#121a45; border:1px solid #27306b; border-radius:12px; padding:8px; z-index:10001; box-shadow:0 6px 18px rgba(0,0,0,0.5); display:flex; flex-direction:column; gap:4px; }
        .mob-lien { display:block; background:#1a2150; color:#e8eaf6; border:1px solid #2a3160; border-radius:14px; padding:8px 12px; font-weight:600; font-size:0.9rem; text-decoration:none; }
        .mob-lien.actif { background:#4527a0; border-color:#5e35b1; color:#ffffff; }
        .mob-sous { display:block; color:#c7cdf5; padding:4px 10px 4px 22px; font-size:0.85rem; text-decoration:none; }
        .mob-sous.actif { color:#ffd000; font-weight:700; }
    }
    .sticky-header { position: fixed; top: 0; left: 0; right: 0; z-index: 9999;
        background-color: #0a0f2c; border-bottom: 1px solid #27306b; padding: 12px 16px 0 16px; }
    .header-inner { max-width: 1200px; margin: 0 auto; display: flex; justify-content: space-between; align-items: flex-start; }
    /* v7.9.3 — entête un PEU plus compacte (pages remontées à l'affichage,
    comme les feuillets) : logo réduit de 190 à 170 px — la hauteur de
    l'entête mesurée par _mesure_entete suit automatiquement. */
    .logo-bloc { width: 170px; text-align: center; }
    .logo-bloc img { width: 100%; height: auto; border-radius: 10px; display: block; margin: 0 auto; }
    .logo-titre-svg { display: block; width: 100%; margin-top: 6px; }
    .bande-defilante { overflow: hidden; white-space: nowrap;
        background: linear-gradient(90deg, #1a2150, #27306b);
        border-top: 1px solid #27306b; }
    .bande-defilante-inner { display: inline-block; padding: 8px 0; white-space: nowrap;
        color: #ffd000 !important; font-weight: 600; font-size: 0.9rem;
        animation: defilement 30s linear infinite; }
    .bande-defilante:hover .bande-defilante-inner { animation-play-state: paused; }
    @keyframes defilement { 0% { transform: translateX(100vw); } 100% { transform: translateX(-100%); } }
    @media (prefers-reduced-motion: reduce) {
        .bande-defilante-inner { animation: none; padding: 8px 15px; }
    }
    @media (max-width: 640px) {
        .logo-bloc { width: 136px; }
        .block-container { padding-top: """ + str(secours_2) + """px !important; }
        [data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; }
        [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] { min-width: 0 !important; }
    }
    @media (max-width: 360px) {
        .logo-bloc { width: 126px; }
        .block-container { padding-top: """ + str(secours_3) + """px !important; }
    }
    /* === TITRES DORÉS/BLEUS GEORGIA — classes haute spécificité (battent le thème) === */
    .stApp .stMarkdown .dpl-titre-g,
    .stApp .stMarkdown .dpl-titre-g * {
        font-family: Georgia, serif !important;
        color: #FFD000 !important;
        font-weight: bold !important;
    }
    .stApp .stMarkdown .dpl-txt-g,
    .stApp .stMarkdown .dpl-txt-g * {
        font-family: Georgia, serif !important;
        color: #FFD000 !important;
    }
    .stApp .stMarkdown .dpl-titre-b,
    .stApp .stMarkdown .dpl-titre-b * {
        font-family: Georgia, serif !important;
        color: #1A237E !important;
        font-weight: bold !important;
    }
    .stApp .stMarkdown .dpl-p-blanc,
    .stApp .stMarkdown .dpl-p-blanc * {
        color: #ffffff !important;
        font-weight: bold !important;
    }
    .stApp .stMarkdown .dpl-titre-or,
    .stApp .stMarkdown .dpl-titre-or * {
        font-family: Georgia, serif !important;
        color: #B8860B !important;
        font-weight: bold !important;
    }
    /* === STYLE RUBRIQUES (langage du dépliant) === */
    .stApp .stMarkdown .rub-carte {
        background: #121a45 !important;
        border: 1px solid #27306b !important;
        border-left: 5px solid #FFD700 !important;
        border-radius: 12px !important;
    }
    .stApp .stMarkdown .rub-carte-titre,
    .stApp .stMarkdown .rub-carte-titre * {
        font-family: Georgia, serif !important;
        color: #FFD000 !important;
        font-weight: bold !important;
    }
    .stApp .stMarkdown .rub-carte-txt,
    .stApp .stMarkdown .rub-carte-txt * {
        color: #e8eaf6 !important;
    }
    /* Expander à liseré doré (Archives, Actualités, Rosaire) */
    .stApp div[data-testid="stExpander"] {
        border-left: 5px solid #FFD700 !important;
        border-radius: 4px 12px 12px 4px !important;
    }
    /* Images des rubriques : style dépliant (cadre, hauteur fixe) */
    .stApp .stMarkdown .rub-photo {
        width:100%; max-width:860px; height:150px; object-fit:contain;
        background:#0a0f2c; border-radius:8px; display:block; margin:10px auto;
    }
    @media (min-width:769px) {
        .stApp .stMarkdown .rub-photo { height:230px; }
    }
    .stApp .stMarkdown h3 { color: #FFD000 !important; font-size: clamp(0.95rem, 4.2vw, 1.25rem) !important; }
    /* === CARTES PRIÈRE v7.7.4 — verrouillage lisibilité (bat le thème sombre) === */
    .stApp .stMarkdown .carte-priere { background:#FFF9C4 !important; border-radius:12px; padding:14px 16px; margin:8px 6px; }
    .stApp .stMarkdown .carte-priere, .stApp .stMarkdown .carte-priere * { font-family:Georgia, serif !important; color:#1a1a1a !important; }
    .stApp .stMarkdown .carte-priere .cp-para { font-size:0.95rem; text-align:left; line-height:1.7; margin:6px 0; }
    .stApp .stMarkdown .carte-priere .cp-titre { color:#1A237E !important; font-weight:bold; font-size:1.02rem; border-bottom:1.5px solid #1A237E; padding-bottom:3px; margin:12px 0 8px 0; }
    .stApp .stMarkdown .carte-priere .cp-rouge { color:#D32F2F !important; font-weight:bold; font-size:0.98rem; text-align:inherit; line-height:1.6; margin:16px 0 4px 0; }
    .stApp .stMarkdown .carte-priere .cp-italique { font-style:italic !important; text-align:center; }
    .stApp .stMarkdown .carte-priere .cp-trait { border:none; border-top:1px solid #1A237E; margin:14px auto; }
    .stApp .stMarkdown .carte-priere .cp-bande { font-weight:bold; border-radius:8px; padding:8px 12px; text-align:center; margin:0 0 10px 0; font-family:sans-serif !important; }
    .stApp .stMarkdown .carte-priere .cp-photo { width:100%; max-width:860px; height:150px; object-fit:contain; border-radius:8px; display:block; margin:0 auto 10px auto; }
    .stApp .stMarkdown .carte-priere .cp-accent { color:var(--c) !important; font-weight:bold; font-size:0.98rem; margin:10px 0 2px 0; }
    .stApp .stMarkdown .carte-priere .cp-accent-inline { color:var(--c) !important; font-weight:bold; }
    .stApp .stMarkdown .carte-priere .cp-accent-bg { background:var(--c) !important; color:#ffffff !important; }
    .stApp .stMarkdown .details-mystere { background:#121a45; border:1px solid #27306b; border-left:6px solid var(--c); border-radius:12px; margin:8px 6px; overflow:hidden; }
    .stApp .stMarkdown .details-mystere summary { list-style:none; cursor:pointer; background:var(--c) !important; color:#ffffff !important; font-weight:bold; font-family:sans-serif !important; padding:10px 16px; font-size:1rem; }
    .stApp .stMarkdown .details-mystere summary::-webkit-details-marker { display:none; }
    @media (min-width:769px) { .stApp .stMarkdown .carte-priere .cp-photo { height:230px; } }
    /* === LIVRET MENSUEL EN AUTONOMIE v7.8 === */
    .flt-barre { position: fixed; top: 230px; left: 0; right: 0; z-index: 600;
        background: #0a0f2c; border-bottom: 1px solid #27306b; padding: 8px 16px; }
    .flt-barre-titre { color: #FFD000; font-weight: bold; text-align: center;
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        font-family: Georgia, serif; font-size: 0.98rem; }
    .flt-pagination { text-align: center; color: #9fa6d8; font-size: 0.9rem;
        margin: 0 0 14px 0; font-family: sans-serif; }
    /* === LIVRET v7.8.11 — MISE EN PAGE TYPOGRAPHIQUE DU FEUILLET === */
    .flt-barre-titre { font-family:'Caveat','Segoe Print','Bradley Hand',cursive;
        font-size:1.3rem; }
    .stApp .stMarkdown .carte-priere .fe-titre-rubrique,
    .stApp .stMarkdown .carte-priere .fe-titre-rubrique * {
        font-family:'Caveat','Segoe Print','Bradley Hand','Comic Sans MS',cursive !important;
        font-size:1.62rem !important; font-weight:700 !important; line-height:1.25 !important; }
    .stApp .stMarkdown .carte-priere .fe-p { margin:0 0 12px 0; }
    .stApp .stMarkdown .carte-priere .fe-gras,
    .stApp .stMarkdown .carte-priere .fe-gras * { font-weight:bold !important; }
    .stApp .stMarkdown .carte-priere .fe-marq { font-weight:bold !important; }
    .stApp .stMarkdown .carte-priere .fe-accueil { color:#1A237E !important;
        font-weight:bold !important; font-size:1.08rem !important;
        text-decoration:underline !important; margin:4px 0 10px 0; }
    .stApp .stMarkdown .carte-priere .fe-passage { font-style:italic !important;
        text-align:center; font-weight:normal !important; }
    .stApp .stMarkdown .carte-priere .fe-photo-cadre { background:#ffffff;
        border:1px solid #C9A227; box-shadow:0 3px 10px rgba(0,0,0,.30);
        border-radius:8px; padding:5px; display:inline-block; }
    .stApp .stMarkdown .carte-priere .fe-photo-cadre .cp-photo { margin:0 auto; }
    .stApp .stMarkdown .carte-priere .fe-photo-droite { float:right; width:47%;
        max-width:320px; margin:4px 0 10px 16px; }
    .stApp .stMarkdown .carte-priere .fe-photo-gauche { float:left; width:47%;
        max-width:320px; margin:4px 16px 10px 0; }
    .stApp .stMarkdown .carte-priere .fe-photo-droite .cp-photo,
    .stApp .stMarkdown .carte-priere .fe-photo-gauche .cp-photo { width:100%;
        height:150px; object-fit:cover; margin:0; }
    @media (min-width:769px) {
        .stApp .stMarkdown .carte-priere .fe-photo-droite .cp-photo,
        .stApp .stMarkdown .carte-priere .fe-photo-gauche .cp-photo { height:170px; }
    }
    .stApp .stMarkdown .carte-priere .fe-cadre-vide { border:2px dashed #C9A227;
        background:#FFFDE7; color:#8d6e08 !important; border-radius:10px;
        padding:12px 10px; text-align:center; font-size:0.9rem;
        margin:4px auto 14px auto; max-width:430px; }
    @media (max-width:640px) {
        .stApp .stMarkdown .carte-priere .fe-photo-droite,
        .stApp .stMarkdown .carte-priere .fe-photo-gauche { float:none !important;
            width:100% !important; max-width:100% !important; margin:4px 0 12px 0 !important; }
    }
    /* v7.8.11 — photos flottantes de la carte Prière/Méditation du fil */
    .stApp .stMarkdown .rub-photo-fd { float:right; width:44%; max-width:300px;
        height:auto; max-height:240px; object-fit:cover; border-radius:8px;
        margin:4px 0 10px 14px; }
    .stApp .stMarkdown .rub-photo-fg { float:left; width:44%; max-width:300px;
        height:auto; max-height:240px; object-fit:cover; border-radius:8px;
        margin:4px 14px 10px 0; }
    @media (max-width:640px) {
        .stApp .stMarkdown .rub-photo-fd, .stApp .stMarkdown .rub-photo-fg {
            float:none; width:100%; max-width:100%; margin:0 0 10px 0; }
    }
    /* === LIVRET v7.8.14 — BANDE DU TITRE : titre sur les ¾ à gauche,
       photo sur le quart à l'extrême droite (emplacement pointillé sinon) === */
    .stApp .stMarkdown .carte-priere .fe-bande-titre { display:flex;
        align-items:stretch; gap:10px; margin:2px 0 12px 0; }
    .stApp .stMarkdown .carte-priere .fe-bande-titre-txt { flex:1 1 75%;
        min-width:0; display:flex; align-items:center; }
    .stApp .stMarkdown .carte-priere .fe-bande-titre-txt .cp-titre {
        flex:1; border-bottom:1.5px solid #1A237E; margin:0; text-align:left; }
    .stApp .stMarkdown .carte-priere .fe-bande-photo { flex:0 0 24%;
        max-width:24%; min-width:70px; display:flex; align-items:center;
        justify-content:center; }
    .stApp .stMarkdown .carte-priere .fe-bande-photo img { width:100%;
        height:auto; max-height:92px; object-fit:contain; border-radius:8px;
        border:1px solid #C9A227; background:#ffffff; padding:2px;
        box-shadow:0 2px 8px rgba(0,0,0,.25); display:block; }
    .stApp .stMarkdown .carte-priere .fe-bande-vide { width:100%;
        border:2px dashed #C9A227; background:#FFFDE7; color:#8d6e08 !important;
        border-radius:8px; text-align:center; font-size:1.15rem; padding:12px 4px; }
    /* === LIVRET v7.8.14 — PHOTOS DU CORPS aux 4 coins : ~¼ de page, texte
       habillé, proportions d'origine (la position centrée disparaît) === */
    .stApp .stMarkdown .carte-priere .fe-photo-hd { float:right; width:26%;
        max-width:26%; margin:4px 0 10px 16px; }
    .stApp .stMarkdown .carte-priere .fe-photo-hg { float:left; width:26%;
        max-width:26%; margin:4px 16px 10px 0; }
    .stApp .stMarkdown .carte-priere .fe-photo-bd { float:right; width:26%;
        max-width:26%; margin:14px 0 6px 16px; }
    .stApp .stMarkdown .carte-priere .fe-photo-bg { float:left; width:26%;
        max-width:26%; margin:14px 16px 6px 0; }
    .stApp .stMarkdown .carte-priere .fe-photo-hd .cp-photo,
    .stApp .stMarkdown .carte-priere .fe-photo-hg .cp-photo,
    .stApp .stMarkdown .carte-priere .fe-photo-bd .cp-photo,
    .stApp .stMarkdown .carte-priere .fe-photo-bg .cp-photo { width:100%;
        height:auto; object-fit:contain; margin:0; }
    @media (max-width:640px) {
        .stApp .stMarkdown .carte-priere .fe-photo-hd,
        .stApp .stMarkdown .carte-priere .fe-photo-hg,
        .stApp .stMarkdown .carte-priere .fe-photo-bd,
        .stApp .stMarkdown .carte-priere .fe-photo-bg { float:none !important;
            width:88% !important; max-width:88% !important;
            margin:6px auto 12px auto !important; }
        .stApp .stMarkdown .carte-priere .fe-bande-titre { flex-wrap:wrap; }
        .stApp .stMarkdown .carte-priere .fe-bande-photo { flex:0 0 34%;
            max-width:34%; }
    }
    </style>""", unsafe_allow_html=True)


def _bandes_defilantes_html(membre=False, pid=None):
    """HTML des bandes défilantes. v7.6 : accès par INDEX (blindé).
    LOT C5 : filtre par contexte paroissial (bandes diocèse + paroisse du contexte)."""
    cond, prm = ("AND (paroisse_cible IS NULL OR paroisse_cible = ?)", [pid]) if pid \
        else ("AND paroisse_cible IS NULL", [])
    try:
        bandes = c.execute(f"""SELECT contenu_texte, fichier_url FROM espace_spirituel
                              WHERE type_contenu='annonce_defilante' {cond}
                              ORDER BY date_publication DESC, id DESC LIMIT 3""", prm).fetchall()
    except Exception:
        return ""
    # 🔎 Diagnostic (s'affiche avec &debug=1)
    if st.query_params.get("debug") == "1":
        _p_raw = st.query_params.get("p")
        if isinstance(_p_raw, list):
            _p_raw = _p_raw[0] if _p_raw else None
        st.caption(f"🔎 DEBUG bandes — pid={pid} | URL p={_p_raw} | "
                   f"session.paroisse_origine={st.session_state.get('paroisse_origine')} | "
                   f"{len(bandes)} bande(s) vue(s) ici : "
                   + " || ".join(f"«{(b[0] or '')[:25]}…» portée={b[1]}" for b in bandes))
    morceaux = []
    for ligne in bandes:
        if len(ligne) < 1:
            continue
        texte = ligne[0]
        cible = ligne[1] if len(ligne) > 1 else None
        if cible == "membre" and not membre:
            continue
        if not texte:
            continue
        duree = max(15, min(60, len(texte) // 2))
        texte_html = html.escape(texte)
        morceaux.append(
            f'<div class="bande-defilante"><div class="bande-defilante-inner" style="animation-duration:{duree}s;">'
            f"📻 {texte_html} &nbsp;&nbsp;📻 {texte_html}</div></div>")
    return "".join(morceaux)


def _render_header(membre=None, matloc=None, masquer_bandes=False,
                   rubriques=None, rub_act=None, sub_act=None, pid=None):
    """Entête FIGÉE — v7.6 : menu en liens HTML avec target="_self"
    (navigation DANS l'onglet courant ; l'intercepteur _liens_meme_onglet
    tente la nav JS puis LAISSE la navigation native agir si le sandbox
    la refuse — v7.8.1). PC : ruban au survol. Mobile : ☰ en <details>."""
    logo_b64 = _logo_base64()
    logo_html = (f'<img src="data:image/png;base64,{logo_b64}" alt="Logo">'
                 if logo_b64 else '<div style="font-size:4rem;">📿</div>')

    titre_svg = ('<svg class="logo-titre-svg" viewBox="0 0 190 22" width="100%" height="22" '
                 'preserveAspectRatio="none" role="img" aria-label="Diocèse de Grand-Bassam">'
                 '<text x="95" y="17" text-anchor="middle" textLength="188" lengthAdjust="spacingAndGlyphs" '
                 'style="fill:#e8eaf6; font-weight:600; font-size:14px;">Diocèse de Grand-Bassam</text></svg>')

    badge_txt = "Espace Membre" if (membre and matloc) else "Espace communautaire"
    droite = ('<div style="padding-top:14px;">'
              '<div style="background-color:#4527a0; color:#ffffff;'
              ' padding:10px 18px; border-radius:30px; font-weight:bold;'
              ' font-size:0.9rem; display:inline-block; white-space:nowrap;">'
              + badge_txt + '</div></div>')

    menu_html = ""
    if rubriques:
        base = "?espace=1"
        if matloc:
            base += "&matloc=" + str(matloc)
        # LOT C5 : le contexte paroissiel voyage avec la navigation interne
        # (chaque clic de menu recharge la page → session neuve → sans p=,
        # paroisse_origine serait perdu)
        if pid:
            base += "&p=" + str(pid)
        items = []
        for i, r in enumerate(rubriques):
            href_r = base + "&nav=1&r=" + str(i)
            sous = SOUS_RUBRIQUES.get(r)
            ruban = ""
            if sous:
                sitems = ""
                for k, s in enumerate(sous):
                    href_s = href_r + "&s=" + str(k)
                    cls = "menu-sub" + (" actif" if (r == rub_act and s == sub_act) else "")
                    sitems += '<a class="' + cls + '" href="' + href_s + '" target="_self">' + s + "</a>"
                ruban = '<div class="sous-ruban">' + sitems + "</div>"
            cls_item = "menu-item" + (" actif" if r == rub_act else "")
            items.append('<div class="' + cls_item + '"><a class="menu-lien" href="' + href_r + '" target="_self">' + r + "</a>" + ruban + "</div>")
        menu_html = '<div class="menu-ligne">' + "".join(items) + "</div>"
        mitems = []
        for i, r in enumerate(rubriques):
            href_r = base + "&nav=1&r=" + str(i)
            mitems.append('<a class="mob-lien' + (" actif" if r == rub_act else "") + '" href="' + href_r + '" target="_self">' + r + "</a>")
            sous = SOUS_RUBRIQUES.get(r)
            if sous:
                for k, s in enumerate(sous):
                    href_s = href_r + "&s=" + str(k)
                    cls = "mob-sous" + (" actif" if (r == rub_act and s == sub_act) else "")
                    mitems.append('<a class="' + cls + '" href="' + href_s + '" target="_self">· ' + s + "</a>")
        menu_html += ('<details class="menu-mobile"><summary>☰</summary>'
                      '<div class="mob-panneau">' + "".join(mitems) + "</div></details>")

    bandes_html = "" if masquer_bandes else _bandes_defilantes_html(membre=bool(membre), pid=pid)

    st.markdown(
        '<div class="sticky-header"><div class="header-inner">'
        '<div class="logo-bloc">' + logo_html + titre_svg + "</div>"
        + droite + "</div>"
        + menu_html + bandes_html + "</div>", unsafe_allow_html=True)


# ====================================================================
# MA DIZAINE AU QUOTIDIEN — portage web de l'application Android
# © MOTIAN TOFFÉ Ahua Innocent — intégrée avec son autorisation
# ====================================================================
DIZ_INTRO1 = "Au Nom du Père, et du Fils et du Saint-Esprit! Amen!\n\nPRIÈRE D’ENTRÉE\n\nSeigneur Jésus, nous nous disposons à prier\nce Rosaire en communion avec la Vierge Marie.\nViens, Esprit Saint, remplis les cœurs de tes fidèles et allume en eux le feu de ton amour.\nDonne-nous la grâce de méditer profondément les mystères de ta vie, pour que, en les imitant, nous obtenions les promesses qu’ils renferment.\nPar le Christ, notre Seigneur. Amen.\n\nJE CROIS EN DIEU\n\nJe crois en Dieu, le Père Tout-Puissant, Créateur du ciel et de la terre.\nEt en Jésus-Christ, son Fils unique, Notre Seigneur, qui a été conçu du Saint-Esprit, est né de la Vierge Marie, a souffert sous Ponce Pilate, a été crucifié, est mort et a été enseveli, est descendu aux enfers, le troisième jour est ressuscité des morts, est monté aux cieux, est assis à la droite de Dieu le Père Tout-Puissant, d’où il viendra juger les vivants et les morts.\nJe crois en l’Esprit-Saint, à la Sainte Église catholique, à la communion des Saints, à la rémission des péchés, à la résurrection de la chair, à la vie éternelle.\nAmen."
DIZ_INTRO2 = "NOTRE PÈRE\n\nNotre Père, qui es aux cieux,\nque ton nom soit sanctifié,\nque ton règne vienne,\nque ta volonté soit faite\nsur la terre comme au ciel.\n\nDonne-nous aujourd’hui notre pain de ce jour. Pardonne-nous nos offenses, comme nous pardonnons aussi à ceux qui nous ont offensés. Et ne nous laisse pas entrer en tentation, mais délivre-nous du Mal. Amen!\n\n3 JE VOUS SALUE MARIE\n\nJe vous salue Marie, pleine de grâce,\nle Seigneur est avec vous. Vous êtes bénie entre toutes les femmes, et Jésus, le fruit de vos entrailles, est béni.\n\nSainte Marie, Mère de Dieu, priez pour nous pauvres pécheurs, maintenant et à l’heure de notre mort. Amen!\n\nGLORIA PATRI\n\nGloria patri, et Filio, et Spiritui Sancto.\nSicut erat in principio, et nunc, et semper, et in saecula saeculorum. Amen!"
DIZ_INTRO3 = "PRIÈRE À LA VIERGE DU PÈRE EYQUEM\n\n[R]Vers Toi je lève les yeux,\nSainte Mère de Dieu;[/R]\ncar je voudrais faire de ma maison,\nune maison où Jésus vienne, selon sa promesse,\nquand plusieurs se réunissent en son nom.\nTu as accueilli le message de l’ange comme\nun message venant de Dieu, et Tu as reçu,\nen raison de ta foi,\nl’incomparable grâce d’accueillir\nen Toi Dieu Lui-même.\nTu as ouvert aux bergers puis aux mages\nla porte de ta maison, sans que\nnul ne se sente gêné\npar sa pauvreté ou sa richesse.\n\n[R]Sois Celle qui chez moi reçoit.[/R]\nAfin que ceux qui ont besoin\nd’être réconfortés le soient;\nceux qui ont le désir de\nrendre grâce puissent le faire ;\nceux qui cherchent la paix la trouvent.\nEt que chacun reparte vers sa propre maison\navec la joie d’avoir rencontré Jésus lui-même,\nLui, le Chemin, la Vérité, la Vie.\nAmen!\n\n[I]Frère Joseph EYQUEM, o.p.,\nFondateur des Équipes du Rosaire[/I]"
DIZ_OUTRO = "SALVE REGINA\n\nSalve Regina, Mater misericordiae;\nvita, dulcedo, et spes nostra salve.\nAd te clamamus, exsules filii Hevae.\nAd te suspiramus, gementes et flentes\nin hac lacrimarum valle.\nEia ergo, advocata nostra,\nillos tuos misericordes oculos ad nos converte;\nEt Iesum, benedictum fructum ventris tui,\nnobis, post hoc exsilium ostende.\nO Clemens, O pia, O dulcis, Virgo Maria.\n\nOra pro nobis, Sancta Dei Genitrix.\nUt digni efficiamur promissionibus Christi.\n\nPRIÈRE FINALE\n\nÔ Dieu, dont le Fils unique nous a acquis\npar sa vie, sa mort et sa résurrection\nles récompenses du salut éternel,\nnous vous supplions : faites que,\nméditant les mystères du très\nSaint Rosaire de\nla Bienheureuse Vierge Marie,\nnous imitions ce qu’ils contiennent\net obtenons ce qu’ils promettent.\nPar le Christ, notre Seigneur. Amen!\n\nÔ Marie, conçue sans péché!\nPriez pour nous qui avons recours à vous!\n\nÔ Marie, conçue sans péché!\nPriez pour nous qui avons recours à vous!\n\nÔ Marie, conçue sans péché!\nPriez pour nous qui avons recours à vous!\n\nAu Nom du Père, et du Fils et du Saint-Esprit! Amen!"


def _diz_txt(texte, couleur="#333333", taille="0.95rem", gras=False, centre=False):
    txt_html = html.escape(str(texte)).replace("\n", "<br>")
    poids = "bold" if gras else "normal"
    align = "center" if centre else "left"
    return (f'<div style="color:{couleur}; font-size:{taille}; font-weight:{poids};'
            f' text-align:{align}; line-height:1.7; margin:8px 0;">{txt_html}</div>')


MOIS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
           "août", "septembre", "octobre", "novembre", "décembre"]

COULEURS_CLAIRES = {"joyeux": "#FF80AB", "lumineux": "#9FA8DA",
                    "douloureux": "#F48FB1", "glorieux": "#A5D6A7"}


def _rendre_intro_eyquem(titre_carte="INTRODUCTION", afficher_titres=True, trait_debut=False):
    """v7.7.4 — carte de la prière du Père Eyquem, conforme au dépliant.
    Refrains rouges SANS soulignement, alignés comme le texte ; trait de
    début optionnel (page Rosaire) ; titres optionnels (livre de la dizaine)."""
    texte = DIZ_INTRO3
    _morceaux = texte.split("\n", 1)
    titre_priere = _morceaux[0].strip()
    reste = _morceaux[1].strip() if len(_morceaux) > 1 else ""
    t_esc = html.escape(reste).replace("\n", "<br>")
    t_esc = t_esc.replace("[R]", '</div><div class="cp-rouge">')
    t_esc = t_esc.replace("[/R]", '</div><div class="cp-para">')
    t_esc = t_esc.replace("[I]", '</div><div class="cp-italique">')
    t_esc = t_esc.replace("[/I]", "</div>")
    corps = '<div class="cp-para">' + t_esc
    _entete = ""
    if afficher_titres:
        _entete = ('<div class="cp-titre">' + html.escape(titre_carte) + "</div>"
                   '<div class="cp-titre" style="text-align:center;">' + html.escape(titre_priere) + "</div>")
    _trait = '<div class="cp-trait" style="margin-top:4px;"></div>' if trait_debut else ""
    return '<div class="carte-priere">' + _trait + _entete + corps + "</div>"

def _texte_sur(couleur_hex):
    """v7.7.6 — contraste automatique : renvoie un texte BLEU FONCÉ si le fond
    est clair, BLANC sinon. Utilisé pour les textes posés sur la couleur d'un
    chapelet (en-têtes des mystères, numéros des Ave)."""
    try:
        _h = str(couleur_hex).lstrip("#")
        _r, _g, _b = int(_h[0:2], 16), int(_h[2:4], 16), int(_h[4:6], 16)
        _lum = (0.299 * _r + 0.587 * _g + 0.114 * _b) / 255
        return "#1A237E" if _lum > 0.6 else "#ffffff"
    except Exception:
        return "#ffffff"


# ====================================================================
# PAGES DES RUBRIQUES
# ====================================================================
def _render_page_livret_thematique():
    """📿 Rosaire → Le Rosaire thématique : VITRINE du livret de méditation
    du mois du Rosaire (protection commerciale pendant la vente en paroisse).
    PUBLIER_LIVRET = True dans livret_thematique.py → contenu complet en ligne."""
    try:
        from views.livret_thematique import (
            PUBLIER_LIVRET, AFFICHE_LIVRET, AUTEURS_LIVRET, DEROULEMENT,
            ACTION_GRACE, CONFITEOR, PRIERE_ESPRIT_SAINT, PRIERE_VIERGE_MARIE,
            INTENTION_GENERALE, CREDO, CHANT_REGARDE_ETOILE, SALVE_REGINA,
            REGINA_COELI, ANGELUS, PRIERE_FINALE_LIVRET, LITANIE,
            SOUS_TITRES_GROUPES, MYSTERES_THEMATIQUES,
            OU_SE_PROCURER, CONTACT_LIVRET_WHATSAPP, PHOTOS_MYSTERES_THEMATIQUE)
    except ImportError:
        from views.livret_thematique import (
            PUBLIER_LIVRET, AFFICHE_LIVRET, AUTEURS_LIVRET, DEROULEMENT,
            ACTION_GRACE, CONFITEOR, PRIERE_ESPRIT_SAINT, PRIERE_VIERGE_MARIE,
            INTENTION_GENERALE, CREDO, CHANT_REGARDE_ETOILE, SALVE_REGINA,
            REGINA_COELI, ANGELUS, PRIERE_FINALE_LIVRET, LITANIE,
            SOUS_TITRES_GROUPES, MYSTERES_THEMATIQUES,
            OU_SE_PROCURER, CONTACT_LIVRET_WHATSAPP, PHOTOS_MYSTERES_THEMATIQUE)

    st.markdown('<div style="background:linear-gradient(135deg,#1A237E 0%,#283593 100%);'
                ' padding:20px; border-radius:15px; text-align:center; margin:10px;'
                ' border:2px solid #FFD700;">'
                '<div style="color:#FFD700 !important; font-size:1.15rem; font-weight:bold;">📿 Le Rosaire thématique</div>'
                '<div style="color:#e8eaf6 !important; font-size:0.9rem; margin-top:6px;">Livret de méditation du mois du Rosaire · « Il posait des questions. Force de la foi ! »</div></div>',
                unsafe_allow_html=True)

    # ---------- VITRINE (toujours visible) ----------
    if AFFICHE_LIVRET and str(AFFICHE_LIVRET).startswith("http"):
        st.markdown('<img src="' + AFFICHE_LIVRET + '" alt="Affiche du livret" '
                    'style="width:100%; max-width:480px; display:block; margin:10px auto; '
                    'border-radius:12px; border:2px solid #FFD700;">', unsafe_allow_html=True)
    st.markdown(_carte_priere(
        '<div class="cp-para">Un livret conçu pour le <b>mois du Rosaire</b> par '
        + html.escape(AUTEURS_LIVRET) + ' : prières, méditations et clausules '
        'déclinant le thème pastoral de l\'année dans chacun des vingt mystères.</div>'),
        unsafe_allow_html=True)
    with st.expander("📋 Déroulement de la prière (aperçu)"):
        st.markdown(_carte_priere(_trait_debut_page()
                    + '<div class="cp-para">' + html.escape(DEROULEMENT).replace("\n", "<br>") + "</div>"),
                    unsafe_allow_html=True)

    _wa_btn = ""
    if CONTACT_LIVRET_WHATSAPP:
        _lien_wa = lien_whatsapp(CONTACT_LIVRET_WHATSAPP,
                                 "Bonjour, je souhaite me procurer le livret de méditation du mois du Rosaire. 📿")
        if _lien_wa:
            _wa_btn = ('<div style="text-align:center; margin:10px 0;">'
                       '<a href="' + _lien_wa + '" target="_blank" '
                       'style="display:inline-block; background:#25D366; color:#ffffff;'
                       ' padding:10px 22px; border-radius:30px; font-weight:bold; text-decoration:none;">'
                       '📱 Commander / renseignements par WhatsApp</a></div>')
    st.markdown(_carte_priere(
        '<div class="cp-para">🛒 <b>Où se procurer le livret ?</b><br>'
        + html.escape(OU_SE_PROCURER) + "</div>"), unsafe_allow_html=True)
    st.markdown(_wa_btn, unsafe_allow_html=True)

    if not PUBLIER_LIVRET:
        st.info("📖 Le contenu intégral du livret (méditations et clausules des vingt "
                "mystères) n'est pas encore mis en ligne : il reste disponible en "
                "paroisse tout le mois du Rosaire.")
        return

    # ---------- CONTENU COMPLET (PUBLIER_LIVRET = True) ----------
    st.markdown(_carte_etape("✝️ DÉBUT DE LA CÉLÉBRATION"), unsafe_allow_html=True)
    _ouvertures = [
        ("🙏 Action de grâce (remerciements)", ACTION_GRACE),
        ("🙏 Confiteor (je confesse à Dieu tout puissant)", CONFITEOR),
        ("🙏 Prière à l'Esprit-Saint", PRIERE_ESPRIT_SAINT),
        ("🙏 Prière à la Vierge Marie", PRIERE_VIERGE_MARIE),
        ("✝️ Credo (Symbole de Nicée)", CREDO),
        ("🙏 Intention générale", INTENTION_GENERALE),
    ]
    for _lib, _txt in _ouvertures:
        if not _txt:
            continue
        with st.expander(_lib):
            st.markdown(_carte_priere(_trait_debut_page() + _rendre_texte_priere(_txt)), unsafe_allow_html=True)

    for nom_type, debut, fin, resume in GROUPES_CHAPELETS:
        couleur_forte = COULEURS_TYPES.get(nom_type.lower(), "#9E9E9E")
        couleur_claire = COULEURS_CLAIRES.get(nom_type.lower(), "#e8eaf6")
        _sous_titre = SOUS_TITRES_GROUPES.get(debut, "")
        st.markdown(
            '<div style="background:#121a45; border-radius:15px; margin:10px 10px 4px 10px; padding:14px 20px; border:1px solid #27306b; border-left:6px solid ' + couleur_forte + ';">'
            '<div style="color:' + couleur_claire + ' !important; font-weight:bold; font-size:1.05rem;">✝️ Mystères ' + nom_type + "</div>"
            '<div style="color:#c7cdf5 !important; font-size:0.85rem; margin-top:2px;">' + html.escape(_sous_titre) + "</div>"
            "</div>", unsafe_allow_html=True)
        for _mid in range(debut, fin + 1):
            _mt = MYSTERES_THEMATIQUES.get(_mid)
            if not _mt:
                continue
            _c_txt = _texte_sur(couleur_forte)
            _summary = (str(_mid).zfill(2) + " — " + html.escape(_mt.get("titre", "").title())
                        + " · " + html.escape(_mt.get("reference", "")))
            # Carte 1 — photo du mystère, citation, méditation, intention
            _photo_th = PHOTOS_MYSTERES_THEMATIQUE.get(_mid) or ""
            _photo_th_html = ('<img class="cp-photo" src="' + _photo_th + '" alt="">'
                              if _photo_th.startswith("http") else "")
            _corps_1 = (_trait_debut_page() + _photo_th_html
                        + '<div class="cp-para" style="font-style:italic;">« ' + html.escape(_mt.get("citation", "")) + ' »</div>'
                        + '<div class="cp-accent" style="--c:' + couleur_forte + ';">Méditation</div>'
                        + '<div class="cp-para">' + html.escape(_mt.get("meditation", "")) + "</div>"
                        + '<div class="cp-accent" style="--c:' + couleur_forte + ';">Intention de prière</div>'
                        + '<div class="cp-para">' + html.escape(_mt.get("intention", "")) + "</div>")
            # Carte 2 — NOTRE PÈRE complet (récitation visible, comme en Équipe)
            _corps_np = _rendre_texte_priere(_DIZ_NOTREPERE)
            # Carte 3 — les DIX « Je vous salue Marie » avec la clausule du livret
            _cla = _mt.get("clausules", [])
            _grains = ""
            for _g in range(1, 11):
                _clausule = _cla[_g - 1] if _g <= len(_cla) else ""
                _clausule = "" if _clausule is None else str(_clausule)
                _grains += ('<div class="cp-para" style="text-align:center; margin:12px 0;">'
                            '<span class="cp-accent-bg" style="--c:' + couleur_forte + '; color:' + _c_txt + ' !important; display:inline-block; width:22px; height:22px; border-radius:4px; font-size:0.72rem; line-height:22px;">' + str(_g) + "</span><br>"
                            "Je vous salue Marie, pleine de grâce,<br>le Seigneur est avec vous.<br>Vous êtes bénie entre toutes les femmes,<br>"
                            '<span class="cp-accent-inline" style="--c:' + couleur_forte + ';">et Jésus, ' + html.escape(_clausule) + "</span><br>"
                            "le fruit de vos entrailles, est béni.<br>"
                            "Sainte Marie, Mère de Dieu,<br>priez pour nous pauvres pécheurs,<br>maintenant et à l’heure de notre mort. Amen!</div>")
            # Carte 4 — GLORIA complet
            _corps_gl = _rendre_texte_priere(_DIZ_GLORIA)
            _details = ('<details class="details-mystere" style="--c:' + couleur_forte + ';">'
                        '<summary style="color:' + _c_txt + ' !important;">' + _summary + "</summary>"
                        '<div style="padding:6px 8px 8px 8px;">'
                        + _carte_priere(_corps_1, couleur_forte)
                        + _carte_priere(_corps_np, couleur_forte)
                        + _carte_priere(_grains, couleur_forte)
                        + _carte_priere(_corps_gl, couleur_forte)
                        + "</div></details>")
            st.markdown(_details, unsafe_allow_html=True)

    st.markdown(_carte_etape("🕯️ FIN DE LA CÉLÉBRATION"), unsafe_allow_html=True)
    _fins = [
        ("🕯️ Litanie de la Vierge Marie", LITANIE),
        ("🕯️ Salve Regina", SALVE_REGINA),
        ("🕯️ Regina Coeli (au temps pascal)", REGINA_COELI),
        ("🕯️ L'Angelus", ANGELUS),
        ("🙏 Prière finale", PRIERE_FINALE_LIVRET),
        ("🎶 Chant : Regarde l'étoile", CHANT_REGARDE_ETOILE),        
    ]
    for _lib, _txt in _fins:
        if not _txt:
            continue
        with st.expander(_lib):
            st.markdown(_carte_priere(_trait_debut_page() + _rendre_texte_priere(_txt)), unsafe_allow_html=True)

# Lecteurs du feuillet — CONSTANTE unique (jamais de libellé retapé dans
# les comparaisons). Les marqueurs R./T./1./2./3. du TEXTE restent la
# référence ligne par ligne pour le futur pupitre.
LBL_LECTEURS_FEUILLET = {"T": "Tous ensemble", "R": "Responsable",
                         "1": "1er lecteur", "2": "2e lecteur", "3": "Chantre",
                         "tous": "Tous ensemble"}


def _badges_lecteurs_feuillet(v):
    """« R,1,T » → 'Responsable · 1er lecteur · Tous ensemble'."""
    if not v:
        return ""
    _codes = [x.strip() for x in str(v).split(",") if x.strip()]
    _libelles = [LBL_LECTEURS_FEUILLET.get(x, x) for x in _codes]
    return " · ".join(html.escape(x) for x in _libelles)


# ====================================================================
# 📖 FEUILLET MENSUEL DE PRIÈRE — v7.8 (aménagement de la zone « Sous-thème »)
# Le feuillet remplace le sous-thème du mois : VITRINE (badge N°, « Mois de… »,
# Sommaire, bouton Ouvrir le livret) puis LIVRET EN AUTONOMIE comme la
# dizaine du jour : entête réduite au logo + carte de l'espace (membre /
# communautaire), sans bandes défilantes, sans le thème de l'année, titre de
# page toujours visible en haut, pagination seule en pied de page.
# ====================================================================
MOIS_PASTORAL_NOMS = ["septembre", "octobre", "novembre", "décembre", "janvier",
                      "février", "mars", "avril", "mai", "juin", "juillet", "août"]


def _feuillet_sections(annee_debut, mois_pastoral):
    """Sections du feuillet ayant un contenu, triées par ordre (blindé).
    v7.8.14 — 9 colonnes (lignes complétées à 9 cases dans tous les replis) :
      0 ordre · 1 titre · 2 contenu · 3 lecteur · 4 image_url · 5 pos_image ·
      6 image_titre (photo de la BANDE du titre) · 7 image_url2 · 8 pos_image2.
    Migration douce : le premier lecteur (public ou Communication) ajoute les
    3 colonnes v7.8.14 au schéma, une seule fois par session."""
    if "fe_mig_7814" not in st.session_state:
        st.session_state["fe_mig_7814"] = True
        for _alt in ("ALTER TABLE feuillet_sections ADD COLUMN image_titre TEXT",
                     "ALTER TABLE feuillet_sections ADD COLUMN image_url2 TEXT",
                     "ALTER TABLE feuillet_sections ADD COLUMN pos_image2 TEXT"):
            try:
                c.execute(_alt)
                commit_and_sync()
            except Exception:
                pass
    try:
        rows = c.execute("""SELECT ordre, titre, contenu, lecteur, image_url, pos_image,
                                   image_titre, image_url2, pos_image2
                            FROM feuillet_sections
                            WHERE annee_debut=? AND mois=? ORDER BY ordre""",
                         (annee_debut, mois_pastoral)).fetchall()
    except Exception:
        try:
            rows = [r + (None, None, None) for r in c.execute(
                """SELECT ordre, titre, contenu, lecteur, image_url, pos_image
                   FROM feuillet_sections
                   WHERE annee_debut=? AND mois=? ORDER BY ordre""",
                (annee_debut, mois_pastoral)).fetchall()]
        except Exception:
            try:
                rows = [r + (None, None, None, None) for r in c.execute(
                    """SELECT ordre, titre, contenu, lecteur, image_url
                       FROM feuillet_sections
                       WHERE annee_debut=? AND mois=? ORDER BY ordre""",
                    (annee_debut, mois_pastoral)).fetchall()]
            except Exception:
                return []
    return [s for s in rows if s[2]]


def _annee_civile_feuillet(annee_debut, mois_pastoral):
    """Mois pastoral → année civile (sept.→déc. = année de départ ; janv.→août = +1)."""
    return annee_debut if mois_pastoral <= 4 else annee_debut + 1


def _couverture_feuillet_html(annee_debut, mois_pastoral, compact=False,
                              lien=None, titre_haut=None):
    """🎨 Couverture du livret (v7.8.10) — carte visuelle du feuillet, du même
    style que la couverture de la dizaine (bleu nuit + or). La couverture
    accompagne : ① l'alerte « 📖 Nouveau feuillet » du fil d'actualité
    (compact=True, mention via titre_haut, bouton-lien via `lien`) ; ② le
    livret lui-même (au-dessus du sommaire). Si la cellule a saisi une image
    de couverture (🎨 expander du feuillet, table feuillets_couvertures),
    elle est montrée ; sinon la carte seule fait office de couverture.
    RETOURNE le HTML — l'appelant l'affiche via st.markdown."""
    _img = None
    try:
        _r = c.execute("""SELECT image_url FROM feuillets_couvertures
                          WHERE annee_debut=? AND mois=?""",
                       (annee_debut, mois_pastoral)).fetchone()
        _img = (_r[0] or "").strip() if _r else None
    except Exception:
        _img = None
    if _img and not str(_img).startswith("http"):
        _img = None
    _theme = None
    try:
        _t = c.execute("""SELECT texte_theme FROM themes_pastoraux
                          WHERE annee_debut=? ORDER BY actif DESC LIMIT 1""",
                       (annee_debut,)).fetchone()
        _theme = (_t[0] or "").strip() if _t else None
    except Exception:
        _theme = None
    _mois_civ = str(_annee_civile_feuillet(annee_debut, mois_pastoral))
    _pad_haut, _pad_bas, _taille_num, _wimg = (
        ("12px 14px 6px", "4px 14px 14px", "1.85rem", 36) if compact
        else ("20px 18px 8px", "6px 18px 24px", "2.4rem", 46))
    _img_html = ""
    if _img:
        # v7.8.14 — FIN DU ROGNAGE : l'image de couverture s'affiche TELLE
        # QUELLE (proportions d'origine), bornée à 420 px de haut.
        _img_html = (
            '<img src="' + html.escape(str(_img)) + '" alt="" '
            'style="width:auto; max-width:calc(100% - ' + str(_wimg) + 'px); '
            'height:auto; max-height:420px; object-fit:contain; border-radius:10px; '
            'border:1px solid rgba(255,215,0,.55); display:block; margin:12px auto 0; '
            'box-shadow:0 4px 14px rgba(0,0,0,.35);">')
    _haut_html = ""
    if titre_haut:
        _haut_html = ('<div style="color:#FFD000 !important; font-weight:bold; '
                      'font-size:0.95rem; padding:14px 16px 0;">'
                      + html.escape(str(titre_haut)) + '</div>')
    _theme_html = ""
    if _theme:
        _theme_html = ('<div style="color:#c5cae9; font-size:0.8rem; font-style:italic; '
                       'margin:10px 14px 0;">« ' + html.escape(_theme) + ' »</div>')
    _lien_html = ""
    if lien:
        _lien_html = '<div style="padding:' + _pad_bas + ';">' + str(lien) + '</div>'
    return (
        '<div style="background:linear-gradient(160deg,#0d1440 0%,#1A237E 55%,#283593 100%); '
        'border:2px solid #FFD700; border-radius:16px; overflow:hidden; text-align:center; '
        'margin:15px 10px 6px 10px; box-shadow:0 6px 18px rgba(0,0,0,.30);">'
        + _haut_html + _img_html
        + '<div style="padding:' + _pad_haut + ';">'
        '<div style="color:#FFD700; letter-spacing:2.5px; font-size:0.7rem; font-weight:bold;">'
        '📿 ÉQUIPES DU ROSAIRE</div>'
        '<div style="color:#ffffff; font-weight:bold; font-size:1.12rem; margin-top:8px;">'
        '📖 Le feuillet mensuel de prière</div>'
        '<div style="color:#FFD700; font-size:' + _taille_num + '; font-weight:bold; line-height:1.15;">'
        'N° ' + str(mois_pastoral) + '</div>'
        '<div style="color:#e8eaf6; font-size:0.95rem; text-transform:uppercase; '
        'letter-spacing:1.5px; margin-top:4px;">'
        + html.escape(MOIS_PASTORAL_NOMS[mois_pastoral - 1]) + " " + _mois_civ + '</div>'
        + _theme_html
        + '</div>' + _lien_html + '</div>')


def _nettoyer_params_livret():
    """Retire ?flt=1&fa=&fm= de l'URL : une fois ouvert, le livret vit dans la
    session (sinon « Fermer » rouvrirait immédiatement le livret)."""
    for _k in ("flt", "fa", "fm"):
        try:
            if _k in st.query_params:
                del st.query_params[_k]
        except Exception:
            pass


def _traiter_lien_profond_livret():
    """v7.8-h · v7.8.2-i — Lien profond ?flt=1&fa=ANNÉE&fm=MOIS : ouvre
    directement le livret en autonomie. Utilisé par les liens « 📖 Relire ce
    feuillet » des expanders d'archivage (Vue d'ensemble) — l'alerte du fil,
    elle, mène désormais à la vitrine de Vue d'ensemble. Sans fa/fm :
    feuillet courant du thème actif."""
    if st.query_params.get("flt") != "1":
        return
    _fa = _fm = None
    try:
        _fa = int(str(st.query_params.get("fa", "")))
    except (ValueError, TypeError):
        _fa = None
    try:
        _fm = int(str(st.query_params.get("fm", "")))
    except (ValueError, TypeError):
        _fm = None
    if not (_fa and _fm and 1 <= _fm <= 12):
        theme = get_theme_actif()
        if theme:
            _fa = theme[2]
            _fm = ((date.today().month - 9) % 12) + 1
        else:
            st.session_state["flt_ouvert"] = False
            _nettoyer_params_livret()
            return
    st.session_state["flt_cle"] = f"{_fa}-{_fm}"
    st.session_state["flt_page"] = 0
    st.session_state["flt_ouvert"] = True
    st.session_state.pop("diz_ouvert", None)
    _nettoyer_params_livret()
    st.rerun()


def _render_feuillet_vitrine(annee_debut, mois_pastoral):
    """📖 VITRINE du feuillet (v7.8 — remplace la zone « Sous-thème du mois ») :
    badge « LE FEUILLET MENSUEL DE PRIÈRE N° X », « Mois de … », Sommaire du
    feuillet, bouton « Ouvrir le livret ». Rien ne s'affiche (qu'une info) si
    aucune section n'est saisie."""
    sections = _feuillet_sections(annee_debut, mois_pastoral)
    if not sections:
        st.info("📖 Le feuillet mensuel de prière de ce mois n'a pas encore été publié.")
        return
    st.markdown(_carte_etape("📖 LE FEUILLET MENSUEL DE PRIÈRE N° " + str(mois_pastoral)),
                unsafe_allow_html=True)
    # v7.8.12 — l'état de PUBLICATION est affiché : la vitrine montre aussi un
    # feuillet simplement SAISI (aperçu, lien profond, sommaire) ; sans ce
    # bandeau, la cellule croyait le mois « publié » alors que l'alerte 🔔 du
    # fil annonce toujours le dernier mois PUBLIÉ par le diocèse (principe SAS :
    # la cellule soumet, le diocèse seul publie).
    try:
        _pub_vit = c.execute("""SELECT 1 FROM feuillets_publications
                                WHERE annee_debut=? AND mois=?""",
                             (annee_debut, mois_pastoral)).fetchone()
    except Exception:
        _pub_vit = None
    if not _pub_vit:
        _dern = None
        try:
            _dern = c.execute("""SELECT annee_debut, mois FROM feuillets_publications
                                 ORDER BY annee_debut DESC, mois DESC LIMIT 1""").fetchone()
        except Exception:
            _dern = None
        _txt_dern = ""
        if _dern:
            _txt_dern = (" — l'alerte 🔔 du fil annonce toujours : N° " + str(_dern[1])
                         + " · " + MOIS_PASTORAL_NOMS[_dern[1] - 1] + " "
                         + str(_annee_civile_feuillet(_dern[0], _dern[1])) + ".")
        st.warning("🟡 **Livret en préparation** — le diocèse n'a pas encore publié ce "
                   "feuillet (circuit « 📨 Soumettre le feuillet au diocèse » → validation)"
                   + _txt_dern + " Une fois validé, l'alerte passera automatiquement "
                   "à ce mois, avec sa couverture.")
    _pluriel = "page" if len(sections) == 1 else "pages"
    _lignes = "".join(
        '<div class="cp-para" style="margin:2px 0;">📖 <b>' + str(s[0]) + "</b> — "
        + html.escape(s[1] or "") + "</div>" for s in sections)
    st.markdown(_carte_priere(
        _trait_debut_page()
        + '<div class="cp-titre fe-titre-rubrique" style="text-align:center;">Mois de '
        + html.escape(MOIS_PASTORAL_NOMS[mois_pastoral - 1]) + " "
        + str(_annee_civile_feuillet(annee_debut, mois_pastoral)) + "</div>"
        + '<div class="cp-accent" style="--c:#1A237E;">Sommaire du feuillet</div>'
        + _lignes
        + '<div class="cp-para" style="text-align:center; font-size:0.85rem;">'
        + str(len(sections)) + " " + _pluriel
        + " · ouvrez le livret pour feuilleter</div>"),
        unsafe_allow_html=True)

    if st.button("📖 Ouvrir le livret", key="flt_open", width="stretch", type="primary"):
        st.session_state["flt_cle"] = f"{annee_debut}-{mois_pastoral}"
        # v7.8.10 — ouverture À LA COUVERTURE (couverture → sommaire → pages),
        # parcours naturel d'un livret papier.
        st.session_state["flt_page"] = -1
        st.session_state["flt_ouvert"] = True
        st.session_state.pop("diz_ouvert", None)
        st.rerun()


# ====================================================================
# v7.10.0 — LE QUESTIONNAIRE DU FEUILLET (côté fidèles)
# Sous le feuillet du mois (🕯️ Thème → Vue d'ensemble), ses questions et
# exercices deviennent un questionnaire : les MEMBRES répondent sous leur
# MatLoc (ils retrouvent leurs réponses et peuvent les corriger), les
# VISITEURS signent du nom qu'ils choisissent. Répondre à nouveau
# remplace SES réponses — jamais celles des autres.
# ====================================================================
def _qf_cle_visiteur(nom):
    """Clé douce du visiteur signant ses réponses (« N:jean-kouassi »)."""
    _n = unicodedata.normalize("NFKD", str(nom or "").strip().lower())
    _n = "".join(ch for ch in _n if not unicodedata.combining(ch))
    _n = re.sub(r"[^a-z0-9]+", "-", _n).strip("-")
    return ("N:" + _n[:60]) if _n else None


def _render_questionnaire_mensuel(annee_debut, mois_pastoral,
                                  est_membre=False, matloc=None,
                                  nom_membre=None, equipe_id=None,
                                  paroisse_id=None):
    questions = feuillet_questions_lister(annee_debut, mois_pastoral, True)
    if not questions:
        return
    _cle = None
    _deja = {}
    _nom_v = ""
    if est_membre and matloc:
        _cle = "M:" + str(matloc).upper().strip()
        _deja = feuillet_reponses_de_cle(annee_debut, mois_pastoral, _cle)
    else:
        _cle = st.session_state.get("qf_cle_visiteur")
        if _cle:
            _deja = feuillet_reponses_de_cle(annee_debut, mois_pastoral, _cle)
    _an_civ = annee_debut if mois_pastoral <= 4 else annee_debut + 1

    st.markdown(_carte_etape("📝 LE QUESTIONNAIRE DU FEUILLET — N° "
                             + str(mois_pastoral)), unsafe_allow_html=True)
    st.markdown(_carte_priere(
        '<div class="cp-para">Le feuillet de ce mois pose des questions et '
        'propose des exercices — réponds ci-dessous, à ton rythme. Tes '
        'réponses nourrissent la marche de tout le Mouvement.'
        + ("</div><div class=\"cp-para\"><b>Tu as déjà répondu</b> : tes "
           "réponses t'attendent en bas — tu peux les corriger et renvoyer."
           if _deja else "")
        + "</div>"), unsafe_allow_html=True)

    _erreurs = []
    with st.form("form_questionnaire_feuillet", clear_on_submit=False):
        if not est_membre:
            _nom_v = st.text_input(
                "Ton nom et prénoms (pour signer tes réponses)",
                value=st.session_state.get("qf_nom_visiteur", ""))
        _valeurs = {}
        for (_qid, _ord, _q_txt, _t, _ch, _ob, _ac) in questions:
            _lbl = (f"Q{_ord}. {_q_txt}"
                    + ("  *" if _ob else ""))
            _rep0 = _deja.get(_qid, "")
            if _t == "texte":
                _valeurs[_qid] = st.text_area(_lbl, value=_rep0, height=70,
                                              key=f"qf_w_{_qid}")
            elif _t == "oui_non":
                _opts = ["Oui", "Non"]
                _idx = _opts.index(_rep0) if _rep0 in _opts else None
                _valeurs[_qid] = st.radio(_lbl, _opts, index=_idx,
                                          horizontal=True, key=f"qf_w_{_qid}")
            else:  # choix
                _opts = [x.strip() for x in (_ch or "").split(",")
                         if x.strip()] or ["Oui", "Non"]
                _idx = _opts.index(_rep0) if _rep0 in _opts else None
                if len(_opts) <= 3:
                    _valeurs[_qid] = st.radio(_lbl, _opts, index=_idx,
                                              horizontal=True,
                                              key=f"qf_w_{_qid}")
                else:
                    _valeurs[_qid] = st.selectbox(_lbl, ["—"] + _opts,
                                                  index=None,
                                                  format_func=(
                                                      lambda x, _o=_opts:
                                                      x if x != "—" else
                                                      "Choisis…"),
                                                  key=f"qf_w_{_qid}")
                    if _rep0 in _opts:
                        _valeurs[_qid] = _rep0
        if st.form_submit_button("📨 Envoyer mes réponses", type="primary",
                                 width="stretch"):
            _manquantes = [f"Q{q[1]}" for q in questions
                           if q[5] and not str(_valeurs.get(q[0]) or "").strip()
                           and str(_valeurs.get(q[0]) or "—") not in ("Oui", "Non")]
            if not est_membre and not (_nom_v or "").strip():
                _erreurs.append("Écris d'abord ton nom et prénoms pour signer "
                                "tes réponses.")
            if _manquantes:
                _erreurs.append("Réponse attendue pour : "
                                + ", ".join(_manquantes) + ".")
            if _erreurs:
                for _e in _erreurs:
                    st.error(_e)
            else:
                _cle_envoi = _cle or _qf_cle_visiteur(_nom_v)
                _n = feuillet_reponses_enregistrer(
                    annee_debut, mois_pastoral, _valeurs, _cle_envoi,
                    qui_nom=(nom_membre if est_membre else _nom_v.strip()),
                    qui_type=("membre" if est_membre else "visiteur"),
                    equipe_id=equipe_id, paroisse_id=paroisse_id)
                if _n:
                    if not est_membre:
                        st.session_state["qf_cle_visiteur"] = _cle_envoi
                        st.session_state["qf_nom_visiteur"] = _nom_v.strip()
                    st.session_state["flash_success"] = (
                        "✅ Merci pour tes " + str(_n) + " réponse(s) ! Le "
                        "Seigneur qui posait des questions écoute les tiennes "
                        "— Que La Vierge Marie te garde. 🕊️")
                    st.rerun()
                else:
                    st.error("Tes réponses n'ont pas pu être notées — "
                             "réessaie.")


def _render_feuillet_livret(annee_debut, mois_pastoral, autonome=True, pfx="flt"):
    """📖 Lecteur du livret — v7.8 : une section = une page.
    autonome=True  : mode plein écran (barre de titre fixe, fermeture) ;
    autonome=False : lecture encastrée (réservé à un usage interne).
    v7.8-e : titre de la page toujours visible en haut (barre fixe, mode
    autonome) · v7.8.2-e : retour en HAUT de page à chaque tour (_scroll_top
    avec nonce) · v7.8-f : sans badge de lecteurs · v7.8-g : pagination seule
    en pied de page sous un trait fin."""
    sections = _feuillet_sections(annee_debut, mois_pastoral)
    if not sections:
        st.info("📖 Ce feuillet n'est pas disponible.")
        if autonome:
            if st.button("✕ Fermer", key=pfx + "_vide_fermer", width="stretch"):
                st.session_state["flt_ouvert"] = False
                _nettoyer_params_livret()
                st.rerun()
        return
    _cle = f"{annee_debut}-{mois_pastoral}"
    _k_page, _k_cle = pfx + "_page", pfx + "_cle"
    if st.session_state.get(_k_cle) != _cle:
        st.session_state[_k_cle] = _cle
        st.session_state[_k_page] = -1
    if _k_page not in st.session_state:
        st.session_state[_k_page] = -1
    idx = st.session_state[_k_page]
    if idx >= len(sections):
        idx = -1
        st.session_state[_k_page] = -1

    _entete_livret = ("📖 Feuillet mensuel de prière N° " + str(mois_pastoral)
                      + " · Mois de " + MOIS_PASTORAL_NOMS[mois_pastoral - 1] + " "
                      + str(_annee_civile_feuillet(annee_debut, mois_pastoral)))

    # ---------- v7.8.14 — ZOOM DU LIVRET : mini-boutons A− / A+ ----------
    # (90 → 150 %, mémorisés pour la session — très petits, en haut du livret)
    if autonome:
        try:
            _zoom = min(1.5, max(0.9, float(st.session_state.get("flt_zoom", 1.0))))
        except (TypeError, ValueError):
            _zoom = 1.0
        st.session_state["flt_zoom"] = round(_zoom, 2)
        _za, _zb, _zt = st.columns([0.065, 0.065, 0.87], gap="small",
                                   vertical_alignment="center")
        with _za:
            if st.button("A−", key=f"{pfx}_zoom_moins", width="stretch",
                         help="Réduire le texte du livret (jusqu'à 90 %)"):
                st.session_state["flt_zoom"] = round(max(0.9, _zoom - 0.1), 2)
                st.rerun()
        with _zb:
            if st.button("A+", key=f"{pfx}_zoom_plus", width="stretch",
                         help="Agrandir le texte du livret (jusqu'à 150 %)"):
                st.session_state["flt_zoom"] = round(min(1.5, _zoom + 0.1), 2)
                st.rerun()
        with _zt:
            st.caption("🔍 Taille du texte : " + str(int(round(_zoom * 100)))
                       + " % · A− / A+ en haut du livret")
        if abs(_zoom - 1.0) > 0.001:
            st.markdown('<style>.stApp .stMarkdown .carte-priere { zoom: '
                        + str(_zoom) + '; }</style>', unsafe_allow_html=True)

    # ---------- SOMMAIRE (page -1) ----------
    if idx < 0:
        # v7.8.10 — la COUVERTURE du livret ouvre la lecture, avant le
        # sommaire (même parcours qu'un livret papier : couverture → sommaire).
        st.markdown(_couverture_feuillet_html(annee_debut, mois_pastoral),
                    unsafe_allow_html=True)
        # v7.8.5-② — présentation UNIQUE : la liste statique doublonnée dans
        # la carte est retirée ; chaque entrée cliquable « 📖 N — Titre »
        # (sans « ▶ », confondu avec un expander) tient lieu de sommaire.
        st.markdown(_carte_priere(
            _trait_debut_page()
            + '<div class="cp-titre fe-titre-rubrique" style="text-align:center;">' + _entete_livret + "</div>"
            + '<div class="cp-accent" style="--c:#1A237E;">Sommaire du feuillet</div>'),
            unsafe_allow_html=True)
        for _i, _s in enumerate(sections):
            if st.button("📖 " + str(_s[0]) + " — " + (_s[1] or "Section " + str(_s[0])),
                         key=f"{pfx}_som_{_i}", width="stretch"):
                st.session_state[_k_page] = _i
                st.rerun()
        if autonome:
            if st.button("✕ Fermer le livret", key=pfx + "_som_fermer", width="stretch"):
                st.session_state["flt_ouvert"] = False
                _nettoyer_params_livret()
                st.rerun()
        return

    # ---------- UNE PAGE = UNE SECTION ----------
    # v7.8.14 — 9 colonnes : …4 image_url · 5 pos_image · 6 image_titre ·
    # 7 image_url2 · 8 pos_image2 (lignes anciennes complétées à None).
    _ligne = list(sections[idx]) + [None] * 9
    ordre, titre, contenu = _ligne[0], _ligne[1], _ligne[2]
    _img_url1 = str(_ligne[4]).strip() if _ligne[4] else ""
    _pos1_raw = _ligne[5] if len(_ligne) > 5 else None
    _img_titre = str(_ligne[6]).strip() if len(_ligne) > 6 and _ligne[6] else ""
    _img_url2 = str(_ligne[7]).strip() if len(_ligne) > 7 and _ligne[7] else ""
    _pos2_raw = _ligne[8] if len(_ligne) > 8 else None
    _titre_page = titre or ("Section " + str(ordre))

    if autonome:
        # v7.8-e — le titre de la page en lecture reste TOUJOURS visible en haut
        st.markdown('<div class="flt-barre"><div class="flt-barre-titre">📖 '
                    + html.escape(_titre_page) + "</div></div>", unsafe_allow_html=True)

    # ---------- v7.8.14 — BANDE DU TITRE (nouvelle spécification) ----------
    # La page ouvre sur une BANDE : le titre occupe les ¾ à gauche, la photo
    # le quart restant à l'EXTRÊME DROITE ; sans photo, emplacement pointillé 📷.
    _img_titre_ok = bool(_img_titre and _img_titre.startswith("http"))
    if _img_titre_ok:
        _cellule_photo = ('<div class="fe-bande-photo"><img src="'
                          + html.escape(_img_titre) + '" alt=""></div>')
    else:
        _cellule_photo = '<div class="fe-bande-photo"><div class="fe-bande-vide">📷</div></div>'
    _page_html = ('<div class="fe-bande-titre">'
                  '<div class="fe-bande-titre-txt">'
                  '<div class="cp-titre fe-titre-rubrique">'
                  + html.escape(_titre_page) + "</div></div>"
                  + _cellule_photo + "</div>")

    # ---------- v7.8.14 — PHOTOS DU CORPS (2 max, 4 coins, texte habillé) ----------
    # Chaque photo (~¼ de page) se place en haut gauche/droite ou bas
    # gauche/droite, le texte habille, proportions d'origine. Les anciennes
    # valeurs « haut / droite / gauche » sont converties (le centré disparaît).
    _POS_COINS_FE = ("haut_droite", "haut_gauche", "bas_droite", "bas_gauche")
    _POS_LEGACY_FE = {"haut": "haut_gauche", "droite": "haut_droite",
                      "gauche": "haut_gauche"}

    def _coin_fe(_v):
        _s = str(_v).strip() if _v else ""
        return _s if _s in _POS_COINS_FE else _POS_LEGACY_FE.get(_s, "haut_droite")

    _pp1, _u1 = _parser_pos_photo(_img_url1)   # ancien préfixe [droite]/[gauche]
    _pos1_fe = _pos1_raw or _pp1
    _photos_haut, _photos_bas = [], []
    for _u, _p in ((_u1, _pos1_fe), (_img_url2, _pos2_raw)):
        if _u and _u.startswith("http"):
            _pc = _coin_fe(_p)
            (_photos_haut if _pc.startswith("haut") else _photos_bas).append((_u, _pc))

    def _cadre_coin(_u, _pc):
        return ('<div class="fe-photo-cadre fe-photo-' + _pc + '">'
                + '<img src="' + html.escape(_u) + '" alt="" class="cp-photo"></div>')

    _corps_fe = _mise_en_page_feuillet(titre, contenu)
    if _photos_haut or _photos_bas:
        _page_html += ('<div class="fe-corps">'
                       + "".join(_cadre_coin(*_p) for _p in _photos_haut)
                       + _corps_fe
                       + "".join(_cadre_coin(*_p) for _p in _photos_bas)
                       + '<div style="clear:both;"></div></div>')
    else:
        _page_html += _corps_fe
    st.markdown(_carte_priere(_trait_debut_page() + _page_html), unsafe_allow_html=True)
    _scroll_top(f"{pfx}{idx}")

    # ---------- NAVIGATION (comme le livre de la dizaine) ----------
    c_prev, c_next = st.columns(2)
    with c_prev:
        if idx > 0:
            if st.button("◀ Précédent", key=f"{pfx}_prev_{idx}", width="stretch"):
                st.session_state[_k_page] = idx - 1
                st.rerun()
        else:
            if st.button("📑 Sommaire", key=f"{pfx}_home_{idx}", width="stretch"):
                st.session_state[_k_page] = -1
                st.rerun()
    with c_next:
        if idx < len(sections) - 1:
            if st.button("Suivant ▶", key=f"{pfx}_next_{idx}", width="stretch", type="primary"):
                st.session_state[_k_page] = idx + 1
                st.rerun()
        else:
            if st.button("✕ Fermer le livret", key=f"{pfx}_end_{idx}", width="stretch"):
                if autonome:
                    st.session_state["flt_ouvert"] = False
                    _nettoyer_params_livret()
                st.session_state[_k_page] = -1
                st.rerun()

    # ---------- PIED DE PAGE : pagination seule sous un trait fin (v7.8-g) ----------
    st.markdown('<div style="border:none; border-top:1px solid #4527a0; '
                'margin:16px auto 6px auto;"></div>'
                '<div class="flt-pagination">Page ' + str(idx + 1) + " / "
                + str(len(sections)) + "</div>", unsafe_allow_html=True)


def _render_feuillet_autonome():
    """📖 Livret ouvert EN AUTONOMIE (comme la dizaine du jour) : l'entête se
    réduit au logo + à la carte de l'espace (membre / communautaire), sans
    bandes défilantes, sans le thème de l'année."""
    _cle = st.session_state.get("flt_cle", "")
    try:
        _annee, _mois = (int(x) for x in str(_cle).split("-"))
    except (ValueError, AttributeError):
        st.session_state["flt_ouvert"] = False
        st.rerun()
        return
    _render_feuillet_livret(_annee, _mois, autonome=True, pfx="flt")


def _render_feuillets_archives_expanders(annee_theme, mois_courant):
    """📚 v7.8.2-i — ARCHIVAGE des feuillets précédents, directement dans
    🕯️ Thème → 🔭 Vue d'ensemble : un expander par feuillet déjà paru (hors
    celui affiché dans la vitrine du mois), chaque expander portant un lien
    « 📖 Relire ce feuillet » qui rouvre le livret EN AUTONOMIE via le lien
    profond ?flt=1&fa=ANNÉE&fm=MOIS (même lecteur que le livret du mois)."""
    try:
        pubs = c.execute("""SELECT annee_debut, mois, numero, date_publication
                            FROM feuillets_publications
                            ORDER BY annee_debut DESC, mois DESC""").fetchall()
    except Exception:
        return
    _prec = [p for p in pubs
             if not (p[0] == annee_theme and p[1] == mois_courant)]
    # v7.8.5-④ — l'emplacement est ANNONCÉ même sans feuillet précédent :
    # l'archivage reste visible « juste après le bouton Ouvrir ».
    st.markdown('<div class="cp-accent" style="--c:#1A237E; margin-top:22px;">'
                "📚 Les feuillets précédents</div>", unsafe_allow_html=True)
    if not _prec:
        st.caption("Les feuillets des mois passés s'archiveront ici, dès la "
                   "publication du prochain feuillet mensuel.")
        return
    # Base du lien profond : l'espace courant voyage (membre : matloc — QR : p=)
    base = "?espace=1"
    _mat = st.query_params.get("matloc")
    if isinstance(_mat, list):
        _mat = _mat[0] if _mat else None
    if _mat:
        base += "&matloc=" + str(_mat)
    _pp = st.query_params.get("p")
    if isinstance(_pp, list):
        _pp = _pp[0] if _pp else None
    if _pp:
        base += "&p=" + str(_pp)
    _r_theme = 1 if _mat else 2   # index de 🕯️ Thème (membre / public)
    for (a, m, num, dp) in _prec:
        _titre = ("📖 Feuillet N° " + str(num or m) + " — Mois de "
                  + MOIS_PASTORAL_NOMS[m - 1] + " " + str(_annee_civile_feuillet(a, m)))
        with st.expander(_titre):
            _meta = "Feuillet mensuel de prière archivé"
            _d = safe_date(dp) if dp else None
            if _d:
                _meta += " · publié le " + _d.strftime("%d/%m/%Y")
            st.caption(_meta)
            _href = (base + "&nav=1&r=" + str(_r_theme) + "&s=0"
                     + "&flt=1&fa=" + str(a) + "&fm=" + str(m))
            st.markdown('<a href="' + _href + '" target="_self" '
                        'style="display:inline-block; background:#4527a0; color:#ffffff; '
                        'padding:9px 22px; border-radius:30px; font-weight:bold; '
                        'font-size:0.9rem; text-decoration:none; margin-top:6px;">'
                        "📖 Relire ce feuillet</a>", unsafe_allow_html=True)


def _render_page_theme_ensemble(est_membre=False, matloc=None,
                                nom_membre=None, equipe_id=None,
                                paroisse_id=None):
    """🕯️ Thème → Vue d'ensemble — v7.7.7 : langage du dépliant (bannière
    bleu-or, badge d'étape, carte jaune verrouillée, trait fin).
    v7.10.0 — le questionnaire du feuillet répond sous la vitrine (membres
    ET visiteurs) ; la signature s'est élargie pour connaître qui répond."""
    theme = get_theme_actif()
    if not theme:
        st.info("🕯️ Aucun thème pastoral n'est actuellement actif. "
                "Il sera publié par le diocèse.")
        return
    texte_theme, mystere_principal, annee_debut = theme
    # Affiche du thème (optionnelle)
    try:
        _row_aff = c.execute("SELECT affiche_url FROM themes_pastoraux WHERE annee_debut=?",
                             (annee_debut,)).fetchone()
        affiche_theme = _row_aff[0] if _row_aff else None
    except Exception:
        affiche_theme = None
    ligne_mystere = ""
    try:
        mm = get_mystere(int(mystere_principal)) if mystere_principal else None
    except (ValueError, TypeError):
        mm = None
    if mm:
        ligne_mystere = ('<div style="color:#e8eaf6 !important; font-size:0.92rem; margin-top:10px;">'
                         "📿 Mystère principal : N°" + str(mm.get("id", "?")) + " — "
                         + html.escape((mm.get("titre") or "").title()) + " ("
                         + html.escape(mm.get("reference") or "") + ")</div>")
    st.markdown(
        '<div style="background:linear-gradient(135deg,#1A237E 0%,#283593 100%);'
        ' padding:24px; border-radius:15px; text-align:center; margin:10px;'
        ' border:2px solid #FFD700;">'
        '<div style="color:#FFD000 !important; font-size:0.85rem; letter-spacing:1px;">🕯️ THÈME PASTORAL '
        + str(annee_debut) + " - " + str(annee_debut + 1) + " · v7.7</div>"
        '<div style="font-family:Georgia, serif !important; color:#FFD700 !important; font-size:1.25rem; font-weight:bold; margin-top:8px; line-height:1.5;">« '
        + html.escape(texte_theme or "") + ' »</div>'
        + ligne_mystere + "</div>", unsafe_allow_html=True)
    if affiche_theme and str(affiche_theme).startswith("http"):
        st.markdown('<img src="' + str(affiche_theme) + '" alt="Affiche du thème" '
                    'style="width:100%; max-width:720px; display:block; margin:10px auto; '
                    'border-radius:12px; border:2px solid #FFD700;">', unsafe_allow_html=True)
    elif affiche_theme:
        try:
            st.image(affiche_theme, width="stretch")
        except Exception:
            pass

    # Mois PASTORAL (Sept=1 … Août=12) — v7.8 : la zone « 📅 LE SOUS-THÈME DU
    # MOIS » est supprimée ; sa place est occupée par le feuillet mensuel de
    # prière (badge N°, Mois de, Sommaire, Ouvrir le livret).
    _mois_pastoral = ((date.today().month - 9) % 12) + 1

    # ---------- 📖 LE FEUILLET MENSUEL DE PRIÈRE (v7.8) ----------
    _render_feuillet_vitrine(annee_debut, _mois_pastoral)

    # ---------- 📝 LE QUESTIONNAIRE DU FEUILLET (v7.10.0) ----------
    # juste sous la vitrine : les questions et exercices du mois, ouverts
    # aux membres comme aux visiteurs.
    _render_questionnaire_mensuel(annee_debut, _mois_pastoral,
                                  est_membre=est_membre, matloc=matloc,
                                  nom_membre=nom_membre, equipe_id=equipe_id,
                                  paroisse_id=paroisse_id)

    # ---------- 📚 FEUILLETS PRÉCÉDENTS (v7.8.2-i) : archivage en expanders ----------
    _render_feuillets_archives_expanders(annee_debut, _mois_pastoral)


def _render_page_en_preparation(emoji, titre, description):
    """Page « en préparation » élégante."""
    st.markdown(
        '<div style="background:linear-gradient(135deg,#1A237E 0%,#283593 100%);'
        ' padding:28px; border-radius:15px; text-align:center; margin:10px;'
        ' border:2px solid #FFD700;">'
        '<div style="font-size:2.2rem;">🚧</div>'
        '<div style="color:#FFD700 !important; font-size:1.15rem; font-weight:bold; margin-top:8px;">'
        + emoji + " " + html.escape(titre) + "</div>"
        '<div style="color:#e8eaf6 !important; font-size:0.95rem; margin-top:10px; line-height:1.7;">'
        + html.escape(description) + "</div></div>", unsafe_allow_html=True)


GROUPES_CHAPELETS = [
    ("Joyeux", 1, 5, "Annoncé, né, présenté, retrouvé — la vie cachée et la lumière de l’enfance"),
    ("Lumineux", 6, 10, "Le Baptême, Cana, l’annonce du Royaume, la Transfiguration, l’Eucharistie"),
    ("Douloureux", 11, 15, "L’agonie, la flagellation, le couronnement d’épines, le portement de croix, la mort sur la croix"),
    ("Glorieux", 16, 20, "La Résurrection, l’Ascension, la Pentecôte, l’Assomption, le Couronnement de Marie"),
]


# ================= ROSAIRE COMPLET EN ÉQUIPE — v7.7.3 =================
# Interrupteur : True = titres de sections visibles (style livre) ;
# False = chaque titre devient un simple trait fin bleu (flux continu).
AFFICHER_TITRES_SECTIONS = False

# 🖼️ PHOTOS DES MYSTÈRES — collez ici vos liens imgbb (Direct link) :
PHOTOS_MYSTERES = {
    1: "https://i.ibb.co/fdsv8yVd/mysteres-1.webp", 2: "https://i.ibb.co/dJL5GpXz/mysteres-2.webp", 3: "https://i.ibb.co/spXgWNQG/mysteres-3.webp", 4: "https://i.ibb.co/35HmgkLB/mysteres-4.webp", 5: "https://i.ibb.co/9kFZDf3X/mysteres-5.webp",
    6: "https://i.ibb.co/GBcT1JJ/mysteres-6.webp", 7: "https://i.ibb.co/0yqC0kMj/mysteres-7.webp", 8: "https://i.ibb.co/xKdZnJGg/mysteres-8.webp", 9: "https://i.ibb.co/JWcN0FfL/mysteres-9.webp", 10: "https://i.ibb.co/20bHZjfr/mysteres-10.webp",
    11: "https://i.ibb.co/s9MNpJSZ/mysteres-11.webp", 12: "https://i.ibb.co/pBfD7qpV/mysteres-12.webp", 13: "https://i.ibb.co/23FyJvNY/mysteres-13.webp", 14: "https://i.ibb.co/M5c9m7hj/mysteres-14.webp", 15: "https://i.ibb.co/LzxLrd5G/mysteres-15.webp",
    16: "https://i.ibb.co/HL89nG7K/mysteres-16.webp", 17: "https://i.ibb.co/CsnpR8JV/mysteres-17.webp", 18: "https://i.ibb.co/8ncVZgcy/mysteres-18.webp", 19: "https://i.ibb.co/5gnfKCrs/mysteres-19.webp", 20: "https://i.ibb.co/vvMdjknN/mysteres-20.webp",
}

_DIZ_NOTREPERE = ("Notre Père, qui es aux cieux,\nque ton nom soit sanctifié,\nque ton règne vienne,\n"
                  "que ta volonté soit faite\nsur la terre comme au ciel.\n\n"
                  "Donne-nous aujourd’hui notre pain de ce jour. Pardonne-nous nos offenses, "
                  "comme nous pardonnons aussi à ceux qui nous ont offensés. Et ne nous laisse pas "
                  "entrer en tentation, mais délivre-nous du Mal. Amen!")

_DIZ_GLORIA = ("Gloria patri, et Filio, et Spiritui Sancto.\nSicut erat in principio, et nunc, "
               "et semper, et in saecula saeculorum. Amen!\n\nÔ mon Jésus, pardonne-nous nos péchés; "
               "préserve-nous du feu de l’Enfer, attire au Ciel toutes les âmes, principalement "
               "celles qui ont le plus besoin de ta miséricorde. Amen!\n\n"
               "Notre Dame du très Saint Rosaire!\nPriez pour nous!")

_DIZ_INTRO2_ESPACE = (
    "NOTRE PÈRE\n\n"
    "Notre Père, qui es aux cieux,\nque ton nom soit sanctifié,\nque ton règne vienne,\n"
    "que ta volonté soit faite\nsur la terre comme au ciel.\n\n"
    "Donne-nous aujourd’hui notre pain de ce jour. Pardonne-nous nos offenses, comme nous "
    "pardonnons aussi à ceux qui nous ont offensés. Et ne nous laisse pas entrer en tentation, "
    "mais délivre-nous du Mal. Amen!\n\n"
    "3 JE VOUS SALUE MARIE\n\n\n"
    "Je vous salue Marie, pleine de grâce,\nle Seigneur est avec vous. Vous êtes bénie entre "
    "toutes les femmes, et Jésus, le fruit de vos entrailles, est béni.\n\n"
    "Sainte Marie, Mère de Dieu, priez pour nous pauvres pécheurs, maintenant et à l’heure de "
    "notre mort. Amen!\n\n\n"
    "Je vous salue Marie, pleine de grâce,\nle Seigneur est avec vous. Vous êtes bénie entre "
    "toutes les femmes, et Jésus, le fruit de vos entrailles, est béni.\n\n"
    "Sainte Marie, Mère de Dieu, priez pour nous pauvres pécheurs, maintenant et à l’heure de "
    "notre mort. Amen!\n\n\n"
    "Je vous salue Marie, pleine de grâce,\nle Seigneur est avec vous. Vous êtes bénie entre "
    "toutes les femmes, et Jésus, le fruit de vos entrailles, est béni.\n\n"
    "Sainte Marie, Mère de Dieu, priez pour nous pauvres pécheurs, maintenant et à l’heure de "
    "notre mort. Amen!\n\n"
    "GLORIA PATRI\n\n"
    "Gloria patri, et Filio, et Spiritui Sancto.\nSicut erat in principio, et nunc, et semper, "
    "et in saecula saeculorum. Amen!")


def _rendre_texte_priere(texte):
    """v7.7.4 — rendu d'un texte de prière. Ligne TOUT MAJUSCULES : trait fin
    (ou titre bleu si AFFICHER_TITRES_SECTIONS). Ligne « ===TRAIT=== » :
    trait de séparation inséré manuellement."""
    _sortie = ""
    _paragraphe = []
    for _ligne in str(texte).split("\n"):
        _l = _ligne.strip()
        if _l == "===TRAIT===":
            if _paragraphe:
                _sortie += '<div class="cp-para">' + "<br>".join(_paragraphe) + "</div>"
                _paragraphe = []
            _sortie += '<div class="cp-trait"></div>'
            continue
        _est_titre = (len(_l) >= 3 and _l == _l.upper() and any(ch.isalpha() for ch in _l))
        if _est_titre:
            if _paragraphe:
                _sortie += '<div class="cp-para">' + "<br>".join(_paragraphe) + "</div>"
                _paragraphe = []
            if AFFICHER_TITRES_SECTIONS:
                _sortie += '<div class="cp-titre">' + html.escape(_l) + "</div>"
            else:
                _sortie += '<div class="cp-trait"></div>'
        elif not _l:
            if _paragraphe:
                _sortie += '<div class="cp-para">' + "<br>".join(_paragraphe) + "</div>"
                _paragraphe = []
        else:
            _paragraphe.append(html.escape(_l))
    if _paragraphe:
        _sortie += '<div class="cp-para">' + "<br>".join(_paragraphe) + "</div>"
    return _sortie


# ================= MISE EN PAGE DU FEUILLET — v7.8.11 =================
# Marqueur de rubrique : R. / T. / 1. / 2. / 3. / 3+T. (suivis de . : — – -).
_RE_MARQ_FE = re.compile(r"^\s*(R|T|1|2|3)(\s*\+\s*T)?\s*[.:=—–-]\s*")
# Titre du passage biblique (section « À l'écoute de la Parole de Dieu ») :
# reste en style normal (italique) quand toute la section passe en gras.
_RE_PASSAGE_FE = re.compile(
    r"^(au livre|évangile\b|lecture (de|du|des|d')|première lecture|deuxième lecture"
    r"|livre (de|du|des)|lettre (de|du|des))", re.I)


def _sans_accents_fe(t):
    """Minuscules sans accents (comparaison robuste des titres)."""
    return unicodedata.normalize("NFD", str(t or "").lower()).encode("ascii", "ignore").decode("utf-8")


def _parser_pos_photo(url):
    """v7.8.11 — un lien d'image peut porter un préfixe « [droite] » ou
    « [gauche] » (position choisie à la soumission). Retourne le couple
    (position, url_propre) — position = None si pas de préfixe."""
    if not url:
        return None, url
    _u = str(url).strip()
    _low = _u.lower()
    if _low.startswith("[droite]"):
        return "droite", _u[8:].strip()
    if _low.startswith("[gauche]"):
        return "gauche", _u[8:].strip()
    return None, _u


def _mise_en_page_feuillet(titre, contenu):
    """v7.8.11 — mise en page typographique du texte d'une section du livret
    (demande n°4), d'après le livret papier :
      a. les marqueurs R. / T. / 1. / 2. / 3+T. sont EN GRAS (seul le marqueur) ;
      b. le texte des réponses « T. » et « 3+T. » est ENTIEREMENT en gras
         (y compris les vers qui suivent, jusqu'à la ligne vide) ;
      c. section « À l'écoute de la Parole de Dieu » : TOUT en gras sauf le
         titre du passage (Évangile… / Au Livre…, rendu en italique centré) ;
      d. section « Salve Regina » : TOUT en gras ;
      e. interligne plus généreux entre deux marqueurs (classe fe-p) ;
      h. « Célébrons en équipe » : la légende des rôles (R — Responsable… /
         1 — 1er lecteur · 2 — 2e lecteur · 3 — Chantre · T — Tous ensemble)
         est en gras, et la ligne « Accueil » devient une puce soulignée de
         taille sous-titre.
    Le comportement de _rendre_texte_priere est conservé pour le reste
    (===TRAIT=== → trait, lignes tout-majuscules → trait fin)."""
    _t = _sans_accents_fe(titre)
    _est_sec7 = "ecoute de la parole" in _t
    _est_salve = "salve regina" in _t
    _est_sec4 = "celebrons en equipe" in _t

    _blocs = []
    _para = []          # [(html_ligne, en_gras)] — paragraphe en cours
    _bloc_tous = False  # v7.8.11 — True tant que court un bloc « T. »/« 3+T. »

    def _flush():
        if not _para:
            return
        if all(g for _h, g in _para):
            _blocs.append('<div class="cp-para fe-p fe-gras">'
                          + "<br>".join(h for h, _g in _para) + "</div>")
        elif not any(g for _h, g in _para):
            _blocs.append('<div class="cp-para fe-p">'
                          + "<br>".join(h for h, _g in _para) + "</div>")
        else:
            _blocs.append('<div class="cp-para fe-p">'
                          + "<br>".join(("<b>" + h + "</b>") if g else h
                                        for h, g in _para) + "</div>")
        _para.clear()

    for _brut in str(contenu or "").split("\n"):
        _l = _brut.strip()
        if _l == "===TRAIT===":
            _flush()
            _bloc_tous = False
            _blocs.append('<div class="cp-trait"></div>')
            continue
        if not _l:
            _flush()
            _bloc_tous = False
            continue
        # (c) titre du passage — jamais en gras, en italique centré
        if _est_sec7 and len(_l) <= 95 and _RE_PASSAGE_FE.match(_l):
            _flush()
            _bloc_tous = False
            _blocs.append('<div class="cp-para fe-p fe-passage">'
                          + html.escape(_l) + "</div>")
            continue
        # Titre tout-majuscules → trait fin (comportement conservé)
        if len(_l) >= 3 and _l == _l.upper() and any(ch.isalpha() for ch in _l):
            _flush()
            _bloc_tous = False
            _blocs.append('<div class="cp-trait"></div>')
            continue
        # (h) puce « Accueil » — sous-titre souligné, Célébrons en équipe
        if _est_sec4 and _l.rstrip(":.").strip().lower() == "accueil":
            _flush()
            _bloc_tous = False
            _blocs.append('<div class="cp-para fe-p fe-accueil">•&nbsp;Accueil</div>')
            continue
        _m = _RE_MARQ_FE.match(_l)
        if _m:
            _token = _l[:_m.end()].strip()
            _reste = _l[_m.end():]
            _est_tous = (_m.group(1) == "T") or ("+" in (_m.group(2) or ""))
            _legende = (_est_sec4 and any(w in _l.lower() for w in
                        ("responsable", "lecteur", "chantre", "tous ensemble")))
            _flush()
            if _est_salve or _est_sec7 or _legende:
                # (c)(d)(h) tout en gras
                _para.append((html.escape(_l), True))
                _bloc_tous = False
                _flush()
            elif _est_tous:
                # (b) réponse « Tous » : marqueur + texte en gras, le bloc
                # continue tant que des vers suivent (ligne vide = fin)
                _para.append((html.escape(_l), True))
                _bloc_tous = True
            else:
                # (a) seul le marqueur est en gras
                _para.append(("<b>" + html.escape(_token) + "</b> "
                              + html.escape(_reste), False))
                _bloc_tous = False
            continue
        if _est_salve or _est_sec7:
            # (c)(d) tout en gras
            _para.append((html.escape(_l), True))
        else:
            _para.append((html.escape(_l), bool(_bloc_tous)))
    _flush()
    return "".join(_blocs)


def _carte_priere(corps_html, couleur=None):
    """v7.7.3 — carte jaune SANS en-tête ; liseré gauche coloré (option)."""
    _b = ' style="border-left:6px solid ' + couleur + ';"' if couleur else ""
    return '<div class="carte-priere"' + _b + ">" + corps_html + "</div>"


def _trait_debut_page():
    """Trait fin bleu en début de page (demande 2)."""
    return '<div class="cp-trait"></div>'


def _carte_etape(libelle):
    """Badge d'étape : bleu foncé, texte doré."""
    return ('<div style="background:#1A237E; border-radius:10px; padding:10px 18px; text-align:center; margin:12px 6px 8px 6px;">'
            '<div style="color:#FFD000 !important; font-weight:bold; font-size:1.05rem;">' + libelle + "</div></div>")


def _est_intention_chaine(ligne):
    """v7.9.0 — reconnaît la ligne « Intention du prochain dans la chaine de
    prière » placée en fin des intentions de chaque mystère (mysteres.py) :
    c'est elle qui devient DYNAMIQUE (chaîne de prière universelle)."""
    l = (ligne or "").strip().lstrip("*").strip().lower()
    return "intention du prochain" in l


def _ligne_chaine(jour_visiteur=None, matloc=None):
    """v7.9.1 — la ligne dynamique du livret, au MODÈLE demandé :
      « 🕯️ Vierge Marie, mère de Dieu, intercède pour {Prénom - Nom du
        visiteur} : {son intention} » ;
      « … intercède pour cet anonyme : {intention} » (intention anonyme) ;
      « … intercède : {intention universelle} » (3ᵉ choix de la chaîne).
    Le tirage dépend du N° méd. du lecteur (jour de naissance) et reste
    stable au sein d'une fenêtre de 20 jours (intention_du_prochain_detail) :
    les visiteurs du jour reçoivent les intentions de leurs prochains selon
    leurs N° méd. et méditent avec, sur 20 jours.
    v7.9.4 — le membre transmet son MatLoc : son intention lui est
    ATTACHÉE sur sa période désignée (membre), comme sur 20 jours pour
    le visiteur.
    v7.9.19 — LE SURPLUS : « Si un N° méd. contient plus d'une intention,
    le membre comme le visiteur qui médite ce N° méd. verra ses intentions
    augmentées selon le surplus. » Chaque intention en plus du N° méd. du
    lecteur s'ajoute à la ligne, l'une sous l'autre."""
    _txt, _qui = intention_du_prochain_detail(jour_visiteur=jour_visiteur,
                                              matloc=matloc)
    if _qui:
        _lignes = ["🕯️ Vierge Marie, mère de Dieu, intercède pour " + _qui
                   + " : " + _txt]
    else:
        _lignes = ["🕯️ Vierge Marie, mère de Dieu, intercède : " + _txt]
    try:
        _surplus = intentions_reserve_surplus(jour_visiteur=jour_visiteur,
                                              matloc=matloc, texte_exclu=_txt)
        for (_s_txt, _s_qui) in _surplus:
            _lignes.append("🕯️ Et elle intercède aussi"
                           + (" pour " + _s_qui if _s_qui else "")
                           + " : " + _s_txt)
    except Exception:
        pass
    return "\n".join(_lignes)


def _render_page_rosaire_eyquem():
    """📿 Rosaire → Le Rosaire complet en Équipe (v7.7.4).
    v7.9.0 — la dernière intention de chaque mystère (« Intention du prochain
    dans la chaine de prière ») devient DYNAMIQUE : elle porte l'intention du
    prochain tirée dans la chaîne de prière universelle (choix de la paroisse
    dans « 🙏 Coins des Intentions »). Le jour de naissance connu en session
    écarte les intentions du lecteur lui-même — personne ne prie la sienne."""
    st.markdown('<div style="background:linear-gradient(135deg,#1A237E 0%,#283593 100%);'
                ' padding:20px; border-radius:15px; text-align:center; margin:10px;'
                ' border:2px solid #FFD700;">'
                '<div style="color:#FFD700 !important; font-size:1.15rem; font-weight:bold;">📿 Le Rosaire chez les Équipiers</div>'
                '<div style="color:#e8eaf6 !important; font-size:0.9rem; margin-top:6px;">Vingt mystères médités en chaîne universelle · v7.7</div></div>',
                unsafe_allow_html=True)

    # ---------- A. DÉBUT ----------
    st.markdown(_carte_etape("✝️ DÉBUT DU ROSAIRE COMPLET"), unsafe_allow_html=True)
    with st.expander("🚩 Débutons notre méditation"):
        st.markdown(_carte_priere(_trait_debut_page() + _rendre_texte_priere(DIZ_INTRO1)), unsafe_allow_html=True)
    with st.expander("📿 Introduction de la prière"):
        st.markdown(_carte_priere(_rendre_texte_priere(_DIZ_INTRO2_ESPACE)), unsafe_allow_html=True)
    with st.expander("🙏 Prière à la Vierge du Père Eyquem"):
        st.markdown(_rendre_intro_eyquem("INTRODUCTION", afficher_titres=False, trait_debut=True), unsafe_allow_html=True)

    # ---------- B-E. LES 20 MYSTÈRES ----------
    # v7.9.0/7.9.1 — l'intention du prochain est tirée UNE fois pour tout le
    # livret (le lecteur ne prie jamais sa propre intention) ; la ligne
    # suit le modèle « intercède pour {qui} : {intention} ».
    _chaine = _ligne_chaine(st.session_state.get("diz_jrnais"))
    for nom_type, debut, fin, resume in GROUPES_CHAPELETS:
        couleur_forte = COULEURS_TYPES.get(nom_type.lower(), "#9E9E9E")
        couleur_claire = COULEURS_CLAIRES.get(nom_type.lower(), "#e8eaf6")
        st.markdown(
            '<div style="background:#121a45; border-radius:15px; margin:10px 10px 4px 10px; padding:14px 20px; border:1px solid #27306b; border-left:6px solid ' + couleur_forte + ';">'
            '<div style="color:' + couleur_claire + ' !important; font-weight:bold; font-size:1.05rem;">✝️ Mystères ' + nom_type + "</div>"
            '<div style="color:#c7cdf5 !important; font-size:0.85rem; margin-top:2px;">' + html.escape(resume) + "</div>"
            "</div>", unsafe_allow_html=True)
        for m in MYSTERES:
            if not (debut <= m.get("id", 0) <= fin):
                continue
            _mid = m.get("id", 0)
            _photo = PHOTOS_MYSTERES.get(_mid) or ""
            _photo_html = '<img class="cp-photo" src="' + _photo + '" alt="">' if _photo.startswith("http") else ""
            _corps_1 = (_trait_debut_page() + _photo_html
                        + '<div class="cp-accent" style="--c:' + couleur_forte + ';">Passage</div>'
                        + '<div class="cp-para">' + html.escape(m.get("passage") or "").replace("\n", "<br>") + "</div>"
                        + '<div class="cp-accent" style="--c:' + couleur_forte + ';">Méditation</div>'
                        + '<div class="cp-para">' + html.escape(m.get("meditation") or "").replace("\n", "<br>") + "</div>")
            _t_actif = get_theme_actif()
            if _t_actif:
                _lien_txt = get_lien_mystere(_t_actif[2], _mid)
                if _lien_txt:
                    _corps_1 += ('<div class="cp-accent" style="--c:' + couleur_forte + ';">🔗 Lien thématique — '
                                 + html.escape(_t_actif[0] or "") + "</div>"
                                 '<div class="cp-para">' + html.escape(_lien_txt).replace("\n", "<br>") + "</div>")
            _intentions = ('<div class="cp-accent" style="--c:' + couleur_forte + ';">Intentions</div>'
                           + "".join(
                               _diz_txt(_chaine if _est_intention_chaine(_l)
                                        else "🕯️ Vierge Marie, mère de Dieu, intercède : "
                                             + _l.strip().lstrip("*").strip(),
                                        "#1a1a1a", gras=_est_intention_chaine(_l))
                               for _l in (m.get("intentions") or "").split("\n") if _l.strip()))
            _fruits = ('<div class="cp-accent" style="--c:' + couleur_forte + ';">Fruits du mystère</div>'
                       + "".join(
                           _diz_txt("✨ " + _l.strip(), "#1a1a1a")
                           for _l in (m.get("fruits") or "").split("\n") if _l.strip()))
            _cla = m.get("clausules") or []
            _grains = ""
            for _g in range(1, 11):
                _clausule = _cla[_g - 1] if _g <= len(_cla) else ""
                _clausule = "" if _clausule is None else str(_clausule)
                _grains += ('<div class="cp-para" style="text-align:center; margin:12px 0;">'
                            '<span class="cp-accent-bg" style="--c:' + couleur_forte + '; display:inline-block; width:22px; height:22px; border-radius:4px; font-size:0.72rem; line-height:22px;">' + str(_g) + "</span><br>"
                            "Je vous salue Marie, pleine de grâce,<br>le Seigneur est avec vous.<br>Vous êtes bénie entre toutes les femmes,<br>"
                            '<span class="cp-accent-inline" style="--c:' + couleur_forte + ';">et Jésus, ' + html.escape(_clausule) + "</span><br>"
                            "le fruit de vos entrailles, est béni.<br>"
                            "Sainte Marie, Mère de Dieu,<br>priez pour nous pauvres pécheurs,<br>maintenant et à l’heure de notre mort. Amen!</div>")
            _details = ('<details class="details-mystere" style="--c:' + couleur_forte + ';">'
                        "<summary>" + str(_mid).zfill(2) + " — " + html.escape((m.get("titre") or "").title())
                        + " · " + html.escape(m.get("reference") or "") + "</summary>"
                        '<div style="padding:6px 8px 8px 8px;">'
                        + _carte_priere(_corps_1, couleur_forte)
                        + _carte_priere(_intentions + _fruits, couleur_forte)
                        + _carte_priere(_rendre_texte_priere(_DIZ_NOTREPERE), couleur_forte)
                        + _carte_priere(_grains, couleur_forte)
                        + _carte_priere(_rendre_texte_priere(_DIZ_GLORIA), couleur_forte)
                        + "</div></details>")
            st.markdown(_details, unsafe_allow_html=True)

    # ---------- F. FIN ----------
    st.markdown(_carte_etape("🕯️ FIN DU ROSAIRE"), unsafe_allow_html=True)
    with st.expander("Prière finale"):
        _txt_fin = DIZ_OUTRO.replace("Ô Marie, conçue sans péché!", "===TRAIT===\nÔ Marie, conçue sans péché!", 1)
        st.markdown(_carte_priere(_rendre_texte_priere(_txt_fin)), unsafe_allow_html=True)

    st.info("📿 La dizaine du jour vous attend sur l'Accueil (🏠 Actualités) — "
            "chaque membre fait avancer la chaîne selon son numéro.")


def _render_page_rosaire_theme():
    """📿 Rosaire → Le thème de l'année : les 20 mystères avec leur lien."""
    theme = get_theme_actif()
    if not theme:
        st.info("🕯️ Aucun thème pastoral n'est actuellement actif.")
        return
    texte_theme, mystere_principal, annee_debut = theme
    st.markdown('<div style="background:linear-gradient(135deg,#1A237E 0%,#283593 100%);'
                ' padding:20px; border-radius:15px; text-align:center; margin:10px;'
                ' border:2px solid #FFD700;">'
                '<div style="color:#9fa6d8 !important; font-size:0.85rem;">📿 LE ROSAIRE SELON LE THÈME DE L’ANNÉE · ' + _VERSION_APPLI + '</div>'
                '<div style="color:#FFD700 !important; font-size:1.1rem; font-weight:bold; margin-top:6px;">« '
                + html.escape(texte_theme or "") + " »</div></div>", unsafe_allow_html=True)
    manquants = 0
    for m in MYSTERES:
        lien = get_lien_mystere(annee_debut, m.get("id", 0))
        couleur = COULEURS_CLAIRES.get((m.get("type") or "").lower(), "#e8eaf6")
        if lien:
            corps_lien = ('<div style="background:#ffffff; border:2px solid #FFD700; border-radius:10px; padding:10px 14px; margin-top:8px;">'
                          '<div style="color:#1A237E !important; font-weight:bold; font-size:0.85rem;">🔗 Lien thématique</div>'
                          '<div style="color:#1a1a1a !important; font-size:0.9rem; line-height:1.7; margin-top:4px;">'
                          + html.escape(lien).replace("\n", "<br>") + "</div></div>")
        else:
            manquants += 1
            corps_lien = ('<div style="color:#c7cdf5 !important; font-size:0.85rem; font-style:italic; margin-top:8px;">'
                          "— lien thématique à préciser par le diocèse —</div>")
        st.markdown(
            '<div style="background:#121a45; border-radius:15px; margin:10px; padding:16px; border-left:6px solid ' + couleur + ';">'
            '<div style="color:' + couleur + ' !important; font-weight:bold; font-size:1rem;">' + str(m.get("id", 0)).zfill(2) + " — "
            + html.escape((m.get("titre") or "").title()) + "</div>"
            '<div style="color:#c7cdf5 !important; font-size:0.82rem;">📖 ' + html.escape(m.get("reference") or "") + "</div>"
            + corps_lien + "</div>", unsafe_allow_html=True)
    if manquants:
        st.caption(f"🔗 {manquants} lien(s) thématique(s) restent à saisir dans l'interface diocèse.")


def _pid_contexte(membre_paroisse_id=None):
    """Contexte paroissial du visiteur (LOT C5) :
    - membre connecté → paroisse de son équipe ;
    - visiteur via QR signé → paroisse du QR ;
    - sinon None (diocèse uniquement)."""
    if membre_paroisse_id:
        return membre_paroisse_id
    return st.session_state.get("paroisse_origine")


def _render_page_archives_textes(type_contenu, message_vide, pid=None):
    """Archives Prières / Méditations. Photo en WIDGET NATIF st.image.
    LOT C5 : ne montre que le diocèse (paroisse_cible NULL) + la paroisse du contexte."""
    cond, prm = ("AND (paroisse_cible IS NULL OR paroisse_cible = ?)", [pid]) if pid \
        else ("AND paroisse_cible IS NULL", [])
    lignes = c.execute(f"""SELECT titre, contenu_texte, image_url, fichier_url FROM espace_spirituel
                          WHERE type_contenu=? {cond} ORDER BY date_publication DESC, id DESC""",
                       [type_contenu] + prm).fetchall()
    if not lignes:
        st.info(message_vide)
        return
    for p in lignes:
        with st.expander(f"📖 {p[0]}"):
            texte, url_pdf = (p[1] or ""), p[3]
            if not url_pdf:
                texte, url_pdf = _extraire_pdf_legacy(texte)
            _pu, _purl = _parser_pos_photo(p[2])
            if _purl and _purl.startswith("http"):
                st.markdown(f'<img src="{_purl}" alt="" class="rub-photo">', unsafe_allow_html=True)
            if texte:
                st.markdown(texte, unsafe_allow_html=True)
            if url_pdf:
                _render_pdf_inline(url_pdf)


def _pistes_du_contexte(pid=None):
    """v7.8.9 — pistes MP3 + vidéos YouTube du contexte paroissial.
    FACTORISÉ : sert la page d'écoute 🎧 ET la mini-barre compagnon."""
    cond, prm = ("AND (paroisse_cible IS NULL OR paroisse_cible = ?)", [pid]) if pid \
        else ("AND paroisse_cible IS NULL", [])
    audios = c.execute(f"""SELECT titre, fichier_url FROM espace_spirituel
                          WHERE type_contenu='audio' {cond} ORDER BY date_publication DESC, id DESC""",
                       prm).fetchall()
    pistes, videos_yt = [], []
    for a in audios:
        u = str(a[1]) if a[1] is not None else ""
        if not u.startswith("http"):
            continue
        # Titre blindé : jamais None, jamais de HTML/JS injecté dans le lecteur
        titre_sur = str(a[0]) if a[0] is not None else "(sans titre)"
        if ("youtube.com/" in u) or ("youtu.be/" in u):
            videos_yt.append({"title": titre_sur, "url": u})
        else:
            pistes.append({"title": html.escape(titre_sur), "url": u})
    return pistes, videos_yt


def _render_page_archives_audios(pid=None):
    """Archives Musiques — LECTEUR COMPLET (playlist, ⏮️⏭️, 🔀, 🔁, sélection).
    Les MP3 en lien direct alimentent la playlist ; les liens YouTube
    s'affichent séparément. LOT C5 : filtre par contexte paroissial.
    v7.8.9 — LECTEUR COMPAGNON : ① bouton d'ouverture intelligent (popup
    nommé sur PC / même onglet sur téléphone) ; ② barre « ◀️ Revenir à
    l'appli » sur la page d'écoute ; ③ la position de lecture est mémorisée
    (sessionStorage) pour la mini-barre compagnon ; ④ Media Session + 📺."""
    pistes, videos_yt = _pistes_du_contexte(pid)
    if not pistes and not videos_yt:
        st.info("Aucun fichier audio.")
        return

    # v7.8.9 — bouton d'ouverture intelligent, masqué sur la page d'écoute
    # elle-même (sinon il réapparaissait dans l'onglet d'écoute, ce qui est
    # inutile). Téléphone (≤ 820 px) : MÊME onglet — la barre « ◀️ Revenir »
    # puis la mini-barre compagnon prennent le relais, la musique suit le
    # visiteur page après page. PC : fenêtre compagnon nommée
    # « rosaire_ecoute » (réutilisée à chaque clic, jamais dupliquée).
    if st.query_params.get("musique") != "1":
        _lien_ecoute = "?espace=1&musique=1" + (f"&p={pid}" if pid else "")
        # v7.8.9 — st.markdown SANITISE le HTML (onclick supprimé, rel=noopener
        # ajouté) : la bascule téléphone/PC se fait donc en CSS PUR (@media) —
        # deux boutons, un seul visible selon la largeur d'écran.
        # Téléphone (≤ 820 px) : lien MÊME onglet « 🎧 Écouter en priant » —
        # la barre « ◀️ Revenir » puis la mini-barre compagnon prennent le
        # relais, la musique suit le visiteur page après page.
        # PC : fenêtre/onglet compagnon nommé « rosaire_ecoute » (réutilisé à
        # chaque clic, jamais dupliqué — le nom sert aussi à la détecter).
        st.markdown(
            '<style>'
            '.btn-eco { display:inline-block; background:#4527a0; color:#ffffff;'
            ' padding:10px 22px; border-radius:30px; font-weight:bold; text-decoration:none;'
            ' margin:0 4px; }'
            '.btn-eco.mob { display:none; }'
            '@media (max-width: 820px) { .btn-eco.mob { display:inline-block; }'
            ' .btn-eco.pc { display:none; } }'
            '</style>'
            '<div style="text-align:center; margin:0 0 6px 0;">'
            '<a class="btn-eco pc" href="' + _lien_ecoute + '" target="rosaire_ecoute">'
            '🎧 Ouvrir l’onglet d’écoute dédié</a>'
            '<a class="btn-eco mob" href="' + _lien_ecoute + '">'
            '🎧 Écouter en priant</a></div>'
            '<div style="text-align:center; color:#9fa6d8 !important; font-size:0.8rem;'
            ' margin:0 0 14px 0;">📱 La musique vous suit ensuite de page en page —'
            ' tapez « ◀️ Revenir à l’appli » pour continuer à prier. 🎶</div>',
            unsafe_allow_html=True)
        _fixer_liens_ecoute()

    # v7.8.9 — barre « ◀️ Revenir à l'appli » (page d'écoute uniquement).
    # Même onglet (téléphone) : un tap ramène à l'Espace de Prière et la
    # mini-barre compagnon reprend la musique. Fenêtre compagnon (PC) :
    # le lecteur masque le bouton et affiche l'astuce « réduisez la fenêtre ».
    if st.query_params.get("musique") == "1" and pistes:
        _lien_retour = "?espace=1" + (f"&p={pid}" if pid else "")
        st.markdown(
            '<style>'
            '.block-container { padding-bottom: 130px !important; }'
            '#bar-revenir { position:fixed; bottom:0; left:0; right:0; z-index:999999;'
            ' background:linear-gradient(135deg,#1A237E 0%,#4527a0 100%);'
            ' border-top:2px solid #FFD700; text-align:center;'
            ' padding:12px 12px calc(12px + env(safe-area-inset-bottom));'
            ' box-shadow:0 -6px 22px rgba(0,0,0,0.45); }'
            '#bar-revenir a.btn-rv { display:inline-block; background:#FFD700; color:#1A237E;'
            ' font-weight:bold; text-decoration:none; padding:12px 38px; border-radius:30px;'
            ' font-size:1.05rem; }'
            '#bar-revenir .hint-rv { display:none; color:#e8eaf6 !important; font-size:0.85rem;'
            ' line-height:1.5; }'
            '</style>'
            '<div id="bar-revenir">'
            '<a class="btn-rv" id="btn-rv-meme" href="' + _lien_retour + '">'
            '◀️ Revenir à l’appli</a>'
            '<div class="hint-rv" id="hint-rv-popup">🖥️ Fenêtre compagnon : réduisez-la,'
            ' la musique continue pendant que vous priez dans la fenêtre principale. 🎶</div>'
            '</div>',
            unsafe_allow_html=True)
        _fixer_liens_ecoute()

    if pistes:
        player_html = """
        <div style="font-family: sans-serif; max-width: 600px; margin: auto; padding: 15px; border: 1px solid #27306b; border-radius: 15px; background: #121a45;">
            <h3 style="text-align:center; color:#ffe082; margin-top:0;">🎵 Lecteur Spirituel</h3>
            <div id="now-playing" style="text-align:center; font-weight:bold; font-size:1.1rem; margin-bottom:15px; min-height: 30px; color:#e8eaf6;">
                Cliquez sur une piste
            </div>
            <div style="display: flex; justify-content: center; gap: 10px; margin-bottom: 15px; flex-wrap: wrap;">
                <button id="btn-prev" style="background:none; border:none; font-size:20px; cursor:pointer; padding:5px;">⏮️</button>
                <button id="btn-shuffle" style="background:none; border:none; font-size:20px; cursor:pointer; opacity:0.5; padding:5px;">🔀</button>
                <button id="btn-loop" style="background:none; border:none; font-size:20px; cursor:pointer; opacity:0.5; padding:5px;">🔁</button>
                <button id="btn-next" style="background:none; border:none; font-size:20px; cursor:pointer; padding:5px;">⏭️</button>
                <button id="btn-pip" style="background:none; border:none; font-size:20px; cursor:pointer; padding:5px; display:none;" title="Vignette flottante">📺</button>
                <button id="btn-play-selection" style="background:#4527a0; color:white; border:none; font-size:14px; cursor:pointer; opacity:0.5; padding:5px 10px; border-radius:15px;">▶️ Sélection</button>
            </div>
            <video id="audio-player" controls controlsList="nodownload" style="width: 100%; outline:none; max-height: 150px; background:black; border-radius:8px;"></video>
            <ul id="playlist" style="list-style: none; padding: 0; margin-top: 15px; max-height: 350px; overflow-y: auto; border-top: 1px solid #27306b; padding-top: 10px;"></ul>
        </div>
        <script>
            const tracks = TRACKS_DATA;
            let currentTrackIndex = 0;
            let isShuffled = false;
            let loopMode = 0;
            let playbackOrder = tracks.map((_, i) => i);
            let selectedTracks = new Set();
            const audio = document.getElementById('audio-player');
            const nowPlaying = document.getElementById('now-playing');
            const playlistEl = document.getElementById('playlist');
            const btnShuffle = document.getElementById('btn-shuffle');
            const btnLoop = document.getElementById('btn-loop');
            const btnPlaySel = document.getElementById('btn-play-selection');
            function renderPlaylist() {
                playlistEl.innerHTML = '';
                playbackOrder.forEach((origIndex) => {
                    const li = document.createElement('li');
                    li.style.padding = '8px';
                    li.style.margin = '4px 0';
                    li.style.background = origIndex === currentTrackIndex ? '#4527a0' : '#1a2150';
                    li.style.borderRadius = '8px';
                    li.style.cursor = 'pointer';
                    li.style.borderLeft = origIndex === currentTrackIndex ? '5px solid #FFD700' : '5px solid transparent';
                    li.style.color = '#e8eaf6';
                    const checkbox = document.createElement('input');
                    checkbox.type = 'checkbox';
                    checkbox.checked = selectedTracks.has(origIndex);
                    checkbox.style.marginRight = '10px';
                    checkbox.style.transform = 'scale(1.3)';
                    checkbox.style.cursor = 'pointer';
                    checkbox.onclick = (e) => {
                        e.stopPropagation();
                        if (selectedTracks.has(origIndex)) selectedTracks.delete(origIndex);
                        else selectedTracks.add(origIndex);
                        updateSelectionButton();
                    };
                    li.prepend(checkbox);
                    const textSpan = document.createElement('span');
                    textSpan.innerHTML = '<span style="color:#FFD700">🎵</span> ' + tracks[origIndex].title;
                    li.appendChild(textSpan);
                    li.onclick = () => playTrack(origIndex);
                    playlistEl.appendChild(li);
                });
                updateSelectionButton();
            }
            function updateSelectionButton() {
                if (selectedTracks.size > 0) {
                    btnPlaySel.style.opacity = '1';
                    btnPlaySel.innerText = '▶️ Lecture (' + selectedTracks.size + ')';
                } else {
                    btnPlaySel.style.opacity = '0.5';
                    btnPlaySel.innerText = '▶️ Sélection';
                }
            }
            function playSelection() {
                if (selectedTracks.size === 0) return;
                playbackOrder = Array.from(selectedTracks);
                playTrack(playbackOrder[0]);
            }
            function playTrack(index) {
                currentTrackIndex = index;
                audio.src = tracks[index].url;
                nowPlaying.innerText = tracks[index].title;
                audio.play().catch(e => console.error("Erreur de lecture:", e));
                renderPlaylist();
            }
            function nextTrack() {
                let currentDisplayIndex = playbackOrder.indexOf(currentTrackIndex);
                if (currentDisplayIndex < playbackOrder.length - 1) {
                    playTrack(playbackOrder[currentDisplayIndex + 1]);
                } else if (loopMode === 1) {
                    playTrack(playbackOrder[0]);
                }
            }
            function prevTrack() {
                if (audio.currentTime > 3) {
                    audio.currentTime = 0;
                } else {
                    let currentDisplayIndex = playbackOrder.indexOf(currentTrackIndex);
                    if (currentDisplayIndex > 0) {
                        playTrack(playbackOrder[currentDisplayIndex - 1]);
                    } else if (loopMode === 1) {
                        playTrack(playbackOrder[playbackOrder.length - 1]);
                    }
                }
            }
            function toggleShuffle() {
                isShuffled = !isShuffled;
                btnShuffle.style.opacity = isShuffled ? '1' : '0.5';
                if (isShuffled) {
                    for (let i = playbackOrder.length - 1; i > 0; i--) {
                        const j = Math.floor(Math.random() * (i + 1));
                        [playbackOrder[i], playbackOrder[j]] = [playbackOrder[j], playbackOrder[i]];
                    }
                } else {
                    playbackOrder = tracks.map((_, i) => i);
                }
                renderPlaylist();
            }
            function toggleLoop() {
                loopMode = (loopMode + 1) % 3;
                if (loopMode === 0) {
                    audio.loop = false;
                    btnLoop.style.opacity = '0.5';
                    btnLoop.innerText = '🔁';
                }
                else if (loopMode === 1) {
                    audio.loop = false;
                    btnLoop.style.opacity = '1';
                    btnLoop.innerText = '🔁';
                }
                else {
                    audio.loop = true;
                    btnLoop.style.opacity = '1';
                    btnLoop.innerText = '🔂';
                }
            }
            audio.addEventListener('ended', () => {
                if (!audio.loop) {
                    nextTrack();
                }
            });
            document.getElementById('btn-prev').addEventListener('click', prevTrack);
            document.getElementById('btn-next').addEventListener('click', nextTrack);
            document.getElementById('btn-shuffle').addEventListener('click', toggleShuffle);
            document.getElementById('btn-loop').addEventListener('click', toggleLoop);
            document.getElementById('btn-play-selection').addEventListener('click', playSelection);

            // ================= v7.8.9 — LECTEUR COMPAGNON =================
            var CLE_ETAT = 'rosaire_lecteur_etat_v1';
            function sauverEtat(enLecture) {
                try {
                    var p = tracks[currentTrackIndex];
                    if (!p) return;
                    sessionStorage.setItem(CLE_ETAT, JSON.stringify({
                        u: p.url, titre: p.title, t: audio.currentTime || 0,
                        playing: !!enLecture, ts: Date.now()
                    }));
                } catch (e) {}
            }
            function majMetaMedia() {
                if (!('mediaSession' in navigator)) return;
                try {
                    var p = tracks[currentTrackIndex];
                    navigator.mediaSession.metadata = new MediaMetadata({
                        title: p ? p.title : 'Lecteur Spirituel',
                        artist: 'Équipes du Rosaire',
                        album: 'Chapelet en musique'
                    });
                } catch (e) {}
            }
            audio.addEventListener('play', function () {
                sauverEtat(true); majMetaMedia();
                if ('mediaSession' in navigator) {
                    try { navigator.mediaSession.playbackState = 'playing'; } catch (e) {}
                }
            });
            audio.addEventListener('pause', function () {
                sauverEtat(false);
                if ('mediaSession' in navigator) {
                    try { navigator.mediaSession.playbackState = 'paused'; } catch (e) {}
                }
            });
            audio.addEventListener('timeupdate', function () { if (!audio.paused) sauverEtat(true); });
            if ('mediaSession' in navigator) {
                try { navigator.mediaSession.setActionHandler('play', function () { audio.play(); }); } catch (e) {}
                try { navigator.mediaSession.setActionHandler('pause', function () { audio.pause(); }); } catch (e) {}
                try { navigator.mediaSession.setActionHandler('previoustrack', prevTrack); } catch (e) {}
                try { navigator.mediaSession.setActionHandler('nexttrack', nextTrack); } catch (e) {}
            }
            // — vignette flottante 📺 (Picture-in-Picture, si le navigateur le permet) —
            (function () {
                var pipOk = false;
                try { pipOk = document.pictureInPictureEnabled && !!audio.requestPictureInPicture; } catch (e) {}
                var pipIOS = !!(audio.webkitSupportsPresentationMode && typeof audio.webkitSetPresentationMode === 'function');
                if (!pipOk && !pipIOS) return;
                var b = document.getElementById('btn-pip');
                b.style.display = 'inline-block';
                try {
                    audio.poster = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(
                        '<svg xmlns="http://www.w3.org/2000/svg" width="320" height="180">'
                        + '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
                        + '<stop offset="0" stop-color="#1A237E"/><stop offset="1" stop-color="#4527a0"/>'
                        + '</linearGradient></defs><rect width="100%" height="100%" fill="url(#g)"/>'
                        + '<text x="160" y="84" font-size="52" text-anchor="middle">🎵</text>'
                        + '<text x="160" y="132" font-size="17" fill="#FFD700" text-anchor="middle" '
                        + 'font-family="sans-serif" font-weight="bold">Équipes du Rosaire</text></svg>');
                } catch (e) {}
                b.addEventListener('click', function () {
                    try {
                        if (document.pictureInPictureElement) { document.exitPictureInPicture(); return; }
                        if (pipOk) {
                            audio.requestPictureInPicture().catch(function () { b.style.opacity = '0.35'; });
                            return;
                        }
                        if (pipIOS) {
                            audio.webkitSetPresentationMode(
                                audio.webkitPresentationMode === 'picture-in-picture' ? 'inline' : 'picture-in-picture');
                        }
                    } catch (e) { b.style.opacity = '0.35'; }
                });
            })();
            // — reprise automatique là où la musique s'était arrêtée —
            (function () {
                var brut = null;
                try { brut = sessionStorage.getItem(CLE_ETAT); } catch (e) {}
                if (!brut) return;
                var etat = null;
                try { etat = JSON.parse(brut); } catch (e) {}
                if (!etat || !etat.u || Date.now() - (etat.ts || 0) > 7200000) return;
                var idx = -1;
                for (var i = 0; i < tracks.length; i++) { if (tracks[i].url === etat.u) { idx = i; break; } }
                if (idx < 0) return;
                currentTrackIndex = idx;
                audio.src = tracks[idx].url;
                nowPlaying.innerText = tracks[idx].title;
                renderPlaylist();
                var reprendreA = (etat.t && isFinite(etat.t)) ? etat.t : 0;
                if (reprendreA > 0) {
                    audio.addEventListener('loadedmetadata', function () {
                        try { audio.currentTime = reprendreA; } catch (e) {}
                    }, { once: true });
                }
                if (etat.playing) {
                    audio.play().catch(function () {
                        console.log('Reprise automatique bloquée par le navigateur : appuyez sur ▶️');
                    });
                }
            })();
            // — adaptation de la barre « Revenir » selon le mode d'ouverture —
            // Fenêtre compagnon (PC, ouverte par window.open) : masquer le bouton
            // « ◀️ Revenir » et afficher l'astuce ; même onglet (téléphone) : le
            // bouton reste visible (par défaut) et ramène à l'Espace de Prière.
            (function () {
                try {
                    var w = window.parent.window;
                    // rel=noopener (ajouté par Streamlit) coupe window.opener :
                    // on identifie la fenêtre/onglet compagnon par son NOM
                    // « rosaire_ecoute » (posé par target=), opener en secours.
                    var estFenetreCompagnon = (w.name === 'rosaire_ecoute') || !!w.opener;
                    var doc = window.parent.document;
                    var bm = doc.getElementById('btn-rv-meme');
                    var bh = doc.getElementById('hint-rv-popup');
                    if (bm && bh && estFenetreCompagnon) {
                        bm.style.display = 'none';
                        bh.style.display = 'inline-block';
                    }
                } catch (e) {}
            })();
            renderPlaylist();
        </script>
        """.replace("TRACKS_DATA", json.dumps(pistes).replace("</", "<\\/"))

        _comp_html(player_html, height=750)

    if videos_yt:
        # v7.7 — PLAYLIST CONTINUE : les vidéos s'enchaînent seules grâce au
        # paramètre natif « playlist » du lecteur YouTube intégré. Elle est
        # aussi présente dans l'onglet d'écoute 🎧 (musique ET vidéos en continu).
        st.markdown("### 🎬 Playlist continue")
        st.caption("Appuyez ▶️ une seule fois : les vidéos s'enchaînent toutes seules. "
                   "Le bouton ⏭️ du lecteur passe à la suivante.")
        _ids_yt = []
        for v in videos_yt:
            _m = re.search(r"(?:youtu\.be/|v=|shorts/|embed/)([A-Za-z0-9_-]{6,})", str(v["url"]))
            if _m:
                _ids_yt.append(_m.group(1))
        if len(_ids_yt) >= 2:
            _src_pl = ("https://www.youtube.com/embed/" + _ids_yt[0]
                       + "?playlist=" + ",".join(_ids_yt[1:]) + "&rel=0")
        elif len(_ids_yt) == 1:
            _src_pl = "https://www.youtube.com/embed/" + _ids_yt[0] + "?rel=0"
        else:
            _src_pl = None
        if _src_pl:
            st.markdown(
                '<div style="border-radius:12px; overflow:hidden; border:1px solid #27306b; margin:0 10px 15px 10px;">'
                '<iframe src="' + _src_pl + '" width="100%" height="360" style="border:none;" '
                'title="Playlist" allow="autoplay; encrypted-media; picture-in-picture" allowfullscreen></iframe></div>',
                unsafe_allow_html=True)
        st.markdown("### 🎬 Morceaux en vidéo")

        for v in videos_yt:
            with st.expander("🎵 " + (v["title"] or "(sans titre)")):
                try:
                    st.video(v["url"])
                except Exception:
                    st.markdown(f"🎬 [Écouter la vidéo]({v['url']})")

# ====================================================================
# v7.8.9 — MINI-BARRE COMPAGNON (musique en continu, page après page)
# ====================================================================
def _render_mini_lecteur(pid=None):
    """MINI-BARRE COMPAGNON — barre flottante en bas de l'écran, présente sur
    TOUTES les pages de l'Espace de Prière (sauf la page d'écoute 🎧 elle-même).
    Dès qu'une musique a été lancée (page d'écoute ou mini-barre), elle se
    REPREND automatiquement là où elle s'était arrêtée : on prie dans
    « 📿 Rosaire chez les Équipiers », le livret ou les archives pendant que
    le chapelet musical continue. Mémoire : sessionStorage (un onglet).
    ⚠️ L'iframe se repositionne LUI-MÊME en position fixe dans la page
    parente via window.frameElement (même origine — motif _mesure_entete).
    Ne rend RIEN (iframe escamotée) sans lecture récente."""
    # v7.8.16 — barre décorative : une micro-coupure vers la base (Turso,
    # « connection closed », http error…) escamote simplement la barre au lieu
    # de faire planter toute la page de l'Espace de Prière.
    try:
        pistes, _yt = _pistes_du_contexte(pid)
    except Exception:
        return
    if not pistes:
        return
    pistes_json = json.dumps(pistes).replace("</", "<\\/")
    mini_html = """
<style>
  html, body { margin:0; padding:0; overflow:hidden; background:transparent; }
  #mini { display:none; align-items:center; gap:8px; height:54px; padding:0 10px;
          box-sizing:border-box; font-family:sans-serif;
          background:linear-gradient(135deg,#1A237E 0%,#4527a0 100%); }
  #mini button { background:rgba(255,255,255,0.12); border:1px solid #FFD700; color:#FFD700;
                 font-size:16px; border-radius:50%; width:38px; height:38px; min-width:38px;
                 cursor:pointer; padding:0; line-height:1; }
  #m-titre { flex:1; color:#e8eaf6; font-size:0.85rem; font-weight:bold;
             white-space:nowrap; overflow:hidden; text-overflow:ellipsis; text-align:left; }
</style>
<div id="mini">
  <button id="m-play" title="Lecture / pause">▶️</button>
  <div id="m-titre"></div>
  <button id="m-next" title="Piste suivante">⏭️</button>
  <button id="m-pip" title="Vignette flottante" style="display:none;">📺</button>
</div>
<audio id="m-audio" playsinline preload="none"></audio>
<script>
(function () {
    var CLE = 'rosaire_lecteur_etat_v1';
    var pistes = PISTES_DATA;
    var audio = document.getElementById('m-audio');
    var box = document.getElementById('mini');
    var btnP = document.getElementById('m-play');
    var titreEl = document.getElementById('m-titre');
    var urlCourante = null, titreCourant = '', idxCourant = -1;

    function escamoter() {
        try {
            var f = window.frameElement;
            if (f) { f.style.display = 'none'; }
        } catch (e) {}
    }
    function flotter() {
        try {
            var f = window.frameElement;
            if (!f) return;
            f.style.display = 'block';
            f.style.position = 'fixed'; f.style.bottom = '12px'; f.style.left = '50%';
            f.style.transform = 'translateX(-50%)';
            f.style.width = 'min(360px, 94vw)'; f.style.height = '56px';
            f.style.minHeight = '56px'; f.style.maxHeight = '56px';
            f.style.zIndex = '999999'; f.style.border = '1px solid #FFD700';
            f.style.borderRadius = '30px'; f.style.boxShadow = '0 8px 26px rgba(0,0,0,0.5)';
            f.style.background = 'transparent';
            try {
                var p = f.parentElement;
                if (p) { p.style.height = '0px'; p.style.overflow = 'hidden';
                         p.style.margin = '0'; p.style.padding = '0';
                         p.style.background = 'transparent'; }
            } catch (e) {}
            var doc = f.ownerDocument;
            var bc = doc.querySelector('.block-container');
            if (bc) bc.style.setProperty('padding-bottom', '96px', 'important');
        } catch (e) {}
    }

    var etat = null;
    try { etat = JSON.parse(sessionStorage.getItem(CLE) || 'null'); } catch (e) {}
    if (!etat || !etat.u || Date.now() - (etat.ts || 0) > 7200000) { escamoter(); return; }

    for (var i = 0; i < pistes.length; i++) { if (pistes[i].url === etat.u) { idxCourant = i; break; } }
    urlCourante = etat.u;
    titreCourant = etat.titre || (idxCourant >= 0 ? pistes[idxCourant].title : 'Musique');
    titreEl.innerText = '🎵 ' + titreCourant;
    audio.src = urlCourante;
    box.style.display = 'flex';
    flotter();

    function sauver(enLecture) {
        try {
            sessionStorage.setItem(CLE, JSON.stringify({
                u: urlCourante, titre: titreCourant, t: audio.currentTime || 0,
                playing: !!enLecture, ts: Date.now()
            }));
        } catch (e) {}
    }
    function majMeta() {
        if (!('mediaSession' in navigator)) return;
        try {
            navigator.mediaSession.metadata = new MediaMetadata({
                title: titreCourant, artist: 'Équipes du Rosaire', album: 'Chapelet en musique'
            });
        } catch (e) {}
    }
    function lancer() {
        audio.play().then(function () { btnP.innerText = '⏸️'; sauver(true); majMeta(); })
                    .catch(function () {
                        btnP.innerText = '▶️';
                        titreEl.innerText = '▶️ Tapez pour reprendre — ' + titreCourant;
                    });
    }
    function changerPiste(p) {
        if (!p) return;
        urlCourante = p.url; titreCourant = p.title;
        idxCourant = pistes.indexOf(p);
        titreEl.innerText = '🎵 ' + titreCourant;
        audio.src = urlCourante;
        lancer();
    }
    btnP.addEventListener('click', function () {
        if (audio.paused) { if (audio.src) lancer(); }
        else { audio.pause(); btnP.innerText = '▶️'; sauver(false); }
    });
    var nxt = document.getElementById('m-next');
    if (pistes.length > 1) {
        nxt.addEventListener('click', function () {
            changerPiste(pistes[(idxCourant + 1) % pistes.length]);
        });
    } else { nxt.style.display = 'none'; }
    audio.addEventListener('play', function () { btnP.innerText = '⏸️'; sauver(true); majMeta(); });
    audio.addEventListener('pause', function () { btnP.innerText = '▶️'; sauver(false); });
    audio.addEventListener('timeupdate', function () { if (!audio.paused) sauver(true); });
    audio.addEventListener('ended', function () {
        if (pistes.length > 1) changerPiste(pistes[(idxCourant + 1) % pistes.length]);
    });
    if ('mediaSession' in navigator) {
        try { navigator.mediaSession.setActionHandler('play', function () { lancer(); }); } catch (e) {}
        try { navigator.mediaSession.setActionHandler('pause', function () { audio.pause(); }); } catch (e) {}
        try { navigator.mediaSession.setActionHandler('nexttrack', function () {
            if (pistes.length > 1) changerPiste(pistes[(idxCourant + 1) % pistes.length]);
        }); } catch (e) {}
    }
    var reprendreA = (etat.t && isFinite(etat.t)) ? etat.t : 0;
    if (reprendreA > 0) {
        audio.addEventListener('loadedmetadata', function () {
            try { if (Math.abs(audio.currentTime - reprendreA) > 1) audio.currentTime = reprendreA; } catch (e) {}
        }, { once: true });
    }
    if (etat.playing) lancer(); else btnP.innerText = '▶️';

    // — vignette flottante 📺 (si le navigateur le permet) —
    var pipOk = false;
    try { pipOk = document.pictureInPictureEnabled && !!audio.requestPictureInPicture; } catch (e) {}
    var pipIOS = !!(audio.webkitSupportsPresentationMode && typeof audio.webkitSetPresentationMode === 'function');
    if (pipOk || pipIOS) {
        var bp = document.getElementById('m-pip');
        bp.style.display = 'inline-block';
        try {
            audio.poster = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(
                '<svg xmlns="http://www.w3.org/2000/svg" width="320" height="180">'
                + '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
                + '<stop offset="0" stop-color="#1A237E"/><stop offset="1" stop-color="#4527a0"/>'
                + '</linearGradient></defs><rect width="100%" height="100%" fill="url(#g)"/>'
                + '<text x="160" y="84" font-size="52" text-anchor="middle">🎵</text>'
                + '<text x="160" y="132" font-size="17" fill="#FFD700" text-anchor="middle" '
                + 'font-family="sans-serif" font-weight="bold">Équipes du Rosaire</text></svg>');
        } catch (e) {}
        bp.addEventListener('click', function () {
            try {
                if (document.pictureInPictureElement) { document.exitPictureInPicture(); return; }
                if (pipOk) {
                    audio.requestPictureInPicture().catch(function () { bp.style.opacity = '0.35'; });
                    return;
                }
                if (pipIOS) audio.webkitSetPresentationMode(
                    audio.webkitPresentationMode === 'picture-in-picture' ? 'inline' : 'picture-in-picture');
            } catch (e) { bp.style.opacity = '0.35'; }
        });
    }
})();
</script>
""".replace("PISTES_DATA", pistes_json)
    try:
        _comp_html(mini_html, height=56)
    except Exception:
        pass


def _pointage_incognito(est_membre=False, matloc=None, nom_membre=None,
                        equipe_id=None, paroisse_id=None, jrnais=None):
    """v7.9.3 — LE POINTAGE INCOGNITO DU BOUTON « ✕ TERMINER » : chaque
    mystère du livre a sa fin (la page GLORIA PATRI) ; le bouton « ✕
    Terminer » qui y figure — « utile à notre cause incognito : en cliquant
    dessus, il est pointé » — note la dizaine SANS demander qui prie. Le
    membre est pointé par son MatLoc (1 fois/jour), le visiteur compte un
    passage anonyme (1 par session/jour). Une seule tentative, aucune
    erreur affichée : le livre se ferme dans tous les cas — le pointage
    explicite « ✅ J'ai égrené ma dizaine aujourd'hui » reste en fin de
    livre avec ses compteurs (flamme, mois)."""
    try:
        if est_membre:
            if matloc and not dizaine_deja_pointee(matloc):
                pointer_dizaine(matloc=matloc, nom=nom_membre,
                                equipe_id=equipe_id, paroisse_id=paroisse_id,
                                est_membre=True)
        elif jrnais:
            _cle_j = "diz_pointee_visiteur_" + date.today().isoformat()
            # v7.9.20 — le passage du visiteur est retrouvé en base : un
            # rechargement ne compte plus deux fois, et la présence du jour
            # redevient visible après le rechargement.
            if not st.session_state.get(_cle_j) and not dizaine_visiteur_pointee(jrnais):
                pointer_dizaine(jrnais=jrnais, paroisse_id=paroisse_id,
                                est_membre=False)
            st.session_state[_cle_j] = True
    except Exception:
        pass  # cause incognito : jamais de plantage pour un pointage


def _msg_dizaine_capitale(est_membre=False, matloc=None):
    """v7.9.4 — le remerciement qui suit la dizaine du jour : « Ta dizaine
    est capitale pour la chaîne — Merci pour ta fidélité! — X dizaine(s)
    ce mois — À demain! 🕊️ » (le compteur du mois est montré au membre ;
    le visiteur, lui, prie en toute simplicité)."""
    _txt = "📿 Ta dizaine est capitale pour la chaîne — Merci pour ta fidélité!"
    if est_membre and matloc:
        try:
            _mois, _fl = compteur_dizaines_mois(matloc)
            _txt += " — " + str(_mois) + " dizaine(s) ce mois"
        except Exception:
            pass
    return _txt + " — À demain! 🕊️"


# --- v7.10.0 — LA RÉCUPÉRATION DES DIZAINES PRIÉES HORS LIGNE --------------
# L'application de méditation du quotidien vit SANS internet : quand son
# fidèle la quitte, elle lui prépare un petit fichier de ses journées
# priées. Le livre « 🕯️ Un jour, une dizaine » le reçoit ici, à la même
# place que « ✕ Terminer » — et chaque journée retrouvée rejoint la
# chaîne, une seule fois, sans jamais recompter ce qui était déjà là.
_MOIS_FR_HL = {"janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5,
               "juin": 6, "juillet": 7, "aout": 8, "septembre": 9,
               "octobre": 10, "novembre": 11, "decembre": 12}


def _jour_valide_hl(_a, _m, _j):
    try:
        return date(int(_a), int(_m), int(_j)).isoformat()
    except (ValueError, TypeError):
        return None


def _jours_dans_texte_hl(_t):
    """Tire les journées (ISO) d'un texte : 2026-10-28 · 28/10/2026 ·
    28-10-2026 · « 28 octobre 2026 ». Rien qui ressemble à demain."""
    _t = unicodedata.normalize("NFKD", _t)
    _t = "".join(ch for ch in _t if not unicodedata.combining(ch))
    _trouvees = set()
    # ISO d'abord (2026-10-28, avec ou sans heure)
    for _m in re.finditer(r"\b(20[2-4]\d)-(\d{1,2})-(\d{1,2})\b", _t):
        _j = _jour_valide_hl(_m.group(1), _m.group(2), _m.group(3))
        if _j:
            _trouvees.add(_j)
    # JJ/MM/AAAA (ou JJ-MM-AAAA, JJ.MM.AAAA) — jour d'abord ; si le 2ᵉ
    # nombre dépasse 12, les deux étaient inversés
    for _m in re.finditer(r"\b(\d{1,2})[/.\-](\d{1,2})[/.\-](20[2-4]\d)\b", _t):
        _j1, _j2 = int(_m.group(1)), int(_m.group(2))
        if _j2 > 12 and _j1 <= 12:
            _j1, _j2 = _j2, _j1
        _j = _jour_valide_hl(_m.group(3), _j2, _j1)
        if _j:
            _trouvees.add(_j)
    # « 28 octobre 2026 » (et 1er mai 2026)
    for _m in re.finditer(r"\b(\d{1,2})(?:er)?\s+([a-zûé]+)\s+(20[2-4]\d)\b",
                          _t, re.IGNORECASE):
        _mois = _MOIS_FR_HL.get(_m.group(2).lower())
        _j = _jour_valide_hl(_m.group(3), _mois, _m.group(1)) if _mois else None
        if _j:
            _trouvees.add(_j)
    return _trouvees


def _lire_jours_dans_fichier(brut):
    """Le fichier de l'application hors ligne → liste de journées ISO,
    triées, sans doublon. JSON (liste de dates ou d'objets avec un champ
    date/jour) comme texte simple (une journée par ligne, séparateurs
    ; , ou tabulation). Tolérant : seules les vraies journées entrent."""
    if not brut:
        return []
    try:
        _t = brut.decode("utf-8", errors="ignore")
    except Exception:
        return []
    if not _t.strip():
        return []
    _extraits = []
    try:
        _j = json.loads(_t)
        if isinstance(_j, dict):
            _liste = None
            for _k, _v in _j.items():
                if isinstance(_v, list):
                    _kl = _k.lower()
                    if _liste is None or any(x in _kl for x in (
                            "date", "jour", "dizaine", "medit", "priere",
                            "histo", "liste", "data")):
                        _liste = _v
                        if any(x in _kl for x in ("date", "jour", "dizaine")):
                            break
            _j = _liste or []
        if isinstance(_j, list):
            for _el in _j:
                if isinstance(_el, str):
                    _extraits.append(_el)
                elif isinstance(_el, dict):
                    _v = None
                    for _k in ("date", "jour", "date_priere", "le", "when",
                               "day", "date_meditation", "timestamp"):
                        if _k in _el and _el.get(_k):
                            _v = str(_el[_k])
                            break
                    if _v:
                        _extraits.append(_v)
    except Exception:
        _extraits = _t.splitlines()
    _jours = set()
    for _el in _extraits:
        _jours |= _jours_dans_texte_hl(str(_el))
    _auj = date.today().isoformat()
    return sorted(j for j in _jours if j <= _auj)


def _recuperer_dizaines_hors_ligne(est_membre=False, matloc=None,
                                   nom_membre=None, equipe_id=None,
                                   paroisse_id=None, jrnais=None):
    """📥 La porte de la récupération — ouverte en fin de livre, à côté du
    pointage du jour, pour le membre comme pour le visiteur. La
    récupération ne recompte jamais une journée déjà dans la chaîne."""
    with st.expander("📿 Tu as prié hors ligne ? Remets tes journées dans la chaîne"):
        st.caption("Choisis le fichier que ton application de méditation t'a "
                   "préparé (bouton Partager / Exporter). Chaque journée "
                   "retrouvée rejoint ta chaîne — une seule fois, même si tu "
                   "repasses le même fichier.")
        _fichier = st.file_uploader("Fichier de ton application",
                                    type=None,
                                    key="pdr_hl_fichier")
        if _fichier is None:
            return
        _jours = _lire_jours_dans_fichier(_fichier.getvalue())
        if not _jours:
            st.warning("Aucune journée reconnaissable dans ce fichier — "
                       "vérifie qu'il vient bien de ton application de "
                       "méditation, ou demande le fichier d'un autre jour.")
            return
        _derniers = ", ".join(_jours[-10:])
        st.info("🕯️ **" + str(len(_jours)) + "** journée(s) priée(s) retrouvée(s)"
                + (" — les dernières : " + _derniers if len(_jours) <= 10
                   else " — les 10 dernières : " + _derniers))
        if st.button("✅ Les remettre dans ma chaîne", key="pdr_hl_ok",
                     type="primary", width="stretch"):
            _aj, _dj, _ig = importer_dizaines_hors_ligne(
                matloc=matloc, nom=nom_membre, jrnais=jrnais,
                equipe_id=equipe_id, paroisse_id=paroisse_id,
                est_membre=est_membre, jours=_jours)
            _msgs = []
            if _aj:
                _msgs.append("📿 " + str(_aj) + " journée(s) rejointe(s) ta "
                             "chaîne de prière — Merci Sainte Mère pour ta "
                             "fidélité ! 🕊️")
            if _dj:
                _msgs.append("🌿 " + str(_dj) + " journée(s) y figuraient "
                             "déjà — rien n'a été recompté.")
            if _ig:
                _msgs.append("🧹 " + str(_ig) + " ligne(s) laissée(s) de côté "
                             "(dates à venir ou non reconnues).")
            if _aj:
                st.success("  ".join(_msgs))
            else:
                st.info(" ".join(_msgs) or "Rien à ajouter pour le moment.")


def _rendre_pointage_dizaine(est_membre=False, matloc=None, nom_membre=None,
                             equipe_id=None, paroisse_id=None, jrnais=None):
    """v7.9.2 — LE POINTAGE DE LA CHAÎNE, affiché sur la DERNIÈRE page du
    livre (« 🕯️ Un jour, une dizaine »). Il répond à la question « sait-on
    si un membre / un visiteur fait sa dizaine ? » : oui, désormais — le
    membre est pointé par son MatLoc (1 fois/jour, visible par son
    responsable), le visiteur compte un « passage » (aucune identité
    exigée, 1 par session/jour).
    v7.9.3 — le bouton « ✕ Terminer » de CHAQUE mystère (page Gloria)
    pointe aussi, en toute discrétion (voir _pointage_incognito).
    v7.9.4 — TON COMPLICEL : « La chaîne compte sur Toi » — ta présence
    du jour et ta gratitude envers La Vierge Marie ; les mentions de
    mécanisme disparaissent (jamais l'impression d'une surveillance)."""
    st.markdown('<div style="margin:14px 6px 0 6px; background:linear-gradient(135deg,#E8EAF6 0%,#F3E5F5 100%);'
                ' border:1px solid #C5CAE9; border-radius:12px; padding:14px 16px;">'
                '<div style="color:#1A237E; font-weight:bold; font-size:1rem;">📿 La chaîne compte sur Toi</div>'
                '<div style="color:#3949AB; font-size:0.88rem; margin-top:4px;">'
                'Marque ta présence du jour et ta gratitude envers La Vierge Marie '
                'pour l\'écoute</div></div>',
                unsafe_allow_html=True)
    if est_membre:
        _deja = dizaine_deja_pointee(matloc)
        if _deja:
            st.success(_msg_dizaine_capitale(est_membre=True, matloc=matloc))
        else:
            if st.button("✅ Merci Sainte Mère pour ton aide de ce jour!",
                         key="diz_pointage_m", width="stretch", type="primary"):
                _st, _msg = pointer_dizaine(matloc=matloc, nom=nom_membre,
                                            equipe_id=equipe_id, paroisse_id=paroisse_id,
                                            est_membre=True)
                if _st == "ok":
                    st.session_state["flash_success"] = _msg_dizaine_capitale(
                        est_membre=True, matloc=matloc)
                    st.rerun()
                st.warning(_msg)
    else:
        _cle_j = "diz_pointee_visiteur_" + date.today().isoformat()
        # v7.9.20 — la présence du visiteur est retrouvée en base (par son
        # jour de naissance) : après un rechargement, le remerciement
        # revient au lieu de re-proposer le bouton (et de compter deux fois).
        _deja_v = bool(st.session_state.get(_cle_j))
        if not _deja_v and jrnais:
            _deja_v = bool(dizaine_visiteur_pointee(jrnais))
        if _deja_v:
            st.success(_msg_dizaine_capitale())
        else:
            if st.button("✅ Merci Sainte Mère pour ton aide de ce jour!",
                         key="diz_pointage_v", width="stretch", type="primary"):
                _st, _msg = pointer_dizaine(jrnais=jrnais, paroisse_id=paroisse_id,
                                            est_membre=False)
                if _st != "erreur":
                    st.session_state[_cle_j] = True
                    st.rerun()
                st.warning(_msg)

    # v7.10.0 — la récupération des journées priées hors ligne : ouverte
    # ICI, juste sous le pointage du jour, pour le membre comme pour le
    # visiteur — le fichier de l'application de méditation rejoint la
    # chaîne, sans jamais recompter une journée déjà présente.
    _recuperer_dizaines_hors_ligne(est_membre=est_membre, matloc=matloc,
                                   nom_membre=nom_membre, equipe_id=equipe_id,
                                   paroisse_id=paroisse_id, jrnais=jrnais)


def _render_dizaine_du_jour(numero_meditation=None, est_membre=False, matloc=None,
                            nom_membre=None, equipe_id=None, paroisse_id=None):
    """La dizaine du jour — UNIQUEMENT sur l'Accueil. Livre = page autonome."""
    # v7.9.6 — « J'ai honoré mon engagement de ce jour » REFERME LA CARTE
    # ENTIÈRE, comme « 📌 Marquer comme lue » referme la sienne : bannière
    # « 📿 Ta dizaine du jour », bouton « 📿 Égrener la dizaine » et le
    # bouton lui-même s'effacent jusqu'à demain. Le livre déjà ouvert
    # reste prioritaire (on ne ferme pas une lecture en cours).
    # v7.9.17 — le masquage SURVIT AU RECHARGEMENT : le clic pose aussi un
    # cookie d'un jour dans le navigateur (« engagement honoré aujourd'hui »)
    # — la session seule est vidée à chaque F5/actualisation. La pose se fait
    # ICI, à chaque passage tant que la session le porte (idempotent) ; le
    # cookie est lu avant tout affichage. Si le navigateur refuse les
    # cookies, le comportement redevient celui d'avant (carte revenue au
    # rechargement) : aucun blocage, aucun message.
    # v7.9.20 — la mémoire tient DÉSORMAIS EN BASE (clé du lecteur) : elle
    # survit au rechargement même quand le navigateur refuse les cookies
    # (consultation depuis une page extérieure) — même tenue, même promesse.
    _jour_eng = date.today().isoformat()
    _cle_lecteur = _cle_lecteur_pdr()
    _eng_session = bool(st.session_state.get("engagement_honore_" + _jour_eng))
    if _eng_session:
        _poser_cookie_pdr("pdr_engagement", _jour_eng)
        marquer_carte_vue(_cle_lecteur, "dizaine_engagement")
    if (not st.session_state.get("diz_ouvert")
            and (_eng_session or _lire_cookie_pdr("pdr_engagement") == _jour_eng
                 or carte_deja_vue(_cle_lecteur, "dizaine_engagement"))):
        return

    st.markdown("---")

    st.session_state.pop("nettoyage_diz", None)
    st.session_state.pop("diz_saisie", None)

    num = None
    if est_membre:
        try:
            num = int(numero_meditation) if numero_meditation else None
        except (ValueError, TypeError):
            num = None
        if not num or not (1 <= num <= 20):
            st.info("📿 Votre numéro de méditation (1-20) n’est pas encore renseigné. "
                    "Demandez-le à votre responsable d’équipe pour recevoir votre dizaine du jour.")
            return
    else:
        if st.session_state.get("diz_ouvert"):
            jrnais = st.session_state.get("diz_jrnais", 0)
            if not jrnais:
                st.session_state["diz_ouvert"] = False
                return
            num = jrnais - 20 if jrnais > 20 else jrnais
        else:
            st.markdown('<div style="background:linear-gradient(135deg,#1A237E 0%,#283593 100%);'
                        ' padding:16px; border-radius:15px; text-align:center; margin:0 10px 6px 10px;'
                        ' border:2px solid #FFD700;">'
                        '<div class="dpl-titre-g" style="font-size:clamp(1.05rem, 4.5vw, 1.2rem);">'
                        '🕯️ Un jour, une dizaine</div>'
                        '<div style="color:#ffffff; font-size:0.85rem; margin-top:4px;">'
                        'Entrez dans la zone en blanc ci-bas votre jour de naissance (1 - 31), Cliquez ✅, puis sur  "📿 Égrener la dizaine"  et rejoignez la chaîne de prière universelle</div></div>',
                        unsafe_allow_html=True)

            _, c_saisie, c_btn, _ = st.columns([0.07, 4.5, 1.2, 0.07],
                                               gap="small", vertical_alignment="bottom")
            with c_saisie:
                saisie = st.number_input("Jour de naissance",
                                         min_value=1, max_value=31, value=None, step=1,
                                         label_visibility="collapsed", key="diz_jour")
            with c_btn:
                if st.button("✅", key="diz_valider", width="stretch", type="primary",
                             help="Valider votre jour de naissance"):
                    if saisie is not None and 1 <= int(saisie) <= 31:
                        st.session_state["diz_jrnais"] = int(saisie)
                        st.session_state.pop("diz_erreur", None)
                    else:
                        st.session_state["diz_erreur"] = "Entrez d'abord votre jour de naissance (chiffre entre 1 et 31)."
            if st.session_state.get("diz_erreur"):
                st.warning(st.session_state.pop("diz_erreur"))

            if "diz_jrnais" not in st.session_state:
                return
            jrnais = st.session_state["diz_jrnais"]
            num = jrnais - 20 if jrnais > 20 else jrnais

    mysteres_jour = get_mysteres_du_jour(num)
    if not mysteres_jour:
        return

    # v7.9.0/7.9.1 — l'intention du prochain (chaîne de prière universelle) est
    # tirée UNE fois pour tout le livre ; pour le visiteur, son jour de
    # naissance écarte ses PROPRES intentions du tirage (personne ne prie
    # la sienne) et son N° méd. désigne l'intention de SON prochain, stable
    # sur la fenêtre de 20 jours. v7.10.1 — RÈGLE D'OR POUR LE MEMBRE AUSSI :
    # sa fiche (jour de naissance ET nom) écarte ses propres intentions du
    # tirage comme du surplus — une intention notée à son nom dans la
    # chaîne de séance ne lui revient plus. La ligne suit le modèle
    # « intercède pour {qui} : … ».
    _chaine = _ligne_chaine(
        st.session_state.get("diz_jrnais") if not est_membre else None,
        matloc=matloc if est_membre else None)

    if st.session_state.get("diz_num") != num:
        st.session_state["diz_num"] = num
        st.session_state["diz_ouvert"] = False
        st.session_state["diz_page"] = 0

    # ---------- COUVERTURE ----------
    if not st.session_state.get("diz_ouvert"):
        pastilles = "".join(
            f'<div style="width:52px; height:52px; border-radius:50%; background:#FFD700;'
            f' color:#1A237E; font-weight:bold; font-size:1.2rem; display:flex;'
            f' align-items:center; justify-content:center;">{m["id"]:02d}</div>'
            for m in mysteres_jour)
        titres = " • ".join((m.get("titre") or "").title() for m in mysteres_jour)
        _bann_chaine = (
            '<div style="display:inline-block; margin-top:12px; background:rgba(255,215,0,0.14);'
            ' border:1px solid #FFD700; border-radius:20px; padding:5px 16px; max-width:94%;'
            ' color:#FFD000; font-size:0.8rem; line-height:1.6;">🕯️ Au cœur de votre dizaine :'
            ' l\u2019intention du prochain, à porter pendant 20 jours (20 mystères)'
            ' — LA CHAÎNE DE PRIÈRE UNIVERSELLE</div>')
        st.markdown(
            f'<div style="background:linear-gradient(135deg,#1A237E 0%,#283593 100%);'
            f' padding:24px; border-radius:15px; text-align:center; margin:10px;'
            f' border:2px solid #FFD700;">'
            f'<div style="color:#FFD700; font-size:1.3rem; font-weight:bold;">📿 Ta dizaine du jour</div>'
            f'<div style="display:flex; justify-content:center; gap:10px; margin:18px 0;">{pastilles}</div>'
            f'<div style="color:#ffffff; font-size:1rem;">{html.escape(titres)}</div>'
            f'{_bann_chaine}'
            f'<div style="color:#9fa6d8; font-size:0.85rem; margin-top:8px;">'
            f'N° méd. {num} — {date.today().strftime("%d/%m/%Y")} · {_VERSION_APPLI}</div>'
            f'</div>', unsafe_allow_html=True)
        _scroll_top("cov")
        if st.button("📿 Égrener la dizaine", key="diz_commencer", width="stretch", type="primary"):
            st.session_state["diz_ouvert"] = True
            st.session_state["diz_page"] = 0
            st.session_state.pop("flt_ouvert", None)  # v7.8 : un seul livre ouvert à la fois
            st.rerun()
        # v7.9.4 — AU RETOUR DE LA MÉDITATION : « J'ai honoré mon engagement
        # de ce jour » s'affiche juste après « 📿 Égrener la dizaine ».
        # v7.9.6 — un clic REFERME LA CARTE ENTIÈRE (bannière + « 📿 Égrener
        # la dizaine » + le bouton) jusqu'à demain, exactement comme
        # « 📌 Marquer comme lue » — la garde en tête de fonction s'en charge
        # au rendu suivant (aucun commentaire affiché).
        # v7.9.20 — le bouton REVIENT AUSSI APRÈS UN RECHARGEMENT pour le
        # visiteur : sa présence du jour est retrouvée en base (par son jour
        # de naissance), au lieu de vivre dans la seule session — et un
        # passage ne compte plus deux fois.
        _cle_eng = "engagement_honore_" + date.today().isoformat()
        if not st.session_state.get(_cle_eng):
            _fait_auj = False
            if est_membre:
                _fait_auj = bool(dizaine_deja_pointee(matloc))
            else:
                _fait_auj = bool(st.session_state.get(
                    "diz_pointee_visiteur_" + date.today().isoformat()))
                if not _fait_auj and st.session_state.get("diz_jrnais"):
                    _fait_auj = bool(dizaine_visiteur_pointee(
                        st.session_state.get("diz_jrnais")))
            if _fait_auj:
                if st.button("J'ai honoré mon engagement de ce jour",
                             key="diz_engagement", width="stretch"):
                    st.session_state[_cle_eng] = True
                    marquer_carte_vue(_cle_lecteur, "dizaine_engagement")
                    st.rerun()
        return

    # ---------- LE LIVRE ----------
    pages = []
    for m in mysteres_jour:
        if m["id"] == 1:
            pages.append({"t": "intro1"})
            pages.append({"t": "intro2"})
            pages.append({"t": "intro3"})
        pages.append({"t": "contenu", "m": m})
        pages.append({"t": "intentions", "m": m})
        pages.append({"t": "notrepere", "m": m})
        for g in range(1, 11):
            pages.append({"t": "grain", "m": m, "g": g})
        pages.append({"t": "gloria", "m": m})
        if m["id"] == 20:
            pages.append({"t": "outro"})

    if "diz_page" not in st.session_state or st.session_state["diz_page"] >= len(pages):
        st.session_state["diz_page"] = 0
    idx = st.session_state["diz_page"]
    page = pages[idx]

    m = page.get("m")
    couleur = COULEURS_TYPES.get((m.get("type") or "").lower(), "#9E9E9E") if m else "#1A237E"

    if page["t"] in ("intro1", "intro2", "intro3"):
        texte = {"intro1": DIZ_INTRO1, "intro2": DIZ_INTRO2, "intro3": DIZ_INTRO3}[page["t"]]
        if "[R]" in texte:
            html_page = _rendre_intro_eyquem("INTRODUCTION")
        else:
            html_page = (
                f'<div style="background:#FFF9C4; border-radius:12px; padding:18px; margin:6px;">'
                f'<div style="color:#1A237E; font-weight:bold; font-size:1.05rem; border-bottom:2px solid #1A237E; padding-bottom:6px; margin-bottom:10px;">INTRODUCTION</div>'
                f'{_diz_txt(texte, "#1a1a1a")}</div>')

    elif page["t"] == "outro":
        html_page = (
            f'<div style="background:#FFF9C4; border-radius:12px; padding:18px; margin:6px;">'
            f'<div style="color:#1A237E; font-weight:bold; font-size:1.05rem; border-bottom:2px solid #1A237E; padding-bottom:6px; margin-bottom:10px;">FIN DU ROSAIRE</div>'
            f'{_diz_txt(DIZ_OUTRO, "#1a1a1a")}</div>')

    else:
        tete = (
            f'<div style="background:{couleur}; border-radius:12px 12px 0 0; padding:12px 16px; margin:6px 6px 0 6px;">'
            f'<div style="color:#ffffff; font-weight:bold; font-size:1.05rem;">{m.get("id", "?")} — {html.escape(m.get("titre") or "")}</div>'
            f'<div style="color:#ffffff; font-size:0.85rem;">📖 {html.escape(m.get("reference") or "")}</div></div>'
            f'<div style="background:#FFF9C4; border-radius:0 0 12px 12px; padding:18px; margin:0 6px 6px 6px;">')

        if page["t"] == "contenu":
            corps = (_diz_txt("PASSAGE", couleur, "1rem", gras=True)
                     + _diz_txt(m.get("passage") or "", "#1a1a1a")
                     + _diz_txt("MÉDITATION", couleur, "1rem", gras=True)
                     + _diz_txt(m.get("meditation") or "", "#1a1a1a"))
            t_actif = get_theme_actif()
            if t_actif:
                lien_txt = get_lien_mystere(t_actif[2], m.get("id", 0))
                if lien_txt:
                    corps += ('<div class="cp-accent" style="--c:' + couleur + ';">🔗 Lien thématique — '
                              + html.escape(t_actif[0] or "") + "</div>"
                              '<div class="cp-para">' + html.escape(lien_txt).replace("\n", "<br>") + "</div>")

        elif page["t"] == "intentions":
            intentions_html = ""
            for ligne in (m.get("intentions") or "").split("\n"):
                l = ligne.strip().lstrip("*").strip()
                if not l:
                    continue
                # v7.9.0/7.9.1 — la ligne « Intention du prochain dans la chaine de
                # prière » devient DYNAMIQUE au modèle demandé (intercède pour
                # {Prénom Nom} / cet anonyme), mise en gras pour se distinguer
                # des intentions fixes.
                if _est_intention_chaine(l):
                    intentions_html += _diz_txt(_chaine, "#1a1a1a", gras=True)
                else:
                    intentions_html += _diz_txt("🕯️ Vierge Marie, mère de Dieu, intercède : " + l, "#1a1a1a")
            fruits_html = "".join(
                _diz_txt("✨ " + ligne.strip(), "#1a1a1a")
                for ligne in (m.get("fruits") or "").split("\n") if ligne.strip())
            corps = (_diz_txt("INTENTIONS", couleur, "1rem", gras=True)
                     + intentions_html
                     + _diz_txt("FRUITS DU MYSTÈRE", couleur, "1rem", gras=True)
                     + fruits_html)

        elif page["t"] == "notrepere":
            corps = (_diz_txt("NOTRE PÈRE", couleur, "1rem", gras=True)
                     + _diz_txt("Notre Père, qui es aux cieux,\nque ton nom soit sanctifié,\nque ton règne vienne,\nque ta volonté soit faite\nsur la terre comme au ciel.\n\nDonne-nous aujourd’hui notre pain de ce jour. Pardonne-nous nos offenses, comme nous pardonnons aussi à ceux qui nous ont offensés. Et ne nous laisse pas entrer en tentation, mais délivre-nous du Mal. Amen!", "#1a1a1a"))

        elif page["t"] == "grain":
            g = page["g"]
            _cla = m.get("clausules") or []
            clausule = _cla[g - 1] if g <= len(_cla) else ""
            clausule = "" if clausule is None else str(clausule)
            carrés = "".join(
                f'<div style="width:22px; height:22px; border-radius:4px; display:flex; align-items:center;'
                f' justify-content:center; font-size:0.7rem; font-weight:bold;'
                f' background:{"#1A237E" if i <= g else "#cccccc"}; color:{"#ffffff" if i == g else "#888888"};">{i}</div>'
                for i in range(1, 11))
            corps = (
                f'<div style="display:flex; gap:5px; margin:6px 0;">{carrés}</div>'
                + _diz_txt("Je vous salue Marie, pleine de grâce,\nle Seigneur est avec vous.\nVous êtes bénie entre toutes les femmes,", "#1a1a1a")
                + _diz_txt("et Jésus, " + clausule, couleur, "1.1rem", gras=True)
                + _diz_txt("le fruit de vos entrailles, est béni.", "#1a1a1a")
                + _diz_txt("Sainte Marie, Mère de Dieu,\npriez pour nous pauvres pécheurs,\nmaintenant et à l’heure de notre mort.\nAmen!", "#1a1a1a"))

        else:  # gloria
            corps = (_diz_txt("GLORIA PATRI", couleur, "1rem", gras=True)
                     + _diz_txt("Gloria patri, et Filio, et Spiritui Sancto.\nSicut erat in principio, et nunc, et semper, et in saecula saeculorum. Amen!\n\nÔ mon Jésus, pardonne-nous nos péchés; préserve-nous du feu de l’Enfer, attire au Ciel toutes les âmes, principalement celles qui ont le plus besoin de ta miséricorde. Amen!\n\nNotre Dame du très Saint Rosaire!\nPriez pour nous!", "#1a1a1a"))

        html_page = tete + corps + '</div>'

    st.markdown(html_page, unsafe_allow_html=True)
    _scroll_top(f"p{idx}")

    # --- v7.9.2 : POINTAGE DE LA DIZAINE (dernière page du livre) ---
    # v7.9.3 — le livre du jour contient UN mystère : sa fin est la page
    # GLORIA (l'outro « Salve Regina » ne s'ajoute que le jour du mystère
    # N° 20). Le pointage explicite s'affiche donc sur la VRAIE dernière
    # page — outro ou gloria finale — chaque jour, pas seulement les jours
    # « N° 20 » ; le bouton « ✕ Terminer » pointe en plus, incognito.
    if page["t"] == "outro" or (page["t"] == "gloria" and idx == len(pages) - 1):
        _rendre_pointage_dizaine(est_membre=est_membre, matloc=matloc,
                                 nom_membre=nom_membre, equipe_id=equipe_id,
                                 paroisse_id=paroisse_id,
                                 jrnais=st.session_state.get("diz_jrnais"))

    # --- Navigation : ON NE RECULE PAS quand on égrène une dizaine ☺️ ---
    # v7.9.3 — CHAQUE MYSTÈRE A SA FIN (la page GLORIA PATRI, « dernière
    # page » du mystère) : un bouton « ✕ Terminer » y figure désormais À
    # CÔTÉ de « Suivant ▶ ». Le cliquer note la dizaine en toute discrétion
    # (cause incognito — « en cliquant dessus, il est pointé ») et referme
    # le livre : celui qui s'arrête après un seul mystère est compté aussi.
    c_av, c_term = st.columns(2)
    with c_av:
        if idx < len(pages) - 1:
            if st.button("Suivant ▶", key=f"diz_next_{idx}", width="stretch", type="primary"):
                st.session_state["diz_page"] = idx + 1
                st.rerun()
        else:
            # Dernière page (outro) : « ✕ Terminer » pointe aussi, sans bruit.
            if st.button("✕ Terminer", key=f"diz_end_{idx}", width="stretch"):
                _pointage_incognito(est_membre=est_membre, matloc=matloc,
                                    nom_membre=nom_membre, equipe_id=equipe_id,
                                    paroisse_id=paroisse_id,
                                    jrnais=st.session_state.get("diz_jrnais"))
                # v7.9.6 — la sortie incognito reste discrète : une ligne
                # courte, sans compteur — le remerciement complet (avec le
                # compteur du mois) appartient au seul bouton « ✅ Merci
                # Sainte Mère… » de la dernière page.
                st.session_state["flash_success"] = "📿 À demain! 🕊️"
                st.session_state["diz_ouvert"] = False
                st.session_state["diz_page"] = 0
                st.rerun()
    with c_term:
        if page["t"] == "gloria" and idx < len(pages) - 1:
            if st.button("✕ Terminer", key=f"diz_fin_{idx}", width="stretch"):
                _pointage_incognito(est_membre=est_membre, matloc=matloc,
                                    nom_membre=nom_membre, equipe_id=equipe_id,
                                    paroisse_id=paroisse_id,
                                    jrnais=st.session_state.get("diz_jrnais"))
                # v7.9.6 — discrétion identique à la sortie de fin de livre.
                st.session_state["flash_success"] = "📿 À demain! 🕊️"
                st.session_state["diz_ouvert"] = False
                st.session_state["diz_page"] = 0
                st.rerun()


def _render_pdf_inline(url_pdf):
    """PDF — v7.6.6 : l'iframe embarque directement le VISUALISEUR GOOGLE.
    Pourquoi : GitHub Raw (comme certains CDN) envoie des en-têtes qui
    INTERDISENT l'affichage dans une iframe ; le lecteur Google les contourne,
    fiable sur tous les navigateurs. Sous le cadre : ouverture directe."""
    try:
        _src = ("https://docs.google.com/viewer?url="
                + urllib.parse.quote(url_pdf, safe="") + "&embedded=true")
    except Exception:
        _src = url_pdf
    st.markdown(
        f'<div style="margin:12px 10px 18px 10px; border-radius:12px; overflow:hidden; border:1px solid #27306b;">'
        f'<iframe src="{_src}" width="100%" height="700" style="border:none;" title="Document"></iframe>'
        f'<div style="text-align:center; padding:8px; background:#121a45;">'
        f'<a href="{url_pdf}" target="_blank" style="color:#b39ddb; font-size:0.85rem;">📄 Ouvrir le document ici</a>'
        f'</div></div>', unsafe_allow_html=True)


def _render_coin_affiche(pid=None):
    """v7.8.6 — le Coin Affiche respecte le périmètre paroissial :
    un évènement créé par une ÉQUIPE n'y apparaît que dans le contexte de
    SA paroisse (QR paroissial ou membre de la paroisse). Sans contexte
    paroissial, seuls les évènements diocèse/paroisse sont visibles."""
    _filtre_eq, _prm_eq = ("(equipe_id IS NULL OR equipe_id IN "
                           "(SELECT id FROM equipes WHERE paroisse_id=?))", [pid]) if pid \
        else ("equipe_id IS NULL", [])
    lignes = []
    erreur_sql = None
    try:
        lignes = c.execute(f"""SELECT type_evenement, date_evenement, lieu, affiche_url, video_url FROM evenements
                              WHERE (affiche_url IS NOT NULL OR video_url IS NOT NULL) AND date_evenement >= ?
                              AND {_filtre_eq}
                              ORDER BY date_evenement ASC LIMIT 5""",
                          [date.today().isoformat()] + _prm_eq).fetchall()
    except Exception as e:
        erreur_sql = str(e)
        lignes = []

    if st.query_params.get("debug") == "1":
        with st.expander("🔎 DEBUG Coin Affiche"):
            st.write("Aujourd'hui :", date.today().isoformat())
            if erreur_sql:
                st.error(f"REQUÊTE PRINCIPALE EN ÉCHEC : {erreur_sql}")
            try:
                st.write("Évènements avec visuel (tous) :",
                         c.execute("SELECT id, type_evenement, date_evenement, affiche_url, video_url FROM evenements WHERE affiche_url IS NOT NULL OR video_url IS NOT NULL").fetchall())
            except Exception as e:
                st.write("ERREUR SQL :", e)

    visuel = None
    for a in lignes:
        if len(a) >= 5 and safe_date(a[1]):
            visuel = a
            break

    if visuel:
        d_v = safe_date(visuel[1])
        date_txt = d_v.strftime("%d/%m/%Y") if d_v else "Date à définir"
        img_part = (f'<img src="{visuel[3]}" alt="Affiche" style="width:100%; height:auto; display:block; border-bottom:3px solid #7b1fa2;">'
                    if visuel[3] else "")
        st.markdown(
            f'<div style="background:#121a45; border-radius:15px; overflow:hidden; border:1px solid #27306b; margin:0 10px 15px 10px; box-shadow:0 2px 8px rgba(0,0,0,0.4);">'
            f'{img_part}'
            f'<div style="padding:15px; text-align:center;">'
            f'<h4 style="margin:0 0 5px 0; color:#e8eaf6; font-size:1.1rem;">📣 {html.escape(visuel[0] or "")}</h4>'
            f'<p style="margin:0; color:#9fa6d8; font-size:0.9rem;">{date_txt} - {html.escape(visuel[2] or "Lieu à définir")}</p>'
            f'</div></div>', unsafe_allow_html=True)
        if visuel[4]:
            try:
                st.video(visuel[4])
            except Exception:
                st.markdown(f"🎬 [Voir la vidéo]({visuel[4]})")
    else:
        try:
            prochain = c.execute(f"""SELECT type_evenement, date_evenement, lieu FROM evenements
                                    WHERE date_evenement >= ? AND {_filtre_eq}
                                    ORDER BY date_evenement ASC LIMIT 1""",
                                 [date.today().isoformat()] + _prm_eq).fetchone()
        except Exception:
            prochain = None
        if prochain and len(prochain) >= 3:
            d = safe_date(prochain[1])
            date_txt = d.strftime("%d/%m/%Y") if d else "Date à définir"
            icone = {"Prière mensuelle": "🧎", "Prière commune": "🙏", "Prière spéciale": "✨",
                     "Pèlerinage": "🚶‍♂️", "Réunion": "🤝"}.get(prochain[0], "📅")
            st.markdown(
                f'<div style="background:linear-gradient(135deg,#1a2150 0%,#121a45 100%); border-radius:15px; margin:0 10px 15px 10px; border:1px solid #27306b;">'
                f'<div style="padding:15px; text-align:center;">'
                f'<h4 style="margin:0 0 5px 0; color:#e8eaf6; font-size:1.1rem;">{icone} {html.escape(prochain[0] or "")}</h4>'
                f'<p style="margin:0; color:#9fa6d8; font-size:0.9rem;">{date_txt} - {html.escape(prochain[2] or "Lieu à définir")}</p>'
                f'</div></div>', unsafe_allow_html=True)

# 📿 Rentrée pastorale : le dépliant s'affiche DÉPLIÉ. Repassez à False
# (et redémarrez l'application) quand la période de présentation sera finie.
DEPLIANT_OUVERT = True
def _depliant_mouvement(paroisse_id=None):
    """📿 Dépliant « vivant » du Mouvement — Espace COMMUNAUTAIRE uniquement.
    Toutes les images se configurent dans le bloc PHOTOS ci-dessous."""
    # ============ 📷 IMAGES DU DÉPLIANT — collez vos URLs ici ============
    PHOTO_BANDEAU    = "https://i.ibb.co/wZxs04Pn/Ekip0.jpg"   # grande photo sous le bandeau https://i.ibb.co/LdM54KB3/Ekip1.jpg(facultatif)
    PHOTO_QUI        = "https://i.ibb.co/PZPF16qV/Ekip2.jpg"   # section 📜 Qui sommes-nous ?
    PHOTO_COMMENT    = "https://i.ibb.co/tw62DQC8/Ekip4.jpg"   # section ⛪ Comment ça marche ?
    PHOTO_PRIERES    = "https://i.ibb.co/1fdZKksR/Ekip5.jpg"   # section 🙏 Deux temps de prière
    PHOTO_MISSION    = "https://i.ibb.co/0R1JQKTD/Ekip3.jpg"   # section ❤️ Notre mission
    PHOTO_RESSOURCES = "https://i.ibb.co/y2SvKp5/Ekip6.jpg"   # section 📖 Ressources
    # =====================================================================

    _resp, _wa, _etiquette = None, None, "responsable diocésain"
    if paroisse_id:
        _etiquette = "responsable paroissial"
        try:
            _r = c.execute("SELECT responsable, whatsapp_responsable FROM paroisses WHERE id=?", (paroisse_id,)).fetchone()
            if _r and _r[0]:
                _resp = _r[0]
            if _r and len(_r) > 1 and _r[1]:
                _wa = _r[1]
        except Exception:
            pass
    else:
        try:
            _d = c.execute("SELECT responsable, whatsapp_responsable FROM diocese WHERE id=?", (1,)).fetchone()
            if _d and _d[0]:
                _resp = _d[0]
            if _d and len(_d) > 1 and _d[1]:
                _wa = _d[1]
        except Exception:
            pass

    _logo_b64 = _logo_base64()
    _logo_html = (f'<img src="data:image/png;base64,{_logo_b64}" alt="Logo" '
                  'style="width:56px; border-radius:10px; border:2px solid #FFD700; display:block;">'
                  if _logo_b64 else '<div style="font-size:2.4rem; line-height:1;">📿</div>')

    def _img(url, classe="dpl-photo"):
        return f'<img src="{url}" alt="" class="{classe}">' if url else ""

    _perles = "".join('<div style="width:12px; height:12px; border-radius:50%; background:#FFD700; '
                      'box-shadow:0 0 5px rgba(255,215,0,0.8);"></div>' for _ in range(10))
    _chapelet = ('<div style="display:flex; align-items:center; justify-content:center; gap:6px; margin-top:10px;">'
                 + _perles + '<div style="font-size:1.3rem; margin-left:6px;">✝️</div></div>')

    def _section(emoji, titre, corps, photo=None):
        return ('<div style="background:#1a2150 !important; border:1px solid #27306b; '
                'border-left:5px solid #FFD700; border-radius:10px; padding:12px 14px; margin:10px 0;">'
                + _img(photo) +
                '<div class="dpl-titre-g" style="font-size:clamp(0.95rem, 4vw, 1.02rem); margin-bottom:6px;">' + emoji + ' ' + titre + '</div>'
                '<div style="color:#e8eaf6 !important; font-size:0.92rem; line-height:1.75;">' + corps + '</div></div>')

    _bouton = ""
    if _wa:
        _msg = ("Bonjour, je souhaite rejoindre une Équipe du Rosaire. " if not paroisse_id
                else "Bonjour, je souhaite rejoindre une Équipe du Rosaire dans notre paroisse. ")
        _lien = lien_whatsapp(_wa, _msg + "Merci de me renseigner. 📿")
        if _lien:
            _bouton = ('<div style="text-align:center; margin-top:12px;">'
                       '<a href="' + _lien + '" target="_blank" '
                       'style="display:inline-block; background:#25D366 !important; color:#ffffff !important; '
                       'padding:11px 24px; border-radius:30px; font-weight:bold; text-decoration:none; '
                       'font-size:0.95rem;">📱 Écrire au ' + _etiquette + '</a></div>')

    _bandeau = (
        '<div style="background:linear-gradient(135deg,#1A237E,#4527a0); border-radius:12px; padding:14px 12px 12px 12px; text-align:center;">'
        '<div style="display:flex; justify-content:flex-start; margin-bottom:4px;">' + _logo_html + '</div>'
        '<div class="dpl-titre-g" style="font-size:clamp(1.0rem, 5.2vw, 1.45rem); '
        'white-space:nowrap; overflow:hidden; text-overflow:ellipsis; letter-spacing:0.5px;">'
        'LES ÉQUIPES DU ROSAIRE</div>'
        '<div class="dpl-txt-g" style="font-size:clamp(0.7rem, 3.1vw, 0.88rem); margin-top:7px; line-height:1.7;">'
        '• Un Mouvement d’Église &nbsp;• Une École de Prière &nbsp;• Un Esprit Missionnaire<br>— depuis 1955 —</div>'
        + _chapelet + '</div>')
    
    _blocs = ['<div style="padding:12px;">', _bandeau]
    if PHOTO_BANDEAU:
        _blocs.append(_img(PHOTO_BANDEAU, "dpl-photo-bandeau"))
    _blocs.append(_section("📜", "Qui sommes-nous ?",
        "Fondé en 1955 par <b><font color='#FFD700'>le Révérend Père Joseph Eyquem (1917-1990)</font></b>, Prêtre dominicain, les \"Équipes du Rosaire\" est un mouvement catholique de prière et d’apostolat des laïcs, reconnu par l’Église "
        "et par l’Ordre des Prêcheurs (Dominicains) en 1972. En Côte d’Ivoire, "
        "<b><font color='#FFD700'>Dominique YOVAN</font></b> introduit le Mouvement en octobre 1980 — "
        "première équipe à l’Église Sainte Famille de la Riviera à Cocody — et en devient le 1er Responsable "
        "National, jusqu’à son rappel à Dieu le 10 juillet 2015 à Abidjan.", PHOTO_QUI))
    _blocs.append(_section("⛪", "Comment ça marche ?",
        "Une équipe est le regroupement de 3 à 12 personnes, ancrée dans un quartier, une rue, un immeuble "
        "ou un village autour de la Vierge Marie, Mère de Notre Seigneur Jésus-Christ, afin de méditer \"Son Rosaire\" et d'avoir une vie de fraternité. Chaque membre reçoit <b><font color='#FFD000'> un numéro de méditation compris entre 01 et 20 (Numéro dans l'équipe) </font></b> "
        "qui lui permet de méditer \"sa dizaine quotidienne\" dans l'Esprit du Frère fondateur; — ainsi ensemble, sans se voir, les 20 mystères du Rosaire "
        "sont couverts chaque jour. C’est la chaîne de prière universelle. Les équipes et paroisses sont coordonnées "
        "par des responsables d'équipe, paroissiaux, diocésains, nationaux. Les équipiers sont encadrés par des aumôniers sectoriels, diocésains et nationaux pour le suivi spirituel.",
        PHOTO_COMMENT))
    _blocs.append(_section("🙏", "Deux temps de prière",
        "<b class='dpl-p-blanc'>• La prière personnelle quotidienne</b> : méditer un mystère du Rosaire, l’Évangile, "
        " dans l'Esprit du <b><i><font color='#FFD700'>Père Joseph EYQUEM</font></i></b>, en communion avec toute la chaîne de prière.<br>"
        "<b class='dpl-p-blanc'>• La rencontre mensuelle</b> : prière commune chez un membre, méditation "
        "de la Parole de Dieu, partage d’intentions et de la vie quotidienne, guidée par le feuillet mensuel "
        "« Le Rosaire en Équipe ».", PHOTO_PRIERES))
    _blocs.append(_section("❤️", "Notre mission",
        "Animés par la passion de l’Évangile et le salut des hommes, nous avons un objectif missionnaire local : "
        "aider amis et voisins à vivre l’Évangile avec Marie, même ceux qui n’ont pas l’habitude d’aller à l’église. "
        "Les équipes favorisent un climat fraternel, convivial et accessible à tous.", PHOTO_MISSION))
    _blocs.append(_section("📖", "Ressources",
        "Chaque année, un thème. Chaque mois, un sous-thème : contenu dans un feuillet \"Le Rosaire en Équipe\" propose la prière du mois, des enseignements "
        "théologiques accessibles et des réflexions pour la vie quotidienne — des outils qui structurent la prière "
        "et renforcent la cohésion de l’équipe.", PHOTO_RESSOURCES))
    _blocs.append(
        '<div style="background:#FFF9C4 !important; border:2px solid #FFD700; border-radius:12px; padding:14px; '
        'margin-top:12px; text-align:center;">'
        '<div class="dpl-titre-g" style="font-size:clamp(1.0rem, 4.2vw, 1.15rem);">'
        'Voulez-vous rejoindre une équipe ?</div>'
        '<div style="color:#4527a0 !important; font-size:0.92rem; line-height:1.6; margin-top:6px;">Adressez-vous au '
        + _etiquette + ' <b style="color:#1A237E !important;">' + html.escape((str(_resp).strip() if _resp else "") or "du Mouvement")
        + '</b>.<br>Juste en dessous : confiez votre intention à une équipe '
        '(« 🙏 Vos intentions à une équipe »), puis entrez votre jour de naissance '
        'dans « 🕯️ Un jour, une dizaine » et priez avec nous. 🕊️</div>' + _bouton + '</div>')
    _blocs.append('</div>')
    _corps = "".join(_blocs)

    st.markdown('<style>'
                '.depliant-eq76 summary::-webkit-details-marker{display:none;}'
                '.depliant-eq76 summary{list-style:none;}'
                '.dpl-photo { width:100%; max-width:860px; height:150px; object-fit:contain; '
                'background:#0a0f2c; border-radius:8px; display:block; margin:0 auto 10px auto; }'
                '.dpl-photo-bandeau { width:100%; border-radius:12px; display:block; margin-top:12px; }'
                '@media (min-width:769px) { .dpl-photo { height:230px; } }'
                '</style>', unsafe_allow_html=True)

    _attr_ouvert = " open" if DEPLIANT_OUVERT else ""
    _consigne = "cliquez pour replier ▴" if DEPLIANT_OUVERT else "cliquez pour ouvrir ▾"
    st.markdown(
        '<details class="depliant-eq76"' + _attr_ouvert + ' style="background:#121a45 !important; border:1px solid #FFD700; '
        'border-radius:15px; margin:12px 10px; overflow:hidden;">'
        '<summary style="cursor:pointer; padding:12px 14px; background:linear-gradient(135deg,#1A237E,#4527a0); text-align:center;">'
        '<div class="dpl-titre-g" style="font-size:clamp(0.95rem, 4.3vw, 1.25rem); '
        'white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">'
        '📿 Découvrez les Équipes du Rosaire !</div>'
        '<div style="color:#e8eaf6 !important; font-size:clamp(0.7rem, 3vw, 0.82rem); font-weight:normal; margin-top:2px;">'
        + _consigne + '</div></summary>' + _corps + '</details>', unsafe_allow_html=True)

#     st.markdown(
#         '<details class="depliant-eq76" style="background:#121a45 !important; border:1px solid #FFD700; '
#         'border-radius:15px; margin:12px 10px; overflow:hidden;">'
#         '<summary style="cursor:pointer; padding:12px 14px; background:linear-gradient(135deg,#1A237E,#4527a0); text-align:center;">'
#         '<div class="dpl-titre-g" style="font-size:clamp(0.95rem, 4.3vw, 1.25rem); '
#         'white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">'
#         '📿 Découvrez les Équipes du Rosaire !</div>'
#         '<div style="color:#e8eaf6 !important; font-size:clamp(0.7rem, 3vw, 0.82rem); font-weight:normal; margin-top:2px;">'
#         'cliquez pour ouvrir ▾</div></summary>' + _corps + '</details>', unsafe_allow_html=True)

def _render_actualites(pid=None):
    """📰 Actualités (publications « actualite » du Service Communication :
    affiche +/ou BA, enseignements, salves…). 5 dernières, les plus récentes
    d'abord. LOT C5 : ne montre que le diocèse (cible NULL) + la paroisse du
    contexte. v7.9.18 — titre simplifié (« Actualités » : les publications
    ciblées sur une paroisse y figurent aussi) et appel DANS le fil
    d'actualité (_render_fil_actualites), où elles avaient disparu."""
    cond, prm = ("AND (paroisse_cible IS NULL OR paroisse_cible = ?)", [pid]) if pid \
        else ("AND paroisse_cible IS NULL", [])
    try:
        lignes = c.execute(f"""SELECT titre, contenu_texte, image_url, fichier_url, date_publication
                              FROM espace_spirituel
                              WHERE type_contenu='actualite' {cond}
                              ORDER BY date_publication DESC, id DESC LIMIT 5""", prm).fetchall()
    except Exception:
        return
    if not lignes:
        return
    st.markdown('<h3 style="font-family:Georgia, serif;">📰 Actualités</h3>', unsafe_allow_html=True)
    for a in lignes:
        with st.expander("📰 " + (a[0] or "(sans titre)")):
            st.caption(f"Publié le {a[4] or '—'}")
            _au, _aurl = _parser_pos_photo(a[2])
            if _aurl and _aurl.startswith("http"):
                st.markdown(f'<img src="{_aurl}" alt="" class="rub-photo">', unsafe_allow_html=True)
            if a[1]:
                st.markdown(a[1].replace("\n", "  \n"), unsafe_allow_html=True)
            if a[3] and str(a[3]).startswith("http"):
                try:
                    st.video(a[3], width="stretch")
                except Exception:
                    st.markdown(f"🎬 [Voir la vidéo]({a[3]})")


# ──────────────────────────────────────────────────────────────────────
# v7.9.17 — LA MÉMOIRE D'UN JOUR : « 📌 Marquer l'alerte comme lue » et
# « J'ai honoré mon engagement de ce jour » masquaient leur carte jusqu'au
# rechargement seulement (l'état vivait dans la session, vidée à chaque
# F5/actualisation). Un petit cookie d'un jour posé dans le navigateur
# porte désormais le « déjà traité aujourd'hui » : la carte reste masquée
# au rechargement et revient le lendemain (affichage 1 fois par jour, par
# navigateur). Le cookie est posé par un script invisible ; s'il ne peut
# pas l'être (réglages stricts), tout se comporte exactement comme avant.
# ──────────────────────────────────────────────────────────────────────
def _lire_cookie_pdr(nom):
    """Valeur du cookie `nom` posé par l'application côté navigateur, ou
    '' si absent / indisponible (tests, cookies bloqués)."""
    try:
        _entetes = getattr(st, "context", None)
        if _entetes is None:
            return ""
        _brut = ""
        try:
            for _k, _v in (_entetes.headers or {}).items():
                if str(_k).lower() == "cookie":
                    _brut = str(_v or "")
                    break
        except Exception:
            _brut = ""
        if not _brut:
            return ""
        for _partie in _brut.split(";"):
            _k, _sep, _v = _partie.strip().partition("=")
            if _sep and _k == nom:
                return _v.strip()
    except Exception:
        pass
    return ""


def _poser_cookie_pdr(nom, valeur):
    """Pose (côté navigateur) le cookie `nom=valeur` pour une journée
    (max-age 86400). Silencieux en cas d'échec : aucun message, aucun
    blocage — la carte se comporte alors comme avant la v7.9.17."""
    try:
        _comp_html(
            "<script>(function(){try{document.cookie='" + str(nom) + "="
            + str(valeur) + "; path=/; max-age=86400; SameSite=Lax';}"
            "catch(e){}})();</script>", height=0)
    except Exception:
        pass


# ──────────────────────────────────────────────────────────────────────
# v7.9.20 — LA CLÉ DU LECTEUR : la mémoire d'un jour tient DÉSORMAIS EN
# BASE (voir marquer_carte_vue / carte_deja_vue dans database.py) — le
# cookie, lui, ne suffit plus : la session est vidée à chaque rechargement
# et, quand l'Espace est vu depuis une page extérieure (le site), le
# navigateur refuse les cookies dits « tierce partie » — la carte
# réapparaissait donc au rechargement. La clé identifie le lecteur SANS
# cookie ni session : le membre par son MatLoc (dans l'adresse), le
# visiteur par l'empreinte de sa consultation (navigateur + adresse
# réseau, hachée — aucune donnée personnelle n'est gardée). Elle est
# stable au rechargement comme à la navigation.
# ──────────────────────────────────────────────────────────────────────
def _cle_lecteur_pdr():
    """La clé du lecteur pour la mémoire d'un jour (v7.9.20) : « M:… » pour
    un membre reconnu (MatLoc porté par l'adresse), « N:… » pour un visiteur
    (empreinte hachée de sa consultation). Stable au rechargement."""
    try:
        _mat = st.query_params.get("matloc")
        if _mat:
            return "M:" + str(_mat).upper().strip()
    except Exception:
        pass
    _ua, _ip = "", ""
    try:
        _entetes = getattr(st, "context", None)
        if _entetes is not None:
            for _k, _v in (_entetes.headers or {}).items():
                _kl = str(_k).lower()
                if _kl == "user-agent":
                    _ua = str(_v or "")
                elif _kl == "x-forwarded-for":
                    _ip = str(_v or "").split(",")[0].strip()
    except Exception:
        pass
    import hashlib as _hl
    return "N:" + _hl.sha256((_ua + "|" + _ip).encode(
        "utf-8", "ignore")).hexdigest()[:24]


def _alerte_feuillet_fil(lien_theme=None):
    """v7.8-h · v7.8.2-h — Alerte « nouveau feuillet » en tête du fil d'actualité.
    Visible 45 jours après la publication (couvre un mois pastoral complet) ;
    le clic OUVRE DIRECTEMENT le livret du feuillet annoncé (lien profond
    ?flt=1&fa=ANNÉE&fm=MOIS — v7.8.4, même mécanisme que les liens
    d'archive) ; « 📌 Marquer comme lue » la masque pour la session en
    cours. Blindage v7.8.3 : pas d'alerte si le feuillet annoncé n'a
    aucune section saisie."""
    try:
        _pubs = c.execute("""SELECT annee_debut, mois, numero, date_publication
                             FROM feuillets_publications
                             ORDER BY annee_debut DESC, mois DESC""").fetchall()
    except Exception:
        return
    if not _pubs:
        return
    # v7.8.11 — l'alerte annonce le DERNIER MOIS PASTORAL paru récemment (et
    # non la dernière publication en date) : republier le feuillet de
    # septembre après celui d'octobre ne renvoie plus l'alerte sur septembre.
    # Une publication dont la date est illisible est considérée comme « à
    # annoncer » (sans mention de date) : auto-réparation des lignes à date
    # mal formatée. Hors délai de 45 jours : pas d'alerte.
    pub, _dpub = None, None
    for _p in _pubs:
        _d = safe_date(_p[3])
        if _d is None or (date.today() - _d).days <= 45:
            pub, _dpub = _p, _d
            break
    if not pub:
        return
    # v7.8.3 — pas d'alerte pour une publication sans contenu (sinon le clic
    # mènerait à une vitrine « pas encore publié »).
    if not _feuillet_sections(pub[0], pub[1]):
        return
    # v7.9.17 — le masquage SURVIT AU RECHARGEMENT : le clic pose aussi un
    # cookie d'un jour (clé du feuillet + date du jour) ; la carte revient
    # le lendemain, ou dès qu'une NOUVELLE publication remplace la clé.
    # v7.9.20 — la mémoire tient DÉSORMAIS EN BASE (clé du lecteur) : elle
    # survit au rechargement même quand le navigateur refuse les cookies
    # (consultation depuis une page extérieure) — même tenue, même promesse.
    _cle = f"{pub[0]}-{pub[1]}"
    _jour_al = date.today().isoformat()
    _val_cookie = _cle + "|" + _jour_al
    _cle_lecteur = _cle_lecteur_pdr()
    _carte_jour = "feuillet:" + _cle
    _lue_session = st.session_state.get("alerte_feuillet_lue") == _cle
    if _lue_session:
        _poser_cookie_pdr("pdr_alerte_feuillet", _val_cookie)
        marquer_carte_vue(_cle_lecteur, _carte_jour)
    if (_lue_session
            or _lire_cookie_pdr("pdr_alerte_feuillet") == _val_cookie
            or carte_deja_vue(_cle_lecteur, _carte_jour)):
        return
    _lien = ""
    if lien_theme:
        # v7.8.4 — RETOUR au comportement initial : le clic ouvre DIRECTEMENT
        # le livret du feuillet annoncé (lien profond ?flt=1&fa=&fm=, même
        # mécanisme que les liens « 📖 Relire ce feuillet » des archives) ;
        # fa/fm pointent la publication annoncée, quel que soit le mois lu.
        _lien = ('<a href="' + lien_theme + "&flt=1&fa=" + str(pub[0])
                 + "&fm=" + str(pub[1])
                 + '" target="_self" style="display:inline-block; background:#4527a0; '
                 'color:#ffffff; padding:10px 24px; border-radius:30px; font-weight:bold; '
                 'text-decoration:none; margin-top:6px;">📖 Ouvrir le livret du feuillet</a>')
    # v7.8.10 — la couverture du livret ACCOMPAGNE l'alerte : carte visuelle
    # (bleu nuit + or, image personnalisée si saisie par la cellule) portant
    # N°, mois, thème de l'année et le bouton d'ouverture.
    _mention = "🔔 Nouveau : le feuillet mensuel de prière est disponible !"
    if _dpub:
        _mention += " · publié le " + _dpub.strftime("%d/%m/%Y")
    st.markdown(_couverture_feuillet_html(
        pub[0], pub[1], compact=True, lien=_lien, titre_haut=_mention),
        unsafe_allow_html=True)
    if st.button("📌 Marquer l'alerte comme lue", key="alerte_feuillet_lu_btn"):
        st.session_state["alerte_feuillet_lue"] = _cle
        marquer_carte_vue(_cle_lecteur, _carte_jour)
        st.rerun()


def _render_page_galerie(sub):
    """🖼️ GALERIE + (v7.9.1) — nouvelle rubrique de l'Espace de Prière avec
    2 sous-rubriques :
      • « Souvenirs » — les photos de notre marche ensemble (pèlerinages,
        prières mensuelles, moments d'équipe) ;
      • « Témoignages » — les grâces reçues, racontées par ceux qui les vivent.
    Le diocèse publie et retire (menu « 🖼️ Galerie + » du portail gestionnaire) ;
    ici la communauté lit. 🤫 Le principe « être une tombe » des intentions
    n'est pas touché : un témoignage n'entre ici qu'avec l'accord de celui
    qui le vit."""
    _rub = "souvenirs" if sub == "Souvenirs" else "temoignages"
    if _rub == "souvenirs":
        _titre, _sous = ("🏞️ Souvenirs",
                         "Les photos de notre marche ensemble — pèlerinages, prières "
                         "mensuelles, moments d’équipe.")
        _vide = ("🏞️ Aucun souvenir publié pour l’instant. Les photos des évènements "
                 "paraîtront ici dès leur publication par le diocèse.")
    else:
        _titre, _sous = ("💬 Témoignages",
                         "« Rendez grâce en toute occasion » — les grâces reçues, "
                         "racontées par ceux qui les vivent.")
        _vide = ("💬 Aucun témoignage publié pour l’instant. Les grâces reçues "
                 "racontées paraîtront ici, avec l’accord de ceux qui les vivent.")
    st.markdown(
        '<div style="background:linear-gradient(135deg,#1A237E 0%,#283593 100%);'
        ' padding:16px; border-radius:15px; text-align:center; margin:10px;'
        ' border:1px solid #FFD700;">'
        '<div style="color:#FFD700 !important; font-size:1.15rem; font-weight:bold;">'
        '🖼️ Galerie + — ' + html.escape(_titre) + '</div>'
        '<div style="color:#e8eaf6 !important; font-size:0.85rem; margin-top:5px;">'
        + html.escape(_sous) + '</div></div>', unsafe_allow_html=True)
    try:
        items = c.execute(
            """SELECT titre, texte, image_url, date_event, lieu, auteur_nom, date_publication
               FROM galerie_plus WHERE rubrique=?
               ORDER BY COALESCE(date_event, date_publication) DESC, id DESC""",
            (_rub,)).fetchall()
    except Exception:
        items = []
    if not items:
        st.info(_vide)
        return
    for (titre, texte, img, devt, lieu, auteur, dpub) in items:
        _meta = []
        _d = safe_date(devt or dpub)
        if _d:
            _meta.append("📅 " + _d.strftime("%d/%m/%Y"))
        if (lieu or "").strip():
            _meta.append("📍 " + str(lieu).strip())
        if (auteur or "").strip():
            _meta.append("✍️ " + str(auteur).strip())
        _corps = ""
        # v7.9.18 — PLUSIEURS PHOTOS par entrée (téléversement en un seul
        # envoi côté diocèse) : toutes les URLs sont affichées l'une après
        # l'autre, même style ; une entrée d'avant la v7.9.18 (une seule
        # URL) se rend exactement comme avant.
        for _u_gal in urls_galerie(img):
            # v7.9.19 — les photos rangées dans l'application (secours local
            # sans hébergeur) portent une adresse /app/static/… : elles
            # s'affichent exactement comme les photos hébergées.
            if (_u_gal.startswith("http") or _u_gal.startswith("/app/static/")
                    or _u_gal.startswith("app/static/")):
                _corps += ('<img src="' + html.escape(_u_gal) + '" alt="" '
                           'style="width:100%; max-width:560px; border-radius:10px; '
                           'display:block; margin:0 auto 10px auto; border:1px solid #C9A227;">')
        if (texte or "").strip():
            _corps += ('<div style="line-height:1.7; color:#1a1a1a; white-space:pre-wrap;">'
                       + html.escape(str(texte)) + '</div>')
        st.markdown(
            '<div style="background:#FFF9C4; border-radius:12px; padding:14px 16px;'
            ' margin:10px 6px; border-left:6px solid #C9A227;">'
            '<div style="color:#1A237E; font-weight:bold; font-size:1.02rem;">'
            + html.escape(titre or "…") + '</div>'
            + ('<div style="color:#4527a0; font-size:0.8rem; margin:2px 0 8px 0;">'
               + html.escape(" · ".join(_meta)) + '</div>' if _meta else "")
            + _corps + '</div>', unsafe_allow_html=True)
        st.markdown("", unsafe_allow_html=True)


def _assurer_table_intentions():
    """v7.8.14 — table des intentions confiées aux équipes (création douce).
    statut : 'recue' → 'en_priere' → 'archivee' (côté responsable d'équipe).
    v7.8.15 — colonne auteur_contact (WhatsApp / adresse mail du fidèle).
    v7.8.17 — pont vers la RÉPARATION CENTRALISÉE (database.verifier_reparer_
    intentions) : sonde de lecture + ALTER doux de CHAQUE colonne attendue +
    reconnexion si le cache de statements est périmé. Les bases distantes
    créées par un brouillon antérieur peuvent manquer de n'importe quelle
    colonne — plus seulement anonyme/auteur_contact."""
    verifier_reparer_intentions()


def _render_intentions_equipes(pid=None, equipe_membre_id=None, auteur_nom=None):
    """🙏 VOS INTENTIONS À UNE ÉQUIPE (v7.8.15) — présenté COMME LE DÉPLIANT :
    UN SEUL CADRE DORÉ (fond bleu nuit #121a45, liseré or #FFD700) englobant
    la bannière, les badges, l'expanseur « Choix de l'équipe » et tous les
    champs (les champs ont un liséré doré). Champs : Nom et Prénom*, Contact
    WhatsApp / Adresse mail*, Jour de naissance (1-31)*, Intention de
    prière* ; case d'acceptation (anti-spam) obligatoire.
    v7.9.0 — LA CHAÎNE DE PRIÈRE UNIVERSELLE : plus de case d'anonymat (le
    fidèle signe son intention) ; le JOUR DE NAISSANCE devient la clé
    discrète de la chaîne (il garantit que le fidèle ne priera jamais SA
    propre intention dans « 🕯️ Un jour, une dizaine ») ; après l'envoi, un
    appel « 📿 Prier ma dizaine maintenant » ouvre directement le livret pour
    porter l'intention du prochain. L'intention arrive DIRECTEMENT au
    responsable de l'équipe (onglet « 🙏 » de « 📌 Suivi et Agenda »), sans
    passer par le fil public ni par le diocèse.
    v7.9.3 — REMONTÉE + HARMONISATION : la rubrique quitte le fil
    d'actualité et se place JUSTE AVANT « 🕯️ Un jour, une dizaine » ; sa
    bannière reprend EXACTEMENT le langage visuel de cette dernière
    (dégradé #1A237E→#283593, liseré or 2 px, mêmes marges) pour un Accueil
    homogène."""
    if not pid:
        return
    _assurer_table_intentions()
    try:
        equipes = c.execute("""SELECT id, nom_equipe, paroisse_id FROM equipes
                               WHERE paroisse_id=? ORDER BY nom_equipe""",
                            (pid,)).fetchall()
    except Exception:
        equipes = []
    if not equipes:
        return
    # ── CSS du CADRE DORÉ (v7.8.15) : le container bordé (st.container
    # border=True) reçoit la classe .int-cadre-or par un mini-script (même
    # mécanisme que injecter_icone_pwa) — le CSS ne touche donc QUE ce cadre :
    # fond bleu nuit, expanseurs à liseré or, champs à liséré or.
    st.markdown('<style>'
        '.int-cadre-or [data-testid="stExpander"] { border:1.5px solid #C9A227'
        ' !important; border-radius:10px !important; background:rgba(255,215,0,0.07)'
        ' !important; }'
        '.int-cadre-or [data-testid="stExpander"] summary { color:#FFD000'
        ' !important; font-weight:600 !important; }'
        '.int-cadre-or input, .int-cadre-or textarea { border:1.5px solid #C9A227'
        ' !important; border-radius:8px !important; background:#0d1338 !important;'
        ' color:#ffffff !important; }'
        '.int-cadre-or input::placeholder, .int-cadre-or textarea::placeholder'
        ' { color:#8a93c9 !important; }'
        '.int-cadre-or div[data-baseweb="select"] > div { border:1.5px solid'
        ' #C9A227 !important; border-radius:8px !important; background:#0d1338'
        ' !important; color:#ffffff !important; }'
        '.int-cadre-or label, .int-cadre-or label p { color:#e8eaf6 !important; }'
        '.int-cadre-or [data-testid="stCaptionContainer"] p { color:#b8c0e8'
        ' !important; }'
        '.int-depliant-or summary { background:linear-gradient(135deg,#1A237E,'
        ' #4527a0) !important; text-align:center; border-radius:0 !important;'
        ' display:block !important; }'
        '.int-depliant-or summary p, .int-depliant-or summary div {'
        ' color:#FFD000 !important; font-weight:600 !important; }'
        '.int-depliant-or details { background:transparent !important; }'
        '</style>', unsafe_allow_html=True)
    # v7.9.17 — DEMANDE UTILISATRICE : la rubrique est CONTENUE DANS UN
    # DÉPLIANT, comme « 📿 Découvrez les Équipes du Rosaire ! ». L'expander
    # porte le titre ; le mini-script ci-dessous (marker int-or-marker)
    # habille l'EXPANDER lui-même (bordure + fond + summary dégradé).
    # v7.9.19 — DEMANDE UTILISATRICE : « est dans un expander pas dans un
    # dépliant, comme « 📿 Découvrez les Équipes du Rosaire ! », sous la
    # forme de carte lorsqu'elle est repliée » — la rubrique reste un
    # expander (pas le bloc details du dépliant de découverte), habillé
    # EXACTEMENT comme la carte du dépliant (même dégradé, même liseré or,
    # mêmes coins arrondis), et elle se présente REPLIÉE À L'ARRIVÉE : une
    # carte, qui s'ouvre d'un clic. La mini-ligne « cliquez pour ouvrir ▾ »
    # du dépliant de découverte est reprise (posée par le mini-script, qui
    # la retourne au clic) ; un formulaire soumis (messages de reprise
    # visibles) ou le CTA « 📿 Prier ma dizaine maintenant » la maintient
    # ouverte.
    _depl_int_ouvert = (bool(st.session_state.get("form_intention_equipe"))
                        or (st.session_state.get("int_derniere") is not None))
    with st.expander("🙏 Vos intentions à une équipe",
                     expanded=_depl_int_ouvert):
            st.markdown('<div id="int-or-marker"></div>', unsafe_allow_html=True)
            # ── BANNIÈRE (v7.9.3 — harmonisée avec « 🕯️ Un jour, une dizaine » :
            # même dégradé #1A237E→#283593, même liseré or de 2 px, même titre
            # dpl-titre-g) — tout est DANS le cadre doré
            st.markdown(
                '<div style="background:linear-gradient(135deg,#1A237E 0%,#283593 100%);'
                ' border:2px solid #FFD700; border-radius:15px; padding:16px;'
                ' text-align:center; margin:2px 4px 10px 4px;">'
                '<div class="dpl-titre-g" style="font-size:clamp(1.05rem, 4.5vw, 1.25rem);">'
                '🙏 Vos intentions à une équipe</div>'
                '<div style="color:#ffffff; font-size:clamp(0.85rem, 3.6vw, 1rem);'
                ' margin-top:6px; line-height:1.6;">'
                'Confie à Notre Dame du Rosaire ton intention de prière<br>'
                'par le canal d\u2019une équipe</div>'
                '<div style="display:inline-block; margin-top:9px; background:rgba(255,215,0,0.14);'
                ' border:1px solid #FFD700; border-radius:20px; padding:6px 16px; max-width:94%;'
                ' color:#FFD000; font-size:0.78rem; line-height:1.65;">🤫 « Tu es le prochain'
                ' de l\u2019équipe qui prie pour toi. En retour, va dans « 🕯️ Un jour, une dizaine »'
                ' et confie ton prochain à la Vierge Marie : c\u2019est LA CHAÎNE DE PRIÈRE'
                ' UNIVERSELLE »</div></div>',
                unsafe_allow_html=True)
            _idx_def = 0
            if equipe_membre_id:
                for _i, _e in enumerate(equipes):
                    if _e[0] == equipe_membre_id:
                        _idx_def = _i
                        break
            # ── CHOIX DE L'ÉQUIPE : expanseur HORS formulaire — chaque clic met
            # à jour le TITRE de l'expanseur (« — nom de l'équipe ») et le choix
            # est mémorisé en session ; les champs restent dans le formulaire.
            _idx_choisi = st.session_state.get("int_eq_choix")
            if not isinstance(_idx_choisi, int) or _idx_choisi < 0 or _idx_choisi >= len(equipes):
                st.session_state.pop("int_eq_choix", None)  # index obsolète
                _idx_choisi = _idx_def
            _titre_ex = "👥 Choix de l’équipe"
            if "int_eq_choix" in st.session_state:
                _titre_ex += " — " + str(equipes[_idx_choisi][1])
            with st.expander(_titre_ex):
                st.radio("À quelle équipe confier votre intention ?",
                         list(range(len(equipes))), index=_idx_choisi,
                         format_func=lambda i: equipes[i][1],
                         key="int_eq_choix", label_visibility="collapsed")
            # ── v7.9.0 — CTA « à vous de prier » : après un envoi réussi, le
            # fidèle est invité à égrener SA dizaine immédiatement (la chaîne de
            # prière universelle) ; le clic ouvre directement le livret.
            if st.session_state.get("int_derniere") is not None:
                _jn_cta = st.session_state["int_derniere"]
                st.markdown('<div style="background:rgba(255,215,0,0.10); border:1px dashed #FFD700;'
                            ' border-radius:10px; padding:10px 12px; margin:0 4px 10px 4px;'
                            ' text-align:center;">'
                            '<div style="color:#FFD000; font-weight:600;">🙏 Votre intention est'
                            ' partie — à vous de prier maintenant !</div>'
                            '<div style="color:#e8eaf6; font-size:0.85rem; margin-top:4px;">'
                            'Égrenez votre dizaine et portez l’intention du prochain dans'
                            ' la chaîne de prière universelle.</div></div>',
                            unsafe_allow_html=True)
                if st.button("📿 Prier ma dizaine maintenant", key="int_cta_dizaine",
                             type="primary", width="stretch"):
                    st.session_state["diz_jrnais"] = int(_jn_cta)
                    st.session_state["diz_ouvert"] = True
                    st.session_state["diz_page"] = 0
                    st.session_state.pop("int_derniere", None)
                    st.session_state.pop("flt_ouvert", None)  # un seul livre ouvert à la fois
                    st.rerun()
            with st.form("form_intention_equipe", clear_on_submit=False):
                # ── CHAMPS (liséré doré via CSS ci-dessus)
                st.markdown('<div style="color:#FFD000; font-size:0.85rem;'
                            ' margin:2px 2px 6px 2px;">« * » indique les champs'
                            ' obligatoires</div>', unsafe_allow_html=True)
                # Clés PAR GÉNÉRATION (v7.8.15) : les widgets d'un st.form ne se
                # resynchronisent pas au rerun → au succès, int_gen s'incrémente
                # et les champs renaissent NEUFS (vides), sans perdre la saisie
                # en cas de validation refusée (clear_on_submit reste False).
                _gen = st.session_state.get("int_gen", 0)
                _k = lambda b: b + "_" + str(_gen)
                if _k("int_nom") not in st.session_state and (auteur_nom or "").strip():
                    st.session_state[_k("int_nom")] = auteur_nom
                _nom = st.text_input("Nom et Prénom *", key=_k("int_nom"), max_chars=80,
                                     placeholder="Ex : N’guess KONÉ")
                _contact = st.text_input("Contact WhatsApp / Adresse mail *",
                                         key=_k("int_contact"), max_chars=120,
                                         placeholder="Ex : +225 07 00 00 00 00 ou nguekon@exemple.com")
                # v7.9.0 — JOUR DE NAISSANCE : clé discrète de la chaîne de prière.
                # Pré-rempli si le visiteur a déjà validé son jour au livret.
                _jn_pre = st.session_state.get("diz_jrnais")
                _jn_pre = _jn_pre if isinstance(_jn_pre, int) and 1 <= _jn_pre <= 31 else None
                _jour = st.number_input("Jour de naissance (1 - 31) *", min_value=1,
                                        max_value=31, value=_jn_pre, step=1,
                                        key=_k("int_jour"),
                                        help="Votre jour de naissance devient votre clé discrète "
                                             "dans la chaîne de prière universelle : c’est lui qui "
                                             "garantit que vous ne prierez jamais votre propre "
                                             "intention dans « 🕯️ Un jour, une dizaine ».")
                _txt = st.text_area("Intention de prière *", key=_k("int_txt"), height=110,
                                    max_chars=600,
                                    placeholder="Pour la santé de…, pour ma famille…, "
                                                "pour les vocations…")
                # v7.9.1 — retour de la case d'anonymat (demande user) : l'auteur
                # non signé reste inconnu du responsable (« Anonyme »), mais son
                # contact est quand même enregistré — c'est lui qui porte la règle
                # d'unicité (un numéro = une seule intention prise en charge).
                _anon = st.checkbox(
                    "🕊️ Rester anonyme (le responsable verra « Anonyme »)",
                    key=_k("int_anon"))
                _rgpd = st.checkbox(
                    "En envoyant cette intention, j’accepte que certaines données techniques "
                    "soient utilisées à des fins de sécurité et de lutte contre les envois "
                    "automatisés (spam) — voir la politique de confidentialité, en pied "
                    "de page.",
                    key=_k("int_rgpd"))
                if st.form_submit_button("📨 Confier cette intention", type="primary",
                                         width="stretch"):
                    _manque = []
                    if not (_nom or "").strip() and not _anon:
                        _manque.append("votre nom et prénom (ou cochez « 🕊️ Rester anonyme »)")
                    if not (_contact or "").strip():
                        _manque.append("un contact (WhatsApp ou adresse mail)")
                    if _jour is None:
                        _manque.append("votre jour de naissance (chiffre entre 1 et 31)")
                    if not (_txt or "").strip():
                        _manque.append("votre intention de prière")
                    if not _rgpd:
                        _manque.append("l’acceptation (case ☑) de la politique de confidentialité")
                    if _manque:
                        st.warning("Il manque : " + " ; ".join(_manque) + ".")
                    # v7.9.1 — UNICITÉ PAR NUMÉRO : un même numéro de téléphone ne
                    # peut pas porter 2 intentions prises en charge en même temps.
                    # v7.9.4 — le message parle au cœur (date + Matthieu 7.12) :
                    # ni leçon, ni mécanisme — la chaîne ne se brise pas.
                    elif contact_en_priere(_contact):
                        _d_emit = date_intention_en_priere(_contact)
                        _depuis = _d_emit.strftime("%d/%m/%Y") if _d_emit else ""
                        st.warning("📿 Tu es déjà porté(e) en prière"
                                   + (f" depuis le {_depuis}" if _depuis else "")
                                   + ". Ne brise pas la CHAÎNE DE PRIÈRE. Continue de méditer "
                                   "ta dizaine à CAUSE DE TON PROCHAIN.\n\n"
                                   "Matthieu 7.12 : « Faites pour les autres tout ce que vous "
                                   "voudriez qu’ils fassent pour vous, car c’est là tout "
                                   "l’enseignement de la Loi et des prophètes.»")
                    else:
                        _i = st.session_state.get("int_eq_choix")
                        if not isinstance(_i, int) or not (0 <= _i < len(equipes)):
                            _i = 0
                        _eq = equipes[_i]
                        _auteur = ("Anonyme" if _anon
                                   else (_nom or "").strip() or "Visiteur de l’Espace de Prière")
                        # v7.8.16 — envoi blindé : une micro-coupure vers la base
                        # (Turso) affiche un message doux et CONSERVE la saisie au
                        # lieu de faire planter toute la page ; le fidèle peut
                        # réessayer d'un clic sans rien retaper.
                        _err_envoi = False
                        try:
                            c.execute("""INSERT INTO intentions_equipes
                                         (equipe_id, texte, auteur_nom, auteur_contact, anonyme,
                                          jour_naissance, statut, date_soumission)
                                         VALUES (?, ?, ?, ?, ?, ?, 'recue', ?)""",
                                      (_eq[0], _txt.strip(), None if _anon else _auteur,
                                       (_contact or "").strip(),
                                       1 if _anon else 0, int(_jour), date.today().isoformat()))
                            commit_and_sync()
                            # v7.9.4 — LA ZONE DU JOUR : l'intention confiée aujourd'hui
                            # y est recueillie ; v7.9.10 — le SAS : la paroisse est notée
                            # sur la ligne (le sas paroissial la reconnaît d'emblée).
                            verser_intention_du_jour(_txt.strip(), auteur_nom=None if _anon else _auteur,
                                                     auteur_contact=(_contact or "").strip(),
                                                     anonyme=_anon, jour_naissance=int(_jour),
                                                     equipe_id=_eq[0],
                                                     paroisse_id=(_eq[2] if len(_eq) > 2 else None))
                        except Exception:
                            _err_envoi = True
                            st.error("⚠️ L’envoi n’a pas pu aboutir (connexion instable "
                                     "vers la base de données). Merci de réessayer dans "
                                     "quelques instants — votre saisie est conservée.")
                        if not _err_envoi:
                            st.session_state["int_gen"] = _gen + 1  # champs renaissent vides
                            for _b in ("int_nom", "int_contact", "int_txt", "int_jour", "int_rgpd"):
                                st.session_state.pop(_b + "_" + str(_gen), None)
                            # v7.9.0 — le jour de naissance devient l'identité de
                            # chaîne du fidèle (il ne priera jamais sa propre
                            # intention) et le CTA « prier ma dizaine » s'affiche.
                            st.session_state["diz_jrnais"] = int(_jour)
                            st.session_state["int_derniere"] = int(_jour)
                            st.session_state["flash_success"] = (
                                "🙏 Votre intention a été confiée à " + str(_eq[1])
                                + ". Elle arrive directement au responsable — elle sera portée "
                                "en prière, en toute confidentialité. 📿 À vous maintenant : "
                                "égrenez une dizaine et porter en prière votre prochain — c’est LA "
                                "CHAÎNE DE PRIÈRE UNIVERSELLE.")
                            st.rerun()
            # ── Mini-script (dernier élément du dépliant, remonte au bloc puis à
            # l'EXPANDER) : l'habillage doré (bordure, fond, ombre) se pose sur
            # l'expander lui-même (classe .int-depliant-or → summary dégradé via
            # le CSS ci-dessus) et le bloc interne garde la classe
            # .int-cadre-or (champs à liséré or). Comme injecter_icone_pwa :
            # tourne à chaque rerun, iframe invisible.
            # v7.9.19 — le mini-script ajoute AUSSI la mini-ligne du dépliant
            # de découverte (« cliquez pour ouvrir ▾ » / « cliquez pour
            # replier ▴ ») sous le titre, retournée à chaque clic.
            # v7.8.16 — via stcompat (st.iframe) : height=0 est borné à 1 px.
            try:
                _comp_html(
                    "<script>(function(){"
                    "var d=window.parent.document;"
                    "var m=d.getElementById('int-or-marker'); if(!m) return;"
                    "var w=m.closest('div[data-testid=\"stVerticalBlock\"]'); if(!w) return;"
                    "w.classList.add('int-cadre-or');"
                    "var e=m.closest('div[data-testid=\"stExpander\"]')"
                    "||m.closest('details[data-testid=\"stExpander\"]')||w;"
                    "e.style.border='2px solid #FFD700';"
                    "e.style.borderRadius='15px';"
                    "e.style.overflow='hidden';"
                    "e.style.background='#121a45';"
                    "e.style.boxShadow='0 4px 14px rgba(0,0,0,0.35)';"
                    "e.classList.add('int-depliant-or');"
                    "w.style.padding='10px 6px';"
                    "var dt=e.querySelector('details')||e;"
                    "var s=e.querySelector('summary');"
                    "if(s){"
                    "var cons=s.querySelector('.int-consigne');"
                    "if(!cons){"
                    "cons=d.createElement('div');"
                    "cons.className='int-consigne';"
                    "cons.style.cssText='width:100%; color:#e8eaf6 !important;"
                    " font-size:0.78rem; font-weight:normal !important;"
                    " text-align:center;';"
                    "s.appendChild(cons);"
                    "s.style.display='block';}"
                    "var maj=function(){"
                    "var ouvert=dt.hasAttribute('open');"
                    "cons.textContent= ouvert ? 'cliquez pour replier ▴' :"
                    " 'cliquez pour ouvrir ▾';};"
                    "maj();"
                    "s.addEventListener('click', function(){ setTimeout(maj, 60); });}"
                    "})();</script>", height=0)
            except Exception:
                pass


def _carte_vidéo_a_la_demande():
    """🛕 VIDÉO À LA DEMANDE (v7.9.17 ; nom d'aujourd'hui v7.9.20) — la vidéo
    YouTube de la chaîne « Équipes du Rosaire Grand-Bassam », ouverte juste
    avant le pied de page tant que LIEN_YOUTUBE_VIDÉO_A_LA_DEMANDE (en tête
    de module) est renseigné.
    Lecteur incorporé responsive (16:9, même mécanique que la playlist du
    contexte paroissial) + lien d'ouverture directe sur YouTube."""
    _url = str(LIEN_YOUTUBE_VIDÉO_A_LA_DEMANDE or "").strip()
    if not _url:
        return
    _m = re.search(r"(?:youtu\.be/|v=|shorts/|embed/)([A-Za-z0-9_-]{6,})", _url)
    if not _m:
        return
    _src = "https://www.youtube.com/embed/" + _m.group(1) + "?rel=0"
    st.markdown(
        '<div style="background:linear-gradient(135deg,#1A237E 0%,#283593 100%);'
        ' border:2px solid #FFD700; border-radius:15px; padding:16px;'
        ' text-align:center; margin:10px;">'
        '<div class="dpl-titre-g" style="font-size:clamp(1.05rem, 4.5vw, 1.25rem);">'
        '🛕 Vidéo à la demande</div>'
        '<div style="color:#ffffff; font-size:clamp(0.85rem, 3.6vw, 1rem);'
        ' margin-top:6px; line-height:1.6;">'
        'Regardez la vidéo à la demande sur la chaîne des Équipes du Rosaire —'
        ' Diocèse de Grand-Bassam</div>'
        '<div style="position:relative; width:100%; padding-top:56.25%;'
        ' border-radius:12px; overflow:hidden; border:1px solid #FFD700;'
        ' margin:12px 0 0 0;">'
        '<iframe src="' + _src + '" title="Vidéo à la demande"'
        # v7.10.1 — CHARGEMENT PARESSEUX : le lecteur ne se réveille que
        # quand le fidèle descend le voir — l'arrivée dans l'Espace et la
        # navigation ne l'attendent plus (la lenteur ressentie à l'ouverture).
        ' loading="lazy"'
        ' style="position:absolute; top:0; left:0; width:100%; height:100%;'
        ' border:none;" allow="encrypted-media; picture-in-picture"'
        ' allowfullscreen></iframe></div>'
        '<a href="' + html.escape(_url) + '" target="_blank" rel="noopener"'
        ' style="display:inline-block; margin-top:10px; background:rgba(255,215,0,0.14);'
        ' border:1px solid #FFD700; border-radius:20px; padding:6px 16px;'
        ' color:#FFD000; text-decoration:none; font-size:0.8rem;'
        ' max-width:94%;">🎬 Ouvrir la vidéo sur YouTube</a></div>',
        unsafe_allow_html=True)


def _render_fil_actualites(pid=None, lien_theme=None, equipe_membre_id=None,
                           auteur_nom=None, intentions=True):
    """v7.6 — fil du jour BLINDÉ : la ligne est complétée à 5 cases avant
    tout accès par index. LOT C5 : dernière publication VISIBLE du contexte.
    v7.8-h : une alerte « 📖 Nouveau feuillet » couronne le fil quand le
    diocèse vient de publier le feuillet mensuel de prière.
    v7.8.15 — « 🙏 Vos intentions à une équipe » est réservée à l'Espace
    COMMUNAUTAIRE : intentions=False côté vue Membre (elle ne s'y affiche
    plus).
    v7.9.3 — FIL ALLÉGÉ (FIL_ALLEGEE=True) : le fil ne garde plus que la
    section attendue — la prière/méditation DU JOUR. Le Coin Affiche, la
    rubrique intentions (remontée AVANT « 🕯️ Un jour, une dizaine ») et les
    Actualités de la Paroisse ne s'affichent plus ici (code conservé).
    v7.9.18 — les ACTUALITÉS (publications « 📰 actualite » du Service
    Communication : affiches, BA, enseignements…) reviennent dans le fil,
    après la carte du jour — le fil allégé les avait fait disparaître
    totalement : deux publications n'apparaissaient NULLE PART dans
    l'Espace de Prière."""
    _alerte_feuillet_fil(lien_theme)
    # v7.9.19 — la carte vidéo a quitté la tête du fil : elle s'ouvre
    # désormais JUSTE AVANT LE PIED DE PAGE (demande explicite), dans
    # show_espace_membre, sur toutes les pages de l'Espace de Prière.

    cond, prm = ("AND (paroisse_cible IS NULL OR paroisse_cible = ?)", [pid]) if pid \
        else ("AND paroisse_cible IS NULL", [])
    dernier = c.execute(f"""SELECT type_contenu, titre, contenu_texte, image_url, fichier_url
                           FROM espace_spirituel
                           WHERE type_contenu IN ('priere', 'meditation') {cond}
                           ORDER BY date_publication DESC, id DESC LIMIT 1""", prm).fetchone()

    if dernier:
        ligne = list(dernier) + [None] * max(0, 5 - len(dernier))
        etiquette = {"priere": "🙏 ", "meditation": "📖 "}.get(ligne[0], "📿 Du jour")
        texte = ligne[2] or ""
        url_pdf = ligne[4]
        if not url_pdf:
            texte, url_pdf = _extraire_pdf_legacy(texte)

        # v7.8.11 — position de la photo : préfixe [droite]/[gauche] du lien
        # (choisi à la soumission) → image flottante DANS la carte, le texte
        # habille ; sinon l'image reste au-dessus (comportement initial).
        _pos_fil, _url_fil = _parser_pos_photo(ligne[3])
        _img_flottante = ""
        if _pos_fil in ("droite", "gauche") and _url_fil and str(_url_fil).startswith("http"):
            _img_flottante = ('<img src="' + html.escape(str(_url_fil)) + '" alt="" class="'
                              + ("rub-photo-fd" if _pos_fil == "droite" else "rub-photo-fg") + '">')
        elif ligne[3] and str(ligne[3]).startswith("http"):
            st.markdown(f'<img src="{ligne[3]}" alt="" class="rub-photo">', unsafe_allow_html=True)

        texte_html = texte.replace("\n", "<br>")
        st.markdown(
            f'<div class="rub-carte" style="padding:20px; text-align:center; margin:15px 10px;">'
            f'{_img_flottante}'
            f'<div class="rub-carte-titre" style="font-size:1.15rem; border-bottom:1px solid #27306b; padding-bottom:8px; margin-bottom:12px;">{etiquette} - {html.escape(ligne[1] or "")}</div>'
            f'<div class="rub-carte-txt" style="font-size:0.98rem; line-height:1.7; text-align:left;">{texte_html}</div>'
            f'<div style="clear:both;"></div>'
            f'</div>', unsafe_allow_html=True)

        if url_pdf:
            _render_pdf_inline(url_pdf)
    else:
        st.info("Aucun contenu spirituel n'a encore été publié.")

    # v7.9.18 — LES ACTUALITÉS RENTRENT DANS LE FIL : les publications
    # « 📰 actualite » (enseignements, salves, affiches…) du diocèse et de
    # la paroisse du contexte s'affichent APRÈS la carte du jour, pour le
    # public comme pour les membres. Le fil allégé (v7.9.3) les masquait
    # totalement : elles n'apparaissaient NULLE PART. La fonction se tait
    # d'elle-même quand il n'y en a pas — aucun écran pollué à vide.
    _render_actualites(pid)

    # v7.9.3 — FIL D'ACTUALITÉ ALLÉGÉ : une seule section reste dans le fil
    # (la prière/méditation du jour, ci-dessus). Le reste est conservé mais
    # masqué — repasser FIL_ALLEGEE à False pour retrouver l'ancien fil.
    if not FIL_ALLEGEE:
        _render_coin_affiche(pid)
        # v7.8.15 — « 🙏 Vos intentions à une équipe » JUSTE AVANT les actualités
        # de la paroisse — ESPACE COMMUNAUTAIRE UNIQUEMENT (retirée côté Membre).
        if intentions:
            _render_intentions_equipes(pid=pid, equipe_membre_id=equipe_membre_id,
                                       auteur_nom=auteur_nom)
        _render_actualites_paroisse(pid)


def _render_actualites_paroisse(pid=None):
    """📰 Actualités de la Paroisse (v7.8.6) — le fil de l'espace communautaire
    de la paroisse : les prochains évènements créés par ses ÉQUIPES (et par la
    paroisse elle-même). Périmètre strict : visible UNIQUEMENT dans le contexte
    de cette paroisse (QR paroissial ou membre de la paroisse) — jamais au-delà.
    La Réponse de Communion reste dans « 📅 Mes évènements » côté membre."""
    if not pid:
        return  # aucun contexte paroissial → pas d'actualité paroissiale
    try:
        evts = c.execute("""SELECT e.id, e.date_evenement, e.type_evenement, e.lieu,
                                   e.affiche_url, e.video_url, e.auteur_nom,
                                   eq.nom_equipe, e.equipe_id
                            FROM evenements e
                            LEFT JOIN equipes eq ON e.equipe_id = eq.id
                            WHERE e.date_evenement >= ?
                              AND (eq.paroisse_id = ? OR e.paroisse_id = ?)
                            ORDER BY e.date_evenement ASC LIMIT 5""",
                         (date.today().isoformat(), pid, pid)).fetchall()
    except Exception:
        return
    if not evts:
        return
    st.markdown('<h3 style="font-family:Georgia, serif;">📰 Actualités de la Paroisse</h3>',
                unsafe_allow_html=True)
    st.caption("🕊️ Les prochains évènements de votre communauté paroissiale — "
               "annoncés par ses équipes. Membre : signez votre présence dans "
               "« 📅 Mes évènements ».")
    for evt in evts:
        d_e = safe_date(evt[1])
        date_txt = d_e.strftime("%d/%m/%Y") if d_e else "Date à définir"
        delta = (d_e - date.today()).days if d_e else None
        delai = "🔴 Aujourd'hui !" if delta == 0 else "🟠 Demain" if delta == 1 else \
                (f"📅 Dans {delta} jours" if delta is not None else "")
        icone = {"Prière mensuelle": "🧎", "Prière commune": "🙏", "Prière spéciale": "✨",
                 "Pèlerinage": "🚶‍♂️", "Réunion": "🤝"}.get(evt[2], "📅")
        organisateur = f"👥 {evt[7]}" if evt[7] else "🏘️ La paroisse"
        entete = f"{icone} {evt[2]} — {date_txt} · {delai}" if delai else f"{icone} {evt[2]} — {date_txt}"
        with st.expander(entete):
            st.write(f"**🏢 Organisé par :** {organisateur}")
            st.write(f"**📍 Lieu :** {evt[3] or 'Lieu à définir'}")
            _eu, _eurl = _parser_pos_photo(evt[4])
            if _eurl and _eurl.startswith("http"):
                st.markdown(f'<img src="{_eurl}" alt="" class="rub-photo">', unsafe_allow_html=True)
            if evt[5] and str(evt[5]).startswith("http"):
                try:
                    st.video(evt[5], width="stretch")
                except Exception:
                    st.markdown(f"🎬 [Voir la vidéo]({evt[5]})")


def _enregistrer_presence(membre_id, evt_id, choix):
    try:
        deja = c.execute("SELECT id FROM suivi_presences WHERE membre_id=? AND evenement_id=?",
                         (membre_id, evt_id)).fetchone()
        if deja:
            c.execute("UPDATE suivi_presences SET statut=? WHERE id=?", (choix, deja[0]))
        else:
            c.execute("INSERT INTO suivi_presences (membre_id, evenement_id, statut) VALUES (?, ?, ?)",
                      (membre_id, evt_id, choix))
        commit_and_sync()
    except Exception:
        st.session_state["flash_warning"] = "⚠️ Impossible d'enregistrer votre réponse pour le moment. Réessayez."
        st.rerun()
        return
    st.session_state["flash_success"] = "Merci pour votre engagement ! 🙏"
    st.rerun()


# v7.9.14 — le chapelet doré relevé une fois pour toutes (l'incorporation
# ne se refait pas à chaque page) ; None tant qu'il n'a pas été cherché.
_LOGO_PIED_MEMORISE = None

def _render_pied_de_page(matloc_membre=None):
    """🟣 PIED DE PAGE DU SITE (v7.9.3, refondu v7.9.9, disposition v7.9.10,
    assagi v7.9.11) — présent sur TOUTES les pages des Espaces de Prière
    (communautaire, membre, livre ouvert). TROIS colonnes :
      • Colonne 1 — 🔒 Politique de confidentialité · 🍪 Politique de cookies ;
      • Colonne 2 — le LOGO DU MOUVEMENT (le chapelet doré des Équipes du
        Rosaire, dessiné pour lui — v7.9.11 : ce n'est plus l'icône de
        l'application), LES ÉQUIPES DU ROSAIRE, DIOCÈSE DE GRAND-BASSAM,
        le nom de la paroisse du fidèle (reconnu discrètement) et
        « Contactez le responsable paroissial » (WhatsApp quand il est
        renseigné) ;
      • Colonne 3 — 🏠 Actualités · 📿 Rosaire · 🕯️ Thème · 🖼️ Galerie + ·
        📖 Archives : les cinq rubriques de l'Espace, dans l'ordre — le même
        menu que l'entête, naviguant dans l'onglet courant.
    v7.9.11 — les trois phrases d'appel quittent le pied (la chaîne se
    montre, elle ne se raconte plus) : il reste l'essentiel. Fond violet
    nuit du badge « Bienvenue » (du haut jusqu'en bas), barre noire de
    copyright en pied, icône Facebook (si LIEN_FACEBOOK est renseigné).
    Le mode écoute dédié (?musique=1) en est exempté.
    v7.9.14 — le chapelet doré est cherché à côté du module (adresse
    certaine, où que la maison soit installée) et le nom de la paroisse
    est dit chaque fois qu'il peut être connu : fidèle reconnu, ou
    paroisse qui a ouvert la porte (QR / lien paroissial), sinon pied
    sobre — jamais de vide qui ressemble à un oubli."""
    if st.query_params.get("musique") == "1":
        return
    # v7.9.10 — le fidèle est reconnu discrètement (paroisse + responsable) :
    # des lectures tolérantes, aucune fuite en cas d'imprévu.
    # v7.9.14 — le nom de la paroisse est montré chaque fois qu'il peut être
    # connu : celle du fidèle reconnu (même si son statut dort — le pied de
    # page ne décide rien, il dit bonjour), sinon celle qui a ouvert la porte
    # (le QR ou le lien paroissial qui a mené ici). Sinon, pied sobre.
    _nom_par, _wa_par, _pid_par = None, None, None
    _est_membre = False
    if matloc_membre:
        _ml = str(matloc_membre).upper().strip()
        try:
            _row_par = c.execute("""SELECT p.nom, p.whatsapp_responsable, p.id
                                    FROM membres m
                                    JOIN paroisses p ON m.paroisse_id = p.id
                                    WHERE m.matloc=? AND m.statut='actif'
                                    LIMIT 1""", (_ml,)).fetchone()
            if _row_par:
                _nom_par, _wa_par, _pid_par = _row_par[0], _row_par[1], _row_par[2]
                _est_membre = True
        except Exception:
            _nom_par, _wa_par, _pid_par = None, None, None
        if not _est_membre:
            try:
                _row_par = c.execute("""SELECT p.nom, p.whatsapp_responsable, p.id
                                        FROM membres m
                                        JOIN paroisses p ON m.paroisse_id = p.id
                                        WHERE m.matloc=?
                                        LIMIT 1""", (_ml,)).fetchone()
                if _row_par:
                    _nom_par, _wa_par, _pid_par = _row_par[0], _row_par[1], _row_par[2]
                    _est_membre = True
            except Exception:
                pass
    if not _nom_par:
        try:
            _pid_accueil = st.session_state.get("paroisse_origine")
            if _pid_accueil:
                _row_acc = c.execute("""SELECT nom, whatsapp_responsable, id
                                        FROM paroisses WHERE id=?""",
                                     (_pid_accueil,)).fetchone()
                if _row_acc:
                    _nom_par, _wa_par, _pid_par = _row_acc[0], _row_acc[1], _row_acc[2]
        except Exception:
            pass
    # v7.9.10 — la colonne 3 pilote le MÊME menu que l'entête (?r=index) :
    # l'ordre des cinq rubriques et l'index diffèrent (membre ≠ public).
    _rubriques_pied = [
        ("🏠 Actualités", "Actualités"),
        ("📿 Rosaire", "Rosaire"),
        ("🕯️ Thème", "Thème"),
        ("🖼️ Galerie +", "Galerie +"),
        ("📖 Archives", "Archives"),
    ]
    _index_rub = {"🏠 Actualités": 0, "📿 Rosaire": 1, "🕯️ Thème": 2,
                  "🖼️ Galerie +": 3, "📖 Archives": 4}
    if _est_membre:
        _index_rub = {"🏠 Actualités": 0, "📿 Rosaire": 2, "🕯️ Thème": 1,
                      "🖼️ Galerie +": 4, "📖 Archives": 5}
    _base_lien = "?espace=1&nav=1"
    _p_ctx = None
    if _est_membre:
        # membre reconnu : le lien emporte SON adresse (matloc + paroisse)
        # et la colonne 3 suit l'ordre des rubriques membre
        _base_lien += "&matloc=" + urllib.parse.quote(str(matloc_membre))
        _p_ctx = _pid_par
    else:
        _p_ctx = st.session_state.get("paroisse_origine")
    if _p_ctx:
        _base_lien += "&p=" + str(_p_ctx)
    _menu_pied = "".join(
        '<li><a class="pdr-rub" href="' + _base_lien + "&r="
        + str(_index_rub[_lib]) + '">' + _lib + '</a></li>'
        for (_lib, _alt) in _rubriques_pied)
    # v7.9.11 — le LOGO DU MOUVEMENT, INCORPORÉ (aucune adresse à manquer) :
    # le chapelet doré des Équipes du Rosaire (static/logo_equipes_rosaire.png),
    # dessiné pour lui — ce n'est plus l'icône de l'application.
    # v7.9.14 — LE LOGO QUI NE SE PERD PLUS : il est cherché d'abord À CÔTÉ
    # DU MODULE (l'adresse certaine, où que la maison soit installée), puis
    # au coin habituel ; relevé une seule fois puis gardé en mémoire, il ne
    # dépend plus du lieu d'où la page parle.
    global _LOGO_PIED_MEMORISE
    _logo_pied = _LOGO_PIED_MEMORISE
    if _logo_pied is None:
        try:
            import base64 as _b64
            _ici = os.path.dirname(os.path.abspath(__file__))
            # v7.9.15 — images/logo.png D'ABORD : livré dans le paquet, et
            # remplaçable un jour par le logo officiel (même nom) sans toucher
            # au code — l'entête, la page d'accueil et le pied restent alors
            # assortis. Le chapelet dessiné de static/ reste en secours.
            for _cand in (os.path.join(_ici, os.pardir, "images", "logo.png"),
                          os.path.join("images", "logo.png"),
                          os.path.join(_ici, os.pardir, "static",
                                       "logo_equipes_rosaire.png"),
                          os.path.join("static", "logo_equipes_rosaire.png")):
                if os.path.exists(_cand):
                    with open(_cand, "rb") as _f:
                        # v7.9.16 — plus d'attributs width/height figés : la
                        # taille est pilotée par le CSS (.pdr-img)
                        _logo_pied = ('<img class="pdr-img" src="data:image/png;base64,'
                                      + _b64.b64encode(_f.read()).decode("ascii")
                                      + '" alt="Les Équipes du Rosaire">')
                    break
        except Exception:
            _logo_pied = None
        if not _logo_pied:
            _logo_pied = '<div class="pdr-logo">📿</div>'
        _LOGO_PIED_MEMORISE = _logo_pied
    # v7.9.10 — « Contactez le responsable paroissial » : WhatsApp quand la
    # paroisse l'a renseigné, une simple invitation sinon.
    _wa_chiffres = "".join(_ch for _ch in str(_wa_par or "") if _ch.isdigit())
    if _wa_chiffres:
        _contact_html = ('<a class="pdr-contact" href="https://wa.me/' + _wa_chiffres
                         + '" target="_blank" rel="noopener">📞 Contactez le responsable'
                         ' paroissial</a>')
    else:
        _contact_html = ('<div class="pdr-contact">📞 Contactez le responsable'
                         ' paroissial</div>')
    _fb = str(LIEN_FACEBOOK or "").strip()
    _fb_html = ('<a class="pdr-fb" href="' + html.escape(_fb, quote=True) +
                '" target="_blank" rel="noopener" aria-label="Facebook">f</a>') if _fb else ''
    # v7.9.19 — L'ADRESSE DE LA CHAÎNE YOUTUBE (demande : « le lien de la
    # chaîne youtube.com à ajouter comme adresse dans le pied de page ») :
    # une ligne de plus dans la colonne centrale, sous le contact du
    # responsable paroissial, comme une adresse du Mouvement.
    _yt = str(LIEN_YOUTUBE_CHAINE or "").strip()
    _yt_html = ('<a class="pdr-contact pdr-yt" href="' + html.escape(_yt, quote=True)
                + '" target="_blank" rel="noopener">▶️ Notre chaîne YouTube</a>') if _yt else ''
    st.markdown('<style>'
                '.pdr-v910 { margin:30px 10px 18px 10px; border-radius:16px; overflow:hidden;'
                ' background:linear-gradient(165deg, #241042 0%, #3B1177 55%, #4A148C 100%);'
                ' box-shadow:0 6px 22px rgba(26,10,60,.45); }'
                '.pdr-v910 .pdr-cols { display:flex; flex-wrap:wrap; gap:8px 26px;'
                ' padding:22px 20px 14px 20px; }'
                '.pdr-v910 .pdr-col { flex:1 1 210px; min-width:190px; color:#e6dcf7;'
                ' font-size:0.86rem; line-height:1.8; }'
                # v7.9.15 — disposition d'origine (base mobile) : la 3e
                # colonne (menu) part du même rang que les autres, et le
                # bloc @media ci-dessous règle les écrans larges (v7.9.19 :
                # trois colonnes de MÊME largeur — colonne centrale
                # équidistante des deux extrêmes, menu calé à droite).
                # Sur téléphone (< 700 px), les colonnes s'empilent
                # comme avant — aucun changement mobile.
                '.pdr-v910 .pdr-col-droite { flex:1 1 210px; }'
                # v7.9.19 — LA COLONNE CENTRALE ÉQUIDISTANTE DES DEUX EXTRÊMES
                # (demande : « la 2ᵉ colonne semble plus proche de la 3ᵉ ») :
                # sur les écrans larges, les TROIS colonnes ont exactement la
                # même largeur (flex:1 1 0) — le centre du logo/nom tombe au
                # juste milieu ; le menu de droite reste calé à droite. Sur
                # téléphone (< 700 px), l'empilement ne change pas.
                '@media (min-width:700px) {'
                '.pdr-v910 .pdr-cols { flex-wrap:nowrap; }'
                '.pdr-v910 .pdr-col { flex:1 1 0; min-width:0; }'
                '.pdr-v910 .pdr-col-droite { flex:1 1 0; min-width:0;'
                ' margin-left:0; padding-left:0; text-align:right; }'
                '.pdr-v910 ul.pdr-menu { text-align:right; }'
                '}'
                '.pdr-v910 .pdr-col-milieu { text-align:center; }'
                # v7.9.16 — LE LOGO AGRANDI : même largeur que le nom
                # « LES ÉQUIPES DU ROSAIRE » (≈ 240 px), proportion carrée
                # conservée, réduit proprement si l'écran est étroit
                # (max-width:100%). L'ombre suit la forme ronde du chapelet
                # (drop-shadow), pas un carré autour des coins transparents.
                '.pdr-v910 .pdr-img { width:240px; max-width:100%; height:auto;'
                ' filter:drop-shadow(0 3px 10px rgba(0,0,0,.45)); }'
                '.pdr-v910 .pdr-logo { font-size:2.1rem; line-height:1.2;'
                ' filter:drop-shadow(0 2px 6px rgba(0,0,0,.4)); }'
                '.pdr-v910 .pdr-nom { color:#FFFFFF; font-weight:bold; letter-spacing:.06em;'
                ' font-family:Georgia, serif; font-size:1.02rem; margin-top:8px; }'
                '.pdr-v910 .pdr-dio { color:#FFD54F; font-size:0.84rem; letter-spacing:.05em; }'
                '.pdr-v910 .pdr-par { color:#e6dcf7; font-size:0.84rem; margin-top:2px; }'
                '.pdr-v910 ul.pdr-menu { list-style:none; margin:0 0 10px 0; padding:0; }'
                '.pdr-v910 ul.pdr-menu li { padding:3px 0; }'
                '.pdr-v910 ul.pdr-menu a { color:#e6dcf7; text-decoration:none;'
                ' font-size:0.88rem; }'
                '.pdr-v910 ul.pdr-menu a:hover { color:#FFD54F; text-decoration:underline; }'
                '.pdr-v910 p { margin:0 0 12px 0; }'
                '.pdr-v910 details { margin:0 0 10px 0; }'
                '.pdr-v910 summary { cursor:pointer; list-style:none; color:#FFD54F;'
                ' font-size:0.84rem; font-weight:600; padding:3px 0; }'
                '.pdr-v910 summary::-webkit-details-marker { display:none; }'
                '.pdr-v910 summary::before { content:"▸ "; color:#FFD54F; }'
                '.pdr-v910 details[open] summary::before { content:"▾ "; }'
                '.pdr-v910 .pdr-corps { color:#cfc2ea; font-size:0.8rem; line-height:1.75;'
                ' margin-top:6px; }'
                '.pdr-v910 .pdr-corps b { color:#e8eaf6; }'
                '.pdr-v910 .pdr-contact { display:inline-block; color:#FFD54F;'
                ' font-size:0.84rem; text-decoration:none; margin-top:4px; }'
                '.pdr-v910 a.pdr-contact:hover { text-decoration:underline; }'
                # v7.9.19 — la ligne YouTube de la colonne centrale
                '.pdr-v910 .pdr-yt { display:block; margin-top:6px; }'
                '.pdr-v910 .pdr-bas { background:rgba(5,2,12,.88); padding:10px 16px;'
                ' display:flex; flex-wrap:wrap; gap:4px 18px; align-items:center;'
                ' justify-content:space-between; }'
                '.pdr-v910 .pdr-cop { color:#b9a8e0; font-size:0.76rem; }'
                '.pdr-v910 .pdr-fb { display:inline-flex; align-items:center; justify-content:center;'
                ' width:26px; height:26px; border-radius:50%; background:#1877F2; color:#fff;'
                ' font-weight:bold; font-size:0.9rem; text-decoration:none;'
                ' font-family:Georgia, serif; }'
                '</style>', unsafe_allow_html=True)
    st.markdown(
        '<footer class="pdr-v910">'
        '<div class="pdr-cols">'
        '<div class="pdr-col">'
        '<details><summary>🔒 Politique de confidentialité</summary>'
        '<div class="pdr-corps">'
        '<b>1 · Ce que nous recueillons.</b> Les intentions confiées à une équipe '
        'enregistrent le nom (sauf si vous cochez « 🕊️ Rester anonyme »), un contact '
        '(WhatsApp ou adresse mail) et le jour de naissance — cette dernière donnée '
        'sert uniquement de clé discrète dans la chaîne de prière universelle : elle '
        'n&#8217;identifie personne et garantit seulement que vous n&#8217;y prierez jamais votre '
        'propre intention. Le pointage de dizaine (boutons « ✅ J’ai égrené ma dizaine '
        'aujourd’hui » et « ✕ Terminer ») note seulement la participation du jour : '
        'le membre par son matricule (MatLoc), le visiteur en simple passage anonyme — '
        'jamais le contenu de votre prière.<br>'
        '<b>2 · Ce que nous en faisons.</b> Vos données servent exclusivement à la vie '
        'de prière du Mouvement : identifier votre intention auprès du responsable '
        'd&#8217;équipe (et, s’il le souhaite, vous répondre), compter les participations et '
        'assurer la sécurité de l&#8217;espace (lutte contre les envois automatisés — spam). '
        'Elles ne sont ni vendues, ni partagées, ni utilisées à des fins commerciales. '
        '🤫 Principe « être une tombe » : les intentions se portent en prière, elles ne '
        'se racontent pas et ne sortent jamais de l&#8217;équipe.<br>'
        '<b>3 · Vos droits.</b> Vous pouvez demander à tout moment la suppression de '
        'votre intention ou de vos données auprès du responsable de votre équipe ou du '
        'responsable paroissial ; la demande est honorée dans les meilleurs délais. Des '
        'traces techniques minimales (date, session) peuvent être conservées pour la '
        'sécurité de l&#8217;espace.'
        '</div></details>'
        '<details><summary>🍪 Politique de cookies</summary>'
        '<div class="pdr-corps">L&#8217;Espace de Prière ne dépose aucune trace '
        'publicitaire : seuls quelques réglages strictement nécessaires à ta visite '
        'restent dans ton navigateur — jamais ailleurs.</div></details>'
        '</div>'
        '<div class="pdr-col pdr-col-milieu">'
        + _logo_pied +
        '<div class="pdr-nom">LES ÉQUIPES DU ROSAIRE</div>'
        '<div class="pdr-dio">DIOCÈSE DE GRAND-BASSAM</div>'
        # v7.9.16 — la ligne paroisse porte son libellé : « 🕯️ Paroisse : Nom »
        + ('<div class="pdr-par">🕯️ Paroisse : ' + html.escape(str(_nom_par)) + '</div>' if _nom_par else '') +
        _contact_html +
        # v7.9.19 — l'adresse de la chaîne YouTube, comme une adresse du Mouvement
        _yt_html +
        '</div>'
        '<div class="pdr-col pdr-col-droite">'
        '<ul class="pdr-menu">' + _menu_pied + '</ul>'
        '</div>'
        '</div>'
        '<div class="pdr-bas">'
        '<div class="pdr-cop">© 2026 Les Équipes du Rosaire — Diocèse de Grand-Bassam</div>'
        + _fb_html +
        '</div>'
        '</footer>', unsafe_allow_html=True)


# ====================================================================
# PAGE PRINCIPALE
# ====================================================================
def show_espace_membre(matloc_membre=None):
    """Point d'entrée de l'Espace de Prière (v7.9.3) : le corps de page
    (_corps_espace_membre, code d'origine inchangé), PUIS le pied de page
    du site — présent sur toutes les pages, y compris le livre ouvert.
    v7.9.10 — le pied de page connaît le fidèle (paroisse + responsable) :
    v7.9.19 — la carte vidéo s'ouvre JUSTE AVANT le pied de page, sur
    toutes les pages de l'Espace de Prière (demande : « s'il doit
    s'ouvrir, c'est juste avant le pied de page »).
    v7.9.20 — elle porte son nom d'aujourd'hui : la vidéo à la demande.
    v7.10.1 — la vidéo NE SUIT PLUS le lecteur partout : elle ne s'ouvre
    plus comme un second pied de page sous la méditation et la prière des
    intentions. Elle retrouve sa place de carte d'accueil : visible sur la
    page d'arrivée (« 🏠 Actualités »), absente du livre ouvert et des
    autres pages — la prière reste toute à la prière."""
    _corps_espace_membre(matloc_membre)
    # v7.10.1 — accueil SEULEMENT : ni livre ouvert (dizaine, livret), ni
    # autre rubrique (Rosaire, Thème, Galerie, Archives, évènements…).
    if not (st.session_state.get("diz_ouvert") or st.session_state.get("flt_ouvert")):
        try:
            _rub_v = _lire_nav(RUBRIQUES_MEMBRE if matloc_membre
                               else RUBRIQUES_PUBLIC)[0]
        except Exception:
            _rub_v = "🏠 Actualités"
        if _rub_v == "🏠 Actualités":
            _carte_vidéo_a_la_demande()
    _render_pied_de_page(matloc_membre)


def _corps_espace_membre(matloc_membre=None):
    # v7.8 — lien profond « Ouvrir le livret » (?flt=1&fa=&fm=) AVANT tout
    # affichage : il positionne la session et force un rerun propre.
    _traiter_lien_profond_livret()
    livre_ouvert = (st.session_state.get("diz_ouvert", False)
                    or st.session_state.get("flt_ouvert", False))

    _render_theme(compact=livre_ouvert)

    # QR signé ?p=ID — AVANCÉ en tête : le contexte paroissial doit être
    # connu AVANT le comptage des bandes et l'entête.
    if "paroisse_origine" not in st.session_state:
        p_raw = st.query_params.get("p")
        if isinstance(p_raw, list):
            p_raw = p_raw[0] if p_raw else None
        if p_raw:
            try:
                p_int = int(p_raw)
                if c.execute("SELECT id FROM paroisses WHERE id=?", (p_int,)).fetchone():
                    st.session_state["paroisse_origine"] = p_int
            except (ValueError, TypeError):
                pass

    # v7.6.1 — le dimensionnement est assuré par _mesure_entete (mesure
    # autocorrigée). L'ancien comptage n'est conservé QUE pour le
    # diagnostic (&debug=1), désormais avec le BON contexte paroissial.
    if st.query_params.get("debug") == "1":
        _compter_bandes(membre=bool(matloc_membre),
                        pid=st.session_state.get("paroisse_origine"))
    _mesure_entete("entete")

    # v7.6 : les liens du menu naviguent dans l'onglet courant
    _liens_meme_onglet("nav")

    # v7.6.9 — MODE ÉCOUTE DÉDIÉ (?musique=1) : page-lecteur seule, pensée pour
    # être ouverte dans un 2e onglet du navigateur. La musique y joue en continu
    # pendant que l'espace est parcouru dans le premier onglet.
    if st.query_params.get("musique") == "1":
        _render_theme(compact=True)
        st.markdown('<style>.block-container { padding-top: 2rem !important; }</style>', unsafe_allow_html=True)
        st.markdown("<div style=\"background:linear-gradient(135deg,#1A237E 0%,#283593 100%);"
                    " padding:14px; border-radius:15px; text-align:center; margin:10px;"
                    " border:2px solid #FFD700;\">"
                    "<div style=\"color:#FFD700 !important; font-weight:bold;\">🎧 Onglet d’écoute dédié</div>"
                    "<div style=\"color:#e8eaf6 !important; font-size:0.85rem; margin-top:4px;\">"
                    "Lancez la musique, puis « ◀️ Revenir à l’appli » : elle continue et vous suit de page en page. 📿🎶</div></div>",
                    unsafe_allow_html=True)
        _render_page_archives_audios(pid=st.session_state.get("paroisse_origine"))
        return

    # v7.8.9 — MINI-BARRE COMPAGNON : dès qu'une musique a été lancée, elle
    # suit le visiteur sur TOUTES les pages de l'Espace de Prière (accueil,
    # 📿 Rosaire chez les Équipiers, livret, archives…) — reprise automatique
    # là où elle s'était arrêtée. Ne rend RIEN sans lecture récente.
    _render_mini_lecteur(pid=st.session_state.get("paroisse_origine"))

    msg_ok = st.session_state.pop("flash_success", None)
    if msg_ok:
        st.success(msg_ok)
    msg_warn = st.session_state.pop("flash_warning", None)
    if msg_warn:
        st.warning(msg_warn)

    # ================= ÉTAT 1 : VUE PUBLIQUE =================
    if not matloc_membre:
        # v7.6 : compteur fusionné — 1 visite = 1 ARRIVÉE (les navigations
        # internes portent &nav=1). Journal missionnaire si QR signé.
        if "nav" not in st.query_params and "visite_communaute" not in st.session_state:
            st.session_state["visite_communaute"] = True
            compter_visite("communautaire")
            _origine = st.session_state.get("paroisse_origine")
            if _origine:
                try:
                    c.execute("INSERT INTO visites_paroisse (paroisse_id, date_visite) VALUES (?, ?)",
                              (_origine, date.today().isoformat()))
                    commit_and_sync()
                except Exception:
                    try:
                        c.execute("""CREATE TABLE IF NOT EXISTS visites_paroisse (
                                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                                        paroisse_id INTEGER,
                                        date_visite TEXT)""")
                        c.execute("INSERT INTO visites_paroisse (paroisse_id, date_visite) VALUES (?, ?)",
                                  (_origine, date.today().isoformat()))
                        commit_and_sync()
                    except Exception:
                        pass

        rub, sub = _lire_nav(RUBRIQUES_PUBLIC)
        pid_pub = _pid_contexte()
        _render_header(masquer_bandes=livre_ouvert,
                       rubriques=(None if livre_ouvert else RUBRIQUES_PUBLIC),
                       rub_act=rub, sub_act=sub, pid=pid_pub)
        # Accueil personnalisé si arrivée par QR paroissial signé
        _origine = st.session_state.get("paroisse_origine")
        if _origine:
            _nom_par = c.execute("SELECT nom FROM paroisses WHERE id=?", (_origine,)).fetchone()
            if _nom_par:
                st.caption("🕊️ Bienvenue ! Vous découvrez cet espace via la communauté **"
                           + _nom_par[0] + "** — toute la chaîne de prière du diocèse vous accompagne.")

        if livre_ouvert:
            if st.session_state.get("flt_ouvert"):
                # v7.8 — livret mensuel en autonomie (logo + carte espace)
                _render_feuillet_autonome()
                return
            _render_dizaine_du_jour(est_membre=False)
            return

        # v7.9.3 — la page ouverte commence EN HAUT de l'écran (feuillets)
        _scroll_top_si_nouvelle_page("pub", rub, sub)

        # v7.7.2 — le badge de bienvenue n'apparaît QUE sur l'accueil
        if rub == "🏠 Actualités":
            st.markdown('<div style="background:linear-gradient(135deg,#f3e5f5 0%,#e8eaf6 100%); padding:20px; border-radius:15px; text-align:center; margin:15px 10px; box-shadow:0 4px 12px rgba(0,0,0,0.35); border:1px solid #d1c4e9;">'
                        '<div style="color:#4A148C; font-size:1.3rem; font-weight:bold;">Bienvenue dans votre Espace communautaire 🕊️</div>'
                        '<div style="color:#4527a0; font-size:0.9rem; margin-top:6px;">📿 Prières • Méditations • Dizaine du jour — Diocèse de Grand-Bassam · ' + _VERSION_APPLI + '</div>'
                        '<div style="color:#6a1b9a; font-size:0.85rem; margin-top:8px;">📲 Garde-la sous la main : pose le raccourci depuis la '
                        '<a href="/app/static/install_rosaire.html" target="_self" style="color:#4A148C; font-weight:bold;">page d\'installation</a>'
                        ' — menu ⋮ → «&nbsp;Ajouter à l\'écran d\'accueil&nbsp;» (rien à y attendre, elle porte déjà le bon visage).</div></div>', unsafe_allow_html=True)

        if rub == "📿 Rosaire":
            if sub == "Le Rosaire thématique":
                _render_page_livret_thematique()
            else:
                _render_page_rosaire_eyquem()
        elif rub == "📖 Archives":
            if sub == "📖 Méditations":
                _render_page_archives_textes("meditation", "Aucune méditation disponible.", pid=pid_pub)
            elif sub == "🎵 Musiques":
                _render_page_archives_audios(pid=pid_pub)
            else:
                _render_page_archives_textes("priere", "Aucune prière publiée.", pid=pid_pub)
        elif rub == "🕯️ Thème":
            if sub == "🎓 Enseignements":
                _render_page_en_preparation("🎓", "Enseignements",
                                            "Cet espace accueillera les résumés des enseignements reçus, publiés par le diocèse. Il est en préparation.")
            elif sub == "💬 Discussions":
                _render_page_en_preparation("💬", "Discussions",
                                            "Cet espace accueillera les cadres de discussions thématiques. Il est en préparation.")
            else:
                _render_page_theme_ensemble(est_membre=False,
                                            paroisse_id=pid_pub)
        elif rub == "🖼️ Galerie +":
            # v7.9.1 — souvenirs (photos) et témoignages (grâces reçues).
            _render_page_galerie(sub)
        else:
            _depliant_mouvement(st.session_state.get("paroisse_origine"))
            # v7.9.3 — « 🙏 Vos intentions à une équipe » REMONTÉE : elle
            # précède désormais « 🕯️ Un jour, une dizaine » (et lui est
            # harmonisée). Le livre ouvert la masque pour garder l'écran
            # tout à la prière ; le CTA « Prier ma dizaine » reste opérationnel.
            if not st.session_state.get("diz_ouvert"):
                _render_intentions_equipes(pid=pid_pub)
            _render_dizaine_du_jour(est_membre=False)
            if st.session_state.get("diz_ouvert"):
                return
            _lien_theme_pub = ("?espace=1&nav=1&r=2"
                               + (f"&p={pid_pub}" if pid_pub else ""))
            _render_fil_actualites(pid=pid_pub, lien_theme=_lien_theme_pub)
            # v7.9.18 — les actualités sont rendues DANS le fil (voir
            # _render_fil_actualites) ; plus aucun appel séparé ici.
        return

    # ================= ÉTAT 2 : VUE MEMBRE =================
    matloc_membre = str(matloc_membre).upper().strip()

    membre = c.execute("""
        SELECT m.id, m.nom, m.prenom, m.matloc, m.whatsapp, m.date_adhesion, m.photo_path,
               m.numero_meditation, e.nom_equipe, p.nom, m.equipe_id, m.paroisse_id
        FROM membres m
        LEFT JOIN equipes e ON m.equipe_id = e.id
        LEFT JOIN paroisses p ON m.paroisse_id = p.id
        WHERE m.matloc=? AND m.statut='actif'
    """, (matloc_membre,)).fetchone()

    if not membre or len(membre) < 12:
        st.error("Identifiant inconnu ou membre inactif.")
        st.info("💡 Vous pouvez consulter l'espace public ci-dessous.")
        rub_pub, sub_pub = _lire_nav(RUBRIQUES_PUBLIC)
        _render_header(rubriques=RUBRIQUES_PUBLIC, rub_act=rub_pub, sub_act=sub_pub,
                       pid=st.session_state.get("paroisse_origine"))
        _render_fil_actualites(pid=st.session_state.get("paroisse_origine"),
                               lien_theme="?espace=1&nav=1&r=2")
        return

    # v7.6 : compteur membre — 1 visite = 1 ARRIVÉE (même sémantique)
    if "nav" not in st.query_params and "visite_membre" not in st.session_state:
        st.session_state["visite_membre"] = True
        compter_visite("membre")

    rub, sub = _lire_nav(RUBRIQUES_MEMBRE)
    pid_m = _pid_contexte(membre[11])
    _render_header(membre, matloc_membre, masquer_bandes=livre_ouvert,
                   rubriques=(None if livre_ouvert else RUBRIQUES_MEMBRE),
                   rub_act=rub, sub_act=sub, pid=pid_m)

    if livre_ouvert:
        if st.session_state.get("flt_ouvert"):
            # v7.8 — livret mensuel en autonomie (logo + carte espace)
            _render_feuillet_autonome()
            return
        _render_dizaine_du_jour(numero_meditation=membre[7], est_membre=True,
                                matloc=membre[3],
                                nom_membre=((membre[1] or "") + " " + (membre[2] or "")).strip(),
                                equipe_id=membre[10], paroisse_id=membre[11])
        return

    # v7.9.3 — la page ouverte commence EN HAUT de l'écran (feuillets)
    _scroll_top_si_nouvelle_page("mbr", rub, sub)

    with st.popover("👤 Mon profil"):
        if membre[6]:
            try: st.image(membre[6], width=130)
            except Exception: pass
        st.markdown(f"**{membre[1]} {membre[2]}**")
        st.caption(f"MatLoc : `{membre[3]}`")
        st.write(f"👥 Équipe : **{membre[8] or '—'}**")
        st.write(f"🏘️ Paroisse : **{membre[9] or '—'}**")
        st.write(f"💬 WhatsApp : {membre[4] or '—'}")
        st.write(f"📿 N° méditation : {membre[7] or '—'}")
        d_adh = safe_date(membre[5])
        st.write(f"📅 Adhésion : {d_adh.strftime('%d/%m/%Y') if d_adh else '—'}")

    # v7.7.2 — le badge de bienvenue n'apparaît QUE sur l'accueil
    if rub == "🏠 Actualités":
        st.markdown('<div style="background:linear-gradient(135deg,#f3e5f5 0%,#e8eaf6 100%); padding:20px; border-radius:15px; text-align:center; margin:6px 10px; box-shadow:0 4px 12px rgba(0,0,0,0.35); border:1px solid #d1c4e9;">'
                    '<div style="color:#4A148C; font-size:1.3rem; font-weight:bold;">Bienvenue ' + html.escape(membre[2]) + ' 🕊️</div>'
                    '<div style="color:#4527a0; font-size:0.9rem; margin-top:6px;">Votre espace personnel — priez, participez, restez connecté(e) · ' + _VERSION_APPLI + '</div>'
                    '<div style="color:#6a1b9a; font-size:0.85rem; margin-top:8px;">📲 Garde-le sous la main : pose le raccourci depuis la '
                    '<a href="/app/static/install_rosaire.html?espace=1&matloc=' + urllib.parse.quote(str(matloc_membre)) + '" target="_self" style="color:#4A148C; font-weight:bold;">page d\'installation</a>'
                    ' — menu ⋮ → «&nbsp;Ajouter à l\'écran d\'accueil&nbsp;».</div></div>', unsafe_allow_html=True)

    if rub == "📅 Mes évènements":
        if membre[10] is None:
            st.info("Vous n'êtes rattaché(e) à aucune équipe pour le moment.")
        else:
            st.markdown("### 📅 Mes prochains évènements")
            try:
                evts = c.execute('''
                    SELECT e.id, e.date_evenement, e.type_evenement, e.lieu,
                           (SELECT statut FROM suivi_presences WHERE membre_id=? AND evenement_id=e.id)
                    FROM evenements e
                    JOIN evenement_equipes ee ON e.id = ee.evenement_id
                    WHERE ee.equipe_id = ? AND e.date_evenement >= ?
                    ORDER BY e.date_evenement ASC
                ''', (membre[0], membre[10], date.today().isoformat())).fetchall()
            except Exception:
                evts = []
                st.warning("📅 La liste des évènements n'est pas disponible pour le moment.")

            if not evts:
                st.success("✅ Aucun événement à venir. Profitez de ce temps de repos !")
            else:
                for evt in evts:
                    d = safe_date(evt[1])
                    if not d:
                        continue
                    delta = (d - date.today()).days
                    delai = "🔴 Aujourd'hui !" if delta == 0 else "🟠 Demain" if delta == 1 else f"📅 Dans {delta} jours"
                    icone = {"Prière mensuelle": "🧎", "Prière commune": "🙏", "Prière spéciale": "✨",
                             "Pèlerinage": "🚶‍♂️", "Réunion": "🤝"}.get(evt[2], "📅")

                    statut = evt[4]
                    marqueur = "✅ " if statut in ('physique', 'spirituel') else ""

                    with st.expander(f"{marqueur}{icone} {evt[2]} — {d.strftime('%d/%m/%Y')} ({delai})",
                                     expanded=(delta <= 1)):
                        st.write(f"📍 {evt[3] or 'Lieu à définir'}")

                        if statut == 'physique':
                            st.success("✅ Votre réponse de communion : Présent(e) physiquement")
                        elif statut == 'spirituel':
                            st.success("🟡 Votre réponse de communion : Présent(e) spirituellement")
                        else:
                            st.caption("📿 Réponse de Communion — indiquez comment vous vous joignez à nous :")

                        c1, c2 = st.columns(2)
                        with c1:
                            if st.button("🟢 Présent physiquement", key=f"rsp_p_{evt[0]}",
                                         width="stretch",
                                         type="primary" if statut != 'physique' else "secondary"):
                                _enregistrer_presence(membre[0], evt[0], 'physique')
                        with c2:
                            if st.button("🟡 Présent spirituellement", key=f"rsp_s_{evt[0]}",
                                         width="stretch",
                                         type="primary" if statut != 'spirituel' else "secondary"):
                                _enregistrer_presence(membre[0], evt[0], 'spirituel')

    elif rub == "📿 Rosaire":
        if sub == "Le Rosaire thématique":
            _render_page_livret_thematique()
        else:
            _render_page_rosaire_eyquem()

    elif rub == "📖 Archives":
        if sub == "📖 Méditations":
            _render_page_archives_textes("meditation", "Aucune méditation disponible.", pid=pid_m)
        elif sub == "🎵 Musiques":
            _render_page_archives_audios(pid=pid_m)
        else:
            _render_page_archives_textes("priere", "Aucune prière publiée.", pid=pid_m)

    elif rub == "🕯️ Thème":
        if sub == "🎓 Enseignements":
            _render_page_en_preparation("🎓", "Enseignements",
                                        "Cet espace accueillera les résumés des enseignements reçus, publiés par le diocèse. Il est en préparation.")
        elif sub == "💬 Discussions":
            _render_page_en_preparation("💬", "Discussions",
                                        "Cet espace accueillera les cadres de discussions thématiques. Il est en préparation.")
        else:
            _render_page_theme_ensemble(est_membre=True, matloc=membre[3],
                                        nom_membre=((membre[1] or "") + " "
                                                    + (membre[2] or "")).strip(),
                                        equipe_id=membre[10],
                                        paroisse_id=membre[11])

    elif rub == "🖼️ Galerie +":
        # v7.9.1 — souvenirs (photos) et témoignages (grâces reçues),
        # identiques pour les membres et les visiteurs.
        _render_page_galerie(sub)

    else:
        _render_dizaine_du_jour(numero_meditation=membre[7], est_membre=True,
                                matloc=membre[3],
                                nom_membre=((membre[1] or "") + " " + (membre[2] or "")).strip(),
                                equipe_id=membre[10], paroisse_id=membre[11])
        if st.session_state.get("diz_ouvert"):
            return
        _lien_theme_m = ("?espace=1&matloc=" + str(matloc_membre)
                         + (f"&p={pid_m}" if pid_m else "") + "&nav=1&r=1")
        _render_fil_actualites(pid=pid_m, lien_theme=_lien_theme_m,
                               equipe_membre_id=membre[10],
                               auteur_nom=((membre[1] or "") + " " + (membre[2] or "")).strip(),
                               intentions=False)  # v7.8.15 : retiré côté Membre
        # v7.9.18 — les actualités sont rendues DANS le fil (voir
        # _render_fil_actualites) ; plus aucun appel séparé ici.

