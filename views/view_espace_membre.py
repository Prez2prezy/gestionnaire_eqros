import os
import re
import html
import base64
import streamlit as st
from datetime import date
from database import c, commit_and_sync
from services import safe_date
from mysteres import get_mysteres_du_jour, COULEURS_TYPES


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
    if not contenu or ('cloudinary' not in contenu and 'data:application/pdf' not in contenu):
        return contenu, None
    m = PDF_URL_RE.search(contenu)
    url = m.group(1) if m else None
    return DIV_PDF_RE.sub('', contenu).strip(), url


def _render_theme():
    st.markdown("""<style>
    [data-testid="stHeader"] { display: none !important; }
    .stApp, [data-testid="stAppViewContainer"] { background-color: #0a0f2c !important; }
    .block-container { padding-top: 200px !important; padding-bottom: 4rem !important; }
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
    .stApp [data-testid="stVerticalBlockBorderWrapper"] { background-color: #121a45 !important; border: 1px solid #27306b !important; }
    .sticky-header { position: fixed; top: 0; left: 0; right: 0; z-index: 9999;
        background-color: #0a0f2c; border-bottom: 1px solid #27306b; padding: 12px 16px 0 16px; }
    .header-inner { max-width: 1200px; margin: 0 auto; display: flex; justify-content: space-between; align-items: flex-start; }
    .logo-bloc { width: 190px; text-align: center; }
    .logo-bloc img { width: 100%; height: auto; border-radius: 10px; display: block; margin: 0 auto; }
    .logo-titre-svg { display: block; width: 100%; margin-top: 6px; }
    .stApp a.bouton-profil { background-color: #4527a0 !important; color: #ffffff !important; padding: 10px 18px;
        text-decoration: none; border-radius: 30px; font-weight: bold; font-size: 0.9rem; display: inline-block; white-space: nowrap; }
    .stApp a.bouton-profil:hover { background-color: #5e35b1 !important; color: #ffffff !important; }
    .bande-defilante { overflow: hidden; white-space: nowrap;
        background: linear-gradient(90deg, #1a2150, #27306b);
        border-top: 1px solid #27306b; }
    .bande-defilante-inner { display: inline-block; padding: 8px 0; white-space: nowrap;
        color: #ffe082 !important; font-weight: 600; font-size: 0.9rem;
        animation: defilement 30s linear infinite; }
    .bande-defilante:hover .bande-defilante-inner { animation-play-state: paused; }
    @keyframes defilement { 0% { transform: translateX(100vw); } 100% { transform: translateX(-100%); } }
    @media (prefers-reduced-motion: reduce) {
        .bande-defilante-inner { animation: none; padding: 8px 15px; }
    }
    .stApp .event-flyer { background: #121a45; border-radius: 15px; margin: 0 10px 15px 10px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.4); overflow: hidden; border: 1px solid #27306b; }
    .stApp .postcard { background: linear-gradient(135deg, #f3e5f5 0%, #e8eaf6 100%) !important; padding: 20px;
        border-radius: 15px; text-align: center; margin: 15px 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.35); }
    @media (max-width: 640px) {
        .logo-bloc { width: 150px; }
        .block-container { padding-top: 165px !important; }
    }
    @media (max-width: 360px) {
        .logo-bloc { width: 138px; }
        .block-container { padding-top: 155px !important; }
    }
    </style>""", unsafe_allow_html=True)


def _bandes_defilantes_html(membre=False):
    """HTML des bandes défilantes pour l'entête fixe (retourne une chaîne)."""
    try:
        bandes = c.execute("""SELECT contenu_texte, fichier_url FROM espace_spirituel
                              WHERE type_contenu='annonce_defilante'
                              ORDER BY date_publication DESC, id DESC LIMIT 3""").fetchall()
    except Exception:
        return ""
    morceaux = []
    for texte, cible in bandes:
        if cible == 'membre' and not membre:
            continue
        if not texte:
            continue
        duree = max(15, min(60, len(texte) // 2))
        texte_html = html.escape(texte)
        morceaux.append(
            f'<div class="bande-defilante"><div class="bande-defilante-inner" style="animation-duration:{duree}s;">'
            f'📻 {texte_html} &nbsp;&nbsp;📻 {texte_html}</div></div>')
    return "".join(morceaux)


def _render_header(membre=None, matloc=None):
    """Entête FIGÉE : logo (largeur = texte) + bouton Mon profil + bandes défilantes.
    Tout le HTML sur UNE SEULE LIGNE (une ligne vide coupe un bloc markdown)."""
    logo_b64 = _logo_base64()
    logo_html = (f'<img src="data:image/png;base64,{logo_b64}" alt="Logo">'
                 if logo_b64 else '<div style="font-size:4rem;">📿</div>')

    titre_svg = ('<svg class="logo-titre-svg" viewBox="0 0 190 22" width="100%" height="22" '
                 'preserveAspectRatio="none" role="img" aria-label="Diocèse de Grand-Bassam">'
                 '<text x="95" y="17" text-anchor="middle" textLength="188" lengthAdjust="spacingAndGlyphs" '
                 'style="fill:#e8eaf6; font-weight:600; font-size:14px;">Diocèse de Grand-Bassam</text></svg>')

    # Badge identitaire côté droit : "Espace Membre" pour les membres connectés
    # (même pastille que "Espace communautaire" sur la vue publique).
    # Le profil, lui, est en popover natif juste sous l'entête (zéro rechargement).
    droite = ('<div style="padding-top:14px;">'
              '<div style="background-color:#4527a0; color:#ffffff;'
              ' padding:10px 18px; border-radius:30px; font-weight:bold;'
              ' font-size:0.9rem; display:inline-block; white-space:nowrap;">'
              'Espace Membre</div></div>')

    bandes_html = _bandes_defilantes_html(membre=bool(membre))

    st.markdown(
        f'<div class="sticky-header"><div class="header-inner">'
        f'<div class="logo-bloc">{logo_html}{titre_svg}</div>'
        f'{droite}'
        f'</div>{bandes_html}</div>', unsafe_allow_html=True)

# ====================================================================
# MA DIZAINE AU QUOTIDIEN — portage web de l'application Android
# © MOTIAN TOFFÉ Ahua Innocent — intégrée avec son autorisation
# ====================================================================
DIZ_INTRO1 = "Au Nom du Père, et du Fils et du Saint-Esprit! Amen!\n\nPRIÈRE D’ENTRÉE\n\nSeigneur Jésus, nous nous disposons à prier\nce Rosaire en communion avec la Vierge Marie.\nViens, Esprit Saint, remplis les cœurs de tes fidèles et allume en eux le feu de ton amour.\nDonne-nous la grâce de méditer profondément les mystères de ta vie, pour que, en les imitant, nous obtenions les promesses qu’ils renferment.\nPar le Christ, notre Seigneur. Amen.\n\nJE CROIS EN DIEU\n\nJe crois en Dieu, le Père Tout-Puissant, Créateur du ciel et de la terre.\nEt en Jésus-Christ, son Fils unique, Notre Seigneur, qui a été conçu du Saint-Esprit, est né de la Vierge Marie, a souffert sous Ponce Pilate, a été crucifié, est mort et a été enseveli, est descendu aux enfers, le troisième jour est ressuscité des morts, est monté aux cieux, est assis à la droite de Dieu le Père Tout-Puissant, d’où il viendra juger les vivants et les morts.\nJe crois en l’Esprit-Saint, à la Sainte Église catholique, à la communion des Saints, à la rémission des péchés, à la résurrection de la chair, à la vie éternelle.\nAmen."
DIZ_INTRO2 = "NOTRE PÈRE\n\nNotre Père, qui es aux cieux,\nque ton nom soit sanctifié,\nque ton règne vienne,\nque ta volonté soit faite\nsur la terre comme au ciel.\n\nDonne-nous aujourd’hui notre pain de ce jour. Pardonne-nous nos offenses, comme nous pardonnons aussi à ceux qui nous ont offensés. Et ne nous laisse pas entrer en tentation, mais délivre-nous du Mal. Amen!\n\n3 JE VOUS SALUE MARIE\n\nJe vous salue Marie, pleine de grâce,\nle Seigneur est avec vous. Vous êtes bénie entre toutes les femmes, et Jésus, le fruit de vos entrailles, est béni.\n\nSainte Marie, Mère de Dieu, priez pour nous pauvres pécheurs, maintenant et à l’heure de notre mort. Amen!\n\nGLORIA PATRI\n\nGloria patri, et Filio, et Spiritui Sancto.\nSicut erat in principio, et nunc, et semper, et in saecula saeculorum. Amen!"
DIZ_INTRO3 = "PRIÈRE À LA VIERGE DU PÈRE EYQUEM\n\nVers Toi je lève les yeux,\nSainte Mère de Dieu;\n\ncar je voudrais faire de ma maison,\nune maison où Jésus vienne, selon sa promesse,\nquand plusieurs se réunissent en son nom.\nTu as accueilli le message de l’ange comme\nun message venant de Dieu, et Tu as reçu,\nen raison de ta foi,\nl’incomparable grâce d’accueillir\nen Toi Dieu Lui-même.\nTu as ouvert aux bergers puis aux mages\nla porte de ta maison, sans que\nnul ne se sente gêné\npar sa pauvreté ou sa richesse.\n\nSois Celle qui chez moi reçoit.\n\nAfin que ceux qui ont besoin\nd’être réconfortés le soient;\nceux qui ont le désir de\nrendre grâce puissent le faire ;\nceux qui cherchent la paix la trouvent.\nEt que chacun reparte vers sa propre maison\navec la joie d’avoir rencontré Jésus lui-même,\nLui, le Chemin, la Vérité, la Vie.\nAmen!\n\nFrère Joseph EYQUEM, o.p.,\nFondateur des Équipes du Rosaire"
DIZ_OUTRO = "SALVE REGINA\n\nSalve Regina, Mater misericordiae;\nvita, dulcedo, et spes nostra salve.\nAd te clamamus, exsules filii Hevae.\nAd te suspiramus, gementes et flentes\nin hac lacrimarum valle.\nEia ergo, advocata nostra,\nillos tuos misericordes oculos ad nos converte;\nEt Iesum, benedictum fructum ventris tui,\nnobis, post hoc exsilium ostende.\nO Clemens, O pia, O dulcis, Virgo Maria.\n\nOra pro nobis, Sancta Dei Genitrix.\nUt digni efficiamur promissionibus Christi.\n\nPRIÈRE FINALE\n\nÔ Dieu, dont le Fils unique nous a acquis\npar sa vie, sa mort et sa résurrection\nles récompenses du salut éternel,\nnous vous supplions : faites que,\nméditant les mystères du très\nSaint Rosaire de\nla Bienheureuse Vierge Marie,\nnous imitions ce qu’ils contiennent\net obtenons ce qu’ils promettent.\nPar le Christ, notre Seigneur. Amen!\n\nÔ Marie, conçue sans péché!\nPriez pour nous qui avons recours à vous!\n\nÔ Marie, conçue sans péché!\nPriez pour nous qui avons recours à vous!\n\nÔ Marie, conçue sans péché!\nPriez pour nous qui avons recours à vous!\n\nAu Nom du Père, et du Fils et du Saint-Esprit! Amen!"


def _diz_txt(texte, couleur="#333333", taille="0.95rem", gras=False, centre=False):
    """Bloc de texte style inline (leçon : jamais de ligne vide dans un bloc HTML)."""
    txt_html = html.escape(texte).replace("\n", "<br>")
    poids = "bold" if gras else "normal"
    align = "center" if centre else "left"
    return (f'<div style="color:{couleur}; font-size:{taille}; font-weight:{poids};'
            f' text-align:{align}; line-height:1.7; margin:8px 0;">{txt_html}</div>')


def _render_dizaine_du_jour(numero_meditation=None, est_membre=False):
    """La dizaine du jour : membre = automatique via son numero_meditation (1-20) ;
    sympathisant (Espace communautaire) = saisie du numéro, comme dans l’APK."""
    st.markdown("---")

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
        # Sécurité : si une ancienne session avait stocké le champ sous forme de
        # texte, on purge la clé (changement de type du widget texte → numérique)
        if isinstance(st.session_state.get("diz_saisie"), str):
            st.session_state.pop("diz_saisie", None)
        jrnais = st.number_input("📿 Entrez votre jour de naissance (1 - 31)",
                                 min_value=0, max_value=31, value=0, step=1,
                                 key="diz_saisie",
                                 help="Seuls les chiffres sont acceptés. "
                                      "Votre numéro de méditation sera calculé automatiquement.")
        if jrnais == 0:
            return  # rien sélectionné encore → rien d'affiché
        # Conversion jour de naissance → numéro de méditation dans la chaîne
        num = jrnais - 20 if jrnais > 20 else jrnais

    mysteres_jour = get_mysteres_du_jour(num)
    if not mysteres_jour:
        return

    # Réinitialisation du livre si le numéro a changé
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
        titres = " • ".join(m["titre"].title() for m in mysteres_jour)
        st.markdown(
            f'<div style="background:linear-gradient(135deg,#1A237E 0%,#283593 100%);'
            f' padding:24px; border-radius:15px; text-align:center; margin:10px;'
            f' border:2px solid #FFD700;">'
            f'<div style="color:#FFD700; font-size:1.3rem; font-weight:bold;">📿 Ta dizaine du jour</div>'
            f'<div style="display:flex; justify-content:center; gap:10px; margin:18px 0;">{pastilles}</div>'
            f'<div style="color:#ffffff; font-size:1rem;">{html.escape(titres)}</div>'
            f'<div style="color:#9fa6d8; font-size:0.85rem; margin-top:8px;">'
            f'Chaîne n° {num} — {date.today().strftime("%d/%m/%Y")}</div>'
            f'</div>', unsafe_allow_html=True)
        if st.button("📿 Égrener la dizaine", key="diz_commencer", use_container_width=True, type="primary"):
            st.session_state["diz_ouvert"] = True
            st.session_state["diz_page"] = 0
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
    couleur = COULEURS_TYPES.get((m["type"] or "").lower(), "#9E9E9E") if m else "#1A237E"

    # --- Rendu de la page courante : UN SEUL bloc HTML par page
    # (la leçon des lignes vides et des div orphelines, appliquée au livre) ---
    if page["t"] in ("intro1", "intro2", "intro3"):
        texte = {"intro1": DIZ_INTRO1, "intro2": DIZ_INTRO2, "intro3": DIZ_INTRO3}[page["t"]]
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
            f'<div style="color:#ffffff; font-weight:bold; font-size:1.05rem;">{m["id"]} — {html.escape(m["titre"])}</div>'
            f'<div style="color:#ffffff; font-size:0.85rem;">📖 {html.escape(m["reference"])}</div></div>'
            f'<div style="background:#FFF9C4; border-radius:0 0 12px 12px; padding:18px; margin:0 6px 6px 6px;">')

        if page["t"] == "contenu":
            corps = (_diz_txt("PASSAGE", couleur, "1rem", gras=True)
                        + _diz_txt(m["passage"], "#1a1a1a")
                        + _diz_txt("MÉDITATION", couleur, "1rem", gras=True)
                        + _diz_txt(m["meditation"], "#1a1a1a"))

        elif page["t"] == "intentions":
            intentions_html = "".join(
                _diz_txt("🕯️ " + ligne.strip(), "#1a1a1a")
                for ligne in m["intentions"].split("\n") if ligne.strip())
            fruits_html = "".join(
                _diz_txt("✨ " + ligne.strip(), "#1a1a1a")
                for ligne in m["fruits"].split("\n") if ligne.strip())
            corps = (_diz_txt("INTENTIONS", couleur, "1rem", gras=True)
                        + intentions_html
                        + _diz_txt("FRUITS DU MYSTÈRE", couleur, "1rem", gras=True)
                        + fruits_html)

        elif page["t"] == "notrepere":
            corps = (_diz_txt("NOTRE PÈRE", couleur, "1rem", gras=True)
                        + _diz_txt("Notre Père, qui es aux cieux,\nque ton nom soit sanctifié,\nque ton règne vienne,\nque ta volonté soit faite\nsur la terre comme au ciel.\n\nDonne-nous aujourd’hui notre pain de ce jour. Pardonne-nous nos offenses, comme nous pardonnons aussi à ceux qui nous ont offensés. Et ne nous laisse pas entrer en tentation, mais délivre-nous du Mal. Amen!", "#1a1a1a"))

        elif page["t"] == "grain":
            g = page["g"]
            clausule = m["clausules"][g - 1] if g <= len(m["clausules"]) else ""
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

    # --- Navigation : ON NE RECULE PAS quand on égrène une dizaine ☺️ ---
    # Le bouton « ◀ Précédent » a été retiré à la demande de l'utilisateur.
    # --- PAGINATION (code conservé en commentaire, désactivé) ---
    # c_prec, c_pos, c_suiv = st.columns([1, 2, 1])
    # with c_prec:
    #     if idx > 0 and st.button("◀ Précédent", key=f"diz_prev_{idx}", use_container_width=True):
    #         st.session_state["diz_page"] = idx - 1
    #         st.rerun()
    # with c_pos:
    #     st.caption(f"Page {idx + 1} / {len(pages)}")
    c_av, c_term = st.columns(2)
    with c_av:
        if idx < len(pages) - 1:
            if st.button("Suivant ▶", key=f"diz_next_{idx}", use_container_width=True, type="primary"):
                st.session_state["diz_page"] = idx + 1
                st.rerun()
        else:
            if st.button("✕ Terminer", key=f"diz_end_{idx}", use_container_width=True):
                st.session_state["diz_ouvert"] = False
                st.session_state["diz_page"] = 0
                st.rerun()

def _render_pdf_inline(url_pdf):
    import urllib.parse as _up
    gview = f"https://docs.google.com/viewer?url={_up.quote(url_pdf, safe='')}&embedded=true"
    st.markdown(
        f'<div style="margin:12px 10px 18px 10px; border-radius:12px; overflow:hidden; border:1px solid #27306b;">'
        f'<iframe src="{gview}" width="100%" height="760" style="border:none;" title="Document"></iframe>'
        f'<div style="text-align:center; padding:8px; background:#121a45;">'
        f'<a href="{url_pdf}" target="_blank" style="color:#b39ddb; font-size:0.85rem;">📄 Si le document ne saffiche pas, ouvrez-le ici</a>'
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
        if safe_date(a[1]):
            visuel = a
            break

    if visuel:
        d_v = safe_date(visuel[1])
        date_txt = d_v.strftime('%d/%m/%Y') if d_v else "Date à définir"
        img_part = (f'<img src="{visuel[3]}" alt="Affiche" style="width:100%; height:auto; display:block; border-bottom:3px solid #7b1fa2;">'
                    if visuel[3] else "")
        st.markdown(
            f'<div style="background:#121a45; border-radius:15px; overflow:hidden; border:1px solid #27306b; margin:0 10px 15px 10px; box-shadow:0 2px 8px rgba(0,0,0,0.4);">'
            f'{img_part}'
            f'<div style="padding:15px; text-align:center;">'
            f'<h4 style="margin:0 0 5px 0; color:#e8eaf6; font-size:1.1rem;">📣 {html.escape(visuel[0])}</h4>'
            f'<p style="margin:0; color:#9fa6d8; font-size:0.9rem;">{date_txt} - {html.escape(visuel[2] or "Lieu à définir")}</p>'
            f'</div></div>', unsafe_allow_html=True)
        if visuel[4]:
            st.video(visuel[4])
    else:
        try:
            prochain = c.execute("""SELECT type_evenement, date_evenement, lieu FROM evenements
                                    WHERE date_evenement >= ? ORDER BY date_evenement ASC LIMIT 1""",
                                 (date.today().isoformat(),)).fetchone()
        except Exception:
            prochain = None
        if prochain:
            d = safe_date(prochain[1])
            date_txt = d.strftime('%d/%m/%Y') if d else "Date à définir"
            icone = {"Prière mensuelle": "🧎", "Prière commune": "🙏", "Prière spéciale": "✨",
                     "Pèlerinage": "🚶‍♂️", "Réunion": "🤝"}.get(prochain[0], "📅")
            st.markdown(
                f'<div style="background:linear-gradient(135deg,#1a2150 0%,#121a45 100%); border-radius:15px; margin:0 10px 15px 10px; border:1px solid #27306b;">'
                f'<div style="padding:15px; text-align:center;">'
                f'<h4 style="margin:0 0 5px 0; color:#e8eaf6; font-size:1.1rem;">{icone} {html.escape(prochain[0])}</h4>'
                f'<p style="margin:0; color:#9fa6d8; font-size:0.9rem;">{date_txt} - {html.escape(prochain[2] or "Lieu à définir")}</p>'
                f'</div></div>', unsafe_allow_html=True)


def _render_fil_actualites():
    dernier = c.execute("""SELECT type_contenu, titre, contenu_texte, image_url, fichier_url
                           FROM espace_spirituel
                           WHERE type_contenu IN ('priere', 'meditation')
                           ORDER BY date_publication DESC, id DESC LIMIT 1""").fetchone()

    if dernier:
        etiquette = {"priere": "🙏 ", "meditation": "📖 "}.get(dernier[0], "📿 Du jour")
        texte = dernier[2] or ''
        url_pdf = dernier[4]
        if not url_pdf:
            texte, url_pdf = _extraire_pdf_legacy(texte)

        texte_html = texte.replace('\n', '<br>')
        img_html = (f'<img src="{dernier[3]}" alt="Contenu" style="border-radius:12px; width:100%; max-height:220px; object-fit:cover; margin-bottom:15px;">'
                    if dernier[3] else "")
        st.markdown(
            f'<div style="background:linear-gradient(135deg,#f3e5f5 0%,#e8eaf6 100%); padding:20px; border-radius:15px; text-align:center; margin:15px 10px; box-shadow:0 4px 12px rgba(0,0,0,0.35);">'
            f'<div style="color:#4A148C; font-size:1.15rem; font-weight:bold; border-bottom:1px solid #d1c4e9; padding-bottom:8px; margin-bottom:12px;">{etiquette} {html.escape(dernier[1])}</div>'
            f'{img_html}'
            f'<div style="color:#4527a0; font-size:0.98rem; line-height:1.6; text-align:left;">{texte_html}</div>'
            f'</div>', unsafe_allow_html=True)

        if url_pdf:
            _render_pdf_inline(url_pdf)
    else:
        st.info("Aucun contenu spirituel n'a encore été publié.")

    _render_coin_affiche()


def _render_spiritual_tabs():
    """Onglets côte à côte SANS exposition par défaut : un onglet d'accueil neutre
    est placé en tête, de sorte que '🙏 Prières' ne soit plus présélectionné.
    Les contenus ne s'exposent que sur clic de l'utilisateur."""
    t_accueil, t_prieres, t_medits, t_audios = st.tabs(
        ["📇 Sommaire", "🙏 Prières", "📖 Méditations", "🎵 Musiques"])

    with t_accueil:
        st.markdown("👋 Bienvenue dans nos archives spirituelles.")
        st.caption("Choisissez une section ci-dessus : 🙏 Prières, 📖 Méditations ou 🎵 Musiques.")

    with t_prieres:
        prieres = c.execute("""SELECT titre, contenu_texte, image_url, fichier_url FROM espace_spirituel
                               WHERE type_contenu='priere' ORDER BY date_publication DESC, id DESC""").fetchall()
        if not prieres:
            st.info("Aucune prière publiée.")
        else:
            for p in prieres:
                with st.expander(f"📖 {p[0]}"):
                    texte, url_pdf = (p[1] or ''), p[3]
                    if not url_pdf: texte, url_pdf = _extraire_pdf_legacy(texte)
                    if p[2] and p[2].startswith("http"): st.image(p[2], use_container_width=True)
                    if texte: st.markdown(texte, unsafe_allow_html=True)
                    if url_pdf: _render_pdf_inline(url_pdf)

    with t_medits:
        meditations = c.execute("""SELECT titre, contenu_texte, image_url, fichier_url FROM espace_spirituel
                                   WHERE type_contenu='meditation' ORDER BY date_publication DESC, id DESC""").fetchall()
        if not meditations:
            st.info("Aucune méditation disponible.")
        else:
            for m in meditations:
                with st.expander(f"📖 {m[0]}"):
                    texte, url_pdf = (m[1] or ''), m[3]
                    if not url_pdf: texte, url_pdf = _extraire_pdf_legacy(texte)
                    if m[2] and m[2].startswith("http"): st.image(m[2], use_container_width=True)
                    if texte: st.markdown(texte, unsafe_allow_html=True)
                    if url_pdf: _render_pdf_inline(url_pdf)

    with t_audios:
        audios = c.execute("""SELECT titre, fichier_url FROM espace_spirituel
                              WHERE type_contenu='audio' ORDER BY date_publication DESC, id DESC""").fetchall()
        if not audios:
            st.info("Aucun fichier audio.")
        else:
            for a in audios:
                if a[1] and a[1].startswith("http"):
                    st.markdown(f"#### 🎵 {a[0]}")
                    st.audio(a[1])
                    st.markdown("---")
                else:
                    st.warning(f"Le fichier audio pour '{a[0]}' est introuvable.")

def _enregistrer_presence(membre_id, evt_id, choix):
    deja = c.execute("SELECT id FROM suivi_presences WHERE membre_id=? AND evenement_id=?",
                     (membre_id, evt_id)).fetchone()
    if deja:
        c.execute("UPDATE suivi_presences SET statut=? WHERE id=?", (choix, deja[0]))
    else:
        c.execute("INSERT INTO suivi_presences (membre_id, evenement_id, statut) VALUES (?, ?, ?)",
                  (membre_id, evt_id, choix))
    commit_and_sync()
    st.session_state["flash_success"] = "Merci pour votre engagement ! 🙏"
    st.rerun()


# ====================================================================
# PAGE PRINCIPALE
# ====================================================================
def show_espace_membre(matloc_membre=None):
    _render_theme()

    msg_ok = st.session_state.pop("flash_success", None)
    if msg_ok:
        st.success(msg_ok)
    msg_warn = st.session_state.pop("flash_warning", None)
    if msg_warn:
        st.warning(msg_warn)

    # ================= ÉTAT 1 : VUE PUBLIQUE (Espace communautaire) =================
    if not matloc_membre:
        _render_header()
        _render_dizaine_du_jour(est_membre=False)
        _render_fil_actualites()
        _render_spiritual_tabs()
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

    if not membre:
        st.error("Identifiant inconnu ou membre inactif.")
        st.info("💡 Vous pouvez consulter l'espace public ci-dessous.")
        _render_header()
        _render_fil_actualites()
        _render_spiritual_tabs()
        return

    _render_header(membre, matloc_membre)

    # 👤 Mon profil — popover natif (zéro rechargement), aligné à droite
    _, col_profil = st.columns([5, 1])
    with col_profil:
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

    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#f3e5f5 0%,#e8eaf6 100%); padding:20px; border-radius:15px; text-align:center; margin:15px 10px; box-shadow:0 4px 12px rgba(0,0,0,0.35); border:1px solid #d1c4e9;">
        <div style="color:#4A148C; font-size:1.3rem; font-weight:bold;">Bienvenue {membre[2]} 🕊️</div>
        <div style="color:#4527a0; font-size:0.9rem; margin-top:6px;">👥 {membre[8] or '—'} &nbsp;|&nbsp; 🏘️ {membre[9] or '—'}</div>
    </div>
    """, unsafe_allow_html=True)

    _render_dizaine_du_jour(numero_meditation=membre[7], est_membre=True)

    _render_fil_actualites()

    # --- RÈGLE 4 : "📅 Mes prochains évènements" = périmètre ÉQUIPE uniquement ---
    if membre[10] is None:
        st.info("Vous n'êtes rattaché(e) à aucune équipe pour le moment.")
    else:
        st.markdown("### 📅 Mes prochains évènements")
        evts = c.execute('''
            SELECT e.id, e.date_evenement, e.type_evenement, e.lieu,
                   (SELECT statut FROM suivi_presences WHERE membre_id=? AND evenement_id=e.id)
            FROM evenements e
            JOIN evenement_equipes ee ON e.id = ee.evenement_id
            WHERE ee.equipe_id = ? AND e.date_evenement >= ?
            ORDER BY e.date_evenement ASC
        ''', (membre[0], membre[10], date.today().isoformat())).fetchall()

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
                                     use_container_width=True,
                                     type="primary" if statut != 'physique' else "secondary"):
                            _enregistrer_presence(membre[0], evt[0], 'physique')
                    with c2:
                        if st.button("🟡 Présent spirituellement", key=f"rsp_s_{evt[0]}",
                                     use_container_width=True,
                                     type="primary" if statut != 'spirituel' else "secondary"):
                            _enregistrer_presence(membre[0], evt[0], 'spirituel')

    st.markdown("---")

    # ARCHIVES
    _render_spiritual_tabs()

    if st.query_params.get("debug") == "1":
        with st.expander("🔎 DEBUG Bandes défilantes"):
            try:
                st.write("Bandes en base :",
                         c.execute("SELECT id, contenu_texte, fichier_url FROM espace_spirituel WHERE type_contenu='annonce_defilante'").fetchall())
            except Exception as e:
                st.write("ERREUR SQL :", e)
            html_genere = _bandes_defilantes_html(membre=bool(matloc_membre))
            st.write("HTML généré :", (html_genere[:400] + "…") if len(html_genere) > 400 else (html_genere or "⚠️ VIDE"))
