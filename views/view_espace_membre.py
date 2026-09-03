import os
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
</style>
""", unsafe_allow_html=True)


# ====================================================================
# FONCTIONS PRIVÉES (factorisation : l'ancien code dupliquait ~60 lignes
# entre la vue publique et la vue membre)
# ====================================================================
@st.cache_data
def _logo_base64():
    """FIX : remplace le placeholder 'GET LOGO HERE' visible par les utilisateurs."""
    try:
        with open(os.path.join("images", "logo.png"), "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return None


def _render_header(membre=None):
    logo_b64 = _logo_base64()
    logo_html = f'<img src="data:image/png;base64,{logo_b64}" style="height:42px;">' if logo_b64 else '<div style="font-size:1.6rem;">📿</div>'

    if membre:
        # FIX : remplace 'GET PROFIL POPOVER HERE' par les infos du membre
        profil_html = (f'<div style="text-align:right; color:#666; font-size:0.8rem; line-height:1.3;">'
                       f'<b>{membre[2]} {membre[1]}</b><br>'
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


def _render_coin_affiche():
    """Coin Affiche : prochain évènement à venir ayant une affiche.
    FIX CRITIQUE : la colonne affiche_url est créée par la migration de
    database.py ; l'ancien except ValueError ne rattrapait JAMAIS une erreur
    SQL (une erreur SQL n'est pas un ValueError) → traceback rouge pour tout
    visiteur. except Exception = filet de sécurité défensif."""
    try:
        affiches_dispo = c.execute("""SELECT titre, date_evenement, lieu, affiche_url
                                      FROM evenements WHERE affiche_url IS NOT NULL
                                      ORDER BY date_evenement DESC LIMIT 5""").fetchall()
    except Exception:
        affiches_dispo = []

    affiche = None
    if affiches_dispo:
        for a in affiches_dispo:
            d_test = safe_date(a[1])
            if d_test and d_test >= date.today():
                affiche = a
                break

    if affiche:
        d_affiche = safe_date(affiche[1])
        date_txt = d_affiche.strftime('%d/%m/%Y') if d_affiche else "Date à définir"
        st.markdown(f"""
        <div class="event-flyer">
            <img src="{affiche[3]}" alt="Affiche événement">
            <div class="event-flyer-content">
                <h4>📣 {affiche[0]}</h4>
                <p>{date_txt} - {affiche[2] or 'Lieu à définir'}</p>
            </div>
        </div>
        """, unsafe_allow_html=True)


def _render_fil_actualites():
    """FIX : postcard + coin affiche étaient dupliqués entre les 2 états —
    factorisés ici (une seule correction à faire à l'avenir)."""
    dernier_contenu = c.execute("""SELECT titre, contenu_texte, image_url FROM espace_spirituel
                                   WHERE type_contenu IN ('priere', 'meditation')
                                   ORDER BY date_publication DESC, id DESC LIMIT 1""").fetchone()

    if dernier_contenu:
        img_html = f'<img src="{dernier_contenu[2]}" alt="Contenu">' if dernier_contenu[2] else ""
        # FIX : contenu_texte peut être NULL (titre seul suffit à publier) → "None" affiché
        st.markdown(f"""
        <div class="postcard">
            {img_html}
            {dernier_contenu[1] or ''}
        </div>
        """, unsafe_allow_html=True)
    else:
        st.info("Aucun contenu spirituel n'a encore été publié.")

    _render_coin_affiche()


def _render_spiritual_tabs(tab_priere, tab_meditation, tab_musique):
    with tab_priere:
        prieres = c.execute("""SELECT titre, contenu_texte, image_url FROM espace_spirituel
                               WHERE type_contenu='priere' ORDER BY date_publication DESC, id DESC""").fetchall()
        if not prieres:
            st.info("Aucune prière publiée.")
        else:
            for p in prieres:
                with st.expander(f"📖 {p[0]}"):
                    if p[2] and p[2].startswith("http"): st.image(p[2], use_container_width=True)  # FIX : déprécié
                    if p[1]: st.markdown(p[1], unsafe_allow_html=True)

    with tab_meditation:
        meditations = c.execute("""SELECT titre, contenu_texte, image_url FROM espace_spirituel
                                   WHERE type_contenu='meditation' ORDER BY date_publication DESC, id DESC""").fetchall()
        if not meditations:
            st.info("Aucune méditation disponible.")
        else:
            for m in meditations:
                with st.expander(f"📖 {m[0]}"):
                    if m[2] and m[2].startswith("http"): st.image(m[2], use_container_width=True)  # FIX : déprécié
                    if m[1]: st.markdown(m[1], unsafe_allow_html=True)

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

    # FIX : app.py ne route PAS les flashs sur les pages publiques (st.stop()
    # avant le helper central) → affichage local du flash posé au run précédent
    msg_ok = st.session_state.pop("flash_success", None)
    if msg_ok:
        st.success(msg_ok)

    # ====================================================================
    # ÉTAT 1 : LA VUE PUBLIQUE (Sans MatLoc)
    # ====================================================================
    if not matloc_membre:
        _render_header()
        _render_fil_actualites()

        tab_priere, tab_meditation, tab_musique = st.tabs(["🙏 Prières", "📖 Méditations", "🎵 Musiques"])
        _render_spiritual_tabs(tab_priere, tab_meditation, tab_musique)
        return

    # ====================================================================
    # ÉTAT 2 : LA VUE MEMBRE (Avec MatLoc)
    # ====================================================================
    # FIX : normalisation — un lien WhatsApp copié avec espace ou un matloc
    # retapé en minuscules donnait "Identifiant inconnu" sans recours
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
        # FIX : proposer la vue publique plutôt qu'un cul-de-sac
        st.info("💡 Vous pouvez consulter l'espace public ci-dessous.")
        _render_header()
        _render_fil_actualites()
        tab_priere, tab_meditation, tab_musique = st.tabs(["🙏 Prières", "📖 Méditations", "🎵 Musiques"])
        _render_spiritual_tabs(tab_priere, tab_meditation, tab_musique)
        return

    _render_header(membre)

    # CARTE BIENVENUE
    st.markdown(f"""
    <div class="postcard">
        <h2>Bienvenue {membre[2]} 🕊️</h2>
        <p style="font-size: 0.85rem;"><em>{membre[8] or ''} | {membre[9] or ''}</em></p>
    </div>
    """, unsafe_allow_html=True)

    _render_fil_actualites()

    # AGENDA (Expander)
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
                icone_evt = {"Prière mensuelle": "🧎", "Prière commune": "🙏", "Prière spéciale": "✨", "Pèlerinage": "🚶‍♂️", "Réunion": "🤝"}.get(prochain_evt[2], "📅")

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
                            c.execute("UPDATE suivi_presences SET statut=? WHERE membre_id=? AND evenement_id=?", (choix, membre[0], evt_id))
                        else:
                            c.execute("INSERT INTO suivi_presences (membre_id, evenement_id, statut) VALUES (?, ?, ?)", (membre[0], evt_id, choix))
                        commit_and_sync()
                        # FIX : .pop() au lieu de del (KeyError possible si l'état
                        # a été partiellement nettoyé)
                        st.session_state.pop('repondre_event_id', None)
                        st.session_state.pop('choix_action', None)
                        # FIX : flash mémorisé (l'ancien success + rerun était
                        # invisible — et sur cette page, le flash est affiché
                        # localement en haut de show_espace_membre)
                        st.session_state["flash_success"] = "Merci pour votre engagement ! 🙏"
                        st.rerun()
        else:
            st.success("✅ Aucun événement à venir. Profitez de ce temps de repos !")

    st.markdown("---")

    # ARCHIVES
    tab_priere, tab_meditation, tab_musique = st.tabs(["🙏 Prières", "📖 Méditations", "🎵 Musiques"])
    _render_spiritual_tabs(tab_priere, tab_meditation, tab_musique)
