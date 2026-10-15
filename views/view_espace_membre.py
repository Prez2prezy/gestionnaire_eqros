# ====================================================================
# view_espace_membre.py — VERSION 7.8.2 (retour en haut + alerte + archives)
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
# Marqueurs : Ctrl+F → "VERSION 7.6", "_liens_meme_onglet", "· v7.6".
# ====================================================================
import os
import re
import html
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
try:
    from streamlit import iframe as _st_iframe

    def _comp_html(body, height=None):
        _h = height if isinstance(height, int) and height > 0 else 1
        return _st_iframe(body, height=_h)
except (ImportError, AttributeError):
    try:
        from streamlit.components.v1 import html as _comp_html
    except ImportError:
        def _comp_html(body, height=None):
            return None
from database import c, commit_and_sync
from services import safe_date, compter_visite, lien_whatsapp
from mysteres import get_mysteres_du_jour, COULEURS_TYPES, MYSTERES, get_mystere, get_theme_actif, get_sous_theme_du_mois, get_lien_mystere


# ====================================================================
# NAVIGATION
# ====================================================================
RUBRIQUES_MEMBRE = ["🏠 Actualités", "🕯️ Thème", "📿 Rosaire", "📅 Mes évènements", "📖 Archives"]
RUBRIQUES_PUBLIC = ["🏠 Actualités", "📿 Rosaire", "🕯️ Thème", "📖 Archives"]
SOUS_RUBRIQUES = {
    "🕯️ Thème": ["🔭 Vue d'ensemble", "🎓 Enseignements", "💬 Discussions"],
    "📿 Rosaire": ["Le Rosaire chez les Équipiers", "Le Rosaire thématique"],
    "📖 Archives": ["🙏 Prières", "📖 Méditations", "🎵 Musiques"],
}

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
@st.cache_data
def _logo_base64():
    try:
        with open(os.path.join("images", "logo.png"), "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
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
        "var as=d.querySelectorAll('.menu-ligne a,.mob-panneau a');var n=0;"
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
    .logo-bloc { width: 190px; text-align: center; }
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
        .logo-bloc { width: 150px; }
        .block-container { padding-top: """ + str(secours_2) + """px !important; }
        [data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; }
        [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] { min-width: 0 !important; }
    }
    @media (max-width: 360px) {
        .logo-bloc { width: 138px; }
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
    """Sections du feuillet ayant un contenu, triées par ordre (blindé)."""
    try:
        rows = c.execute("""SELECT ordre, titre, contenu, lecteur, image_url
                            FROM feuillet_sections
                            WHERE annee_debut=? AND mois=? ORDER BY ordre""",
                         (annee_debut, mois_pastoral)).fetchall()
    except Exception:
        return []
    return [s for s in rows if s[2]]


def _annee_civile_feuillet(annee_debut, mois_pastoral):
    """Mois pastoral → année civile (sept.→déc. = année de départ ; janv.→août = +1)."""
    return annee_debut if mois_pastoral <= 4 else annee_debut + 1


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
    _pluriel = "page" if len(sections) == 1 else "pages"
    _lignes = "".join(
        '<div class="cp-para" style="margin:2px 0;">📖 <b>' + str(s[0]) + "</b> — "
        + html.escape(s[1] or "") + "</div>" for s in sections)
    st.markdown(_carte_priere(
        _trait_debut_page()
        + '<div class="cp-titre" style="text-align:center;">Mois de '
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
        st.session_state["flt_page"] = 0
        st.session_state["flt_ouvert"] = True
        st.session_state.pop("diz_ouvert", None)
        st.rerun()


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

    # ---------- SOMMAIRE (page -1) ----------
    if idx < 0:
        _lignes = "".join(
            '<div class="cp-para" style="margin:2px 0;">📖 <b>' + str(s[0]) + "</b> — "
            + html.escape(s[1] or "") + "</div>" for s in sections)
        st.markdown(_carte_priere(
            _trait_debut_page()
            + '<div class="cp-titre" style="text-align:center;">' + _entete_livret + "</div>"
            + '<div class="cp-accent" style="--c:#1A237E;">Sommaire du feuillet</div>'
            + _lignes),
            unsafe_allow_html=True)
        for _i, _s in enumerate(sections):
            if st.button("▶ " + str(_s[0]) + ". " + (_s[1] or "Section " + str(_s[0])),
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
    _ligne = list(sections[idx]) + [None] * 5
    ordre, titre, contenu = _ligne[0], _ligne[1], _ligne[2]
    image_url = _ligne[4]
    _titre_page = titre or ("Section " + str(ordre))

    if autonome:
        # v7.8-e — le titre de la page en lecture reste TOUJOURS visible en haut
        st.markdown('<div class="flt-barre"><div class="flt-barre-titre">📖 '
                    + html.escape(_titre_page) + "</div></div>", unsafe_allow_html=True)

    _img_html = ""
    if image_url and str(image_url).startswith("http"):
        _img_html = '<img src="' + str(image_url) + '" alt="" class="cp-photo">'
    st.markdown(_carte_priere(_trait_debut_page()
                              + '<div class="cp-titre" style="text-align:center;">'
                              + html.escape(_titre_page) + "</div>"
                              + _img_html + _rendre_texte_priere(contenu)),
                unsafe_allow_html=True)
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
    if not _prec:
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
    st.markdown('<div class="cp-accent" style="--c:#1A237E; margin-top:22px;">'
                "📚 Les feuillets précédents</div>", unsafe_allow_html=True)
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


def _render_page_theme_ensemble():
    """🕯️ Thème → Vue d'ensemble — v7.7.7 : langage du dépliant (bannière
    bleu-or, badge d'étape, carte jaune verrouillée, trait fin)."""
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


def _render_page_rosaire_eyquem():
    """📿 Rosaire → Le Rosaire complet en Équipe (v7.7.4)."""
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
                               _diz_txt("🕯️ Vierge Marie, mère de Dieu, intercède : " + _l.strip().lstrip("*").strip(), "#1a1a1a")
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
                '<div style="color:#9fa6d8 !important; font-size:0.85rem;">📿 LE ROSAIRE SELON LE THÈME DE L’ANNÉE · v7.6</div>'
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
            if p[2] and p[2].startswith("http"):
                st.markdown(f'<img src="{p[2]}" alt="" class="rub-photo">', unsafe_allow_html=True)
            if texte:
                st.markdown(texte, unsafe_allow_html=True)
            if url_pdf:
                _render_pdf_inline(url_pdf)


def _render_page_archives_audios(pid=None):
    """Archives Musiques — LECTEUR COMPLET (playlist, ⏮️⏭️, 🔀, 🔁, sélection).
    Les MP3 en lien direct alimentent la playlist ; les liens YouTube
    s'affichent séparément. LOT C5 : filtre par contexte paroissial."""
    cond, prm = ("AND (paroisse_cible IS NULL OR paroisse_cible = ?)", [pid]) if pid \
        else ("AND paroisse_cible IS NULL", [])
    audios = c.execute(f"""SELECT titre, fichier_url FROM espace_spirituel
                          WHERE type_contenu='audio' {cond} ORDER BY date_publication DESC, id DESC""",
                       prm).fetchall()
    if not audios:
        st.info("Aucun fichier audio.")
        return
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

    # v7.7 — bouton masqué sur la page d'écoute elle-même (sinon il
    # réapparaissait dans l'onglet d'écoute, ce qui est inutile).
    if st.query_params.get("musique") != "1":
        _lien_ecoute = "?espace=1&musique=1" + (f"&p={pid}" if pid else "")
        st.markdown('<div style="text-align:center; margin:0 0 14px 0;">'
                    '<a href="' + _lien_ecoute + '" target="_blank" '
                    'style="display:inline-block; background:#4527a0; color:#ffffff;'
                    ' padding:10px 22px; border-radius:30px; font-weight:bold; text-decoration:none;">'
                    '🎧 Ouvrir l’onglet d’écoute dédié</a></div>',
                    unsafe_allow_html=True)

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

    if not pistes and not videos_yt:
        st.warning("Les URL des fichiers doivent commencer par http:// ou https://")


def _render_dizaine_du_jour(numero_meditation=None, est_membre=False):
    """La dizaine du jour — UNIQUEMENT sur l'Accueil. Livre = page autonome."""
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
        st.markdown(
            f'<div style="background:linear-gradient(135deg,#1A237E 0%,#283593 100%);'
            f' padding:24px; border-radius:15px; text-align:center; margin:10px;'
            f' border:2px solid #FFD700;">'
            f'<div style="color:#FFD700; font-size:1.3rem; font-weight:bold;">📿 Ta dizaine du jour</div>'
            f'<div style="display:flex; justify-content:center; gap:10px; margin:18px 0;">{pastilles}</div>'
            f'<div style="color:#ffffff; font-size:1rem;">{html.escape(titres)}</div>'
            f'<div style="color:#9fa6d8; font-size:0.85rem; margin-top:8px;">'
            f'N° méd. {num} — {date.today().strftime("%d/%m/%Y")} · v7.6</div>'
            f'</div>', unsafe_allow_html=True)
        _scroll_top("cov")
        if st.button("📿 Égrener la dizaine", key="diz_commencer", width="stretch", type="primary"):
            st.session_state["diz_ouvert"] = True
            st.session_state["diz_page"] = 0
            st.session_state.pop("flt_ouvert", None)  # v7.8 : un seul livre ouvert à la fois
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

    # --- Navigation : ON NE RECULE PAS quand on égrène une dizaine ☺️ ---
    c_av, c_term = st.columns(2)
    with c_av:
        if idx < len(pages) - 1:
            if st.button("Suivant ▶", key=f"diz_next_{idx}", width="stretch", type="primary"):
                st.session_state["diz_page"] = idx + 1
                st.rerun()
        else:
            if st.button("✕ Terminer", key=f"diz_end_{idx}", width="stretch"):
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


def _render_coin_affiche():
    lignes = []
    erreur_sql = None
    try:
        lignes = c.execute("""SELECT type_evenement, date_evenement, lieu, affiche_url, video_url FROM evenements
                              WHERE (affiche_url IS NOT NULL OR video_url IS NOT NULL) AND date_evenement >= ?
                              ORDER BY date_evenement ASC LIMIT 5""",
                          (date.today().isoformat(),)).fetchall()
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
            prochain = c.execute("""SELECT type_evenement, date_evenement, lieu FROM evenements
                                    WHERE date_evenement >= ? ORDER BY date_evenement ASC LIMIT 1""",
                                 (date.today().isoformat(),)).fetchone()
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
        + '</b>.<br>La dizaine du jour vous attend juste en dessous de ce dépliant : entrez votre jour de naissance '
        'et priez avec nous. 🕊️</div>' + _bouton + '</div>')
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
    """📰 Actualités du diocèse (publications simples : affiche +/ou BA).
    5 dernières, les plus récentes d'abord.
    LOT C5 : ne montre que le diocèse (cible NULL) + la paroisse du contexte."""
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
    st.markdown('<h3 style="font-family:Georgia, serif;">📰 Actualités du diocèse</h3>', unsafe_allow_html=True)
    for a in lignes:
        with st.expander("📰 " + (a[0] or "(sans titre)")):
            st.caption(f"Publié le {a[4] or '—'}")
            if a[2] and str(a[2]).startswith("http"):
                st.markdown(f'<img src="{a[2]}" alt="" class="rub-photo">', unsafe_allow_html=True)
            if a[1]:
                st.markdown(a[1].replace("\n", "  \n"), unsafe_allow_html=True)
            if a[3] and str(a[3]).startswith("http"):
                try:
                    st.video(a[3], width="stretch")
                except Exception:
                    st.markdown(f"🎬 [Voir la vidéo]({a[3]})")


def _alerte_feuillet_fil(lien_theme=None):
    """v7.8-h · v7.8.2-h — Alerte « nouveau feuillet » en tête du fil d'actualité.
    Visible 45 jours après la publication (couvre un mois pastoral complet) ;
    le clic mène à 🕯️ Thème → 🔭 Vue d'ensemble, devant la vitrine du feuillet
    (Sommaire du feuillet publié) ; « 📌 Marquer comme lue » la masque pour
    la session en cours."""
    try:
        pub = c.execute("""SELECT annee_debut, mois, numero, date_publication
                           FROM feuillets_publications
                           ORDER BY date_publication DESC, id DESC LIMIT 1""").fetchone()
    except Exception:
        return
    if not pub:
        return
    _dpub = safe_date(pub[3])
    if not _dpub or (date.today() - _dpub).days > 45:
        return
    _cle = f"{pub[0]}-{pub[1]}"
    if st.session_state.get("alerte_feuillet_lue") == _cle:
        return
    _lien = ""
    if lien_theme:
        # v7.8.2-h — le clic mène à 🕯️ Thème → 🔭 Vue d'ensemble (vitrine :
        # Sommaire du feuillet, puis « Ouvrir le livret » pour la lecture).
        _lien = ('<a href="' + lien_theme + "&s=0"
                 + '" target="_self" style="display:inline-block; background:#4527a0; '
                 'color:#ffffff; padding:10px 24px; border-radius:30px; font-weight:bold; '
                 'text-decoration:none; margin-top:10px;">📖 Voir le feuillet du mois</a>')
    st.markdown(
        '<div class="rub-carte" style="border:2px solid #FFD700; padding:18px; '
        'text-align:center; margin:15px 10px 6px 10px;">'
        '<div style="color:#FFD000 !important; font-weight:bold; font-size:1.05rem;">'
        '📖 Nouveau : le feuillet mensuel de prière N° ' + str(pub[2] or pub[1])
        + " est disponible !</div>"
        '<div style="color:#e8eaf6 !important; font-size:0.9rem; margin-top:6px;">'
        "Mois de " + MOIS_PASTORAL_NOMS[pub[1] - 1] + " "
        + str(_annee_civile_feuillet(pub[0], pub[1])) + " · publié le "
        + _dpub.strftime("%d/%m/%Y") + "</div>" + _lien + "</div>",
        unsafe_allow_html=True)
    if st.button("📌 Marquer l'alerte comme lue", key="alerte_feuillet_lu_btn"):
        st.session_state["alerte_feuillet_lue"] = _cle
        st.rerun()


def _render_fil_actualites(pid=None, lien_theme=None):
    """v7.6 — fil du jour BLINDÉ : la ligne est complétée à 5 cases avant
    tout accès par index. LOT C5 : dernière publication VISIBLE du contexte.
    v7.8-h : une alerte « 📖 Nouveau feuillet » couronne le fil quand le
    diocèse vient de publier le feuillet mensuel de prière."""
    _alerte_feuillet_fil(lien_theme)

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

        if ligne[3] and str(ligne[3]).startswith("http"):
            st.markdown(f'<img src="{ligne[3]}" alt="" class="rub-photo">', unsafe_allow_html=True)

        texte_html = texte.replace("\n", "<br>")
        st.markdown(
            f'<div class="rub-carte" style="padding:20px; text-align:center; margin:15px 10px;">'
            f'<div class="rub-carte-titre" style="font-size:1.15rem; border-bottom:1px solid #27306b; padding-bottom:8px; margin-bottom:12px;">{etiquette} - {html.escape(ligne[1] or "")}</div>'
            f'<div class="rub-carte-txt" style="font-size:0.98rem; line-height:1.7; text-align:left;">{texte_html}</div>'
            f'</div>', unsafe_allow_html=True)

        if url_pdf:
            _render_pdf_inline(url_pdf)
    else:
        st.info("Aucun contenu spirituel n'a encore été publié.")

    _render_coin_affiche()


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


# ====================================================================
# PAGE PRINCIPALE
# ====================================================================
def show_espace_membre(matloc_membre=None):
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
                    "Laissez cet onglet ouvert : la musique continue pendant que vous priez dans l’autre onglet. 📿</div></div>",
                    unsafe_allow_html=True)
        _render_page_archives_audios(pid=st.session_state.get("paroisse_origine"))
        return

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

        # v7.7.2 — le badge de bienvenue n'apparaît QUE sur l'accueil
        if rub == "🏠 Actualités":
            st.markdown('<div style="background:linear-gradient(135deg,#f3e5f5 0%,#e8eaf6 100%); padding:20px; border-radius:15px; text-align:center; margin:15px 10px; box-shadow:0 4px 12px rgba(0,0,0,0.35); border:1px solid #d1c4e9;">'
                        '<div style="color:#4A148C; font-size:1.3rem; font-weight:bold;">Bienvenue dans votre Espace communautaire 🕊️</div>'
                        '<div style="color:#4527a0; font-size:0.9rem; margin-top:6px;">📿 Prières • Méditations • Dizaine du jour — Diocèse de Grand-Bassam · v7.6</div></div>', unsafe_allow_html=True)

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
                _render_page_theme_ensemble()
        else:
            _depliant_mouvement(st.session_state.get("paroisse_origine"))
            _render_dizaine_du_jour(est_membre=False)
            if st.session_state.get("diz_ouvert"):
                return
            _lien_theme_pub = ("?espace=1&nav=1&r=2"
                               + (f"&p={pid_pub}" if pid_pub else ""))
            _render_fil_actualites(pid=pid_pub, lien_theme=_lien_theme_pub)
            _render_actualites(pid=pid_pub)
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
        _render_dizaine_du_jour(numero_meditation=membre[7], est_membre=True)
        return

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
                    '<div style="color:#4527a0; font-size:0.9rem; margin-top:6px;">Votre espace personnel — priez, participez, restez connecté(e) · v7.6</div></div>', unsafe_allow_html=True)

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
            _render_page_theme_ensemble()

    else:
        _render_dizaine_du_jour(numero_meditation=membre[7], est_membre=True)
        if st.session_state.get("diz_ouvert"):
            return
        _lien_theme_m = ("?espace=1&matloc=" + str(matloc_membre)
                         + (f"&p={pid_m}" if pid_m else "") + "&nav=1&r=1")
        _render_fil_actualites(pid=pid_m, lien_theme=_lien_theme_m)
        _render_actualites(pid=pid_m)

