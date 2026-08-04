import sqlite3
import os
import time
import hashlib

# --- LE CAMOUFLAGE TURSO (Compatible Python 3.14) ---
class TursoCamouflage:
    """Fait croire au reste de l'application qu'il utilise sqlite3, 
    mais parle en réalité au client officiel libsql-client."""
    def __init__(self, url, auth_token):
        import libsql_client
        self.client = libsql_client.Client(url=url, auth_token=auth_token)
        
    def cursor(self):
        return self 
        
    def execute(self, query, params=None):
        if params:
            self._result = self.client.execute(query, params)
        else:
            self._result = self.client.execute(query)
        return self
        
    def fetchone(self):
        return self._result.fetchone()
        
    def fetchall(self):
        return self._result.fetchall()
        
    @property
    def lastrowid(self):
        return self._result.last_rowid
        
    def commit(self):
        pass # libsql-client valide automatiquement
        
    def close(self):
        self.client.close()
# ------------------------------------------------

# --- Connexion DB ---
def create_connection():
    try:
        import streamlit as st
        url = st.secrets.get("TURSO_URL")
        token = st.secrets.get("TURSO_AUTH_TOKEN")
        if url and token:
            url_https = url.replace("libsql://", "https://")
            return TursoCamouflage(url_https, token), True
    except Exception:
        pass
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
        for attempt in range(3):
            try:
                return self.cursor.execute(query, tuple(params) if params else ())
            except Exception as e:
                error_msg = str(e).lower()
                if "stream not found" in error_msg or "connection reset" in error_msg:
                    time.sleep(1)
                    global conn
                    conn, _ = create_connection()
                    self.cursor = conn.cursor()
                    continue
                if "duplicate column" not in error_msg:
                    import streamlit as st
                    st.error(f"Erreur SQL : {e}")
                raise e
    def __getattr__(self, name):
        return getattr(self.cursor, name)

c = CursorWrapper(conn.cursor()) if USE_TURSO else conn.cursor()

def commit_and_sync():
    conn.commit()

# --- Création des tables ---
def init_tables():
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
    
    if c.execute("SELECT COUNT(*) FROM diocese").fetchone()[0] == 0:
        c.execute("INSERT INTO diocese (nom, responsable, bureau) VALUES (?, ?, ?)", ("GRAND-BASSAM", "À définir", "À définir"))
        
    if c.execute("SELECT COUNT(*) FROM utilisateurs WHERE role='diocese'").fetchone()[0] == 0:
        admin_hash = hashlib.sha256("admin123".encode()).hexdigest()
        c.execute("INSERT INTO utilisateurs (username, password, role, diocese_id) VALUES (?, ?, ?, ?)", ("diocese", admin_hash, "diocese", 1))
        
    commit_and_sync()

init_tables()

# --- Sécurité pour les anciennes bases de données ---
try:
    c.execute("ALTER TABLE membres RENAME COLUMN matricule TO matloc")
    commit_and_sync()
except: pass
try:
    c.execute("ALTER TABLE membres RENAME COLUMN mle_sup TO matricule")
    commit_and_sync()
except: pass
try:
    c.execute("ALTER TABLE membres ADD COLUMN matricule TEXT")
    commit_and_sync()
except: pass

# Ajout de la colonne pour le "Faire suivre"
try:
    c.execute("ALTER TABLE agenda ADD COLUMN a_faire_suivre INTEGER DEFAULT 0")
    commit_and_sync()
except sqlite3.OperationalError:
    pass

# --- MIGRATION : Gestion des événements multi-équipes ---
try:
    c.execute("ALTER TABLE evenements ADD COLUMN paroisse_id INTEGER")
    commit_and_sync()
except: pass
try:
    c.execute("ALTER TABLE evenements ADD COLUMN diocese_id INTEGER")
    commit_and_sync()
except: pass
try:
    c.execute("ALTER TABLE evenements ADD COLUMN auteur_nom TEXT")
    commit_and_sync()
except: pass

# --- MIGRATION CRUCIALE : Récupérer les anciens événements ---
try:
    anciens_evts = c.execute("SELECT id, equipe_id FROM evenements WHERE equipe_id IS NOT NULL AND paroisse_id IS NULL AND diocese_id IS NULL").fetchall()
    for evt_id, eq_id in anciens_evts:
        existe = c.execute("SELECT id FROM evenement_equipes WHERE evenement_id=? AND equipe_id=?", (evt_id, eq_id)).fetchone()
        if not existe:
            c.execute("INSERT INTO evenement_equipes (evenement_id, equipe_id) VALUES (?, ?)", (evt_id, eq_id))
    commit_and_sync()
except Exception:
    pass

# --- FORCER LE CHANGEMENT DU DEFAUT PAR DEFAUT SUR L'ANCIENNE BASE ---
try:
    c.execute("ALTER TABLE suivi_presences ALTER COLUMN statut SET DEFAULT 'a_contacter'")
    commit_and_sync()
except Exception:
    pass

# --- MIGRATION PHILOSOPHIQUE : De l'obéissance à la discipline de communion ---
try:
    c.execute("UPDATE suivi_presences SET statut='physique' WHERE statut='present'")
    c.execute("UPDATE suivi_presences SET statut='spirituel' WHERE statut='excuse'")
    c.execute("UPDATE suivi_presences SET statut='a_contacter' WHERE statut='absent'")
    commit_and_sync()
except Exception:
    pass
