import os
import re
import html
import base64
import streamlit as st
from datetime import date
from database import c, commit_and_sync
from services import safe_date


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

    if membre and matloc:
        profil_actif = st.query_params.get("profil") == "1"
        next_val = "0" if profil_actif else "1"
        label = "✕ Fermer le profil" if profil_actif else "👤 Mon profil"
        droite = (f'<div style="padding-top:14px;">'
                  f'<a href="?espace=1&matloc={matloc}&profil={next_val}" class="bouton-profil">{label}</a></div>')
    else:
        droite = ('<div style="padding-top:14px;">'
                  '<div style="background-color:#4527a0; color:#ffffff;'
                  ' padding:10px 18px; border-radius:30px; font-weight:bold;'
                  ' font-size:0.9rem; display:inline-block; white-space:nowrap;">'
                  'Espace communautaire</div></div>')

    bandes_html = _bandes_defilantes_html(membre=bool(membre))

    st.markdown(
        f'<div class="sticky-header"><div class="header-inner">'
        f'<div class="logo-bloc">{logo_html}{titre_svg}</div>'
        f'{droite}'
        f'</div>{bandes_html}</div>', unsafe_allow_html=True)

    if membre and matloc and st.query_params.get("profil") == "1":
        with st.container(border=True):
            c_img, c_infos = st.columns([1, 2])
            with c_img:
                if membre[6]:
                    try: st.image(membre[6], width=130)
                    except Exception: pass
            with c_infos:
                st.markdown(f"**{membre[1]} {membre[2]}**")
                st.caption(f"MatLoc : `{membre[3]}`")
                st.write(f"👥 Équipe : **{membre[8] or '—'}**")
                st.write(f"🏘️ Paroisse : **{membre[9] or '—'}**")
                st.write(f"💬 WhatsApp : {membre[4] or '—'}")
                st.write(f"📿 N° méditation : {membre[7] or '—'}")
                d_adh = safe_date(membre[5])
                st.write(f"📅 Adhésion : {d_adh.strftime('%d/%m/%Y') if d_adh else '—'}")
        st.markdown("<div style='margin-bottom:10px;'></div>", unsafe_allow_html=True)


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


def _render_spiritual_tabs(titre_section="📖 Archives spirituelles"):
    """FIX : remplace les onglets par des sections REPLIÉES. Un onglet Streamlit
    impose toujours une sélection par défaut (le 1er contenu s'expose d'office).
    Des expanders : rien n'est présélectionné, chaque section ne s'ouvre que
    sur clic — et le nombre de contenus informe sans déplier."""
    try:
        nb_prieres = c.execute("SELECT COUNT(*) FROM espace_spirituel WHERE type_contenu='priere'").fetchone()[0]
        nb_meds = c.execute("SELECT COUNT(*) FROM espace_spirituel WHERE type_contenu='meditation'").fetchone()[0]
        nb_audios = c.execute("SELECT COUNT(*) FROM espace_spirituel WHERE type_contenu='audio'").fetchone()[0]
    except Exception:
        nb_prieres, nb_meds, nb_audios = 0, 0, 0

    with st.expander(f"🙏 Prières ({nb_prieres})"):
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

    with st.expander(f"📖 Méditations ({nb_meds})"):
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

    with st.expander(f"🎵 Musiques ({nb_audios})"):
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

    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#f3e5f5 0%,#e8eaf6 100%); padding:20px; border-radius:15px; text-align:center; margin:15px 10px; box-shadow:0 4px 12px rgba(0,0,0,0.35); border:1px solid #d1c4e9;">
        <div style="color:#4A148C; font-size:1.3rem; font-weight:bold;">Bienvenue {membre[2]} 🕊️</div>
        <div style="color:#4527a0; font-size:0.9rem; margin-top:6px;">👥 {membre[8] or '—'} &nbsp;|&nbsp; 🏘️ {membre[9] or '—'}</div>
    </div>
    """, unsafe_allow_html=True)

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
