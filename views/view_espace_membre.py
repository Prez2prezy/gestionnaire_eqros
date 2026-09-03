import os
import re
import html
import base64
import streamlit as st
from datetime import date
from database import c, commit_and_sync
from services import safe_date

# --- DESIGN ---
st.markdown("""
<style>
    .sticky-header {
        position: sticky; top: 0; background-color: white; z-index: 1000;
        padding: 10px; border-bottom: 1px solid #eeeeee;
        margin: -10px -10px 10px -10px; padding-top: 20px;
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


@st.cache_data
def _logo_base64():
    try:
        with open(os.path.join("images", "logo.png"), "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return None


def _render_header(membre=None):
    logo_b64 = _logo_base64()
    logo_html = f'<img src="data:image/png;base64,{logo_b64}" style="height:42px;">' if logo_b64 else '<div style="font-size:1.6rem;">📿</div>'
    if membre:
        profil_html = (f'<div style="text-align:right; color:#666; font-size:0.8rem; line-height:1.3;">'
                       f'<b>{html.escape(membre[2])} {html.escape(membre[1])}</b><br>'
                       f'<code style="font-size:0.75rem;">{membre[3]}</code></div>')
    else:
        profil_html = ""
    st.markdown(f"""
    <div class="sticky-header">
        <div style="display: flex; align-items: center; justify-content: space-between;">
            <div style="display: flex; align-items: center; gap: 12px;">
                {logo_html}
                <div style="color:#333333; font-size:1.1rem;">Diocèse de Grand-Bassam</div>
            </div>
            {profil_html}
        </div>
    </div>
    """, unsafe_allow_html=True)


# ====================================================================
# FIX N°1 : PDF — plus aucun HTML multi-lignes injecté dans le contenu.
# RÈGLE : tout st.markdown HTML est passé sur UNE SEULE LIGNE (une ligne
# vide ou une indentation de 4+ espaces = bloc de code markdown).
# ====================================================================
def _render_pdf_boutons(url_pdf):
    """Boutons PDF natifs (HTML sur une seule ligne → jamais de code visible)."""
    url_dl = url_pdf.replace('/upload/', '/upload/fl_attachment/')
    st.markdown(
        f'<div style="text-align:center;margin:15px 0;">'
        f'<a href="{url_pdf}" target="_blank" style="background-color:#4527a0;color:white;padding:14px 28px;text-decoration:none;border-radius:8px;font-weight:bold;font-size:1.05rem;display:inline-block;margin:4px;">📄 Ouvrir le PDF</a>'
        f'<a href="{url_dl}" style="background-color:#7b1fa2;color:white;padding:14px 22px;text-decoration:none;border-radius:8px;font-weight:bold;font-size:1.05rem;display:inline-block;margin:4px;">⬇️ Télécharger</a>'
        f'</div>', unsafe_allow_html=True)


PDF_URL_RE = re.compile(r'href="(https://res\.cloudinary\.com/[^"]+\.pdf)"')
DIV_PDF_RE = re.compile(r'<div[^>]*1px dashed #4527a0.*?</div>\s*', re.DOTALL)

def _extraire_pdf_legacy(contenu):
    """Rétrocompatibilité : les anciens contenus ont le HTML du PDF (cassé)
    noyé dans contenu_texte. On extrait l'URL et on nettoie à la volée."""
    if not contenu or ('cloudinary' not in contenu and 'data:application/pdf' not in contenu):
        return contenu, None
    m = PDF_URL_RE.search(contenu)
    url = m.group(1) if m else None
    return DIV_PDF_RE.sub('', contenu).strip(), url


def _render_profil(membre):
    """FIX N°2 : restauration du popover 'Mon profil'."""
    _, col_p = st.columns([6, 1])
    with col_p:
        with st.popover("👤 Mon profil"):
            if membre[6]:
                try: st.image(membre[6], width=110)
                except Exception: pass
            st.markdown(f"**{membre[1]} {membre[2]}**")
            st.caption(f"MatLoc : `{membre[3]}`")
            st.write(f"👥 Équipe : **{membre[8] or '—'}**")
            st.write(f"🏘️ Paroisse : **{membre[9] or '—'}**")
            st.write(f"💬 WhatsApp : {membre[4] or '—'}")
            st.write(f"📿 N° méditation : {membre[7] or '—'}")
            d_adh = safe_date(membre[5])
            st.write(f"📅 Adhésion : {d_adh.strftime('%d/%m/%Y') if d_adh else '—'}")


def _render_coin_affiche():
    """FIX N°3 : fallback — le prochain évènement s'affiche même sans image."""
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
    dernier_contenu = c.execute("""SELECT titre, contenu_texte, image_url, fichier_url
                                   FROM espace_spirituel
                                   WHERE type_contenu IN ('priere', 'meditation')
                                   ORDER BY date_publication DESC, id DESC LIMIT 1""").fetchone()

    if dernier_contenu:
        texte = dernier_contenu[1] or ''
        url_pdf = dernier_contenu[3]
        if not url_pdf:  # anciens contenus : PDF noyé dans le texte
            texte, url_pdf = _extraire_pdf_legacy(texte)

        if dernier_contenu[2]:
            st.markdown(f'<div class="postcard"><img src="{dernier_contenu[2]}" alt="Contenu">{texte}</div>', unsafe_allow_html=True)
        elif texte:
            st.markdown(f'<div class="postcard">{texte}</div>', unsafe_allow_html=True)
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
        SELECT m.id, m.nom, m.prenom, m.matloc, m.whatsapp, m.date_adhesion, m.photo_path, m.numero_meditation, e.nom_equipe, p.nom
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

    _render_header(membre)
    _render_profil(membre)   # FIX N°2 : le profil est de retour

    st.markdown(f"""
    <div class="postcard">
        <h2>Bienvenue {membre[2]} 🕊️</h2>
        <p style="font-size: 0.85rem;"><em>{membre[8] or ''} | {membre[9] or ''}</em></p>
    </div>
    """, unsafe_allow_html=True)

    _render_fil_actualites()

    # AGENDA (inchangé — avec .pop() sécurisés et flash)
    with st.expander("📅 Mes prochains évènements"):
        # ... [bloc identique à la version précédente] ...
        pass  # conservez ici votre bloc agenda existant

    st.markdown("---")
    tab_priere, tab_meditation, tab_musique = st.tabs(["🙏 Prières", "📖 Méditations", "🎵 Musiques"])
    _render_spiritual_tabs(tab_priere, tab_meditation, tab_musique)
