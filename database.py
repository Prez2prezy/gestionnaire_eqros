import sqlite3
import os
import time
import hashlib
import secrets
import logging
from datetime import date, datetime

# Configuration du logging pour éviter d'utiliser st.error dans la base de données
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

# --- Connexion DB ---
def create_connection():
    try:
        try:
            from libsql import connect as turso_connect
        except ImportError:
            from libsql_experimental import connect as turso_connect
        import streamlit as st
        url = st.secrets.get("TURSO_URL")
        token = st.secrets.get("TURSO_AUTH_TOKEN")
        if url and token:
            # On fait 2 tentatives en cas de micro-coupure réseau
            for attempt in range(2):
                try:
                    return turso_connect(url, auth_token=token), True
                except Exception as e:
                    if attempt == 0:
                        import time
                        time.sleep(1) # On attend 1 seconde et on réessaie
                    else:
                        raise e # Si ça rate 2 fois, on laisse planter l'app pour forcer un redémarrage propre
    except Exception as e:
        # Vérification de sécurité : Les clés Turso sont-elles dans les paramètres ?
        url = None
        token = None
        try:
            import streamlit as st
            url = st.secrets.get("TURSO_URL")
            token = st.secrets.get("TURSO_AUTH_TOKEN")
        except Exception:
            pass
        
        # SI les clés Turso existent mais la connexion échoue, ON NE FAIT PAS DE FALLBACK.
        # On lève une erreur pour forcer Streamlit Cloud à redémarrer l'app proprement.
        if url and token:
            raise Exception(f"Connexion à Turso perdue. Redémarrage en cours... ({e})")
            
    # Si Turso n'est pas configuré du tout, on utilise bien le fichier local
    return sqlite3.connect('gestion_religieuse.db', check_same_thread=False), False

def init_db():
    import streamlit as st
    @st.cache_resource
    def get_conn():
        conn, is_turso = create_connection()
        return conn, is_turso
    return get_conn()

conn, USE_TURSO = init_db()

class CursorWrapper:
    def __init__(self, cursor):
        self.cursor = cursor

    def execute(self, query, params=None):
        last_err = None
        for attempt in range(3):
            try:
                return self.cursor.execute(query, tuple(params) if params else ())
            except Exception as e:
                msg = str(e).lower()
                # v7.8.16 — micro-coupures Hrana/Turso élargies : outre
                # « stream not found » et « connection reset », on rattrape
                # désormais « connection closed before message completed »,
                # les erreurs http transitoires et les dépassements de délai
                # (observés en production Streamlit Cloud, où ils faisaient
                # planter la page entière). Après 3 tentatives + reconnexion,
                # l'erreur remonte normalement.
                if ("stream not found" in msg or "connection reset" in msg
                        or "connection closed" in msg
                        or "connection terminated" in msg
                        or "http error" in msg
                        or "timeout" in msg or "timed out" in msg):
                    time.sleep(1)
                    global conn
                    try:
                        conn, _ = create_connection()
                        self.cursor = conn.cursor()
                        last_err = e
                        continue
                    except Exception as e2:
                        last_err = e2
                        continue
                if "duplicate column" not in msg:
                    logger.error(f"Erreur SQL : {e}")
                raise
        raise Exception(f"Connexion Turso instable : 3 tentatives échouées ({last_err})")

    def __getattr__(self, name):
        return getattr(self.cursor, name)

c = CursorWrapper(conn.cursor()) if USE_TURSO else conn.cursor()

def commit_and_sync():
    try:
        conn.commit()
    except Exception as e:
        logger.error(f"Erreur lors du commit : {e}")

# --- Fonction de migration sécurisée ---
def safe_migrate(query, error_ignore_phrases=["duplicate column", "duplicate column name"]):
    """Exécute une requête de migration en ignorant silencieusement les erreurs de doublon.
    v7.6.2 : s'exécute sur une CONNEXION JETABLE — une migration qui échoue
    ne peut plus contaminer le curseur partagé utilisé par l'application."""
    try:
        conn_tmp, _ = create_connection()
        cur_tmp = conn_tmp.cursor()
        cur_tmp.execute(query)
        conn_tmp.commit()
        try:
            conn_tmp.close()
        except Exception:
            pass
    except Exception as e:
        error_msg = str(e).lower()
        if not any(phrase in error_msg for phrase in error_ignore_phrases):
            logger.warning(f"Migration ignorée ou échouée: {e}")

# --- Création des tables et Migrations (Exécuté UNE SEULE FOIS) ---
def _definir_mdp(p):
    """PBKDF2 local (services.py ne peut pas être importé ici : dépendance circulaire)."""
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", p.encode(), bytes.fromhex(salt), 200_000)
    return f"pbkdf2${salt}${dk.hex()}"

def init_tables_and_migrations():
    # --- 1. CRÉATION DES TABLES ---
    c.execute("""CREATE TABLE IF NOT EXISTS diocese (id INTEGER PRIMARY KEY, nom TEXT, responsable TEXT, bureau TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS paroisses (id INTEGER PRIMARY KEY, nom TEXT, commune TEXT, ville TEXT, responsable TEXT, bureau TEXT, diocese_id INTEGER)""")
    c.execute("""CREATE TABLE IF NOT EXISTS equipes (id INTEGER PRIMARY KEY, nom_equipe TEXT, responsable TEXT, bureau TEXT, paroisse_id INTEGER, max_membres INTEGER DEFAULT 10)""")
    c.execute("""CREATE TABLE IF NOT EXISTS membres (id INTEGER PRIMARY KEY, matloc TEXT UNIQUE, nom TEXT, prenom TEXT, date_naissance DATE, whatsapp TEXT, date_adhesion DATE, photo_path TEXT, paroisse_id INTEGER, equipe_id INTEGER, statut TEXT DEFAULT 'actif', numero_meditation TEXT, matricule TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS utilisateurs (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, role TEXT, diocese_id INTEGER, paroisse_id INTEGER, equipe_id INTEGER)""")
    c.execute("""CREATE TABLE IF NOT EXISTS abonnements (id INTEGER PRIMARY KEY, membre_id INTEGER, annee_debut INTEGER, date_paiement DATE, montant REAL DEFAULT 0, type_abonnement TEXT DEFAULT 'abonnement', statut TEXT DEFAULT 'non_paye')""")
    c.execute("""CREATE TABLE IF NOT EXISTS archives (id INTEGER PRIMARY KEY, membre_id INTEGER, situation TEXT, date_debut DATE, date_fin DATE, commentaire TEXT, auteur_id INTEGER, auteur_nom TEXT, auteur_role TEXT, paroisse_id INTEGER, equipe_id INTEGER)""")
    c.execute("""CREATE TABLE IF NOT EXISTS evenements (id INTEGER PRIMARY KEY, equipe_id INTEGER, paroisse_id INTEGER, diocese_id INTEGER, type_evenement TEXT, date_evenement DATE, lieu TEXT, auteur_nom TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS evenement_equipes (id INTEGER PRIMARY KEY, evenement_id INTEGER, equipe_id INTEGER)""")
    c.execute("""CREATE TABLE IF NOT EXISTS suivi_presences (id INTEGER PRIMARY KEY, membre_id INTEGER, evenement_id INTEGER, statut TEXT DEFAULT 'a_contacter')""")
    c.execute("""CREATE TABLE IF NOT EXISTS agenda (id INTEGER PRIMARY KEY, equipe_id INTEGER, paroisse_id INTEGER, diocese_id INTEGER, date_event DATE, type_event TEXT, lieu TEXT, description TEXT, auteur_nom TEXT, a_faire_suivre INTEGER DEFAULT 0, evenement_id INTEGER)""")
    c.execute("""CREATE TABLE IF NOT EXISTS periodes_cloturees (id INTEGER PRIMARY KEY AUTOINCREMENT, entite_type TEXT, entite_id INTEGER, annee_debut INTEGER, date_cloture TEXT, auteur_nom TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS espace_spirituel (id INTEGER PRIMARY KEY, type_contenu TEXT, titre TEXT, contenu_texte TEXT, fichier_url TEXT, date_publication DATE, auteur_nom TEXT, image_url TEXT)""")
    # Soumissions Communication — schéma COMPLET dès la création
    c.execute("""CREATE TABLE IF NOT EXISTS soumissions_comm (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    auteur_id INTEGER, type_contenu TEXT, titre TEXT,
                    contenu_texte TEXT, image_url TEXT, fichier_url TEXT,
                    video_url TEXT, date_evenement TEXT, lieu TEXT,
                    statut TEXT DEFAULT 'attente', motif_refus TEXT,
                    date_soumission TEXT, paroisse_cible INTEGER)""")
    # Statistiques & traçabilité
    c.execute("""CREATE TABLE IF NOT EXISTS visites_paroisse (id INTEGER PRIMARY KEY AUTOINCREMENT, paroisse_id INTEGER, date_visite TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS stats_visites (id INTEGER PRIMARY KEY AUTOINCREMENT, page TEXT, date_visite DATE)""")
    # Sessions persistantes (rester connecté malgré le rafraîchissement)
    c.execute("""CREATE TABLE IF NOT EXISTS sessions_persistantes (
                    token TEXT PRIMARY KEY, user_id INTEGER, date_creation DATE,
                    menu_courant TEXT)""")
    # Thème pastoral (3 tables requises par mysteres.py + components.py)
    c.execute("""CREATE TABLE IF NOT EXISTS themes_pastoraux (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    annee_debut INTEGER UNIQUE, texte_theme TEXT,
                    mystere_principal INTEGER, actif INTEGER DEFAULT 0)""")
    c.execute("""CREATE TABLE IF NOT EXISTS sous_themes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    annee_debut INTEGER, mois INTEGER,
                    titre TEXT, contenu TEXT, feuillet_pdf TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS theme_mystere (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    annee_debut INTEGER, mystere_id INTEGER, texte_lien TEXT,
                    UNIQUE(annee_debut, mystere_id))""")
    # Sections du feuillet mensuel en équipe (v7.7.9) — créée DÈS L'INIT
    # (auparavant seulement à la volée dans components.py, ce qui rendait
    # les lectures de l'Espace membre dépendantes d'une visite préalable
    # de la gestion diocèse du thème).
    c.execute("""CREATE TABLE IF NOT EXISTS feuillet_sections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    annee_debut INTEGER, mois INTEGER,
                    ordre INTEGER, titre TEXT, contenu TEXT,
                    lecteur TEXT, image_url TEXT)""")
    # Publications du feuillet mensuel de prière (v7.8) — publier un feuillet
    # déclenche l'alerte dans le fil d'actualité et son archivage automatique.
    c.execute("""CREATE TABLE IF NOT EXISTS feuillets_publications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    annee_debut INTEGER, mois INTEGER, numero INTEGER,
                    date_publication TEXT,
                    UNIQUE(annee_debut, mois))""")
    # v7.8.10 — couverture personnalisée du livret (par mois pastoral) :
    # elle accompagne l'alerte « 📖 Nouveau feuillet » et le sommaire du
    # livret. Sans image saisie, une couverture est générée automatiquement.
    c.execute("""CREATE TABLE IF NOT EXISTS feuillets_couvertures (
                    annee_debut INTEGER, mois INTEGER, image_url TEXT,
                    UNIQUE(annee_debut, mois))""")
    # v7.8.16 — intentions confiées aux équipes : la table est créée ICI aussi
    # (elle ne l'était qu'à la volée dans les vues). Sur les bases distantes
    # créées par une version antérieure (Turso / Streamlit Cloud), la table
    # existe SANS les colonnes récentes — les ALTER idempotents ci-dessous
    # réparent la structure au démarrage, sans toucher aux données.
    c.execute("""CREATE TABLE IF NOT EXISTS intentions_equipes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    equipe_id INTEGER NOT NULL,
                    texte TEXT NOT NULL,
                    auteur_nom TEXT,
                    auteur_contact TEXT,
                    anonyme INTEGER DEFAULT 0,
                    jour_naissance INTEGER,
                    statut TEXT DEFAULT 'recue',
                    date_soumission TEXT,
                    date_statut TEXT)""")
    # v7.9.0 — réglages de l'application (choix de l'« intention du prochain »
    # dans la chaîne de prière universelle, etc.). Petite table clé/valeur
    # créée ici pour exister dès le 1er démarrage sur TOUTES les bases.
    c.execute("""CREATE TABLE IF NOT EXISTS parametres (
                    cle TEXT PRIMARY KEY,
                    valeur TEXT)""")
    # v7.9.1 — GALERIE + : souvenirs (photos des évènements, pèlerinages,
    # moments d'équipe) et témoignages (grâces reçues). Publiée par le
    # diocèse, lue par toute la communauté dans la rubrique « 🖼️ Galerie + »
    # des Espaces de Prière.
    c.execute("""CREATE TABLE IF NOT EXISTS galerie_plus (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rubrique TEXT,
                    titre TEXT,
                    texte TEXT,
                    image_url TEXT,
                    date_event TEXT,
                    lieu TEXT,
                    auteur_nom TEXT,
                    date_publication TEXT)""")
    # v7.9.2 — JOURNAL DES DIZAINES : le pointage « ✅ J'ai égrené ma
    # dizaine aujourd'hui » (fin du livre « 🕯️ Un jour, une dizaine »).
    # Un membre est identifié par son matloc (1 pointage/jour, contrainte
    # UNIQUE) ; un visiteur n'a pas d'identité fiable : il est compté
    # comme un « passage » (type='visiteur', jrnais = jour de naissance
    # saisi au livret, sans contrainte d'unicité).
    c.execute("""CREATE TABLE IF NOT EXISTS dizaines_journal (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    matloc TEXT,
                    nom TEXT,
                    type TEXT DEFAULT 'membre',
                    jrnais INTEGER,
                    equipe_id INTEGER,
                    paroisse_id INTEGER,
                    jour TEXT,
                    heure TEXT,
                    UNIQUE(matloc, jour))""")
    # v7.9.3 — RÉSERVE D'INTENTIONS PAR N° MÉD. : pour CHACUN des 20 N° de
    # méditation, les responsables d'équipe et paroissiaux préparent À
    # L'AVANCE 20 intentions (celles de leurs membres). Le visiteur du jour
    # reçoit, selon SON N° méd., l'intention placée à cet emplacement de la
    # réserve et la médite sur 20 jours — la chaîne ne tombe jamais à sec.
    c.execute("""CREATE TABLE IF NOT EXISTS intentions_reserve (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    numero_med INTEGER NOT NULL,
                    texte TEXT NOT NULL,
                    auteur_nom TEXT,
                    equipe_id INTEGER,
                    paroisse_id INTEGER,
                    date_ajout TEXT)""")
    commit_and_sync()

    # --- 2. DONNÉES PAR DÉFAUT ---
    if c.execute("SELECT COUNT(*) FROM diocese").fetchone()[0] == 0:
        c.execute("INSERT INTO diocese (nom, responsable, bureau) VALUES (?, ?, ?)", ("GRAND-BASSAM", "À définir", "À définir"))
    if c.execute("SELECT COUNT(*) FROM utilisateurs WHERE role='diocese'").fetchone()[0] == 0:
        c.execute("INSERT INTO utilisateurs (username, password, role, diocese_id) VALUES (?, ?, ?, ?)",
                  ("diocese", _definir_mdp("admin123"), "diocese", 1))
    commit_and_sync()

    # --- 3. MIGRATIONS STRUCTURELLES (idempotentes) ---
    safe_migrate("ALTER TABLE membres RENAME COLUMN matricule TO matloc")
    # v7.6.2 — migration « mle_sup » RETIRÉE : la colonne n'existe pas dans
    # la base actuelle ; cette requête échouait à chaque démarrage et
    # contaminait les requêtes suivantes (erreurs « tuple index out of range »).
    # safe_migrate("ALTER TABLE membres RENAME COLUMN mle_sup TO matricule")
    safe_migrate("ALTER TABLE membres ADD COLUMN matricule TEXT")
    safe_migrate("ALTER TABLE agenda ADD COLUMN a_faire_suivre INTEGER DEFAULT 0")
    safe_migrate("ALTER TABLE evenements ADD COLUMN paroisse_id INTEGER")
    safe_migrate("ALTER TABLE evenements ADD COLUMN diocese_id INTEGER")
    safe_migrate("ALTER TABLE evenements ADD COLUMN auteur_nom TEXT")
    safe_migrate("ALTER TABLE agenda ADD COLUMN evenement_id INTEGER")
    safe_migrate("ALTER TABLE espace_spirituel ADD COLUMN image_url TEXT")
    # Visuels d'évènements + ciblage paroissial
    safe_migrate("ALTER TABLE evenements ADD COLUMN affiche_url TEXT")
    safe_migrate("ALTER TABLE evenements ADD COLUMN video_url TEXT")
    safe_migrate("ALTER TABLE evenements ADD COLUMN paroisse_cible INTEGER")
    safe_migrate("ALTER TABLE espace_spirituel ADD COLUMN paroisse_cible INTEGER")
    # WhatsApp responsables
    safe_migrate("ALTER TABLE paroisses ADD COLUMN whatsapp_responsable TEXT")
    safe_migrate("ALTER TABLE diocese ADD COLUMN whatsapp_responsable TEXT")
    # Base ancienne : colonne ajoutée rétroactivement
    safe_migrate("ALTER TABLE soumissions_comm ADD COLUMN paroisse_cible INTEGER")
    # Affiches du thème pastoral et des sous-thèmes mensuels
    safe_migrate("ALTER TABLE themes_pastoraux ADD COLUMN affiche_url TEXT")
    safe_migrate("ALTER TABLE sous_themes ADD COLUMN affiche_url TEXT")
    # Rubrique courante mémorisée dans le jeton de session
    safe_migrate("ALTER TABLE sessions_persistantes ADD COLUMN menu_courant TEXT")
    # Colonnes de l'actualité validée (date + lieu informatifs) — migrées ici
    # plutôt qu'à la volée dans view_communication_validation.py (robustesse)
    safe_migrate("ALTER TABLE espace_spirituel ADD COLUMN date_evenement TEXT")
    safe_migrate("ALTER TABLE espace_spirituel ADD COLUMN lieu TEXT")
    # v7.8.11 — position de la photo dans la page du livret (haut/droite/gauche)
    safe_migrate("ALTER TABLE feuillet_sections ADD COLUMN pos_image TEXT")
    # v7.8.16 — intentions_equipes : colonnes récentes ajoutées rétroactivement
    # (correctif de l'erreur « table intentions_equipes has no column named
    # anonyme » observée sur la base de production Streamlit Cloud/Turso).
    safe_migrate("ALTER TABLE intentions_equipes ADD COLUMN auteur_contact TEXT")
    safe_migrate("ALTER TABLE intentions_equipes ADD COLUMN anonyme INTEGER DEFAULT 0")
    # v7.9.0 — jour de naissance du fidèle (clé discrète de la chaîne de
    # prière : il garantit qu'un visiteur ne prie jamais SA propre intention).
    safe_migrate("ALTER TABLE intentions_equipes ADD COLUMN jour_naissance INTEGER")
    # v7.9.1 — Galerie + (souvenirs / témoignages) : la table est aussi
    # (re)créée doucement ici, pour les bases distantes antérieures.
    try:
        c.execute("""CREATE TABLE IF NOT EXISTS galerie_plus (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        rubrique TEXT, titre TEXT, texte TEXT,
                        image_url TEXT, date_event TEXT, lieu TEXT,
                        auteur_nom TEXT, date_publication TEXT)""")
        commit_and_sync()
    except Exception:
        pass
    # v7.8.11 — publications de feuillets : dédoublonnage puis index UNIQUE.
    # Les bases créées avant la contrainte UNIQUE(annee_debut, mois)
    # pouvaient accumuler des lignes jumelles à chaque republication, ce qui
    # embrouillait l'alerte « 📖 Nouveau feuillet » ; l'index garantit aussi
    # le fonctionnement des upserts (ON CONFLICT) sur ces bases anciennes.
    try:
        c.execute("""DELETE FROM feuillets_publications WHERE id NOT IN
                     (SELECT MAX(id) FROM feuillets_publications
                      GROUP BY annee_debut, mois)""")
        c.execute("""CREATE UNIQUE INDEX IF NOT EXISTS idx_feuillets_pub_mois
                     ON feuillets_publications(annee_debut, mois)""")
        commit_and_sync()
    except Exception:
        pass

    # --- 4. MIGRATION DE DONNÉES (évènements anciens) ---
    try:
        anciens_evts = c.execute("SELECT id, equipe_id FROM evenements WHERE equipe_id IS NOT NULL AND paroisse_id IS NULL AND diocese_id IS NULL").fetchall()
        for evt_id, eq_id in anciens_evts:
            existe = c.execute("SELECT id FROM evenement_equipes WHERE evenement_id=? AND equipe_id=?", (evt_id, eq_id)).fetchone()
            if not existe:
                c.execute("INSERT INTO evenement_equipes (evenement_id, equipe_id) VALUES (?, ?)", (evt_id, eq_id))
        commit_and_sync()
    except Exception as e:
        logger.warning(f"Erreur migration événements: {e}")

    # ATTENTION : Les UPDATE de renommage de statut sont retirés d'ici.
    # Les exécuter à chaque chargement fige la DB. Ils doivent être lancés MANUELLEMENT 
    # UNE SEULE FOIS dans un outil de gestion SQLite (comme DB Browser) si la base est ancienne.

# --- INITIALISATION AUTOMATIQUE ---
# On utilise un flag dans session_state pour s'assurer que ça ne tourne qu'UNE SEULE FOIS par session utilisateur
def setup_database():
    import streamlit as st
    if "db_initialized" not in st.session_state:
        init_tables_and_migrations()
        st.session_state.db_initialized = True

# Lancement au chargement du module
try:
    setup_database()
except Exception as e:
    logger.error(f"Erreur critique lors de l'initialisation de la DB: {e}")


# ======================================================================
# v7.8.17 — RÉPARATION CENTRALISÉE de la table intentions_equipes
# ======================================================================
# Les bases distantes (Turso / Streamlit Cloud) créées par un brouillon
# antérieur à la v7.8.14 peuvent manquer de N'IMPORTE QUELLE colonne — et
# le `except` muet de l'onglet équipe masquait l'erreur réelle (aucune trace
# dans les journaux). Cette fonction, appelée par les 2 vues avant toute
# lecture/écriture des intentions :
#   1. SONDE la lecture complète (exactement celle des vues) ;
#   2. en cas d'échec : crée la table si absente + ALTER doux de CHAQUE
#      colonne attendue (idempotent, « duplicate column » ignoré) ;
#   3. re-sonde ; si ça échoue encore, RECRÉE la connexion partagée (cache
#      de statements préparés périmé après ALTER) et sonde une 3e fois ;
#   4. JOURNALISE chaque incident — fini les erreurs invisibles.
_COLONNES_INTENTIONS = (
    "equipe_id INTEGER",
    "texte TEXT",
    "auteur_nom TEXT",
    "auteur_contact TEXT",
    "anonyme INTEGER DEFAULT 0",
    "jour_naissance INTEGER",
    "statut TEXT DEFAULT 'recue'",
    "date_soumission TEXT",
    "date_statut TEXT",
)
_SELECT_INTENTIONS = ("SELECT id, equipe_id, texte, auteur_nom, auteur_contact, "
                      "anonyme, jour_naissance, statut, date_soumission, date_statut "
                      "FROM intentions_equipes LIMIT 1")


def verifier_reparer_intentions():
    """Sonde la table intentions_equipes et la répare si nécessaire (v7.8.17).
    Ne fait RIEN (1 seule petite lecture) quand tout est en ordre."""
    try:
        c.execute(_SELECT_INTENTIONS).fetchone()
        return  # lecture OK : rien à faire
    except Exception as e_probe:
        logger.warning(f"intentions_equipes : sonde en échec ({e_probe}) — réparation")
    # --- Réparation structurelle ---
    try:
        c.execute("""CREATE TABLE IF NOT EXISTS intentions_equipes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        equipe_id INTEGER NOT NULL,
                        texte TEXT NOT NULL,
                        auteur_nom TEXT,
                        auteur_contact TEXT,
                        anonyme INTEGER DEFAULT 0,
                        jour_naissance INTEGER,
                        statut TEXT DEFAULT 'recue',
                        date_soumission TEXT,
                        date_statut TEXT)""")
        for _col in _COLONNES_INTENTIONS:
            try:
                c.execute("ALTER TABLE intentions_equipes ADD COLUMN " + _col)
            except Exception as e_col:
                if "duplicate column" not in str(e_col).lower():
                    logger.warning(f"intentions_equipes : ALTER « {_col} » ignoré ({e_col})")
        commit_and_sync()
    except Exception as e_rep:
        logger.error(f"intentions_equipes : réparation impossible ({e_rep})")
        return
    # --- Re-sonde ; cache périmé → reconnexion partagée puis 3e sonde ---
    try:
        c.execute(_SELECT_INTENTIONS).fetchone()
    except Exception as e2:
        logger.warning(f"intentions_equipes : sonde encore en échec ({e2}) — reconnexion partagée")
        global conn
        try:
            conn, _ = create_connection()
            c.cursor = conn.cursor()
            c.execute(_SELECT_INTENTIONS).fetchone()
        except Exception as e3:
            logger.error(f"intentions_equipes : toujours en échec après reconnexion ({e3})")


# ======================================================================
# v7.9.0 — LA CHAÎNE DE PRIÈRE UNIVERSELLE
# ======================================================================
# Le fidèle qui confie une intention devient « le prochain » de celui qui
# prie : dans « 🕯️ Un jour, une dizaine », la dernière intention de chaque
# mystère (« Intention du prochain dans la chaine de prière ») devient
# DYNAMIQUE et porte une vraie intention.
#
# Le choix de la source est fait par la paroisse (onglet « 🙏 Coins des
# Intentions » de « 📌 Suivi et Agenda ») et mémorisé dans la table
# `parametres` :
#   chaine_mode       = 'recues' (1er choix) | 'en_priere' (2e) | 'universelle' (3e)
#   chaine_universelle= texte choisi parmi INTENTIONS_UNIVERSELLES, ou
#                       'rotation' (rotation quotidienne des trois)
#
# Règle d'or : « Un visiteur ne doit pas pouvoir prier son intention » —
# le jour de naissance saisi à la soumission (colonne jour_naissance) sert
# de clé discrète : quand le visiteur égrène sa dizaine (même jour saisi au
# livret), ses PROPRES intentions sont écartées du tirage.
INTENTIONS_UNIVERSELLES = (
    "La Paix dans le monde",
    "Le Sacrement de la réconciliation",
    "La gestion juste et durable de la ressource vitale : l’eau",
)

_REGLE_20_JOURS = ("NB : une intention prise en charge reste en prière au minimum "
                   "20 jours (20 mystères), sinon jusqu’à la prochaine prière mensuelle.")


def get_parametre(cle, defaut=None):
    """Lit un réglage dans la table parametres (v7.9.0). Tolérant : base
    ancienne sans table → valeur par défaut."""
    try:
        r = c.execute("SELECT valeur FROM parametres WHERE cle=?", (cle,)).fetchone()
        return r[0] if r and r[0] is not None else defaut
    except Exception:
        return defaut


def set_parametre(cle, valeur):
    """Écrit (upsert) un réglage dans la table parametres (v7.9.0)."""
    c.execute("""CREATE TABLE IF NOT EXISTS parametres (
                    cle TEXT PRIMARY KEY,
                    valeur TEXT)""")
    c.execute("INSERT INTO parametres (cle, valeur) VALUES (?, ?) "
              "ON CONFLICT(cle) DO UPDATE SET valeur=excluded.valeur", (cle, str(valeur)))
    commit_and_sync()


def intention_du_prochain_detail(jour_visiteur=None):
    """Retourne (TEXTE, QUI) de l'« intention du prochain » à porter dans la
    dizaine du jour (v7.9.0), selon le choix enregistré par la paroisse :
      1er choix  → les intentions RECUES pas encore prises en charge ;
      2e choix   → les intentions PRISES EN CHARGE (en prière) ;
      3e choix   → une intention universelle de l'Église (fixe ou rotation
                   quotidienne).
    La chaîne est UNIVERSELLE : elle puise dans les intentions confiées à
    toutes les équipes, quel que soit le contexte paroissial du visiteur.
    jour_visiteur = jour de naissance du lecteur (1-31) : ses propres
    intentions lui sont masquées — personne ne prie sa propre intention.
    QUI (v7.9.1) donne la personne INTERCÉDÉE, telle que le livret l'affiche :
      None        → intention universelle (« intercède : … ») ;
      'cet anonyme' → intention anonyme (« intercède pour cet anonyme : … ») ;
      'Prénom Nom'  → intention signée (« intercède pour Prénom Nom : … »).
    v7.9.1 — tirage SELON LE N° MÉD. du lecteur : chaque visiteur reçoit
    l'intention placée à son rang dans la file, au sein d'une fenêtre de
    20 jours (le cycle) — il retrouve la même intention à chaque dizaine de
    la période et deux N° méd. différents portent des intentions différentes
    dès que la file le permet. « Les visiteurs du jour reçoivent les
    intentions de leurs prochains selon leurs N° méd. et méditent avec,
    sur 20 jours. »
    En cas d'intention indisponible, la chaîne ne se casse jamais : elle
    retombe sur « La Paix dans le monde » (QUI = None)."""
    _secours = (INTENTIONS_UNIVERSELLES[0], None)
    try:
        mode = get_parametre("chaine_mode", "recues")
        if mode == "universelle":
            choix = get_parametre("chaine_universelle", INTENTIONS_UNIVERSELLES[0])
            if choix == "rotation":
                # rotation quotidienne (jour de l'année) : les trois intentions
                # universelles se relaient chaque jour.
                return (INTENTIONS_UNIVERSELLES[date.today().timetuple().tm_yday % 3], None)
            return ((choix if choix in INTENTIONS_UNIVERSELLES else _secours[0]), None)
        # v7.9.3 — LA RÉSERVE PAR N° MÉD. : les responsables préparent À
        # L'AVANCE 20 intentions par N° méd. (les intentions de leurs
        # membres). Si l'emplacement du N° du lecteur est nourri, le lecteur
        # reçoit UNE intention de CETTE réserve (rotation tous les 20 jours)
        # — « les visiteurs du jour reçoivent les intentions de leurs
        # prochains selon leurs N° méd. ». La file des soumissions reste le
        # secours : quand la réserve est vide, le tirage v7.9.1 s'applique.
        if jour_visiteur is not None:
            try:
                _res = intention_reserve_pour_numero(jour_visiteur)
                if _res and str(_res[0] or "").strip():
                    return (str(_res[0]).strip(), _res[1])
            except Exception as e:
                logger.warning(f"intention_du_prochain : réserve N° méd. ({e!r})")
        statut = "en_priere" if mode == "en_priere" else "recue"
        lignes = c.execute("""SELECT texte, jour_naissance, auteur_nom, anonyme
                              FROM intentions_equipes
                              WHERE statut=? AND TRIM(COALESCE(texte,'')) != ''
                              ORDER BY date_soumission ASC, id ASC""", (statut,)).fetchall()
        admissibles = []
        for _txt, _jn, _nom, _anon in lignes:
            # La règle d'or : le lecteur ne prie jamais sa propre intention.
            if jour_visiteur is not None and _jn is not None and int(_jn) == int(jour_visiteur):
                continue
            if _anon:
                qui = "cet anonyme"
            else:
                qui = str(_nom or "").strip() or "notre prochain"
            admissibles.append((str(_txt).strip(), qui))
        if admissibles:
            if jour_visiteur is not None and len(admissibles) > 1:
                # Fenêtre glissante de 20 jours : le rang du lecteur (N° méd.)
                # désigne SON intention, stable pendant toute la période.
                _cycle = (date.today() - date(2024, 1, 1)).days // 20
                _i = (int(jour_visiteur) - 1 + _cycle) % len(admissibles)
            else:
                _i = 0
            return admissibles[_i]
    except Exception as e:
        logger.warning(f"intention_du_prochain : tirage impossible ({e!r}) — secours")
    return _secours


def intention_du_prochain(jour_visiteur=None):
    """TEXTE seul de l'intention du prochain (v7.9.0, compat) — voir
    intention_du_prochain_detail() pour la version (texte, qui) v7.9.1."""
    return intention_du_prochain_detail(jour_visiteur)[0]


# ======================================================================
# v7.9.1 — RÈGLE DU LENDEMAIN + UNICITÉ PAR NUMÉRO
# ======================================================================
# « Les visiteurs du jour ont leurs intentions prises en charge au
# lendemain de la réception, pour 20 jours » — le balayage tourne au fil
# des pages (onglet équipe, onglet paroisse) et bascule chaque intention
# reçue J en « en prière » à J+1, date_statut étant datée AU LENDEMAIN
# (le décompte J+X/20 ne dépend pas du moment du balayage).
#
# « Un même numéro de téléphone ne peut avoir 2 intentions prises en
# charge » — vérifié à la soumission ET au balayage : un contact qui porte
# déjà une intention « en prière » n'en voit pas une seconde basculer
# (elle attend l'archivage de la première).


def _contact_cle(contact):
    """Clé de comparaison d'un contact (v7.9.1) : espaces/tirets/points retirés,
    indicatif +225 / 00 225 unifié, casse minuscule — « +225 07 00 11 11 22 »
    et « 0700111122 » sont le même numéro."""
    _k = "".join(str(contact or "").split()).replace("-", "").replace(".", "")
    _k = _k.replace("(", "").replace(")", "").lower()
    if _k.startswith("+"):
        _k = _k[1:]
    if _k.startswith("00"):
        _k = _k[2:]
    if _k.startswith("225"):
        _k = _k[3:]
    return _k


def contact_en_priere(contact):
    """RÈGLE D'UNICITÉ (v7.9.1) : retourne 1 si ce contact porte déjà une
    intention « en prière » (prise en charge), 0 sinon (libre)."""
    cle = _contact_cle(contact)
    if not cle:
        return 0
    try:
        if not c.execute("SELECT COUNT(*) FROM intentions_equipes "
                         "WHERE statut='en_priere'").fetchone()[0]:
            return 0
        for (ct,) in c.execute("SELECT auteur_contact FROM intentions_equipes "
                               "WHERE statut='en_priere' AND auteur_contact IS NOT NULL").fetchall():
            if _contact_cle(ct) == cle:
                return 1
    except Exception as e:
        logger.warning(f"contact_en_priere : {e!r}")
    return 0


def prise_en_charge_automatique():
    """RÈGLE DU LENDEMAIN (v7.9.1) : bascule en « en prière » toute intention
    reçue dont le lendemain de la réception est atteint ou dépassé, pour
    20 jours (20 mystères) ; date_statut = date_soumission + 1 jour. La
    règle d'unicité s'applique aussi ici : un contact qui porte déjà une
    intention en prière n'en voit pas une seconde basculer — elle attendra
    l'archivage de la première. Tolérante : toute erreur est journalisée
    sans jamais casser la page qui l'appelle."""
    try:
        _auj = date.today().isoformat()
        _deja = {_contact_cle(ct) for (ct,) in c.execute(
            "SELECT auteur_contact FROM intentions_equipes "
            "WHERE statut='en_priere' AND auteur_contact IS NOT NULL").fetchall()}
        _deja.discard("")
        _attente = c.execute("""SELECT id, auteur_contact FROM intentions_equipes
                                WHERE statut='recue'
                                  AND date_soumission IS NOT NULL
                                  AND TRIM(date_soumission) != ''
                                  AND date(date_soumission, '+1 day') <= ?
                                ORDER BY date_soumission ASC, id ASC""",
                             (_auj,)).fetchall()
        _vus = set()
        _n = 0
        for _iid, _ct in _attente:
            _cle = _contact_cle(_ct)
            if _cle and (_cle in _deja or _cle in _vus):
                continue  # unicité : ce contact porte déjà son intention
            c.execute("UPDATE intentions_equipes SET statut='en_priere', "
                      "date_statut=date(date_soumission, '+1 day') WHERE id=?", (_iid,))
            if _cle:
                _vus.add(_cle)
            _n += 1
        if _n:
            commit_and_sync()
            logger.info(f"prise_en_charge_automatique : {_n} intention(s) "
                        "passée(s) « en prière » (règle du lendemain)")
    except Exception as e:
        logger.warning(f"prise_en_charge_automatique : {e!r}")


def jours_depuis(d_iso):
    """Nombre de jours écoulés depuis une date ISO (tolérant : None/illisible → 0)."""
    try:
        d = safe_date(d_iso) if "safe_date" in globals() else None
        if d is None:
            from datetime import date as _d
            d = _d.fromisoformat(str(d_iso))
        return max(0, (date.today() - d).days) if d else 0
    except Exception:
        return 0


# ======================================================================
# v7.9.2 — LA CHAÎNE EN DIRECT : JOURNAL DES DIZAINES
# ======================================================================
# « Y a-t-il une possibilité de savoir si un membre / un visiteur fait sa
# dizaine ? » — OUI : le pointage « ✅ J'ai égrené ma dizaine aujourd'hui »
# en fin de livre (« 🕯️ Un jour, une dizaine ») enregistre la participation
# du jour. Principe d'honnêteté : le pointage part du LIVRE — il atteste
# d'une dizaine égrenée DANS l'application, pas d'une promesse.
#
#   - Membre   : identifié par son matloc → 1 pointage/jour (UNIQUE),
#                visible à son responsable (qui a fait / qui n'a pas fait).
#   - Visiteur : aucune identité fiable → 1 « passage » par session et par
#                jour (comptage global, sans nom).


def _assurer_dizaines_journal():
    """Création douce de dizaines_journal (bases distantes anciennes)."""
    try:
        c.execute("SELECT id FROM dizaines_journal LIMIT 1")
    except Exception:
        c.execute("""CREATE TABLE IF NOT EXISTS dizaines_journal (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        matloc TEXT,
                        nom TEXT,
                        type TEXT DEFAULT 'membre',
                        jrnais INTEGER,
                        equipe_id INTEGER,
                        paroisse_id INTEGER,
                        jour TEXT,
                        heure TEXT,
                        UNIQUE(matloc, jour))""")
        commit_and_sync()


def dizaine_deja_pointee(matloc=None):
    """1 si ce membre a déjà pointé sa dizaine aujourd'hui, 0 sinon."""
    if not matloc:
        return 0
    try:
        _assurer_dizaines_journal()
        return 1 if c.execute(
            "SELECT 1 FROM dizaines_journal WHERE matloc=? AND jour=? LIMIT 1",
            (matloc, date.today().isoformat())).fetchone() else 0
    except Exception as e:
        logger.warning(f"dizaine_deja_pointee : {e!r}")
        return 0


def pointer_dizaine(matloc=None, nom=None, jrnais=None, equipe_id=None,
                    paroisse_id=None, est_membre=True):
    """Enregistre la dizaine du jour (v7.9.2). Retourne (statut, message)
    avec statut dans {'ok', 'deja', 'erreur'} — le même membre ne peut
    pointer qu'UNE fois par jour (UNIQUE(matloc, jour)). Les visiteurs
    (est_membre=False) sont comptés comme passages sans nom."""
    try:
        _assurer_dizaines_journal()
        _jour = date.today().isoformat()
        if est_membre:
            if not matloc:
                return ("erreur", "Membre non identifié.")
            if dizaine_deja_pointee(matloc):
                return ("deja", "Votre dizaine d'aujourd'hui est déjà pointée. 📿")
            c.execute("""INSERT INTO dizaines_journal
                         (matloc, nom, type, jrnais, equipe_id, paroisse_id, jour, heure)
                         VALUES (?, ?, 'membre', NULL, ?, ?, ?, ?)""",
                      (matloc, nom or None, equipe_id, paroisse_id, _jour,
                       datetime.now().strftime("%H:%M")))
        else:
            c.execute("""INSERT INTO dizaines_journal
                         (matloc, nom, type, jrnais, equipe_id, paroisse_id, jour, heure)
                         VALUES (NULL, NULL, 'visiteur', ?, ?, ?, ?, ?)""",
                      (jrnais, equipe_id, paroisse_id, _jour,
                       datetime.now().strftime("%H:%M")))
        commit_and_sync()
        return ("ok", "Pointée ! Votre dizaine d'aujourd'hui est enregistrée. 📿✨")
    except Exception as e:
        logger.warning(f"pointer_dizaine : {e!r}")
        return ("erreur", "Le pointage n'a pas pu être enregistré — réessayez.")


def stats_dizaines_jour(jour=None, equipe_id=None):
    """Comptages du jour (v7.9.2) : (membres, visiteurs, liste_membres).
    equipe_id filtre les membres sur une équipe (les visiteurs restent
    globaux — ils n'appartiennent à aucune équipe)."""
    _jour = jour or date.today().isoformat()
    try:
        _assurer_dizaines_journal()
        _ph, _prm = ("AND equipe_id=?", [equipe_id]) if equipe_id else ("", [])
        _mbrs = c.execute(f"""SELECT nom, matloc, heure FROM dizaines_journal
                              WHERE type='membre' AND jour=? {_ph}
                              ORDER BY heure ASC""", (_jour, *_prm)).fetchall()
        _vis = c.execute("SELECT COUNT(*) FROM dizaines_journal "
                         "WHERE type='visiteur' AND jour=?", (_jour,)).fetchone()[0]
        return (len(_mbrs), _vis, _mbrs)
    except Exception as e:
        logger.warning(f"stats_dizaines_jour : {e!r}")
        return (0, 0, [])


def serie_dizaines(nb_jours=7, equipe_id=None):
    """[(jour, membres, visiteurs)] des N derniers jours (v7.9.2), le plus
    ancien d'abord — pour la courbe des responsables."""
    try:
        _assurer_dizaines_journal()
        _ph, _prm = ("AND equipe_id=?", [equipe_id]) if equipe_id else ("", [])
        _deb = date.fromordinal(date.today().toordinal() - nb_jours + 1).isoformat()
        rows = c.execute(f"""SELECT jour,
                             SUM(CASE WHEN type='membre' THEN 1 ELSE 0 END),
                             SUM(CASE WHEN type='visiteur' THEN 1 ELSE 0 END)
                             FROM dizaines_journal WHERE jour>=? {_ph}
                             GROUP BY jour ORDER BY jour ASC""",
                          (_deb, *_prm)).fetchall()
        _map = {r[0]: (r[1] or 0, r[2] or 0) for r in rows}
        _serie = []
        for _i in range(nb_jours):
            _d = date.fromordinal(date.today().toordinal() - nb_jours + 1 + _i).isoformat()
            _mv, _vv = _map.get(_d, (0, 0))
            _serie.append((_d, _mv, _vv))
        return _serie
    except Exception as e:
        logger.warning(f"serie_dizaines : {e!r}")
        return [(date.fromordinal(date.today().toordinal() - nb_jours + 1 + i).isoformat(), 0, 0)
                for i in range(nb_jours)]


def compteur_dizaines_mois(matloc):
    """Nombre de dizaines pointées CE MOIS par un membre (v7.9.2) + série
    des derniers jours consécutifs (flamme 📿)."""
    try:
        _assurer_dizaines_journal()
        _deb = date.today().replace(day=1).isoformat()
        _n = c.execute("SELECT COUNT(*) FROM dizaines_journal "
                       "WHERE matloc=? AND jour>=?", (matloc, _deb)).fetchone()[0]
        _flamme = 0
        for _i in range(0, 60):
            _d = date.fromordinal(date.today().toordinal() - _i).isoformat()
            if c.execute("SELECT 1 FROM dizaines_journal WHERE matloc=? AND jour=? LIMIT 1",
                         (matloc, _d)).fetchone():
                _flamme += 1
            else:
                break
        return (_n, _flamme)
    except Exception as e:
        logger.warning(f"compteur_dizaines_mois : {e!r}")
        return (0, 0)


# ======================================================================
# v7.9.3 — LA RÉSERVE D'INTENTIONS PAR N° MÉD.
# ======================================================================
# « Les visiteurs du jour reçoivent les intentions de leurs prochains selon
# leurs N° méd. et méditent avec sur 20 jours : il est capital d'avoir AU
# PRÉALABLE 20 intentions pour chacun des N° méd. Ça sera l'affaire des
# responsables d'équipe et paroissial : ils ajoutent les intentions de leurs
# membres. » — la table intentions_reserve stocke, pour chaque N° méd.
# (1-20), les intentions préparées d'avance ; l'« intention du prochain »
# du livret puise D'ABORD dans la réserve du N° du lecteur (rotation à
# chaque fenêtre de 20 jours), la file des soumissions restant le secours
# (comportement v7.9.1 conservé quand la réserve est vide).

OBJECTIF_RESERVE = 20   # intentions par N° méd.


def _assurer_table_reserve():
    """Création douce de intentions_reserve (bases distantes anciennes)."""
    try:
        c.execute("SELECT id FROM intentions_reserve LIMIT 1")
    except Exception:
        try:
            c.execute("""CREATE TABLE IF NOT EXISTS intentions_reserve (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            numero_med INTEGER NOT NULL,
                            texte TEXT NOT NULL,
                            auteur_nom TEXT,
                            equipe_id INTEGER,
                            paroisse_id INTEGER,
                            date_ajout TEXT)""")
            commit_and_sync()
        except Exception as e:
            logger.warning(f"_assurer_table_reserve : {e!r}")


def _numero_med_normale(jour):
    """Jour de naissance (1-31) → N° méd. (1-20), même règle que le livret
    (« Un jour, une dizaine ») : au-delà de 20, on retranche 20. None sinon."""
    try:
        _n = int(jour)
    except (TypeError, ValueError):
        return None
    if _n > 20:
        _n -= 20
    return _n if 1 <= _n <= 20 else None


def ajouter_intention_reserve(numero_med, texte, auteur_nom=None,
                              equipe_id=None, paroisse_id=None):
    """Ajoute une intention à la réserve d'un N° méd. (v7.9.3).
    Retourne (ok, message) — le message est prêt à être affiché."""
    _assurer_table_reserve()
    _num = _numero_med_normale(numero_med)
    if _num is None:
        return (False, "Le N° méd. doit être un chiffre entre 1 et 20.")
    _txt = str(texte or "").strip()
    if not _txt:
        return (False, "Le texte de l'intention est obligatoire.")
    if len(_txt) > 500:
        return (False, "L'intention est trop longue (500 caractères maximum).")
    try:
        c.execute("""INSERT INTO intentions_reserve
                     (numero_med, texte, auteur_nom, equipe_id, paroisse_id, date_ajout)
                     VALUES (?, ?, ?, ?, ?, ?)""",
                  (_num, _txt, (str(auteur_nom).strip() or None) if auteur_nom else None,
                   equipe_id, paroisse_id, date.today().isoformat()))
        commit_and_sync()
        return (True, "📚 Intention ajoutée à la réserve du N° méd. " + str(_num) + ".")
    except Exception as e:
        logger.warning(f"ajouter_intention_reserve : {e!r}")
        return (False, "L'ajout n'a pas pu aboutir — réessayez dans un instant.")


def retirer_intention_reserve(rid, equipe_id=None):
    """Retire une intention de la réserve (v7.9.3). Si equipe_id est fourni,
    le retrait est refusé pour une ligne d'une autre équipe (prudence).
    Retourne True uniquement si une ligne a VRAIMENT été supprimée."""
    _assurer_table_reserve()
    try:
        if equipe_id is not None:
            _eq = c.execute("SELECT equipe_id FROM intentions_reserve WHERE id=?",
                            (rid,)).fetchone()
            if not _eq or _eq[0] != equipe_id:
                return False
        cur = c.execute("DELETE FROM intentions_reserve WHERE id=?", (rid,))
        commit_and_sync()
        return bool(getattr(cur, "rowcount", 0))
    except Exception as e:
        logger.warning(f"retirer_intention_reserve : {e!r}")
        return False


def reserve_compteur():
    """{N° méd. (1-20) : nombre d'intentions en réserve} (v7.9.3) — les
    20 emplacements existent TOUJOURS (compteur à 0 quand vide)."""
    _d = {n: 0 for n in range(1, 21)}
    try:
        _assurer_table_reserve()
        for _num, _n in c.execute("""SELECT numero_med, COUNT(*) FROM intentions_reserve
                                     GROUP BY numero_med""").fetchall():
            if 1 <= int(_num) <= 20:
                _d[int(_num)] = _n
    except Exception as e:
        logger.warning(f"reserve_compteur : {e!r}")
    return _d


def reserve_lignes(equipe_id=None, paroisse_id=None, limite=300):
    """Intentions en réserve, les plus récentes d'abord (v7.9.3) :
    (id, numero_med, texte, auteur_nom, equipe_id, date_ajout)."""
    _assurer_table_reserve()
    _cond, _prm = [], []
    if equipe_id is not None:
        _cond.append("equipe_id=?")
        _prm.append(equipe_id)
    if paroisse_id is not None:
        _cond.append("paroisse_id=?")
        _prm.append(paroisse_id)
    _where = ("WHERE " + " AND ".join(_cond)) if _cond else ""
    try:
        return c.execute(f"""SELECT id, numero_med, texte, auteur_nom, equipe_id,
                                    date_ajout FROM intentions_reserve {_where}
                              ORDER BY id DESC LIMIT {int(limite)}""",
                         tuple(_prm)).fetchall()
    except Exception as e:
        logger.warning(f"reserve_lignes : {e!r}")
        return []


def intention_reserve_pour_numero(numero_med, cycle=None):
    """TIRAGE DANS LA RÉSERVE (v7.9.3) : retourne (texte, QUI) de l'intention
    placée au N° méd. du lecteur, ou None si cet emplacement est vide.
    La rotation suit la même fenêtre glissante de 20 jours que la chaîne :
    le lecteur retrouve la même intention sur toute la période, puis la
    réserve passe à la suivante (c'est le sens du stock de 20 par N°)."""
    _num = _numero_med_normale(numero_med)
    if _num is None:
        return None
    try:
        _assurer_table_reserve()
        rows = c.execute("""SELECT texte, auteur_nom FROM intentions_reserve
                            WHERE numero_med=? ORDER BY id ASC""", (_num,)).fetchall()
        if not rows:
            return None
        if cycle is None:
            cycle = (date.today() - date(2024, 1, 1)).days // 20
        _i = int(cycle) % len(rows)
        _qui = str(rows[_i][1] or "").strip() or "notre prochain"
        return (str(rows[_i][0]).strip(), _qui)
    except Exception as e:
        logger.warning(f"intention_reserve_pour_numero : {e!r}")
        return None
