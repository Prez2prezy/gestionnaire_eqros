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
                # v7.9.10 — le rattrapage embrasse le dernier visage des
                # micro-coupures : le flux rendu au repos trop longtemps
                # (transaction annulée — SQLITE_BUSY) était le seul à passer
                # encore au travers ; il est repris comme les autres.
                if ("stream not found" in msg or "connection reset" in msg
                        or "connection closed" in msg
                        or "connection terminated" in msg
                        or "http error" in msg
                        or "timeout" in msg or "timed out" in msg
                        or "sqlite_busy" in msg or "busy" in msg
                        or "idle for too long" in msg
                        or "rolled back" in msg
                        or "stream error" in msg
                        or "hrana" in msg):
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
    """v7.9.10 — le commit rattrape lui aussi les micro-coupures : une
    première tentative avortée est rejouée une seconde plus tard ; l'échec
    final reste silencieux et journalisé (l'app ne casse jamais au fidèle)."""
    for _essai in range(2):
        try:
            conn.commit()
            return
        except Exception as e:
            if _essai == 0:
                try:
                    time.sleep(1)
                except Exception:
                    pass
                continue
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
    # L'AVANCE les intentions (celles de leurs membres). Le visiteur du jour
    # reçoit, selon SON N° méd., l'intention placée à cet emplacement de la
    # réserve et la médite sur 20 jours — la chaîne ne tombe jamais à sec.
    # v7.9.4 — UNE intention par N° méd. : la colonne `active` distingue
    # l'intention en place (1) de celles qu'elle a remplacées (0, historique) ;
    # `qui` porte le nom tel que le livret l'affiche, `jour_naissance`
    # conserve la règle d'or (personne ne prie sa propre intention).
    c.execute("""CREATE TABLE IF NOT EXISTS intentions_reserve (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    numero_med INTEGER NOT NULL,
                    texte TEXT NOT NULL,
                    auteur_nom TEXT,
                    equipe_id INTEGER,
                    paroisse_id INTEGER,
                    date_ajout TEXT,
                    active INTEGER DEFAULT 1,
                    qui TEXT,
                    jour_naissance INTEGER,
                    publiee INTEGER DEFAULT 1,
                    date_publication TEXT)""")
    # v7.9.4 — LA ZONE DU JOUR : toutes les intentions confiées dans la
    # journée y sont recueillies d'abord ; le LENDEMAIN, chacune entre dans
    # la réserve (traitee=1, date_traitement posé).
    c.execute("""CREATE TABLE IF NOT EXISTS intentions_du_jour (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    texte TEXT NOT NULL,
                    auteur_nom TEXT,
                    auteur_contact TEXT,
                    anonyme INTEGER DEFAULT 0,
                    jour_naissance INTEGER,
                    equipe_id INTEGER,
                    paroisse_id INTEGER,
                    date_reception TEXT NOT NULL,
                    traitee INTEGER DEFAULT 0,
                    date_traitement TEXT)""")
    # v7.9.4 — L'ATTACHEMENT DE L'INTENTION DU PROCHAIN : l'intention reçue
    # reste LA SIENNE pendant sa période (membre : période désignée ;
    # visiteur : 20 jours), même si la réserve se renouvelle — cle = 'M:…'
    # (membre, par MatLoc) ou 'J:…' (visiteur, par N° méd.).
    c.execute("""CREATE TABLE IF NOT EXISTS attributions_prochain (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cle TEXT NOT NULL,
                    numero_med INTEGER,
                    texte TEXT NOT NULL,
                    qui TEXT,
                    date_debut TEXT NOT NULL,
                    date_fin TEXT)""")
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
    # v7.9.10 — LE SAS DES INTENTIONS : la réserve gagne les colonnes de la
    # publication différée. DEFAULT 1 : les intentions déjà en place restent
    # publiées exactement comme avant ; seules les NOUVELLES venues de la
    # zone du jour naissent publiee=0, en attendant 00h00 du jour suivant.
    safe_migrate("ALTER TABLE intentions_reserve ADD COLUMN publiee INTEGER DEFAULT 1")
    safe_migrate("ALTER TABLE intentions_reserve ADD COLUMN date_publication TEXT")
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


def intention_du_prochain_detail(jour_visiteur=None, matloc=None):
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
    v7.9.1 — tirage SELON LE N° MÉD. du lecteur : chaque lecteur reçoit
    l'intention placée à son rang, au sein d'une fenêtre de 20 jours.
    v7.9.4 — LA RÉSERVE SEULE NOURRIT LE TIRAGE (les responsables y placent
    UNE intention par N° méd. ; les intentions confiées dans la journée
    l'entretiennent chaque lendemain, au hasard) et L'INTENTION REÇUE
    S'ATTACHE à son lecteur (matloc du membre, ou N° méd. du visiteur) :
    il la retrouve à chaque dizaine de SA période — 20 jours, ou période
    désignée du membre — même si la réserve se renouvelle entre-temps.
    En cas d'intention indisponible, la chaîne ne se casse jamais : elle
    retombe sur « La Paix dans le monde » (QUI = None)."""
    _secours = (INTENTIONS_UNIVERSELLES[0], None)
    try:
        # v7.9.4 — les intentions de la veille entrent d'abord en réserve
        traiter_intentions_du_jour()
        # v7.9.10 — le réveil de la publication : les intentions dont
        # l'heure est venue (00h00 du jour suivant leur entrée en réserve)
        # deviennent visibles dans la chaîne
        publier_reserve_due()
        mode = get_parametre("chaine_mode", "recues")
        if mode == "universelle":
            choix = get_parametre("chaine_universelle", INTENTIONS_UNIVERSELLES[0])
            if choix == "rotation":
                # rotation quotidienne (jour de l'année) : les trois intentions
                # universelles se relaient chaque jour.
                return (INTENTIONS_UNIVERSELLES[date.today().timetuple().tm_yday % 3], None)
            return ((choix if choix in INTENTIONS_UNIVERSELLES else _secours[0]), None)
        # v7.9.4 — L'ATTACHEMENT D'ABORD : l'intention déjà reçue reste LA
        # SIENNE pendant toute sa période (membre : période désignée ;
        # visiteur : 20 jours), quel que soit le renouvellement de la réserve.
        _cle = None
        if matloc:
            _cle = "M:" + str(matloc)
        elif jour_visiteur is not None:
            _n = _numero_med_normale(jour_visiteur)
            _cle = ("J:" + str(_n)) if _n else None
        if _cle:
            _att = prochain_attache(_cle)
            if _att and str(_att[0] or "").strip():
                return (_att[0], _att[1])
        # LA RÉSERVE (v7.9.3, affinée v7.9.4) : l'intention placée au N° méd.
        # du lecteur — la règle d'or l'y protège aussi de la sienne.
        if jour_visiteur is not None:
            try:
                _res = intention_reserve_pour_numero(jour_visiteur,
                                                     jour_exclu=jour_visiteur)
                if _res and str(_res[0] or "").strip():
                    if _cle:
                        attribuer_prochain(_cle, _res[0], _res[1],
                                           numero_med=_numero_med_normale(jour_visiteur))
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
            if _cle:
                attribuer_prochain(_cle, admissibles[_i][0], admissibles[_i][1],
                                   numero_med=_numero_med_normale(jour_visiteur))
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
                return ("deja", "📿 Merci Sainte Mère pour ton aide de ce jour! — À demain! 🕊️")
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
        return ("ok", "📿 Ta dizaine est capitale pour la chaîne — Merci pour ta fidélité! — À demain! 🕊️")
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
# v7.9.3 — LA RÉSERVE D'INTENTIONS PAR N° MÉD. · v7.9.4 — UNE PAR N°
# ======================================================================
# « Les visiteurs du jour reçoivent les intentions de leurs prochains selon
# leurs N° méd. et méditent avec sur 20 jours. Que chacun ait sa dernière
# intention selon son N° méd. » — v7.9.4 précise le modèle :
#   • UNE SEULE intention par N° méd. (les 20 emplacements de la réserve) ;
#   • la réserve nourrit l'« intention du prochain » du livret ;
#   • les intentions confiées dans la journée sont d'abord recueillies dans
#     la ZONE DU JOUR (intentions_du_jour) — harmonisées à l'avance ;
#   • le LENDEMAIN, chacune entre dans la réserve en remplaçant, au HASARD,
#     l'une des intentions en place (l'ancienne passe active=0, gardée en
#     historique) — si les demandes abondent, le stock tournant de chaque
#     N° méd. s'élargit d'autant (quota augmenté) ;
#   • l'intention reçue S'ATTACHE à son lecteur (attributions_prochain) :
#     période désignée du membre / 20 jours du visiteur, même si la
#     réserve se renouvelle entre-temps.

OBJECTIF_RESERVE = 1    # v7.9.4 — UNE intention par N° méd.


def _assurer_table_reserve():
    """Création douce de intentions_reserve (bases distantes anciennes).
    v7.9.4 — les colonnes active/qui/jour_naissance sont ajoutées en ALTER
    doux (idempotent) : une base Cloud née avant v7.9.4 doit rester lisible."""
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
                            date_ajout TEXT,
                            active INTEGER DEFAULT 1,
                            qui TEXT,
                            jour_naissance INTEGER)""")
            commit_and_sync()
        except Exception as e:
            logger.warning(f"_assurer_table_reserve : {e!r}")
    for _col in ("active INTEGER DEFAULT 1", "qui TEXT", "jour_naissance INTEGER",
                 "publiee INTEGER DEFAULT 1", "date_publication TEXT"):
        try:
            c.execute(f"ALTER TABLE intentions_reserve ADD COLUMN {_col}")
            commit_and_sync()
        except Exception:
            pass  # colonne déjà présente


def _assurer_table_du_jour():
    """Création douce de intentions_du_jour — LA ZONE DU JOUR (v7.9.4) :
    elle reçoit toutes les intentions confiées dans la journée ; le
    lendemain, chacune entre dans la réserve (traiter_intentions_du_jour)."""
    try:
        c.execute("SELECT id FROM intentions_du_jour LIMIT 1")
    except Exception:
        try:
            c.execute("""CREATE TABLE IF NOT EXISTS intentions_du_jour (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            texte TEXT NOT NULL,
                            auteur_nom TEXT,
                            auteur_contact TEXT,
                            anonyme INTEGER DEFAULT 0,
                            jour_naissance INTEGER,
                            equipe_id INTEGER,
                            paroisse_id INTEGER,
                            date_reception TEXT NOT NULL,
                            traitee INTEGER DEFAULT 0,
                            date_traitement TEXT)""")
            commit_and_sync()
        except Exception as e:
            logger.warning(f"_assurer_table_du_jour : {e!r}")


def _assurer_table_attributions():
    """Création douce de attributions_prochain (v7.9.4) — l'intention du
    prochain reçue reste attachée à son lecteur pendant sa période."""
    try:
        c.execute("SELECT id FROM attributions_prochain LIMIT 1")
    except Exception:
        try:
            c.execute("""CREATE TABLE IF NOT EXISTS attributions_prochain (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            cle TEXT NOT NULL,
                            numero_med INTEGER,
                            texte TEXT NOT NULL,
                            qui TEXT,
                            date_debut TEXT NOT NULL,
                            date_fin TEXT)""")
            commit_and_sync()
        except Exception as e:
            logger.warning(f"_assurer_table_attributions : {e!r}")


# v7.9.4 — garde-fou : le transfert « zone du jour → réserve » ne tourne
# qu'une fois par jour et par processus (idempotent de toute façon :
# seules les lignes traitee=0 reçues AVANT aujourd'hui sont prises).
_TRAITEMENT_DJ_FAIT_LE = None


def verser_intention_du_jour(texte, auteur_nom=None, auteur_contact=None,
                             anonyme=0, jour_naissance=None,
                             equipe_id=None, paroisse_id=None):
    """ZONE DU JOUR (v7.9.4) : recueille une intention confiée aujourd'hui.
    Appelée à chaque soumission du formulaire « 🙏 Vos intentions à une
    équipe » — en plus de l'INSERT classique (le travail des responsables
    reste inchangé). Tolérante : jamais de plantage au fidèle."""
    _txt = str(texte or "").strip()
    if not _txt:
        return False
    try:
        _assurer_table_du_jour()
        c.execute("""INSERT INTO intentions_du_jour
                     (texte, auteur_nom, auteur_contact, anonyme, jour_naissance,
                      equipe_id, paroisse_id, date_reception, traitee)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)""",
                  (_txt, (str(auteur_nom).strip() or None) if auteur_nom else None,
                   (str(auteur_contact).strip() or None) if auteur_contact else None,
                   1 if anonyme else 0,
                   int(jour_naissance) if jour_naissance else None,
                   equipe_id, paroisse_id, date.today().isoformat()))
        commit_and_sync()
        return True
    except Exception as e:
        logger.warning(f"verser_intention_du_jour : {e!r}")
        return False


def traiter_intentions_du_jour(force=False):
    """LE LENDEMAIN (v7.9.4) : chaque intention recueillie la veille (ou
    avant, non traitée) entre dans la réserve — elle remplace AU HASARD
    l'intention en place d'un N° méd. (l'ancienne passe active=0 ; si les
    demandes abondent, les suivantes du même jour élargissent le stock
    tournant du N° — quota augmenté). Idempotent : ne prend QUE les lignes
    traitee=0 reçues avant aujourd'hui ; une seule exécution par jour et
    par processus (garde-fou _TRAITEMENT_DJ_FAIT_LE), silencieuse.
    v7.9.10 — LE SAS : l'entrée en réserve n'est PLUS une publication —
    chaque arrivée naît publiee=0 avec date_publication DEMAIN (00h00 du
    jour suivant) ; le réveil publier_reserve_due la rendra visible."""
    global _TRAITEMENT_DJ_FAIT_LE
    _auj = date.today().isoformat()
    _demain = date.fromordinal(date.today().toordinal() + 1).isoformat()
    if not force and _TRAITEMENT_DJ_FAIT_LE == _auj:
        return
    try:
        _assurer_table_du_jour()
        _attente = c.execute("""SELECT id, texte, auteur_nom, anonyme,
                                       jour_naissance, equipe_id, paroisse_id
                                FROM intentions_du_jour
                                WHERE traitee=0 AND date_reception < ?
                                ORDER BY id ASC""", (_auj,)).fetchall()
        _TRAITEMENT_DJ_FAIT_LE = _auj
        if not _attente:
            return
        import random as _rd
        _slots = list(range(1, 21))
        _rd.shuffle(_slots)
        _remplace = set()
        for (_zid, _txt, _nom, _anon, _jn, _eqi, _pri) in _attente:
            _slot = _slots[0]
            _slots = _slots[1:] + [_slot]     # pioche mélangée : ordre aléatoire
            if _slot not in _remplace:
                c.execute("""UPDATE intentions_reserve SET active=0
                             WHERE numero_med=? AND active=1""", (_slot,))
                _remplace.add(_slot)
            c.execute("""INSERT INTO intentions_reserve
                         (numero_med, texte, auteur_nom, equipe_id, paroisse_id,
                          date_ajout, active, qui, jour_naissance, publiee, date_publication)
                         VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, 0, ?)""",
                      (_slot, _txt, None if _anon else ((str(_nom).strip() or None) if _nom else None),
                       _eqi, _pri, _auj, "cet anonyme" if _anon else "notre prochain",
                       int(_jn) if _jn else None, _demain))
            c.execute("""UPDATE intentions_du_jour SET traitee=1, date_traitement=?
                         WHERE id=?""", (_auj, _zid))
        commit_and_sync()
        logger.info(f"traiter_intentions_du_jour : {len(_attente)} intention(s) "
                    "du jour précédent entrée(s) en réserve")
    except Exception as e:
        logger.warning(f"traiter_intentions_du_jour : {e!r}")


# ======================================================================
# v7.9.9 — LA ZONE DU JOUR VISIBLE : le traitement AVANT l'affichage
# ======================================================================
# « Afin d'harmoniser l'intention du prochain à l'affichage, il est
# nécessaire de la traiter auparavant. Créer donc une zone qui recevra
# toutes les intentions du jour. » — la table existait (v7.9.4) ; voici
# l'écran qui la rend visible : le responsable lit chaque intention le
# jour même, harmonise son texte (orthographe, dignité, clarté) AVANT
# l'entrée en réserve, ou l'écarte — et c'est ce texte soigné que la
# chaîne de prière porte au lecteur. Aucune migration : la table
# intentions_du_jour suffit (traitee : 0 = en attente, 1 = entrée en
# réserve, 2 = écartée — le transfert ne prend JAMAIS traitee=2).


def intentions_du_jour_attente(equipe_ids=None, paroisse_id=None):
    """ZONE DU JOUR (v7.9.9) : toutes les intentions pas encore placées en
    réserve (traitee=0), de la plus récente à la plus ancienne — la matière
    du travail des responsables. v7.9.10 — SCOPE PAROISSIAL : passer
    paroisse_id et/ou equipe_ids ne montre que les intentions de la maison
    (l'OR honore les lignes anciennes dont la paroisse n'était pas notée).
    Tolérante : [] si indisponible."""
    try:
        _assurer_table_du_jour()
        _scope, _prm = "", []
        _parts = []
        if paroisse_id is not None:
            _parts.append("z.paroisse_id=?")
            _prm.append(paroisse_id)
        if equipe_ids:
            _ph = ",".join("?" * len(equipe_ids))
            _parts.append(f"z.equipe_id IN ({_ph})")
            _prm.extend(equipe_ids)
        if _parts:
            _scope = " AND (" + " OR ".join(_parts) + ")"
        return c.execute(f"""SELECT z.id, z.texte, z.auteur_nom, z.anonyme,
                                   z.jour_naissance, z.equipe_id, z.paroisse_id,
                                   z.date_reception
                            FROM intentions_du_jour z
                            WHERE z.traitee=0{_scope}
                            ORDER BY z.date_reception DESC, z.id DESC""",
                         tuple(_prm)).fetchall()
    except Exception as e:
        logger.warning(f"intentions_du_jour_attente : {e!r}")
        return []


def intentions_du_jour_compte(equipe_ids=None, paroisse_id=None):
    """ZONE DU JOUR (v7.9.9) : (en attente, envoyées en réserve aujourd'hui,
    écartées) — trois chiffres qui résument la journée. v7.9.10 — scope
    paroissial : mêmes filtres que intentions_du_jour_attente."""
    try:
        _assurer_table_du_jour()
        _auj = date.today().isoformat()
        _parts = []
        _prm = []
        if paroisse_id is not None:
            _parts.append("paroisse_id=?")
            _prm.append(paroisse_id)
        if equipe_ids:
            _ph = ",".join("?" * len(equipe_ids))
            _parts.append(f"equipe_id IN ({_ph})")
            _prm.extend(equipe_ids)
        _scope = (" AND (" + " OR ".join(_parts) + ")") if _parts else ""
        _attente = c.execute(f"SELECT COUNT(*) FROM intentions_du_jour "
                             f"WHERE traitee=0{_scope}", tuple(_prm)).fetchone()[0]
        _reserve = c.execute(f"SELECT COUNT(*) FROM intentions_du_jour "
                             f"WHERE traitee=1 AND date_traitement=?{_scope}",
                             [_auj] + _prm).fetchone()[0]
        _ecartees = c.execute(f"SELECT COUNT(*) FROM intentions_du_jour "
                              f"WHERE traitee=2{_scope}", tuple(_prm)).fetchone()[0]
        return (_attente, _reserve, _ecartees)
    except Exception as e:
        logger.warning(f"intentions_du_jour_compte : {e!r}")
        return (0, 0, 0)


def harmoniser_intention_du_jour(zid, texte):
    """ZONE DU JOUR (v7.9.9) : harmonise le texte d'une intention EN ATTENTE
    (traitee=0) — l'entrée en réserve, le lendemain, emportera ce texte
    soigné, et l'affichage de la chaîne le recevra ainsi. Retourne True si
    une ligne a bien été mise à jour (id encore en attente)."""
    _txt = str(texte or "").strip()
    if not _txt:
        return False
    try:
        _assurer_table_du_jour()
        c.execute("UPDATE intentions_du_jour SET texte=? "
                  "WHERE id=? AND traitee=0", (_txt, int(zid)))
        commit_and_sync()
        return bool(c.execute("SELECT 1 FROM intentions_du_jour "
                              "WHERE id=? AND traitee=0 AND texte=?",
                              (int(zid), _txt)).fetchone())
    except Exception as e:
        logger.warning(f"harmoniser_intention_du_jour : {e!r}")
        return False


def ecarter_intention_du_jour(zid):
    """ZONE DU JOUR (v7.9.9) : écarte une intention de la chaîne — traitee=2
    la met HORS du transfert (traiter_intentions_du_jour ne prend que
    traitee=0) : elle ne nourrira jamais la réserve. Gardée en zone pour
    la mémoire du travail. Retourne True si l'écart a été posé."""
    try:
        _assurer_table_du_jour()
        c.execute("UPDATE intentions_du_jour SET traitee=2, date_traitement=? "
                  "WHERE id=? AND traitee=0",
                  (date.today().isoformat(), int(zid)))
        commit_and_sync()
        return bool(c.execute("SELECT 1 FROM intentions_du_jour "
                              "WHERE id=? AND traitee=2",
                              (int(zid),)).fetchone())
    except Exception as e:
        logger.warning(f"ecarter_intention_du_jour : {e!r}")
        return False


# ======================================================================
# v7.9.10 — LE SAS DES INTENTIONS · LA PUBLICATION À 00h00
# ======================================================================
# « Les intentions c'est une affaire des paroisses et de ses équipes.
# Ramener la Zone du jour dans 🙏 Coins des Intentions / 📌 Suivi et
# Agenda - Paroisse. C'est le sas des intentions. Aucune intention ne peut
# être publiée sans y passer. Toutes les intentions reçues y transitent,
# elles sont traitées puis envoyées vers la réserve immédiatement. La
# publication se fait à 00h00 du jour suivant. » —
#   • la zone du jour devient PAROISSIALE (scope paroisse_id / équipes) ;
#   • « 🕊️ Traiter & envoyer en réserve » part DU SAS, tout de suite ;
#   • l'arrivée en réserve n'est pas la publication : publiee=0,
#     date_publication = demain (00h00 du jour suivant) ;
#   • le réveil publier_reserve_due — appelé à chaque tirage — rend
#     l'intention visible à l'heure dite. Les intentions déjà en place
#     (colonnes absentes avant v7.9.10) restent publiées comme avant.

_PUBLICATION_RESERVE_FAIT_LE = None


def publier_reserve_due(force=False):
    """LE RÉVEIL DE LA PUBLICATION (v7.9.10) : rend visibles dans la chaîne
    les intentions dont l'heure est venue — publiee=0 et date_publication
    atteinte (00h00 du jour suivant leur entrée en réserve). Paresseux et
    idempotent : une seule exécution par jour et par processus (sauf
    force=True), silencieux. Retourne le nombre d'intentions réveillées."""
    global _PUBLICATION_RESERVE_FAIT_LE
    _auj = date.today().isoformat()
    if not force and _PUBLICATION_RESERVE_FAIT_LE == _auj:
        return 0
    try:
        _assurer_table_reserve()
        _cur = c.execute("""UPDATE intentions_reserve SET publiee=1
                            WHERE publiee=0 AND date_publication IS NOT NULL
                            AND date_publication <= ?""", (_auj,))
        commit_and_sync()
        _PUBLICATION_RESERVE_FAIT_LE = _auj
        return int(getattr(_cur, "rowcount", 0) or 0)
    except Exception as e:
        logger.warning(f"publier_reserve_due : {e!r}")
        return 0


def envoyer_intention_du_jour_en_reserve(zid, texte=None):
    """LE SAS (v7.9.10) : envoie IMMÉDIATEMENT une intention de la zone du
    jour (traitee=0) en réserve, avec le texte harmonisé passé (ou son
    texte actuel). La publication reste réglée à 00h00 du jour suivant :
    l'intention naît publiee=0, date_publication=demain — le réveil
    publier_reserve_due la montrera au fidèle à l'heure dite. L'emplacement
    (N° méd.) est tiré au hasard : l'intention de longue date cède sa
    place, celles nées aujourd'hui élargissent le stock tournant.
    Retourne (ok, message prêt à afficher)."""
    try:
        _assurer_table_du_jour()
        _assurer_table_reserve()
        _row = c.execute("""SELECT texte, auteur_nom, anonyme, jour_naissance,
                                   equipe_id, paroisse_id
                            FROM intentions_du_jour WHERE id=? AND traitee=0""",
                         (int(zid),)).fetchone()
        if not _row:
            return (False, "Intention introuvable ou déjà traitée.")
        _txt = str(texte if texte is not None else (_row[0] or "")).strip()
        if not _txt:
            return (False, "Le texte de l'intention est vide — harmonisez-le "
                           "ou écartez l'intention.")
        _anon = int(_row[2] or 0)
        _auj = date.today()
        _demain = date.fromordinal(_auj.toordinal() + 1).isoformat()
        import random as _rd
        _slot = _rd.randint(1, 20)
        # v7.9.10 — l'arrivée du jour cède sa place à l'intention en place
        # (même règle que le lot automatique : 1 active par N° en régime
        # normal), SAUF aux compagnes nées aujourd'hui du sas (publiee=0,
        # date_ajout=aujourd'hui) : elles élargissent le stock tournant.
        c.execute("""UPDATE intentions_reserve SET active=0
                     WHERE numero_med=? AND active=1
                       AND NOT (COALESCE(publiee,1)=0 AND date_ajout=?)""",
                  (_slot, _auj.isoformat()))
        c.execute("""INSERT INTO intentions_reserve
                     (numero_med, texte, auteur_nom, equipe_id, paroisse_id,
                      date_ajout, active, qui, jour_naissance, publiee, date_publication)
                     VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, 0, ?)""",
                  (_slot, _txt,
                   None if _anon else ((str(_row[1]).strip() or None) if _row[1] else None),
                   _row[4], _row[5], _auj.isoformat(),
                   "cet anonyme" if _anon else "notre prochain",
                   int(_row[3]) if _row[3] else None,
                   _demain))
        c.execute("UPDATE intentions_du_jour SET traitee=1, date_traitement=? "
                  "WHERE id=?", (_auj.isoformat(), int(zid)))
        commit_and_sync()
        return (True, "🕊️ Intention envoyée en réserve (N° méd. " + str(_slot)
                       + ") — elle sera publiée à 00h00 demain.")
    except Exception as e:
        logger.warning(f"envoyer_intention_du_jour_en_reserve : {e!r}")
        return (False, "L'envoi n'a pas pu aboutir — réessayez dans un instant.")


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
                              equipe_id=None, paroisse_id=None,
                              jour_naissance=None, qui=None):
    """Ajoute une intention à la réserve d'un N° méd. (v7.9.3).
    v7.9.4 — UNE intention par N° méd. : si l'emplacement est déjà pourvu,
    l'ajout est refusé avec un message doux (il se renouvelle de lui-même
    avec les intentions confiées — ou retirez d'abord celle en place).
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
        _deja = c.execute("""SELECT id FROM intentions_reserve
                             WHERE numero_med=? AND active=1 LIMIT 1""",
                          (_num,)).fetchone()
        if _deja:
            return (False, "📿 L'emplacement du N° méd. " + str(_num)
                           + " est déjà pourvu : chaque N° porte UNE intention. "
                           "Il se renouvelle au fil des intentions confiées — ou "
                           "retirez d'abord celle en place (🗑️) si elle doit laisser "
                           "la place.")
        c.execute("""INSERT INTO intentions_reserve
                     (numero_med, texte, auteur_nom, equipe_id, paroisse_id,
                      date_ajout, active, qui, jour_naissance)
                     VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)""",
                  (_num, _txt, (str(auteur_nom).strip() or None) if auteur_nom else None,
                   equipe_id, paroisse_id, date.today().isoformat(),
                   (str(qui).strip() or None) if qui else None,
                   int(jour_naissance) if jour_naissance else None))
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
    20 emplacements existent TOUJOURS (compteur à 0 quand vide).
    v7.9.4 — seules les intentions ACTIVES comptent (une par N° en régime
    normal ; plus si les demandes abondent)."""
    _d = {n: 0 for n in range(1, 21)}
    try:
        _assurer_table_reserve()
        for _num, _n in c.execute("""SELECT numero_med, COUNT(*) FROM intentions_reserve
                                     WHERE active=1 GROUP BY numero_med""").fetchall():
            if 1 <= int(_num) <= 20:
                _d[int(_num)] = _n
    except Exception as e:
        logger.warning(f"reserve_compteur : {e!r}")
    return _d


def reserve_lignes(equipe_id=None, paroisse_id=None, limite=300):
    """Intentions ACTIVES en réserve, les plus récentes d'abord (v7.9.3,
    filtre active=1 v7.9.4) :
    (id, numero_med, texte, auteur_nom, equipe_id, date_ajout)."""
    _assurer_table_reserve()
    _cond, _prm = ["active=1"], []
    if equipe_id is not None:
        _cond.append("equipe_id=?")
        _prm.append(equipe_id)
    if paroisse_id is not None:
        _cond.append("paroisse_id=?")
        _prm.append(paroisse_id)
    try:
        return c.execute(f"""SELECT id, numero_med, texte, auteur_nom, equipe_id,
                                    date_ajout FROM intentions_reserve
                              WHERE {' AND '.join(_cond)}
                              ORDER BY id DESC LIMIT {int(limite)}""",
                         tuple(_prm)).fetchall()
    except Exception as e:
        logger.warning(f"reserve_lignes : {e!r}")
        return []


def intention_reserve_pour_numero(numero_med, cycle=None, jour_exclu=None):
    """TIRAGE DANS LA RÉSERVE (v7.9.3) : retourne (texte, QUI) de l'intention
    placée au N° méd. du lecteur, ou None si cet emplacement est vide.
    v7.9.4 — seules les intentions ACTIVES sont tirées (une par N° en régime
    normal ; stock tournant élargi quand les demandes abondent) et la règle
    d'or s'applique aussi ici : jour_exclu (jour de naissance du lecteur)
    écarte l'intention qu'il a lui-même confiée. La rotation suit la fenêtre
    glissante de 20 jours quand plusieurs intentions coexistent au même N°."""
    _num = _numero_med_normale(numero_med)
    if _num is None:
        return None
    try:
        _assurer_table_reserve()
        # v7.9.10 — le réveil puis le filtre : seules les intentions
        # PUBLIÉES (ou d'avant v7.9.10) nourrissent le tirage — rien ne
        # s'affiche avant 00h00 du jour suivant son entrée en réserve.
        publier_reserve_due()
        rows = c.execute("""SELECT texte, qui, auteur_nom, jour_naissance
                            FROM intentions_reserve
                            WHERE numero_med=? AND active=1
                              AND (publiee IS NULL OR publiee<>0)
                            ORDER BY id ASC""", (_num,)).fetchall()
        if jour_exclu is not None:
            rows = [r for r in rows
                    if r[3] is None or int(r[3]) != int(jour_exclu)]
        if not rows:
            return None
        if cycle is None:
            cycle = (date.today() - date(2024, 1, 1)).days // 20
        _i = int(cycle) % len(rows)
        _qui = (str(rows[_i][1] or "").strip()
                or str(rows[_i][2] or "").strip()
                or "notre prochain")
        return (str(rows[_i][0]).strip(), _qui)
    except Exception as e:
        logger.warning(f"intention_reserve_pour_numero : {e!r}")
        return None


# ======================================================================
# v7.9.4 — L'ATTACHEMENT DE L'INTENTION DU PROCHAIN
# ======================================================================
# « L'intention du prochain attribuée à un membre / visiteur s'attache à
# lui sur la période désignée (membre) ou sur 20 jours (visiteur). » —
# même si la réserve se renouvelle entre-temps, chacun garde SON intention
# jusqu'au bout de sa période ; la suivante sera tirée dans la réserve
# renouvelée. cle = 'M:{matloc}' (membre) ou 'J:{n° méd.}' (visiteur).

DUREE_ATTACHEMENT = 20


def prochain_attache(cle):
    """L'intention actuellement attachée à cette clé (v7.9.4) :
    (texte, qui) ou None si aucune / période échue."""
    if not cle:
        return None
    try:
        _assurer_table_attributions()
        _auj = date.today().isoformat()
        row = c.execute("""SELECT texte, qui FROM attributions_prochain
                           WHERE cle=? AND (date_fin IS NULL OR date_fin>=?)
                           ORDER BY id DESC LIMIT 1""", (cle, _auj)).fetchone()
        if row and str(row[0] or "").strip():
            return (str(row[0]).strip(),
                    (str(row[1] or "").strip() or "notre prochain"))
    except Exception as e:
        logger.warning(f"prochain_attache : {e!r}")
    return None


def attribuer_prochain(cle, texte, qui=None, numero_med=None, duree=None):
    """Attache l'intention reçue à son lecteur (v7.9.4) pour sa période
    (visiteur : 20 jours ; membre : période désignée — la même fenêtre,
    la désignation du responsable encadrant). Un nouveau tirage remplace
    proprement l'ancienne attribution (les vieilles lignes restent en
    historique). Tolérante : jamais bloquante pour la page."""
    if not cle:
        return
    try:
        _assurer_table_attributions()
        _deb = date.today()
        _fin = _deb.fromordinal(_deb.toordinal()
                                + (int(duree) if duree else DUREE_ATTACHEMENT) - 1)
        c.execute("DELETE FROM attributions_prochain WHERE cle=?", (cle,))
        c.execute("""INSERT INTO attributions_prochain
                     (cle, numero_med, texte, qui, date_debut, date_fin)
                     VALUES (?, ?, ?, ?, ?, ?)""",
                  (cle, numero_med, str(texte or "").strip(),
                   (str(qui).strip() or None) if qui else None,
                   _deb.isoformat(), _fin.isoformat()))
        commit_and_sync()
    except Exception as e:
        logger.warning(f"attribuer_prochain : {e!r}")


def date_intention_en_priere(contact):
    """Date d'émission de l'intention « en prière » portée par ce contact
    (v7.9.4 — pour le message au fidèle qui revient). None si libre."""
    cle = _contact_cle(contact)
    if not cle:
        return None
    def _parse(s):
        try:
            return date.fromisoformat(str(s)[:10])
        except Exception:
            return None
    try:
        for (ct, d_sub, d_st) in c.execute(
                """SELECT auteur_contact, date_soumission, date_statut
                   FROM intentions_equipes
                   WHERE statut='en_priere' AND auteur_contact IS NOT NULL""").fetchall():
            if _contact_cle(ct) == cle:
                return _parse(d_st) or _parse(d_sub)
    except Exception as e:
        logger.warning(f"date_intention_en_priere : {e!r}")
    return None
