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
    .block-container { padding-top: 150px !important; padding-bottom: 4rem !important; }
    .stApp .stMarkdown, .stApp .stMarkdown p, .stApp .stMarkdown li, .stApp .stMarkdown span,
    .stApp .stMarkdown h1, .stApp .stMarkdown h2, .stApp .stMarkdown h3, .stApp .stMarkdown h4,
    .stApp .stMarkdown strong, .stApp .stMarkdown em { color: #e8eaf6 !important; }
    .stApp .stMarkdown a { color: #b39ddb !important; }
    [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p { color: #9fa6d8 !important; }
    [data-testid="stExpander"] { background-color: #121a45 !important; border: 1px solid #27306b !important; border-radius: 12px !important; }
    details, [data-testid="stExpanderDetails"] { background-color: transparent !important; }
    summary, [data-testid="stExpander"] p { color: #e8eaf6 !important; }
    [data-baseweb="tab-list"] { border-bottom-color: #27306b !important; }
    [data-baseweb="tab"] p { color: #9fa6d8 !important; }
    [data-baseweb="tab"][aria-selected="true"] p { color: #ffffff !important; }
    [data-baseweb="tab-highlight"] { background-color: #7b1fa2 !important; }
    .stButton > button { background-color: #1a2150 !important; color: #e8eaf6 !important; border: 1px solid #2a3160 !important; }
    .stButton > button[kind="primary"] { background-color: #4527a0 !important; border-color: #5e35b1 !important; color: #ffffff !important; }
    [data-testid="stAlert"] { background-color: #151b3d !important; }
    [data-testid="stAlert"] p { color: #e8eaf6 !important; }
    .stApp [data-testid="stVerticalBlockBorderWrapper"] { background-color: #121a45 !important; border: 1px solid #27306b !important; }
    .sticky-header { position: fixed; top: 0; left: 0; right: 0; z-index: 9999;
        background-color: #0a0f2c; border-bottom: 1px solid #27306b; padding: 12px 16px; }
    .header-inner { max-width: 1200px; margin: 0 auto; display: flex; justify-content: space-between; align-items: flex-start; }
    .logo-bloc { width: 170px; text-align: center; }
    .logo-bloc img { height: 64px; width: auto; max-width: 170px; border-radius: 10px; display: block; margin: 0 auto; }
    .stApp .logo-titre { width: 170px; color: #e8eaf6 !important; font-weight: 600; font-size: 0.95rem; line-height: 1.25; margin-top: 6px; }
    .stApp a.bouton-profil { background-color: #4527a0 !important; color: #ffffff !important; padding: 10px 18px;
        text-decoration: none; border-radius: 30px; font-weight: bold; font-size: 0.9rem; display: inline-block; white-space: nowrap; }
    .stApp a.bouton-profil:hover { background-color: #5e35b1 !important; color: #ffffff !important; }
    .stApp .postcard { background: linear-gradient(135deg, #f3e5f5 0%, #e8eaf6 100%) !important; padding: 20px;
        border-radius: 15px; text-align: center; margin: 15px 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.35); }
    .stApp .postcard p, .stApp .postcard em, .stApp .postcard strong { color: #4527a0 !important; }
    .stApp .postcard h2, .stApp .postcard h3 { color: #4A148C !important; white-space: normal !important; overflow: visible !important; }
    .stApp .postcard a { color: #4527a0 !important; }
    .stApp .postcard img { border-radius: 12px; width: 100%; max-height: 220px; object-fit: cover; margin-bottom: 15px; }
    .stApp .event-flyer { background: #121a45; border-radius: 15px; margin: 0 10px 15px 10px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.4); overflow: hidden; border: 1px solid #27306b; }
    .stApp .event-flyer img { width: 100%; display: block; border-bottom: 3px solid #7b1fa2; max-height: 250px; object-fit: cover; }
    .stApp .event-flyer-content { padding: 15px; text-align: center; }
    .stApp .event-flyer h4 { margin: 0 0 5px 0; color: #e8eaf6 !important; font-size: 1.1rem; }
    .stApp .event-flyer p { margin: 0; color: #9fa6d8 !important; font-size: 0.9rem; }
    .stApp .pdf-cadre { margin: 12px 10px 18px 10px; border-radius: 12px; overflow: hidden; border: 1px solid #27306b; }
    @media (max-width: 640px) {
        .logo-bloc { width: 130px; }
        .logo-bloc img { height: 52px; }
        .stApp .logo-titre { width: 130px; font-size: 0.85rem; }
        .block-container { padding-top: 128px !important; }
    }
    </style>""", unsafe_allow_html=True)


def _render_header(membre=None, matloc=None):
    logo_b64 = _logo_base64()
    logo_html = (f'<img src="data:image/png;base64,{logo_b64}" alt="Logo">'
                 if logo_b64 else '<div style="font-size:4rem;">📿</div>')

    if membre and matloc:
        profil_actif = st.query_params.get("profil") == "1"
        next_val = "0" if profil_actif else "1"
        label = "✕ Fermer le profil" if profil_actif else "👤 Mon profil"
        profil_html = (f'<div style="padding-top:14px;">'
                       f'<a href="?espace=1&matloc={matloc}&profil={next_val}" class="bouton-profil">{label}</a></div>')
    else:
        profil_html = ""

    st.markdown(f"""
    <div class="sticky-header">
        <div class="header-inner">
            <div class="logo-bloc">{logo_html}<div class="logo-titre">Diocèse de Grand-Bassam</div></div>
            {profil_html}
        </div>
    </div>
    """, unsafe_allow_html=True)

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
    url_inline = url_pdf.replace('/upload/', '/upload/fl_inline/')
    st.markdown(f'<div class="pdf-cadre"><iframe src="{url_inline}" width="100%" height="760" '
                f'style="border:none;" title="Document"></iframe></div>', unsafe_allow_html=True)


def _render_coin_affiche():
    """Priorité d'affichage : BANDE-ANNONCE (vidéo) > AFFICHE (image) > texte."""
    lignes = []
    try:
        lignes = c.execute("""SELECT titre, date_evenement, lieu, affiche_url, video_url FROM evenements
                              WHERE (affiche_url IS NOT NULL OR video_url IS NOT NULL) AND date_evenement >= ?
                              ORDER BY date_evenement ASC LIMIT 5""",
                          (date.today().isoformat(),)).fetchall()
    except Exception:
        lignes = []

    if st.query_params.get("debug") == "1":
        with st.expander("🔎 DEBUG Coin Affiche"):
            st.write("Aujourd'hui :", date.today().isoformat())
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
        st.markdown(
            f'<div class="event-flyer">'
            f'<div class="event-flyer-content"><h4>📣 {html.escape(visuel[0])}</h4>'
            f'<p>{date_txt} - {html.escape(visuel[2] or "Lieu à définir")}</p></div>',
            unsafe_allow_html=True)
        if visuel[4]:
            st.video(visuel[4])   # YouTube ou MP4 Cloudinary
        elif visuel[3]:
            st.image(visuel[3], use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
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
                f'<div class="event-flyer"><div class="event-flyer-content">'
                f'<h4>{icone} {html.escape(prochain[0])}</h4>'
                f'<p>{date_txt} - {html.escape(prochain[2] or "Lieu à définir")}</p></div></div>',
                unsafe_allow_html=True)


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

        img_html = f'<img src="{dernier[3]}" alt="Contenu">' if dernier[3] else ""
        st.markdown(
            f'<div class="postcard"><h3 style="margin:0 0 12px 0;">{etiquette} — {html.escape(dernier[1])}</h3>'
            f'{img_html}{texte}</div>', unsafe_allow_html=True)

        if url_pdf:
            _render_pdf_inline(url_pdf)
    else:
        st.info("Aucun contenu spirituel n'a encore été publié.")

    _render_coin_affiche()


def _render_spiritual_tabs(tab_priere, tab_meditation, tab_musique):
    with tab_priere:
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

    with tab_meditation:
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

    with tab_musique:
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

    # ================= ÉTAT 1 : VUE PUBLIQUE =================
    if not matloc_membre:
        _render_header()
        _render_fil_actualites()
        tab_priere, tab_meditation, tab_musique = st.tabs(["🙏 Prières", "📖 Méditations", "🎵 Musiques"])
        _render_spiritual_tabs(tab_priere, tab_meditation, tab_musique)
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
        tab_priere, tab_meditation, tab_musique = st.tabs(["🙏 Prières", "📖 Méditations", "🎵 Musiques"])
        _render_spiritual_tabs(tab_priere, tab_meditation, tab_musique)
        return

    _render_header(membre, matloc_membre)

    # FIX N°1 : carte bienvenue 100% en styles INLINE (aucune classe CSS,
    # aucun conflit possible avec les feuilles de style globale/custom)
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#f3e5f5 0%,#e8eaf6 100%); padding:20px; border-radius:15px; text-align:center; margin:15px 10px; box-shadow:0 4px 12px rgba(0,0,0,0.35); border:1px solid #d1c4e9;">
        <div style="color:#4A148C; font-size:1.3rem; font-weight:bold;">Bienvenue {membre[2]} 🕊️</div>
        <div style="color:#4527a0; font-size:0.9rem; margin-top:6px;">👥 {membre[8] or '—'} &nbsp;|&nbsp; 🏘️ {membre[9] or '—'}</div>
    </div>
    """, unsafe_allow_html=True)

    _render_fil_actualites()

    # --- FIX N°4 : chaque évènement dans SON expander, avec état de présence ---
    if membre[10] is None and membre[11] is None:
        st.info("Vous n'êtes rattaché(e) à aucune équipe ou paroisse pour le moment.")
    else:
        st.markdown("### 📅 Mes prochains évènements")
        evts = c.execute('''
            SELECT e.id, e.date_evenement, e.type_evenement, e.lieu,
                   (SELECT statut FROM suivi_presences WHERE membre_id=? AND evenement_id=e.id),
                   ee.equipe_id, e.paroisse_id
            FROM evenements e
            LEFT JOIN evenement_equipes ee ON e.id = ee.evenement_id AND ee.equipe_id = ?
            WHERE e.date_evenement >= ?
              AND (ee.equipe_id IS NOT NULL OR e.paroisse_id = ? OR e.diocese_id IS NOT NULL)
            ORDER BY e.date_evenement ASC
        ''', (membre[0], membre[10], date.today().isoformat(), membre[11])).fetchall()

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

                if evt[5]:
                    origine = "👥 Invitation de votre équipe"
                elif evt[6] == membre[11] and evt[6] is not None:
                    origine = "🏘️ Évènement de votre paroisse"
                else:
                    origine = "🏛️ Évènement du diocèse"

                statut = evt[4]
                marqueur = "✅ " if statut in ('physique', 'spirituel') else ""

                with st.expander(f"{marqueur}{icone} {evt[2]} — {d.strftime('%d/%m/%Y')} ({delai})",
                                 expanded=(delta <= 1)):
                    st.write(f"📍 {evt[3] or 'Lieu à définir'}")
                    st.caption(origine)

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
    tab_priere, tab_meditation, tab_musique = st.tabs(["🙏 Prières", "📖 Méditations", "🎵 Musiques"])
    _render_spiritual_tabs(tab_priere, tab_meditation, tab_musique)
