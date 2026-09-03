import os
import streamlit as st
from database import c
from services import hash_password, afficher_messages_flash

# --- Configuration de la page ---
st.set_page_config(page_title="Gestionnaire des Équipes du Rosaire - Diocèse de Grand-Bassam", layout="wide")

# --- CSS personnalisé ---
# FIX : déplacé AVANT l'interception des liens spéciaux, pour que les pages
# publiques (espace spirituel, réponse membre) profitent aussi des styles.
st.markdown("""
<style>
    .stApp { background-color: #FFFFFF !important; }
    .main > div { background-color: #FFFFFF !important; }
    .stMarkdown, .stMarkdown p, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 { color: #1A237E !important; }
    .stMetric label, .stMetric .stMarkdown { color: #1A237E !important; }
    .stSidebar { background-color: #FFFFFF !important; }
    .stSidebar .stMarkdown, .stSidebar label { color: #1A237E !important; }
    .stTextInput input, .stTextArea textarea, .stSelectbox select { background-color: #FFFFFF !important; color: #1A237E !important; }
    .whatsapp-link {
        display: inline-block; background-color: #25D366; color: white !important;
        padding: 5px 12px; border-radius: 30px; text-decoration: none; font-size: 13px; margin-top: 5px;
    }
    .whatsapp-link:hover { background-color: #128C7E; color: white !important; }
    .stMarkdown h1, .stMarkdown h1 * {
        color: #1A237E !important; white-space: nowrap !important; overflow: hidden !important;
        text-overflow: ellipsis !important; font-size: clamp(1rem, 3vw, 2rem) !important;
    }
    .stMarkdown h2 { color: #1A237E !important; font-size: 1.4rem !important; }
    .stMarkdown h3, .stMarkdown h3 * {
        color: #1A237E !important; white-space: nowrap !important; overflow: hidden !important;
        text-overflow: ellipsis !important; font-size: clamp(0.8rem, 4vw, 1.2rem) !important; margin-bottom: 5px !important;
    }
    .custom-info-box { font-size: 0.9rem; color: #1A237E; margin-bottom: 40px !important; line-height: 1.6; }
    [data-testid="stMetricLabel"] { font-size: 0.9rem !important; }
    [data-testid="stMetricValue"] { font-size: 1.3rem !important; }
    [data-testid="stMetricDelta"] { font-size: 0.8rem !important; }
    @media (max-width: 768px) {
        .stMarkdown p, .stText { font-size: 0.9rem !important; }
    }
</style>
""", unsafe_allow_html=True)


def afficher_logo():
    if not os.path.exists("images"):
        try:
            os.makedirs("images")
        except Exception:
            pass
    logo_path = os.path.join("images", "logo.png")
    if os.path.exists(logo_path):
        try:
            st.sidebar.image(logo_path, width="stretch")   # FIX : use_container_width déprécié
        except Exception:
            st.sidebar.caption("⚡ Erreur de chargement du logo")
    st.sidebar.markdown("---\n#### 🏛️ DIOCÈSE DE GRAND-BASSAM\n---")


# --- INTERCEPTION DES LIENS SPECIAUX ---
params = st.query_params
espace_val = params.get("espace", None)
matloc_val = params.get("matloc", None)
event_val = params.get("e", None)

if espace_val:
    if isinstance(espace_val, list): espace_val = espace_val[0]
    if isinstance(matloc_val, list): matloc_val = matloc_val[0]
    from views.view_espace_membre import show_espace_membre
    # FIX : normalisation + dégradation PROPRE vers la vue publique si matloc absent
    # (l'ancien lien ?espace=1 sans matloc passait None à la vue)
    matloc_propre = str(matloc_val).upper().strip() if matloc_val else None
    show_espace_membre(matloc_propre)
    st.stop()

elif event_val:
    if isinstance(event_val, list): event_val = event_val[0]
    from components import afficher_page_reponse_membre
    afficher_page_reponse_membre(event_val)
    st.stop()


# --- AUTH ---
if 'logged_in' not in st.session_state:
    afficher_logo()

    st.caption("🔒 Application réservée aux gestionnaires autorisés.")
    with st.expander("📜 Mentions Légales & Confidentialité"):
        st.markdown("""
        **Responsable de traitement :** Diocèse de Grand-Bassam.

        **Finalité :** Gestion administrative, spirituelle et logistique des membres des équipes du Rosaire (contacts, présences, abonnements, photos).

        **Données collectées :** Nom, prénom, date de naissance, numéro WhatsApp, photo d'identité.

        **Durée de conservation :** Les données sont conservées tant que le membre est actif, puis archivées. Elles sont supprimées 3 ans après le départ définitif.

        **Vos droits :** Vous pouvez demander au responsable de votre équipe de modifier ou supprimer vos informations en lui envoyant un message WhatsApp.

        *Conformément aux principes de protection des données personnelles.*
        """)

    st.sidebar.title("🔐 Connexion")
    # FIX : st.form → la touche Entrée soumet désormais le formulaire
    with st.sidebar.form("form_login"):
        u = st.text_input("Utilisateur", key="login_user")
        p = st.text_input("Mot de passe", type="password", key="login_pass")
        submitted_login = st.form_submit_button("Se connecter", width="stretch")

    if submitted_login:
        if not u.strip() or not p:   # FIX : garde champs vides
            st.sidebar.warning("Veuillez saisir vos identifiants.")
        else:
            # FIX : SELECT explicite des colonnes (l'ancien SELECT * casse si
            # une colonne est ajoutée/réordonnée : rôle attribué silencieusement faux)
            user = c.execute('''SELECT id, username, password, role, diocese_id, paroisse_id, equipe_id
                                FROM utilisateurs WHERE username=? AND password=?''',
                             (u.strip(), hash_password(p))).fetchone()
            if user:
                st.session_state.update({
                    'logged_in': True, 'user_id': user[0], 'username': user[1],
                    'role': user[3], 'diocese_id': user[4], 'paroisse_id': user[5], 'equipe_id': user[6]
                })
                # FIX : flash mémorisé (l'ancien st.success + st.rerun était invisible)
                st.session_state['flash_success'] = f"Bienvenue {user[1]} !"
                st.rerun()
            else:
                st.sidebar.error("Identifiants incorrects")
    st.stop()

afficher_logo()
st.sidebar.success(f"Connecté : {st.session_state['username']}")
if st.sidebar.button("Déconnexion"):
    for k in list(st.session_state.keys()): del st.session_state[k]
    st.query_params.clear()   # FIX : purge aussi ?e= / ?espace= / ?matloc de l'URL
    st.rerun()

st.markdown('<a href="#" style="text-decoration: none; color: inherit;"><h1 style="color:#1A237E; cursor: pointer;">📿 GESTIONNAIRE DES ÉQUIPES DU ROSAIRE</h1></a>', unsafe_allow_html=True)
st.markdown("---")

# FIX : affichage des messages flash posés au run précédent (login, vues...)
afficher_messages_flash()

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
else:
    # FIX : plus de page blanche silencieuse sur rôle inconnu
    st.error(f"⚠️ Rôle inconnu ('{st.session_state.get('role')}'). Contactez l'administrateur.")
