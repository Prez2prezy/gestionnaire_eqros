import streamlit as st
from datetime import date
from database import c
from services import safe_date

# --- Un design plus doux et apaisant pour l'espace de prière ---
st.markdown("""
<style>
    .espace-header {
        text-align: center;
        padding: 30px;
        background: linear-gradient(135deg, #e8eaf6 0%, #f3e5f5 100%);
        border-radius: 15px;
        margin-bottom: 30px;
    }
    .espace-title {
        color: #4527a0 !important;
        font-size: 2rem !important;
        margin-bottom: 10px !important;
    }
    .espace-subtitle {
        color: #6a1b9a !important;
        font-size: 1.1rem !important;
    }
</style>
""", unsafe_allow_html=True)

def show_espace_membre(matloc_membre=None):
    # --- 1. EN-TÊTE PERSONNALISÉ OU PUBLIC ---
    if matloc_membre:
        membre = c.execute("SELECT nom, prenom, nom_equipe FROM membres m JOIN equipes e ON m.equipe_id = e.id WHERE m.matloc=? AND m.statut='actif'", (matloc_membre,)).fetchone()
        if membre:
            st.markdown(f"""
            <div class="espace-header">
                <h1 class="espace-title">🙏 Bienvenue {membre[1]} {membre[0]}</h1>
                <p class="espace-subtitle">Équipe {membre[2]}</p>
                <p class="espace-subtitle" style="font-size: 0.9rem; opacity: 0.8;">Voici votre espace de ressourcement spirituel</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="espace-header">
                <h1 class="espace-title">📿 Espace de Prière</h1>
                <p class="espace-subtitle">Bienvenue dans cet espace de paix</p>
            </div>
            """, unsafe_allow_html=True)
            st.warning("Identifiant de membre inconnu. Vous voyez l'espace public.")
    else:
        st.markdown("""
        <div class="espace-header">
            <h1 class="espace-title">📿 Espace de Prière & Méditation</h1>
            <p class="espace-subtitle">Diocèse de Grand-Bassam</p>
        </div>
        """, unsafe_allow_html=True)

    # --- 2. LES ONGLETS DE CONTENU ---
    tab_priere, tab_meditation, tab_musique, tab_evenements = st.tabs([
        "🙏 Prières & Oraisons", 
        "📖 Méditations", 
        "🎵 Musique & Chants", 
        "📅 Mes prochains événements"
    ])

    with tab_priere:
        st.markdown("### 🙏 Textes de prières")
        prières = c.execute("SELECT titre, contenu_texte, image_url FROM espace_spirituel WHERE type_contenu='priere' ORDER BY date_publication DESC").fetchall()
        if not prières:
            st.info("Aucune prière publiée pour le moment.")
        else:
            for p in prières:
                with st.expander(f"📖 {p[0]}"):
                    if p[2]: # S'il y a une image d'illustration
                        st.image(p[2], width="stretch")
                    st.write(p[1])

    with tab_meditation:
        st.markdown("### 📖 Textes de méditation")
        meditations = c.execute("SELECT titre, contenu_texte, image_url FROM espace_spirituel WHERE type_contenu='meditation' ORDER BY date_publication DESC").fetchall()
        if not meditations:
            st.info("Aucune méditation disponible pour le moment.")
        else:
            for m in meditations:
                with st.expander(f"📖 {m[0]}"):
                    if m[2]: # S'il y a une image d'illustration
                        st.image(m[2], width="stretch")
                    st.write(m[1])

    with tab_musique:
        st.markdown("### 🎵 Écouter des chants et méditations audio")
        # CORRECTION : On récupère maintenant l'image_url
        audios = c.execute("SELECT titre, fichier_url, image_url FROM espace_spirituel WHERE type_contenu='audio' ORDER BY date_publication DESC").fetchall()
        if not audios:
            st.info("Aucun fichier audio n'a encore été ajouté.")
        else:
            for a in audios:
                st.markdown("---")
                col_image, col_player = st.columns([1, 3])
                with col_image:
                    if a[2]: # S'il y a une image
                        st.image(a[2], use_column_width="always")
                    else:
                        st.markdown("<div style='background:#f3e5f5; height:150px; border-radius:10px; display:flex; align-items:center; justify-content:center; font-size:3rem;'>🎵</div>", unsafe_allow_html=True)
                with col_player:
                    st.markdown(f"#### {a[0]}")
                    if a[1]:
                        st.audio(a[1])

    with tab_evenements:
        st.markdown("### 📅 Événements à venir")
        if matloc_membre:
            evenements = c.execute('''
                SELECT e.id, e.date_evenement, e.type_evenement, e.lieu 
                FROM evenements e 
                JOIN evenement_equipes ee ON e.id = ee.evenement_id 
                JOIN membres m ON ee.equipe_id = m.equipe_id 
                WHERE m.matloc = ? AND e.date_evenement >= ?
                ORDER BY e.date_evenement ASC LIMIT 5
            ''', (matloc_membre, date.today().isoformat())).fetchall()
            
            if not evenements:
                st.success("✅ Aucun événement à venir. Profitez de ce temps de repos !")
            else:
                for ev in evenements:
                    ev_date = safe_date(ev[1])
                    if not ev_date: continue
                    
                    # Calcul du délai
                    delta = (ev_date - date.today()).days
                    if delta == 0: delai = "🔴 Aujourd'hui !"
                    elif delta == 1: delai = "🟠 Demain"
                    elif delta <= 7: delai = f"🟡 Dans {delta} jours"
                    else: delai = f"🟢 Dans {delta} jours"
                    
                    icone = {"Prière mensuelle": "🧎", "Prière commune": "🙏", "Prière spéciale": "✨", "Pèlerinage": "🚶‍♂️", "Réunion": "🤝"}.get(ev[2], "📅")
                    
                    # Affichage en carte
                    st.markdown(f"""
                    <div style="background: white; padding: 15px; border-radius: 10px; border-left: 5px solid #4527a0; margin-bottom: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.05);">
                        <b>{icone} {ev[2]}</b><br>
                        📅 {ev_date.strftime('%d/%m/%Y')} ({delai})<br>
                        📍 {ev[3] or 'Lieu à définir'}
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Bouton de réponse rapide
                    base_url = "https://gestionnaireeqros-4s9fbumnsa6wmyy6dw4rft.streamlit.app/" 
                    magic_link = f"{base_url}/?e={ev[0]}"
                    st.markdown(f'<a href="{magic_link}" target="_blank" style="display: inline-block; background-color: #4527a0; color: white; padding: 5px 15px; border-radius: 20px; text-decoration: none; font-size: 0.9rem; margin-top: -10px;">✍️ Confirmer ma présence</a>', unsafe_allow_html=True)
        else:
            st.info("Connectez-vous avec votre lien personnel (contenant votre numéro MatLoc) pour voir vos prochains événements ici.")
