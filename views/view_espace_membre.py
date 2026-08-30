import streamlit as st

# --- DESIGN DE L'ESPACE SPIRITUEL ---
st.markdown("""
<style>
    /* L'en-tête épuré */
    .header-spirituel {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 10px 0px 0px 10px;
    }
    .header-text-main { color: #4527a0; font-weight: bold; font-size: 1.1rem; margin: 0; line-height: 1.2; }
    .header-text-sub { color: #666; font-size: 0.85rem; margin: 0; }
    
    /* La Carte Postale Spirituelle */
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
        border-radius: 12px; 
        width: 100%; 
        max-height: 220px; /* Réduction de la taille de l'image */
        object-fit: cover; /* Recadrage automatique sans écraser l'image */
        margin-bottom: 15px; 
        box-shadow: 0 2px 6px rgba(0,0,0,0.1); 
    }
</style>
""", unsafe_allow_html=True)

def show_espace_membre(matloc_membre=None):
    
    # ====================================================================
    # ÉTAT 1 : LA VUE PUBLIQUE (Sans MatLoc)
    # ====================================================================
    if not matloc_membre:
        # En-tête Public
        st.markdown("""
        <div class="header-spirituel">
            <img src="https://img.icons8.com/fluency/48/rosary.png" width="45">
            <div>
                <p class="header-text-main">Équipes du Rosaire</p>
                <p class="header-text-sub">Diocèse de Grand-Bassam</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # La Carte Postale
        st.markdown("""
        <div class="postcard">
            <img src="https://images.unsplash.com/photo-1507692049790-de58290a4334?w=800" alt="Méditation">
            <h2>La paix du Seigneur soit avec vous</h2>
            <p>"Venez à moi, vous tous qui êtes fatigués et chargés, et je vous donnerai du repos."</p>
            <p style="font-size: 0.8rem; color: #666;"><em>Méditation du jour</em></p>
        </div>
        """, unsafe_allow_html=True)
        
        # Les onglets d'archives
        tab_priere, tab_meditation, tab_musique = st.tabs(["🙏 Prières", "📖 Méditations", "🎵 Musiques"])
        with tab_priere: st.info("Ici, l'historique de toutes les prières (Vue Publique)")
        with tab_meditation: st.info("Ici, l'historique de toutes les méditations (Vue Publique)")
        with tab_musique: st.info("Ici, le lecteur de musiques natif de Streamlit (Vue Publique)")
        return

    # ====================================================================
    # ÉTAT 2 : LA VUE MEMBRE (Avec MatLoc)
    # ====================================================================
    
    # En-tête Membre : Logo à gauche, Profil à droite
    col_header, col_profil = st.columns([6, 1])
    with col_header:
        st.markdown("""
        <div class="header-spirituel">
            <img src="https://img.icons8.com/fluency/48/rosary.png" width="45">
            <div>
                <p class="header-text-main">Équipes du Rosaire</p>
                <p class="header-text-sub">Diocèse de Grand-Bassam</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col_profil:
        st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True) # Petit espace pour aligner
        with st.popover("👤 Mon Profil"):
            st.markdown("### 📄 Mes informations")
            st.code("🪪 MatLoc : GBA-7YK50")
            st.code("📿 N° Méditation : 05")
            st.code("👥 Équipe : Équipe 2")
            st.code("📅 Fidélité : 5 an(s)")

    # La Carte Postcale Personnalisée
    st.markdown("""
    <div class="postcard">
        <img src="https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=800" alt="Prière">
        <h2>Bienvenue Germaine 🕊️</h2>
        <p style="font-size: 0.85rem;"><em>Équipe 2 | Notre Dame de L'Assomption</em></p>
        <hr style="border: 0.5px solid #d1c4e9; width: 50%; margin: 10px auto;">
        <p>"Seigneur, fais de moi un instrument de ta paix..."</p>
        <p style="font-size: 0.8rem; color: #666;"><em>Prière du jour</em></p>
    </div>
    """, unsafe_allow_html=True)

    # L'agenda dans un expander
    with st.expander("📅 Mes prochains évènements"):
        st.markdown("**🧎 Prière mensuelle**")
        st.write("📍 Église de Koumassi")
        st.caption("📅 Dans 12 jours")
        
        col1, col2 = st.columns(2)
        with col1: st.button("🟢 Présent physiquement", use_container_width=True, type="primary")
        with col2: st.button("🟡 Présent spirituellement", use_container_width=True)

    st.markdown("---")
    
    # Les onglets d'archives
    tab_priere, tab_meditation, tab_musique = st.tabs(["🙏 Prières", "📖 Méditations", "🎵 Musiques"])
    with tab_priere: st.info("Ici, l'historique de toutes les prières (Vue Membre)")
    with tab_meditation: st.info("Ici, l'historique de toutes les méditations (Vue Membre)")
    with tab_musique: st.info("Ici, le lecteur de musiques natif de Streamlit (Vue Membre)")
