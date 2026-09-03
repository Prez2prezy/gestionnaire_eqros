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
    """Rétrocompatibilité : retire le HTML de PDF (ancien format) noyé dans
    contenu_texte et récupère l'URL du document."""
    if not contenu or ('cloudinary' not in contenu and 'data:application/pdf' not in contenu):
        return contenu, None
    m = PDF_URL_RE.search(contenu)
    url = m.group(1) if m else None
    return DIV_PDF_RE.sub('', contenu).strip(), url


def _render_theme():
    """FIX MAJEUR : le CSS est injecté ICI (à chaque affichage) et non plus au
    niveau du module. L'ancien CSS d'import ne s'exécutait qu'une fois par
    process → styles perdus pour tous les runs suivants (entête non figée,
    carte Bienvenue sans fond, etc.). Thème : fond bleu nuit."""
    st.markdown("""<style>
    /* Masque le header natif Streamlit + fond bleu nuit */
    [data-testid="stHeader"] { display: none !important; }
    .stApp { background-color: #0a0f2c !important; }
    .block-container { padding-top: 1rem !important; padding-bottom: 4rem !important; }
    /* Nécessaire pour que position:sticky fonctionne dans Streamlit */
    [data-testid="stAppViewContainer"], [data-testid="stMain"],
    [data-testid="stMainBlockContainer"] { overflow: visible !important; }
    /* Textes clairs */
    .stMarkdown, .stMarkdown p, .stMarkdown li, .stMarkdown span { color: #e8eaf6 !important; }
    .stMarkdown h1, .stMarkdown h2, .stMarkdown h3, .stMarkdown h4 { color: #e8eaf6 !important; }
    [data-testid="stCaptionContainer"] { color: #9fa6d8 !important; }
    /* Expanders sombres */
    [data-testid="stExpander"] { background-color: #121a45 !important; border: 1px solid #27306b !important; border-radius: 12px !important; }
    details, [data-testid="stExpanderDetails"] { background-color: transparent !important; }
    summary { color: #e8eaf6 !important; }
    [data-testid="stExpander"] p { color: #e8eaf6 !important; }
    /* Onglets */
    [data-baseweb="tab-list"] { border-bottom-color: #27306b !important; }
    [data-baseweb="tab"] p { color: #9fa6d8 !important; }
    [data-baseweb="tab"][aria-selected="true"] p { color: #ffffff !important; }
    [data-baseweb="tab-highlight"] { background-color: #4527a0 !important; }
    /* Boutons */
    .stButton > button { background-color: #1a2150 !important; color: #e8eaf6 !important; border: 1px solid #2a3160 !important; }
    .stButton > button[kind="primary"] { background-color: #4527a0 !important; border-color: #5e35b1 !important; color: #ffffff !important; }
    /* Alertes sombres */
    [data-testid="stAlert"] { background-color: #151b3d !important; }
    [data-testid="stAlert"] p { color: #e8eaf6 !important; }
    /* --- ENTÊTE FIGÉE --- */
    .sticky-header { position: sticky; top: 0; z-index: 1000; background-color: #0a0f2c;
        padding: 10px 12px 12px 12px; margin: -6px -10px 12px -10px; border-bottom: 1px solid #27306b; }
    .logo-bloc { width: 170px; text-align: center; }
    .logo-bloc img { width: 170px; border-radius: 10px; display: block; }
    .logo-bloc .logo-titre { width: 170px; color: #e8eaf6; font-weight: 600; font-size: 0.95rem; line-height: 1.25; margin-top: 6px; }
    .bouton-profil { background-color: #4527a0; color: #ffffff; padding: 10px 18px; text-decoration: none;
        border-radius: 30px; font-weight: bold; font-size: 0.9rem; display: inline-block; white-space: nowrap; }
    /* --- Cartes (contraste sur fond sombre) --- */
    .postcard { background: linear-gradient(135deg, #f3e5f5 0%, #e8eaf6 100%); padding: 20px;
        border-radius: 15px; text-align: center; margin: 15px 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.35); color: #4527a0; }
    .postcard h2 { margin-top: 0; color: #4527a0; font-size: 1.2rem; }
    .postcard p { color: #4527a0; font-size: 0.95rem; margin: 5px 0; }
    .postcard img { border-radius: 12px; width: 100%; max-height: 220px; object-fit: cover; margin-bottom: 15px; }
    .postcard-titre { font-size: 1.15rem; font-weight: bold; color: #4A148C; margin-bottom: 12px;
        border-bottom: 1px solid #d1c4e9; padding-bottom: 8px; }
    .event-flyer { background: #121a45; border-radius: 15px; margin: 0 10px 15px 10px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.4); overflow: hidden; border: 1px solid #27306b; }
    .event-flyer img { width: 100%; display: block; border-bottom: 3px solid #7b1fa2; max-height: 250px; object-fit: cover; }
    .event-flyer-content { padding: 15px; text-align: center; }
    .event-flyer h4 { margin: 0 0 5px 0; color: #e8eaf6; font-size: 1.1rem; }
    .event-flyer p { margin: 0; color: #9fa6d8; font-size: 0.9rem; }
    .event-flyer-sans-image { background: linear-gradient(135deg, #1a2150 0%, #121a45 100%); }
    .pdf-cadre { margin: 12px 10px 18px 10px; border-radius: 12px; overflow: hidden; border: 1px solid #27306b; }
    </style>""", unsafe_allow_html=True)


def _render_header(membre=None, matloc=None):
    """Entête FIGÉE : logo (texte dessous, même largeur) + bouton Mon profil à droite."""
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
        <div style="display:flex; justify-content:space-between; align-items:flex-start;">
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
    """FIX N°2 : le PDF s'affiche DIRECTEMENT dans la page (iframe Cloudinary
    avec le flag fl_inline qui force l'affichage navigateur). Les boutons
    'Ouvrir' / 'Télécharger' sont supprimés."""
    url_inline = url_pdf.replace('/upload/', '/upload/fl_inline/')
    st.markdown(f'<div class="pdf-cadre"><iframe src="{url_inline}" width="100%" height="760" '
                f'style="border:none;" title="Document"></iframe></div>', unsafe_allow_html=True)


def _render_coin_affiche():
    """Affiche du prochain évènement à venir (avec image), sinon fallback texte.
    Mode diagnostic : ajouter &debug=1 à l'URL pour voir le contenu de la base."""
    lignes = []
    try:
        lignes = c.execute("""SELECT titre, date_evenement, lieu, affiche_url FROM evenements
                              WHERE affiche_url IS NOT NULL AND date_evenement >= ?
                              ORDER BY date_evenement ASC LIMIT 5""",
                          (date.today().isoformat(),)).fetchall()
    except Exception:
        lignes = []

    if st.query_params.get("debug") == "1":
        with st.expander("🔎 DEBUG Coin Affiche"):
            st.write("Aujourd'hui :", date.today().isoformat())
            try:
                st.write("Évènements avec affiche (tous) :",
                         c.execute("SELECT id, titre, date_evenement, affiche_url FROM evenements WHERE affiche_url IS NOT NULL").fetchall())
            except Exception as e:
                st.write("ERREUR SQL :", e)

    affiche = None
    for a in lignes:
        if safe_date(a[1]):
            affiche = a
            break

    if affiche:
        d_affiche = safe_date(affiche[1])
        date_txt = d_affiche.strftime('%d/%m/%Y') if d_affiche else "Date à définir"
        st.markdown(
            f'<div class="event-flyer"><img src="{affiche[3]}" alt="Affiche événement">'
            f'<div class="event-flyer-content"><h4>📣 {html.escape(affiche[0])}</h4>'
            f'<p>{date_txt} - {html.escape(affiche[2] or "Lieu à définir")}</p></div></div>',
            unsafe_allow_html=True)
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
                f'<div class="event-flyer event-flyer-sans-image"><div class="event-flyer-content">'
                f'<h4>{icone} {html.escape(prochain[0])}</h4>'
                f'<p>{date_txt} - {html.escape(prochain[2] or "Lieu à définir")}</p></div></div>',
                unsafe_allow_html=True)


def _render_fil_actualites():
    """FIX N°3 : 'Prière du jour' / 'Méditation du jour' selon l'origine."""
    dernier = c.execute("""SELECT type_contenu, titre, contenu_texte, image_url, fichier_url
                           FROM espace_spirituel
                           WHERE type_contenu IN ('priere', 'meditation')
                           ORDER BY date_publication DESC, id DESC LIMIT 1""").fetchone()

    if dernier:
        etiquette = {"priere": "🙏 Prière du jour", "meditation": "📖 Méditation du jour"}.get(dernier[0], "📿 Du jour")
        texte = dernier[2] or ''
        url_pdf = dernier[4]
        if not url_pdf:
            texte, url_pdf = _extraire_pdf_legacy(texte)

        img_html = f'<img src="{dernier[3]}" alt="Contenu">' if dernier[3] else ""
        st.markdown(
            f'<div class="postcard"><div class="postcard-titre">{etiquette} — {html.escape(dernier[1])}</div>'
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
    """FIX N°6 : réponse de communion EN UN CLIC (identité déjà validée par le
    lien matloc — aucune vérification supplémentaire)."""
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
    # CSS injecté À CHAQUE AFFICHAGE (correctif majeur, cf. _render_theme)
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

    # FIX N°6 : l'id d'équipe (index 10) est récupéré pour l'agenda complet
    membre = c.execute("""
        SELECT m.id, m.nom, m.prenom, m.matloc, m.whatsapp, m.date_adhesion, m.photo_path,
               m.numero_meditation, e.nom_equipe, p.nom, m.equipe_id
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

    st.markdown(f"""
    <div class="postcard">
        <h2>Bienvenue {membre[2]} 🕊️</h2>
        <p style="font-size: 0.85rem;"><em>{membre[8] or ''} | {membre[9] or ''}</em></p>
    </div>
    """, unsafe_allow_html=True)

    _render_fil_actualites()

    # --- AGENDA : TOUS les évènements à venir, réponse en 1 clic ---
    if membre[10] is None:
        st.info("Vous n'êtes rattaché(e) à aucune équipe pour le moment.")
    else:
        with st.expander("📅 Mes prochains évènements", expanded=True):
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

                    st.markdown(f"**{icone} {evt[2]}** — {d.strftime('%d/%m/%Y')} ({delai})")
                    st.write(f"📍 {evt[3] or 'Lieu à définir'}")

                    statut = evt[4]
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

    st.markdown("---")

    # ARCHIVES
    tab_priere, tab_meditation, tab_musique = st.tabs(["🙏 Prières", "📖 Méditations", "🎵 Musiques"])
    _render_spiritual_tabs(tab_priere, tab_meditation, tab_musique)
