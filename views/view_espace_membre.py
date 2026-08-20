import streamlit as st
from datetime import date
from database import c

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
        audios = c.execute("SELECT titre, fichier_url FROM espace_spirituel WHERE type_contenu='audio' ORDER BY date_publication DESC").fetchall()
        if not audios:
            st.info("Aucun fichier audio n'a encore été ajouté.")
        else:
            for a in audios:
                st.markdown(f"#### 🎵 {a[0]}")
                if a[1]:
                    st.audio(a[1])
                st.markdown("---")

    with tab_evenements:
        st.markdown("### 📅 Événements à venir")
        if matloc_membre:
            # S'il est connecté avec son matloc, on cherche ses événements à venir non passés
            evenements = c.execute('''
                SELECT e.date_evenement, e.type_evenement, e.lieu 
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
                    st.markdown(f"**{ev[1]}** - 📅 {ev[0]} - 📍 {ev[2] or 'Lieu à définir'}")
        else:
            st.info("Connectez-vous avec votre lien personnel (contenant votre numéro MatLoc) pour voir vos prochains événements ici.")
