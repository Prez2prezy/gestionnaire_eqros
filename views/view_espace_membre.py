import streamlit as st

# --- DESIGN DE L'ESPACE SPIRITUEL ---
st.markdown("""
<style>
    /* L'en-tête épuré */
    .header-spirituel {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 10px 20px;
        background-color: white;
        border-bottom: 1px solid #f0f0f0;
    }
    
    /* La Carte Postale Spirituelle */
    .postcard {
        background: linear-gradient(135deg, #f3e5f5 0%, #e8eaf6 100%);
        padding: 30px;
        border-radius: 20px;
        text-align: center;
        margin: 20px;
        box-shadow: 0 4px 15px rgba(69, 39, 160, 0.1);
        color: #4527a0;
    }
    .postcard h2 { margin-top: 0; color: #4527a0; }
    .postcard img { border-radius: 15px; max-width: 100%; margin-bottom: 20px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }
    
    /* L'agenda doux */
    .soft-agenda {
        background: white;
        padding: 20px;
        border-radius: 15px;
        margin: 0px 20px 20px 20px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        border-left: 5px solid #7e57c2;
    }
</style>
""", unsafe_allow_html=True)

def show_espace_membre(matloc_membre=None):
    
    # ====================================================================
    # ÉTAT 1 : LA VUE PUBLIQUE (Sans MatLoc)
    # ====================================================================
    if not matloc_membre:
        st.markdown('<div class="header-spirituel"><div style="text-align:center; width:100%;"><h2 style="color:#4527a0; margin:0;">🕊️ Équipes du Rosaire - Grand-Bassam</h2></div></div>', unsafe_allow_html=True)
        
        # La Carte Postale
        st.markdown("""
        <div class="postcard">
            <img src="https://images.unsplash.com/photo-1507692049790-de58290a4334?w=800" alt="Méditation">
            <h2>La paix du Seigneur soit avec vous</h2>
            <p style="font-size: 1.1rem;">"Venez à moi, vous tous qui êtes fatigués et chargés, et je vous donnerai du repos."</p>
            <p><em>Méditation du jour - Publié le 24/05/2024</em></p>
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
    
    # En-tête : Logo à gauche, Profil à droite
    st.markdown("""
    <div class="header-spirituel">
        <div style="display: flex; align-items: center; gap: 10px;">
            <img src="https://img.icons8.com/fluency/48/rosary.png" width="40">
            <span style="color:#4527a0; font-weight:bold; font-size:1.1rem;">Rosaire GB</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # La petite icône Profil (Cachant l'admin)
    with st.popover("👤 Mon Profil"):
        st.markdown("### 📄 Mes informations administratives")
        st.code("🪪 MatLoc : GBA-7YK50")
        st.code("📿 N° Méditation : 05")
        st.code("👥 Équipe : Équipe 2")
        st.code("📅 Fidélité : 5 an(s)")
        st.markdown("*Ces infos seront cachées de l'écran principal pour ne pas polluer la prière.*")

    # La Carte Postale Personnalisée
    st.markdown("""
    <div class="postcard">
        <img src="https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=800" alt="Prière">
        <h2>Bienvenue Germaine 🕊️</h2>
        <p style="font-size: 1.1rem;"><em>Équipe 2 | Notre Dame de L'Assomption</em></p>
        <hr style="border: 0.5px solid #d1c4e9; width: 50%; margin: 15px auto;">
        <p>"Seigneur, fais de moi un instrument de ta paix..."</p>
        <p><em>Prière du jour</em></p>
    </div>
    """, unsafe_allow_html=True)

    # L'agenda doux (Uniquement pour le membre)
    st.markdown("""
    <div class="soft-agenda">
        <h4 style="color:#4527a0; margin-top:0;">🧎 Prochain rassemblement</h4>
        <p><b>Prière mensuelle</b> - Samedi 15 Juin</p>
        <p>📍 Église de Koumassi</p>
        <p style="font-size:0.9rem; color:#666;">📅 Dans 12 jours</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1: st.button("🟢 Présent physiquement", use_container_width=True, type="primary")
    with col2: st.button("🟡 Présent spirituellement", use_container_width=True)

    st.markdown("---")
    
    # Les onglets d'archives (Identiques au public)
    tab_priere, tab_meditation, tab_musique = st.tabs(["🙏 Prières", "📖 Méditations", "🎵 Musiques"])
    with tab_priere: st.info("Ici, l'historique de toutes les prières (Vue Membre)")
    with tab_meditation: st.info("Ici, l'historique de toutes les méditations (Vue Membre)")
    with tab_musique: st.info("Ici, le lecteur de musiques natif de Streamlit (Vue Membre)")
