import os
import streamlit as st

# --- v7.9.12 — LA SENTINELLE DU PAQUET COMPLET ----------------------------
# Le paquet vit d'un seul souffle : si un versement chez l'hébergeur est
# arrivé incomplet (un fichier ancien qui survit au milieu des nouveaux,
# observé le 26 octobre 2026 — les vues nouvelles devant l'ancien cœur),
# les pages s'emmêlent et le fidèle voit un mur de code. Désormais le cœur
# se fait reconnaître AVANT tout autre import : si l'un des gestes récents
# lui manque, la maison affiche sa note douce et s'arrête net — jamais de
# traceback, ni pour la fondatrice, ni pour les fidèles.
import database as _coeur_paquet
_paquet_complet = all(hasattr(_coeur_paquet, _nom) for _nom in (
    "tableau_pointages_equipe",               # v7.9.11 — le tableau de la chaîne
    "tableau_pointages_visiteurs",            # v7.9.11 — les passages anonymes
    "publier_reserve_due",                    # v7.9.10 — le réveil de 00h00
    "envoyer_intention_du_jour_en_reserve",   # v7.9.10 — le sas des intentions
    "feuillet_reponses_enregistrer",          # v7.10.0 — le questionnaire du feuillet
    "mission_creer",                          # v7.10.0 — l'envoi en mission
    "importer_dizaines_hors_ligne",           # v7.10.0 — les dizaines hors ligne
))
# ---------------------------------------------------------------------------

# v7.8.16 — fin des avertissements « Please replace st.components.v1.html
# with st.iframe » : rendu HTML centralisé dans stcompat.py (st.iframe si
# disponible, repli components.v1.html sur les anciennes versions).
from stcompat import comp_html as _comp_html
from database import c, commit_and_sync
from services import (hash_password, verifier_mot_de_passe,
                      migrer_hash_si_legacy, definir_mot_de_passe,
                      creer_token_session, verifier_token_session,
                      supprimer_token_session)

# --- Configuration de la page ---
# v7.8.14 — page_icon par défaut 📿 : l'icône Streamlit (❗) disparaît de l'onglet.
# L'injection dynamique (injecter_icone_pwa) affine ensuite : 📿 Espaces / 🔑 Admin.
st.set_page_config(page_title="Gestionnaire des Équipes du Rosaire - Diocèse de Grand-Bassam",
                   page_icon="📿", layout="wide")

# --- v7.9.12 — LA NOTE DOUCE DU VERSEMENT INCOMPLET ------------------------
# (le drapeau _paquet_complet a été levé tout en haut, avant les imports ;
#  la note s'affiche APRÈS set_page_config — première commande Streamlit)
if not _paquet_complet:
    st.markdown("""
    <div style="min-height:58vh; display:flex; align-items:center; justify-content:center;">
      <div style="background:linear-gradient(135deg,#241042 0%,#4A148C 100%);
                  border-radius:20px; padding:2.6rem 2rem; text-align:center;
                  border:1px solid rgba(255,255,255,0.14); max-width:540px;
                  box-shadow:0 18px 50px rgba(20,8,45,0.45); margin:2rem auto;">
        <div style="font-size:3rem; line-height:1;">🕊️</div>
        <div style="color:#ffffff; font-size:1.2rem; font-weight:600; margin:0.9rem 0 0.6rem;">
          Un instant — la maison se pare</div>
        <div style="color:#eadcff; font-size:0.98rem; line-height:1.65;">
          Quelque chose de beau se met en place derrière les murs et la
          préparation n'est pas tout à fait achevée.<br>
          Reviens nous voir dans quelques minutes : tout sera prêt.</div>
        <div style="color:#c9b3f2; font-size:0.86rem; margin-top:1.2rem; font-style:italic;">
          Sainte Marie, veille sur cette maison pendant qu'elle se prépare.</div>
      </div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()
# ---------------------------------------------------------------------------

# --- v7.8.8 : RÉVEIL des publications programmées (lazy cron) ---
# Streamlit n'a pas de tâche de fond : chaque chargement de page vérifie
# (au plus toutes les 60 s par session) si des publications programmées
# par le diocèse sont arrivées à échéance et les publie.
import time as _time_mod
if _time_mod.time() - float(st.session_state.get("_reveil_programmes_ts", 0)) > 60:
    st.session_state["_reveil_programmes_ts"] = _time_mod.time()
    from services import executer_publications_programmees
    executer_publications_programmees()


# --- INTERCEPTION DES LIENS SPECIAUX ---
params = st.query_params

# Utilisation de .get() qui est la méthode moderne et fiable de Streamlit
espace_val = params.get("espace", None)
matloc_val = params.get("matloc", None)
event_val = params.get("e", None)

if espace_val:
    # Au cas où Streamlit renvoie une liste au lieu d'une chaîne
    if isinstance(espace_val, list): espace_val = espace_val[0]
    if isinstance(matloc_val, list): matloc_val = matloc_val[0]
    
    # v7.8.14 — icône 📿 (favicon + PWA) pour les Espaces de Prière
    from components import injecter_icone_pwa
    injecter_icone_pwa(espace=True)

    from views.view_espace_membre import show_espace_membre
    show_espace_membre(matloc_val)
    st.stop()
    
elif event_val:
    if isinstance(event_val, list): event_val = event_val[0]
    from components import afficher_page_reponse_membre, injecter_icone_pwa
    injecter_icone_pwa(espace=True)   # page publique : icône 📿
    afficher_page_reponse_membre(event_val)
    st.stop()

# v7.8.14 — Administration (connexion + rôles) : icône 🔑 (favicon + PWA)
from components import injecter_icone_pwa
injecter_icone_pwa(espace=False)

# --- CSS personnalisé ---
st.markdown("""
<style>
    .stApp { background-color: #FFFFFF !important; }
    .main > div { background-color: #FFFFFF !important; }
    .stMarkdown, .stMarkdown p, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 { color: #1A237E !important; }
    .stMetric label, .stMetric .stMarkdown { color: #1A237E !important; }
    .stSidebar { background-color: #FFFFFF !important; }
    .stSidebar .stMarkdown, .stSidebar label { color: #1A237E !important; }
    .stTextInput input, .stTextArea textarea, .stSelectbox select { background-color: #FFFFFF !important; color: #1A237E !important; }
    /* === v7.10.4 — TOUT LISIBLE SUR BLANC (bat le thème sombre du navigateur) ===
       L'Administration est peinte blanc : libellés des champs, notes,
       alertes et titres d'expanders restent en encre bleue, les champs sur
       fond blanc — quel que soit le mode (clair/sombre) du téléphone.
       (Répare les textes invisibles de la chaîne d'une séance et du
       questionnaire quand l'écran du lecteur est en mode sombre.) */
    .stApp label, .stApp label p, .stApp label div { color: #1A237E !important; }
    .stApp [data-testid="stWidgetLabel"] p { color: #1A237E !important; }
    .stApp [data-testid="stCaptionContainer"],
    .stApp [data-testid="stCaptionContainer"] * { color: #3E517A !important; }
    .stApp [data-testid="stAlert"] { background-color: #E8EAF6 !important; }
    .stApp [data-testid="stAlert"] .stMarkdown,
    .stApp [data-testid="stAlert"] p,
    .stApp [data-testid="stAlert"] div,
    .stApp [data-testid="stAlert"] span,
    .stApp [data-testid="stAlert"] li { color: #1A237E !important; }
    .stApp details summary, .stApp details summary p,
    .stApp details summary div { color: #1A237E !important; }
    .stApp input, .stApp textarea { background-color: #FFFFFF !important;
        color: #1A237E !important; }
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
    # v7.9.15 — LE LOGO PARTOUT : le fichier images/logo.png est désormais
    # LIVRÉ avec l'application (c'est le chapelet doré des Équipes du
    # Rosaire). Il est cherché à plusieurs adresses certaines : à côté du
    # fichier app.py (où que l'application soit installée), puis depuis le
    # dossier de lancement ; en dernier recours, le chapelet livré dans
    # static/ prend le relais. Pour passer au logo officiel du Mouvement,
    # il suffira de déposer la nouvelle image sous le même nom
    # (images/logo.png) — aucun code à modifier.
    _ici = os.path.dirname(os.path.abspath(__file__))
    for _chemin in (os.path.join(_ici, "images", "logo.png"),
                    os.path.join("images", "logo.png"),
                    os.path.join(_ici, "static", "logo_equipes_rosaire.png"),
                    os.path.join("static", "logo_equipes_rosaire.png")):
        if os.path.exists(_chemin):
            try:
                st.sidebar.image(_chemin, width="stretch")
            except Exception:
                pass
            break

    st.sidebar.markdown("---\n#### 🏛️ DIOCÈSE DE GRAND-BASSAM\n---")

# --- SESSION PERSISTANTE : rester connecté malgré le rafraîchissement ---
if 'logged_in' not in st.session_state:
    _tok = st.query_params.get("t")
    if isinstance(_tok, list):
        _tok = _tok[0] if _tok else None
    if _tok:
        _user = verifier_token_session(_tok)
        if _user:
            st.session_state.update({
                'logged_in': True, 'user_id': _user[0], 'username': _user[1],
                'role': _user[3], 'diocese_id': _user[4], 'paroisse_id': _user[5],
                'equipe_id': _user[6]
            })
            # Restaurer la rubrique où l'utilisateur se trouvait avant le F5
            if _user[7]:
                _cle_menu = {"diocese": "nav_dio", "paroisse": "nav_par",
                             "equipe": "nav_eq"}.get(_user[3])
                if _cle_menu:
                    st.session_state[_cle_menu] = _user[7]
                st.session_state["_menu_sync"] = _user[7]
        else:
            # Jeton inconnu ou expiré : on le retire de l'URL
            try:
                del st.query_params["t"]
            except Exception:
                pass

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

    # PARADE AUTOFILL (v2) : le gestionnaire de mots de passe remplit les champs
    # sans déclencher l'événement que Streamlit écoute. On notifie Streamlit de
    # TOUTE valeur présente au branchement (autofill déjà effectué) puis de tout
    # changement ultérieur sans événement.
    _comp_html("""
        <script>
        (function(){
          function notifier(f){
            try{
              var natif = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
              natif.call(f, f.value);
            }catch(e){}
            f.dispatchEvent(new Event('input', {bubbles:true}));
            f.dispatchEvent(new Event('change', {bubbles:true}));
          }
          var essais = 0;
          var t = setInterval(function(){
            essais++;
            try {
              var d = window.parent.document;
              var zone = d.querySelector('[data-testid="stSidebar"]') || d;
              var ins = zone.querySelectorAll('input[type="text"], input[type="password"]');
              for(var i=0;i<ins.length;i++){
                var f = ins[i];
                if(f.dataset.pf77 === undefined){
                  f.dataset.pf77 = f.value || '';
                  if(f.value){ notifier(f); }
                  f.addEventListener('input', function(){ this.dataset.pf77 = this.value; });
                } else if(f.value !== (f.dataset.pf77 || '')){
                  notifier(f);
                  f.dataset.pf77 = f.value;
                }
              }
            } catch(e) {}
            if(essais > 600){ clearInterval(t); }
          }, 300);
        })();
        </script>
    """, height=0)

    # v7.9.11 — LA CONNEXION D'UNE SEULE PIÈCE : les deux champs forment
    # désormais UN formulaire — coller l'utilisateur puis le mot de passe
    # ne déclenche plus de rechargement intermédiaire qui essuyait le
    # premier champ (« Identifiants incorrects » alors que tout était
    # pourtant collé). Tout part ensemble, au clic ; la parade AUTOFILL
    # ci-dessus demeure pour les gestionnaires de mots de passe.
    with st.sidebar.form("connexion_gestionnaire", clear_on_submit=False):
        u = st.text_input("Utilisateur", key="login_user")
        p = st.text_input("Mot de passe", type="password", key="login_pass")
        _connecter = st.form_submit_button("Se connecter", use_container_width=True)
    if _connecter:
        row = c.execute("SELECT id, username, password, role, diocese_id, paroisse_id, equipe_id FROM utilisateurs WHERE username=?",
                        ((u or "").strip(),)).fetchone()
        if row and verifier_mot_de_passe(p or "", row[2]):
            migrer_hash_si_legacy(row[0], row[2], p or "")
            st.session_state.update({
                'logged_in': True, 'user_id': row[0], 'username': row[1],
                'role': row[3], 'diocese_id': row[4], 'paroisse_id': row[5], 'equipe_id': row[6]
            })
            # On force le menu de navigation sur la PREMIÈRE rubrique du rôle
            _entrees = {"diocese": ("nav_dio", "🏛️ Voir diocèse"),
                        "paroisse": ("nav_par", "🏘️ Ma paroisse"),
                        "equipe": ("nav_eq", "👥 Mon équipe")}
            if row[3] in _entrees:
                _cle, _val = _entrees[row[3]]
                st.session_state[_cle] = _val
            # Session persistante : jeton dans l'URL → le rafraîchissement
            # ne déconnecte plus (30 jours, révoqué à la déconnexion)
            _menu_premier = st.session_state.get({"diocese": "nav_dio", "paroisse": "nav_par",
                                                  "equipe": "nav_eq"}.get(row[3]))
            st.query_params["t"] = creer_token_session(row[0], _menu_premier)
            st.rerun()
        else:
            st.sidebar.error("Identifiants incorrects.")

    # v7.9.8 — le gestionnaire sous la main : la carte « raccourcis » de la
    # page de recherche du navigateur n'écrit PAS sur l'écran d'accueil —
    # seul le menu du navigateur pose la vraie icône.
    # v7.9.10 — la page d'installation porte le bon visage dès le premier
    # octet : le raccourci posé DEPUIS ELLE ne peut plus porter un autre nom.
    st.sidebar.caption("📲 Garde-le sous la main : menu ⋮ du navigateur → « Ajouter à l'écran d'accueil ».")
    st.sidebar.markdown('<a href="/app/static/install_rosaire_admin.html" target="_self"'
                        ' style="text-decoration:none;">📲 Poser le raccourci — page'
                        ' d&#8217;installation</a>', unsafe_allow_html=True)

    # 🔑 Secours « mot de passe oublié » — placé APRÈS le bouton Se connecter
    _reset_token = None
    try:
        _reset_token = st.secrets.get("RESET_TOKEN")
    except Exception:
        pass
    if _reset_token:
        with st.sidebar.expander("🔑 Mot de passe oublié ?"):
            tok = st.text_input("Clé de secours", type="password", key="rst_tok")
            nu = st.text_input("Utilisateur", value="diocese", key="rst_user")
            np1 = st.text_input("Nouveau mot de passe", type="password", key="rst_pwd")
            if st.button("Réinitialiser"):
                if tok != _reset_token or not np1:
                    st.sidebar.error("Clé invalide ou mot de passe vide.")
                elif not c.execute("SELECT 1 FROM utilisateurs WHERE username=?", ((nu or "").strip(),)).fetchone():
                    st.sidebar.error("Utilisateur inconnu.")
                else:
                    c.execute("UPDATE utilisateurs SET password=? WHERE username=?",
                              (definir_mot_de_passe(np1), (nu or "").strip()))
                    commit_and_sync()
                    st.sidebar.success("Mot de passe réinitialisé ! Connectez-vous.")

    st.stop()

afficher_logo()
st.sidebar.success(f"Connecté : {st.session_state['username']}")
if st.sidebar.button("Déconnexion"):
    _tok = st.query_params.get("t")
    if isinstance(_tok, list):
        _tok = _tok[0] if _tok else None
    if _tok:
        supprimer_token_session(_tok)
    for k in list(st.session_state.keys()): del st.session_state[k]
    try:
        del st.query_params["t"]   # retire le jeton de l'URL
    except Exception:
        pass
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
elif st.session_state['role'] == 'communication':
    from views.view_communication import show_communication
    show_communication()
