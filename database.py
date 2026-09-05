import sqlite3
import time
import hashlib
import logging

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

# --- Connexion DB ---
def create_connection():
    """Secrets Turso présents -> Turso OBLIGATOIRE (raise si échec).
    Secrets absents -> SQLite local (timeout + WAL)."""
    url, token = None, None
    try:
        import streamlit as st
        url = st.secrets.get("TURSO_URL")
        token = st.secrets.get("TURSO_AUTH_TOKEN")
    except Exception:
        pass

    if url and token:
        from libsql import connect as turso_connect
        last_error = None
        for attempt in range(2):
            try:
                return turso_connect(url, auth_token=token), True
            except Exception as e:
                last_error = e
                if attempt == 0:
                    time.sleep(1)
        raise Exception(f"Connexion à Turso impossible. ({last_error})")

    local = sqlite3.connect('gestion_religieuse.db', check_same_thread=False, timeout=30)
    try:
        local.execute("PRAGMA journal_mode=WAL")
    except Exception:
        pass
    return local, False


def init_db():
    import streamlit as st
    @st.cache_resource
    def get_conn():
        return create_connection()
    return get_conn()

conn, USE_TURSO = init_db()


class CursorWrapper:
    def __init__(self, cursor):
        self.cursor = cursor

    def execute(self, query, params=None):
        last_error = None
        for attempt in range(3):
            try:
                return self.cursor.execute(query, tuple(params) if params else ())
            except Exception as e:
                last_error = e
                error_msg = str(e).lower()
                if "stream not found" in error_msg or "connection reset" in error_msg:
                    time.sleep(1)
                    global conn
                    conn, _ = create_connection()
                    self.cursor = conn.cursor()
                    continue
                if "duplicate column" not in error_msg:
                    logger.error(f"Erreur SQL : {e}")
                raise
        # FIX : ne jamais retourner None après épuisement des retries
        raise last_error

    def __getattr__(self, name):
        return getattr(self.cursor, name)

c = CursorWrapper(conn.cursor()) if USE_TURSO else conn.cursor()


def commit_and_sync():
    # FIX : propage l'erreur (l'ancien code affichait "✅" alors que rien n'était persisté)
    try:
        conn.commit()
    except Exception as e:
        logger.error(f"Erreur lors du commit : {e}")
        raise


def safe_migrate(query, error_ignore_phrases=["duplicate column", "duplicate column name"]):
    try:
        c.execute(query)
        commit_and_sync()
    except Exception as e:
        error_msg = str(e).lower()
        if not any(phrase in error_msg for phrase in error_ignore_phrases):
            logger.warning(f"Migration ignorée ou échouée: {e}")


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
    c.execute("""CREATE TABLE IF NOT EXISTS espace_spirituel (id INTEGER PRIMARY KEY, type_contenu TEXT, titre TEXT, contenu_texte TEXT, fichier_url TEXT, date_publication DATE, auteur_nom TEXT)""")

    # --- 2. MIGRATIONS STRUCTURELLES ---
    safe_migrate("ALTER TABLE espace_spirituel ADD COLUMN image_url TEXT")
    safe_migrate("ALTER TABLE evenements ADD COLUMN affiche_url TEXT")
    # NOUVEAU : bandes-annonces (URL YouTube ou vidéo Cloudinary) du Coin Affiche
    safe_migrate("ALTER TABLE evenements ADD COLUMN video_url TEXT")
    safe_migrate("ALTER TABLE membres RENAME COLUMN matricule TO matloc", error_ignore_phrases=["no such column"])
    safe_migrate("ALTER TABLE membres RENAME COLUMN mle_sup TO matricule", error_ignore_phrases=["no such column"])
    safe_migrate("ALTER TABLE membres ADD COLUMN matricule TEXT")
    safe_migrate("ALTER TABLE agenda ADD COLUMN a_faire_suivre INTEGER DEFAULT 0")
    safe_migrate("ALTER TABLE evenements ADD COLUMN paroisse_id INTEGER")
    safe_migrate("ALTER TABLE evenements ADD COLUMN diocese_id INTEGER")
    safe_migrate("ALTER TABLE evenements ADD COLUMN auteur_nom TEXT")
    safe_migrate("ALTER TABLE agenda ADD COLUMN evenement_id INTEGER")

    # --- 3. DONNÉES PAR DÉFAUT ---
    if c.execute("SELECT COUNT(*) FROM diocese").fetchone()[0] == 0:
        c.execute("INSERT INTO diocese (nom, responsable, bureau) VALUES (?, ?, ?)", ("GRAND-BASSAM", "À définir", "À définir"))

    if c.execute("SELECT COUNT(*) FROM utilisateurs WHERE role='diocese'").fetchone()[0] == 0:
        admin_pwd = "admin123"
        try:
            import streamlit as st
            admin_pwd = st.secrets.get("ADMIN_DEFAULT_PASSWORD", "admin123")
        except Exception:
            pass
        # Hash cohérent avec services.hash_password (pas d'import direct : circularité)
        c.execute("INSERT INTO utilisateurs (username, password, role, diocese_id) VALUES (?, ?, ?, ?)",
                  ("diocese", hashlib.sha256(admin_pwd.encode()).hexdigest(), "diocese", 1))
    commit_and_sync()

    # --- 4. MIGRATION DE DONNÉES : evenements.equipe_id -> evenement_equipes ---
    try:
        anciens_evts = c.execute("SELECT id, equipe_id FROM evenements WHERE equipe_id IS NOT NULL AND paroisse_id IS NULL AND diocese_id IS NULL").fetchall()
        for evt_id, eq_id in anciens_evts:
            existe = c.execute("SELECT id FROM evenement_equipes WHERE evenement_id=? AND equipe_id=?", (evt_id, eq_id)).fetchone()
            if not existe:
                c.execute("INSERT INTO evenement_equipes (evenement_id, equipe_id) VALUES (?, ?)", (evt_id, eq_id))
        commit_and_sync()
    except Exception as e:
        logger.warning(f"Erreur migration événements: {e}")

    # --- 5. INDEX UNIQUES (dédoublonnage AVANT création) ---
    try:
        c.execute("""DELETE FROM evenement_equipes WHERE rowid NOT IN
                     (SELECT MIN(rowid) FROM evenement_equipes GROUP BY evenement_id, equipe_id)""")
        c.execute("""DELETE FROM suivi_presences WHERE rowid NOT IN
                     (SELECT MIN(rowid) FROM suivi_presences GROUP BY membre_id, evenement_id)""")
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_evt_equipe ON evenement_equipes(evenement_id, equipe_id)")
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_sp_membre_evt ON suivi_presences(membre_id, evenement_id)")
        commit_and_sync()
    except Exception as e:
        logger.warning(f"Index uniques non créés : {e}")


def setup_database():
    import streamlit as st
    @st.cache_resource
    def _migrations_done():
        init_tables_and_migrations()
        return True
    _migrations_done()


try:
    setup_database()
except Exception as e:
    logger.error(f"Erreur critique lors de l'initialisation de la DB: {e}")
    raise
