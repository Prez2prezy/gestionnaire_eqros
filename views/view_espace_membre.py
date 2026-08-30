import os
import streamlit as st
import streamlit.components.v1 as components
import json
from datetime import date
from database import c, commit_and_sync
from services import safe_date

# --- DESIGN DE L'ESPACE SPIRITUEL ---
st.markdown("""
<style>
    .postcard {
        background: linear-gradient(135deg, #f3e5f5 0%, #e8eaf6 100%);
        padding: 20px;
        border-radius: 15px;
        text-align: center;
        margin: 15px 10px;
        box-shadow: 0 4px 12px rgba(69, 39, 160, 0.08);
        color: #4527a0;
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
        width: 100%; margin-bottom: 0; border-bottom: 3px solid #4527a0; max-height: 250px; object-fit: cover;
    }
    .event-flyer-content { padding: 15px; text-align: center; }
    .event-flyer h4 { margin: 0 0 5px 0; color: #4527a0; font-size: 1.1rem; }
    .event-flyer p { margin: 0; color: #666; font-size: 0.9rem; }
</style>
""", unsafe_allow_html=True)

def show_espace_membre(matloc_membre=None):
    
    # ====================================================================
    # ÉTAT 1 : LA VUE PUBLIQUE (Sans MatLoc)
    # ====================================================================
    if not matloc_membre:
        col_logo, col_titre = st.columns([1, 5])
        with col_logo:
            logo_path = os.path.join("images", "logo.png")
            if os.path.exists(logo_path):
                st.image(logo_path, width=600)
        with col_titre:
            st.markdown("<h2 style='color:#4527a0; margin:0;'>Équipes du Rosaire</h2><p style='color:#666; margin:0;'>Diocèse de Grand-Bassam</p>", unsafe_allow_html=True)
        
        # --- CARTE POSTALE PUBLIQUE ---
        dernier_contenu = c.execute("SELECT titre, contenu_texte, image_url FROM espace_spirituel WHERE type_contenu IN ('priere', 'meditation') ORDER BY date_publication DESC LIMIT 1").fetchone()
        if dernier_contenu:
            img_html = f"<img src='{dernier_contenu[2]}' alt='Méditation'>" if dernier_contenu[2] else ""
            st.markdown(f"""
            <div class="postcard">
                {img_html}
                {dernier_contenu[1]}
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("Aucun contenu spirituel n'a encore été publié.")

        # --- COIN AFFICHE PUBLIQUE ---
        try:
            affiches_dispo = c.execute("SELECT titre, date_evenement, lieu, affiche_url FROM evenements WHERE affiche_url IS NOT NULL ORDER BY date_evenement DESC LIMIT 5").fetchall()
        except ValueError:
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
        
        # --- ARCHIVES ---
        tab_priere, tab_meditation, tab_musique = st.tabs(["🙏 Prières", "📖 Méditations", "🎵 Musiques"])
        _render_spiritual_tabs(tab_priere, tab_meditation, tab_musique)
        return

    # ====================================================================
    # ÉTAT 2 : LA VUE MEMBRE (Avec MatLoc)
    # ====================================================================
    membre = c.execute("""
        SELECT m.id, m.nom, m.prenom, m.matloc, m.whatsapp, m.date_adhesion, m.photo_path, m.numero_meditation, e.nom_equipe, p.nom 
        FROM membres m 
        LEFT JOIN equipes e ON m.equipe_id = e.id 
        LEFT JOIN paroisses p ON m.paroisse_id = p.id 
        WHERE m.matloc=? AND m.statut='actif'
    """, (matloc_membre,)).fetchone()
    
    if not membre:
        st.error("Identifiant inconnu ou membre inactif.")
        return

    # EN-TÊTE MEMBRE
    col_logo, col_titre, col_profil = st.columns([1, 5, 1])
    with col_logo:
        logo_path = os.path.join("images", "logo.png")
        if os.path.exists(logo_path):
            st.image(logo_path, width=600)
    with col_titre:
        st.markdown("<h2 style='color:#4527a0; margin:0;'>Équipes du Rosaire</h2><p style='color:#666; margin:0;'>Diocèse de Grand-Bassam</p>", unsafe_allow_html=True)
    with col_profil:
        with st.popover("👤 Mon Profil"):
            st.markdown("### 📄 Mes informations")
            st.code(f"🪪 MatLoc : {membre[3]}")
            st.code(f"📿 N° Méditation : {membre[7] or 'Non défini'}")
            st.code(f"👥 Équipe : {membre[8] or 'Non assignée'}")
            st.code(f"🏛️ Paroisse : {membre[9] or 'Non assignée'}")
            if membre[4]: st.code(f"💬 WhatsApp : {membre[4]}")

    # --- CARTE POSTALE MEMBRE ---
    dernier_contenu = c.execute("SELECT titre, contenu_texte, image_url FROM espace_spirituel WHERE type_contenu IN ('priere', 'meditation') ORDER BY date_publication DESC LIMIT 1").fetchone()
    if dernier_contenu:
        img_html = f"<img src='{dernier_contenu[2]}' alt='Prière'>" if dernier_contenu[2] else ""
        st.markdown(f"""
        <div class="postcard">
            {img_html}
            <h2>Bienvenue {membre[2]} 🕊️</h2>
            <p style="font-size: 0.85rem;"><em>{membre[8] or ''} | {membre[9] or ''}</em></p>
            <hr style="border: 0.5px solid #d1c4e9; width: 50%; margin: 10px auto;">
            {dernier_contenu[1]}
        </div>
        """, unsafe_allow_html=True)

    # --- COIN AFFICHE MEMBRE ---
    try:
        affiches_dispo = c.execute("SELECT titre, date_evenement, lieu, affiche_url FROM evenements WHERE affiche_url IS NOT NULL ORDER BY date_evenement DESC LIMIT 5").fetchall()
    except ValueError:
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

    # --- AGENDA (Expander) ---
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

                if 'repondre_event_id' in st.session_state:
                    evt_id = st.session_state['repondre_event_id']
                    if st.button("✅ Confirmer définitivement", type="primary"):
                        choix = st.session_state.get('choix_action', 'physique')
                        deja_repondu = c.execute("SELECT statut FROM suivi_presences WHERE membre_id=? AND evenement_id=?", (membre[0], evt_id)).fetchone()
                        if deja_repondu:
                            c.execute("UPDATE suivi_presences SET statut=? WHERE membre_id=? AND evenement_id=?", (choix, membre[0], evt_id))
                        else:
                            c.execute("INSERT INTO suivi_presences (membre_id, evenement_id, statut) VALUES (?, ?, ?)", (membre[0], evt_id, choix))
                        commit_and_sync()
                        del st.session_state['repondre_event_id']
                        del st.session_state['choix_action']
                        st.success("Merci pour votre engagement ! 🙏")
                        st.rerun()
        else:
            st.success("✅ Aucun événement à venir. Profitez de ce temps de repos !")

    st.markdown("---")
    
    # --- ARCHIVES ---
    tab_priere, tab_meditation, tab_musique = st.tabs(["🙏 Prières", "📖 Méditations", "🎵 Musiques"])
    _render_spiritual_tabs(tab_priere, tab_meditation, tab_musique)


# ====================================================================
# FONCTIONS PRIVÉES
# ====================================================================
def _render_spiritual_tabs(tab_priere, tab_meditation, tab_musique):
    with tab_priere:
        prières = c.execute("SELECT titre, contenu_texte, image_url FROM espace_spirituel WHERE type_contenu='priere' ORDER BY date_publication DESC").fetchall()
        if not prières: st.info("Aucune prière publiée.")
        else:
            for p in prières:
                with st.expander(f"📖 {p[0]}"):
                    if p[2] and p[2].startswith("http"): st.image(p[2], use_column_width="auto")
                    if p[1]: st.markdown(p[1], unsafe_allow_html=True)

    with tab_meditation:
        meditations = c.execute("SELECT titre, contenu_texte, image_url FROM espace_spirituel WHERE type_contenu='meditation' ORDER BY date_publication DESC").fetchall()
        if not meditations: st.info("Aucune méditation disponible.")
        else:
            for m in meditations:
                with st.expander(f"📖 {m[0]}"):
                    if m[2] and m[2].startswith("http"): st.image(m[2], use_column_width="auto")
                    if m[1]: st.markdown(m[1], unsafe_allow_html=True)

    with tab_musique:
        audios = c.execute("SELECT titre, fichier_url FROM espace_spirituel WHERE type_contenu='audio' ORDER BY date_publication DESC").fetchall()
        if not audios: st.info("Aucun fichier audio.")
        else:
            for a in audios:
                if a[1] and a[1].startswith("http"):
                    st.markdown(f"#### 🎵 {a[0]}")
                    st.audio(a[1])
                    st.markdown("---")
                else:
                    st.warning(f"Le fichier audio pour '{a[0]}' est introuvable.")
