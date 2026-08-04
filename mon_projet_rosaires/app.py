import os
import streamlit as st
from database import c, commit_and_sync
from services import hash_password

# --- Configuration de la page ---
st.set_page_config(page_title="Gestionnaire des Équipes du Rosaire - Diocèse de Grand-Bassam", layout="wide")

# --- INTERCEPTION DU LIEN MAGIQUE (MEMBRE) ---
try:
    params = st.query_params
    if "e" in params:
        event_id = params["e"]
        
        # CORRECTION CRITIQUE : Les nouvelles versions de Streamlit renvoient une liste ex: ["11"] au lieu de "11"
        if isinstance(event_id, list):
            event_id = event_id[0]
            
        from components import afficher_page_reponse_membre
        afficher_page_reponse_membre(event_id)
        st.stop() # On bloque l'affichage du reste de la page (donc pas de connexion demandée)
except Exception as e:
    pass # En cas d'erreur, on laisse l'application se charger normalement
# -------------------------------------------------

# --- CSS personnalisé ---
st.markdown("""
<style>
    .stApp { background-color: #FFFFFF !important; }
    .main > div { background-color: #FFFFFF !important; }
    .stMarkdown, .stMarkdown p, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 { color: #1A237E !important; }
    .streamlit-expanderHeader span:last-child { display: none !important; }
    .stMetric label, .stMetric .stMarkdown { color: #1A237E !important; }
    .stSidebar { background-color: #FFFFFF !important; }
    .stSidebar .stMarkdown, .stSidebar label { color: #1A237E !important; }
    .stTextInput input, .stTextArea textarea, .stSelectbox select { background-color: #FFFFFF !important; color: #1A237E !important; }
    .whatsapp-link {
        display: inline-block;
        background-color: #25D366;
        color: white !important;
        padding: 5px 12px;
        border-radius: 30px;
        text-decoration: none;
        font-size: 13px;
        margin-top: 5px;
    }
    .whatsapp-link:hover {
        background-color: #128C7E;
        color: white !important;
    }

    /* TITRE PRINCIPAL (h1) */
    .stMarkdown h1, .stMarkdown h1 * {
        color: #1A237E !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        font-size: clamp(1rem, 3vw, 2rem) !important;
    }

    /* TITRES DE SECTIONS (h2) */
    .stMarkdown h2 {
        color: #1A237E !important;
        font-size: 1.4rem !important;
    }

    /* SOUS-TITRES (h3) */
    .stMarkdown h3, .stMarkdown h3 * {
        color: #1A237E !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        font-size: clamp(0.8rem, 4vw, 1.2rem) !important;
        margin-bottom: 5px !important;
    }
    
    /* BLOC D'INFORMATIONS */
    .custom-info-box {
        font-size: 0.9rem;
        color: #1A237E;
        margin-bottom: 40px !important;
        line-height: 1.6;
    }

    /* Donne de l'air au bouton "Modifier" (expanders) */
    .streamlit-expander {
        margin-top: 20px !important;
    }

    /* ✅ RÉDUIRE LA TAILLE DES INDICATEURS (st.metric) */
    [data-testid="stMetricLabel"] {
        font-size: 0.9rem !important;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.3rem !important;
    }
    [data-testid="stMetricDelta"] {
        font-size: 0.8rem !important;
    }
    
    /* RÈGLES POUR LES PETITS ÉCRANS */
    @media (max-width: 768px) {
        .stMarkdown p, .stText {
            font-size: 0.9rem !important;
        }
    }
</style>
""", unsafe_allow_html=True)


def afficher_logo():
    # Créer le dossier s'il n'existe pas
    if not os.path.exists("images"):
        try:
            os.makedirs("images")
        except Exception:
            pass
    
    logo_path = os.path.join("images", "logo.png")
    if os.path.exists(logo_path):
        try:
            st.sidebar.image(logo_path, use_container_width=True)
        except Exception:
            st.sidebar.caption("⚡ Erreur de chargement du logo")
    
    st.sidebar.markdown("---\n#### 🏛️ DIOCÈSE DE GRAND-BASSAM\n---")

# --- AUTH ---
if 'logged_in' not in st.session_state:
    afficher_logo()
    st.sidebar.title("🔐 Connexion")
    
    # Ajout de clés explicites pour éviter les conflits de mémoire de Streamlit
    u = st.sidebar.text_input("Utilisateur", key="login_user")
    p = st.sidebar.text_input("Mot de passe", type="password", key="login_pass")
    
    if st.sidebar.button("Se connecter"):
        user = c.execute("SELECT * FROM utilisateurs WHERE username=? AND password=?", (u, hash_password(p))).fetchone()
        if user:
            st.session_state.update({
                'logged_in': True, 
                'user_id': user[0], 
                'username': user[1], 
                'role': user[3], 
                'diocese_id': user[4], 
                'paroisse_id': user[5], 
                'equipe_id': user[6]
            })
            st.success(f"Bienvenue {u}")
            st.rerun()
        else: 
            st.sidebar.error("Identifiants incorrects")
    st.stop()

afficher_logo()
st.sidebar.success(f"Connecté : {st.session_state['username']}")
if st.sidebar.button("Déconnexion"):
    for k in list(st.session_state.keys()): del st.session_state[k]
    st.rerun()

st.markdown('<a href="#" style="text-decoration: none; color: inherit;"><h1 style="color:#1A237E; cursor: pointer;">📿 GESTIONNAIRE DES ÉQUIPES DU ROSAIRE</h1></a>', unsafe_allow_html=True)
st.markdown("---")

# --- ROUTAGE MVC ---
if st.session_state['role'] == 'diocese':
    from views.view_diocese import show_diocese
    show_diocese()
elif st.session_state['role'] == 'paroisse':
    from views.view_paroisse import show_paroisse
    show_paroisse()
elif st.session_state['role'] == 'equipe':
    from views.view_equipe import show_equipe
    show_equipe()