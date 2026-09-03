import os
import re
import html
import base64
import streamlit as st
from datetime import date
from database import c, commit_and_sync
from services import safe_date

# --- DESIGN DE L'ESPACE SPIRITUEL ---
st.markdown("""
<style>
    .sticky-header {
        position: sticky; top: 0; background-color: white; z-index: 1000;
        padding: 10px 10px 12px 10px; border-bottom: 1px solid #eeeeee;
        margin: -10px -10px 10px -10px; padding-top: 20px;
    }
    /* BLOC LOGO : texte EN DESSOUS du logo, même largeur que lui */
    .logo-bloc { width: 170px; text-align: center; }
    .logo-bloc img { width: 170px; border-radius: 10px; display: block; }
    .logo-bloc .logo-titre {
        width: 170px; color: #333333; font-weight: 600; font-size: 0.95rem;
        line-height: 1.25; margin-top: 6px; word-wrap: break-word;
    }
    .bouton-profil {
        background-color: #4527a0; color: white; padding: 10px 18px;
        text-decoration: none; border-radius: 30px; font-weight: bold;
        font-size: 0.9rem; display: inline-block; white-space: nowrap;
    }
    .postcard {
        background: linear-gradient(135deg, #f3e5f5 0%, #e8eaf6 100%);
        padding: 20px; border-radius: 15px; text-align: center; margin: 15px 10px;
        box-shadow: 0 4px 12px rgba(69, 39, 160, 0.08); color: #4527a0;
    }
    .postcard h2 { margin-top: 0; color: #4527a0; font-size: 1.2rem; }
    .postcard p { font-size: 0.95rem; margin: 5px 0; }
    .postcard img {
        border-radius: 12px; width: 100%; max-height: 220px;
        object-fit: cover; margin-bottom: 15px; box-shadow: 0 2px 6px rgba(0,0,0,0.1);
    }
    .postcard-titre {
        font-size: 1.15rem; font-weight: bold; color: #4A148C;
        margin-bottom: 12px; border-bottom: 1px solid #d1c4e9; padding-bottom: 8px;
    }
    .pdf-box {
        background: #fff8e1; border: 2px solid #4527a0; border-radius: 12px;
        padding: 16px; text-align: center; margin: 12px 10px 18px 10px;
    }
    .pdf-box-titre { font-weight: bold; color: #4527a0; font-size: 1.05rem; margin-bottom: 12px; }
    .event-flyer {
        background: white; border-radius: 15px; margin: 0px 10px 15px 10px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06); overflow: hidden; border: 1px solid #eeeeee;
    }
    .event-flyer img {
        width: 100%; margin-bottom: 0; border-bottom: 3px solid #4527a0;
        max-height: 250px; object-fit: cover;
    }
    .event-flyer-content { padding: 15px; text-align: center; }
    .event-flyer h4 { margin: 0 0 5px 0; color: #4527a0; font-size: 1.1rem; }
    .event-flyer p { margin: 0; color: #666; font-size: 0.9rem; }
    .event-flyer-sans-image { background: linear-gradient(135deg, #e8eaf6 0%, #f3e5f5 100%); }
</style>
""", unsafe_allow_html=True)


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
    """Rétrocompatibilité : retire le HTML de PDF (ancien format, cassé) noyé
    dans contenu_texte et récupère l'URL du document."""
    if not contenu or ('cloudinary' not in contenu and 'data:application/pdf' not in contenu):
        return contenu, None
    m = PDF_URL_RE.search(contenu)
    url = m.group(1) if m else None
    return DIV_PDF_RE.sub('', contenu).strip(), url


def _render_header(membre=None, matloc=None):
    """Entête FIGÉE : bloc logo (texte dessous, même largeur) à gauche,
    bouton 'Mon profil' à droite. 100% HTML → le sticky fonctionne."""
    logo_b64 = _logo_base64()
    logo_html = (f'<img src="data:image/png;base64,{logo_b64}" alt="Logo">'
                 if logo_b64 else '<div style="font-size:4rem;">📿</div>')

    if membre and matloc:
        profil_actif = st.query_params.get("profil") == "1"
        # Toggle via paramètre d'URL : clic = rechargement, la carte profil
        # se déroule sous l'entête (équivalent natif d'un popover)
        next_val = "0" if profil_actif else "1"
        label = "✕ Fermer le profil" if profil_actif else "👤 Mon profil"
        lien = f"?espace=1&matloc={matloc}&profil={next_val}"
        profil_html = f'<div style="padding-top:14px;"><a href="{lien}" class="bouton-profil">{label}</a></div>'
    else:
        profil_html = ""

    st.markdown(f"""
    <div class="sticky-header">
        <div style="display:flex; justify-content:space-between; align-items:flex-start;">
            <div class="logo-bloc">
                {logo_html}
                <div class="logo-titre">Diocèse de Grand-Bassam</div>
            </div>
            {profil_html}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Carte profil déroulante (affichée si activée par le bouton)
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


def _render_pdf_boutons(url_pdf):
    """Encart PDF BIEN VISIBLE : titre, bouton ouvrir + bouton télécharger.
    HTML sur UNE seule ligne (jamais de code affiché)."""
    url_dl = url_pdf.replace('/upload/', '/upload/fl_attachment/')
    st.markdown(
        '<div class="pdf-box"><div class="pdf-box-titre">📎 Document à lire</div>'
        f'<a href="{url_pdf}" target="_blank" style="background-color:#4527a0;color:white;padding:14px 28px;text-decoration:none;border-radius:8px;font-weight:bold;font-size:1.05rem;display:inline-block;margin:4px;">📄 Ouvrir le PDF</a>'
        f'<a href="{url_dl}" style="background-color:#7b1fa2;color:white;padding:14px 22px;text-decoration:none;border-radius:8px;font-weight:bold;font-size:1.05rem;display:inline-block;margin:4px;">⬇️ Télécharger</a>'
        '</div>', unsafe_allow_html=True)


def _render_coin_affiche():
    """Affiche du prochain évènement à venir. AVEC image si une affiche a été
    publiée (via Agenda → 🖼️ Affiches), sinon version texte élégante."""
    affiche = None
    try:
        lignes = c.execute("""SELECT titre, date_evenement, lieu, affiche_url FROM evenements
                              WHERE affiche_url IS NOT NULL AND date_evenement >= ?
                              ORDER BY date_evenement ASC LIMIT 5""",
                          (date.today().isoformat(),)).fetchall()
    except Exception:
        lignes = []
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
    """Dernière publication (prière OU méditation) : titre bien visible,
    contenu, puis encart PDF distinct si un document est joint."""
    dernier = c.execute("""SELECT type_contenu, titre, contenu_texte, image_url, fichier_url
                           FROM espace_spirituel
                           WHERE type_contenu IN ('priere', 'meditation')
                           ORDER BY date_publication DESC, id DESC LIMIT 1""").fetchone()

    if dernier:
        etiquette = "🙏 Dernière prière" if dernier[0] == 'priere' else "📖 Dernière méditation"
        texte = dernier[2] or ''
        url_pdf = dernier[4]
        if not url_pdf:
            texte, url_pdf = _extraire_pdf_legacy(texte)

        img_html = f'<img src="{dernier[3]}" alt="Contenu">' if dernier[3] else ""
        st.markdown(
            f'<div class="postcard"><div class="postcard-titre">{etiquette} — {html.escape(dernier[1])}</div>'
            f'{img_html}{texte}</div>', unsafe_allow_html=True)

        if url_pdf:
            _render_pdf_boutons(url_pdf)
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
                    if url_pdf: _render_pdf_boutons(url_pdf)

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
                    if url_pdf: _render_pdf_boutons(url_pdf)

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


# ====================================================================
# PAGE PRINCIPALE
# ====================================================================
def show_espace_membre(matloc_membre=None):
    msg_ok = st.session_state.pop("flash_success", None)
    if msg_ok:
        st.success(msg_ok)

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
               m.numero_meditation, e.nom_equipe, p.nom
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

    # Entête figée (logo + texte dessous + bouton profil) puis carte profil déroulante
    _render_header(membre, matloc_membre)

    st.markdown(f"""
    <div class="postcard">
        <h2>Bienvenue {membre[2]} 🕊️</h2>
        <p style="font-size: 0.85rem;"><em>{membre[8] or ''} | {membre[9] or ''}</em></p>
    </div>
    """, unsafe_allow_html=True)

    _render_fil_actualites()

    # AGENDA
    with st.expander("📅 Mes prochains évènements"):
        prochain_evt = c.execute('''
            SELECT e.id, e.date_evenement, e.type_evenement, e.lieu,
                   (SELECT statut FROM suivi_presences WHERE membre_id=? AND evenement_id=e.id)
            FROM evenements e
            JOIN evenement_equipes ee ON e.id = ee.evenement_id
            WHERE ee.equipe_id = (SELECT equipe_id FROM membres WHERE matloc=?)
            AND e.date_evenement >= ?
            ORDER BY e.date_evenement ASC LIMIT 1
        ''', (membre[0], matloc_membre, date.today().isoformat())).fetchone()

        if prochain_evt:
            evt_date = safe_date(prochain_evt[1])
            if evt_date:
                delta = (evt_date - date.today()).days
                delai = "🔴 Aujourd'hui !" if delta == 0 else "🟠 C'est demain !" if delta == 1 else f"📅 Dans {delta} jours"
                icone_evt = {"Prière mensuelle": "🧎", "Prière commune": "🙏", "Prière spéciale": "✨",
                             "Pèlerinage": "🚶‍♂️", "Réunion": "🤝"}.get(prochain_evt[2], "📅")

                st.markdown(f"**{icone_evt} {prochain_evt[2]}**")
                st.write(f"📍 {prochain_evt[3] or 'Lieu à définir'}")
                st.caption(delai)

                if not prochain_evt[4]:
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("🟢 Présent physiquement", use_container_width=True, type="primary"):
                            st.session_state['repondre_event_id'] = prochain_evt[0]
                            st.session_state['choix_action'] = "physique"
                            st.rerun()
                    with col2:
                        if st.button("🟡 Présent spirituellement", use_container_width=True):
                            st.session_state['repondre_event_id'] = prochain_evt[0]
                            st.session_state['choix_action'] = "spirituel"
                            st.rerun()
                else:
                    statut_txt = "✅ Physique" if prochain_evt[4] == 'physique' else "🟡 Spirituel"
                    st.success(f"Vous êtes inscrit : {statut_txt}")

                if st.session_state.get('repondre_event_id'):
                    evt_id = st.session_state['repondre_event_id']
                    if st.button("✅ Confirmer définitivement", type="primary"):
                        choix = st.session_state.get('choix_action', 'physique')
                        deja_repondu = c.execute("SELECT statut FROM suivi_presences WHERE membre_id=? AND evenement_id=?",
                                                 (membre[0], evt_id)).fetchone()
                        if deja_repondu:
                            c.execute("UPDATE suivi_presences SET statut=? WHERE membre_id=? AND evenement_id=?",
                                      (choix, membre[0], evt_id))
                        else:
                            c.execute("INSERT INTO suivi_presences (membre_id, evenement_id, statut) VALUES (?, ?, ?)",
                                      (membre[0], evt_id, choix))
                        commit_and_sync()
                        st.session_state.pop('repondre_event_id', None)
                        st.session_state.pop('choix_action', None)
                        st.session_state["flash_success"] = "Merci pour votre engagement ! 🙏"
                        st.rerun()
        else:
            st.success("✅ Aucun événement à venir. Profitez de ce temps de repos !")

    st.markdown("---")

    # ARCHIVES
    tab_priere, tab_meditation, tab_musique = st.tabs(["🙏 Prières", "📖 Méditations", "🎵 Musiques"])
    _render_spiritual_tabs(tab_priere, tab_meditation, tab_musique)
