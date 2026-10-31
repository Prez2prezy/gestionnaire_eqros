import sqlite3
import os
import re
import json
import time
import hashlib
import secrets
import logging
import threading
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

# === v7.9.11 — LA PAIX DES FILS (la base à l'heure des cinq téléphones) ====
# Chaque fidèle navigue dans son propre fil d'exécution ; jusque-là, TOUS
# se partageaient le MÊME curseur : quand plusieurs téléphones visitaient
# les pages en même temps (formation pastorale, cinq téléphones), les
# requêtes s'entremêlaient — lectures croisées d'un fil à l'autre,
# identifiants confondus, transactions rendues au repos (SQLITE_BUSY).
# Désormais, trois disciplines silencieuses :
#   ① un VERROU sérialise chaque requête et chaque commit — deux fils ne
#     parlent plus à la base en même temps ;
#   ② les lignes sont CAPTURÉES à l'instant de l'exécution : fetchone()
#     et fetchall() relisent LE résultat de CETTE requête, jamais celui
#     du voisin ;
#   ③ lastrowid / rowcount / description se lisent par fil (le dernier
#     résultat de CHACUN lui appartient) ;
#   ④ (v7.9.13) LA MAIN PRUDENTE : les lignes ne sont demandées qu'aux
#     lectures — une écriture n'a rien à rendre, et chez l'hébergeur le
#     conducteur distant peut répondre None sans mentir sur la réussite.
#     Chaque métadonnée est lue avec des gants : rien ne peut plus
#     briser une requête au moment où on relève son résultat.
# Le rattrapage des micro-coupures Hrana/Turso (v7.8.16, v7.9.10) demeure
# à l'identique, à l'intérieur du verrou.
_verrou_db = threading.RLock()      # réentrant : un même fil peut enchaîner
_tls = threading.local()            # le dernier résultat DE CE fil


class ResultatRequete:
    """Le résultat capturé d'une requête (v7.9.11) : les lignes sont
    relevées à l'exécution, sous le verrou — fetchone()/fetchall()
    relisent ces lignes-là, même si un autre fil a exécuté entre-temps."""
    __slots__ = ("_lignes", "lastrowid", "rowcount", "description")

    def __init__(self, lignes, lastrowid, rowcount, description):
        self._lignes = lignes
        self.lastrowid = lastrowid
        self.rowcount = rowcount
        self.description = description

    def fetchone(self):
        return self._lignes[0] if self._lignes else None

    def fetchall(self):
        return list(self._lignes)

    def fetchmany(self, n=None):
        return list(self._lignes) if n is None else self._lignes[:n]

    def __iter__(self):
        return iter(self._lignes)

    def __len__(self):
        return len(self._lignes)


class CursorWrapper:
    def __init__(self, cursor):
        self.cursor = cursor

    def execute(self, query, params=None):
        with _verrou_db:
            last_err = None
            # v7.9.13 — LA MAIN PRUDENTE : chez l'hébergeur (le dialecte
            # distant de Turso), le curseur laissait `description` posée
            # après une écriture pendant que `fetchall()` répondait None —
            # et `list(None)` brisait alors chaque INSERT / UPDATE / DELETE /
            # CREATE en production (26 octobre 2026). Désormais on ne
            # demande des lignes qu'aux lectures ; les écritures n'y
            # touchent jamais, et chaque métadonnée est lue avec des gants :
            # si le conducteur se dérobe, la requête poursuit sa route.
            _est_lecture = (query or "").lstrip().upper().startswith(
                ("SELECT", "WITH", "PRAGMA", "VALUES", "EXPLAIN"))
            for attempt in range(3):
                try:
                    cur = self.cursor.execute(query,
                                              tuple(params) if params else ())
                    # v7.9.11 — capture IMMÉDIATE, sous le verrou : les
                    # lignes et les métadonnées deviennent la propriété de
                    # CETTE requête (aucun partage avec le fil voisin).
                    _desc = None
                    _brut = None
                    if _est_lecture:
                        try:
                            _desc = cur.description
                        except Exception:
                            _desc = None
                        _brut = cur.fetchall()
                    _lignes = list(_brut) if _brut is not None else []
                    try:
                        _lastrowid = cur.lastrowid
                    except Exception:
                        _lastrowid = 0
                    try:
                        _rowcount = cur.rowcount
                    except Exception:
                        _rowcount = 0
                    _res = ResultatRequete(_lignes, _lastrowid,
                                           _rowcount, _desc)
                    _tls.dernier = _res
                    return _res
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
            raise Exception(f"Connexion instable : 3 tentatives échouées ({last_err})")

    def __getattr__(self, name):
        # v7.9.11 — les lectures faites DIRECTEMENT sur `c` (c.fetchone(),
        # c.fetchall(), c.description, c.lastrowid…) relisent le dernier
        # résultat DU FIL COURANT ; le reste est délégué au curseur réel.
        if name in ("fetchone", "fetchall", "fetchmany"):
            def _relire(*args, **kwargs):
                _res = getattr(_tls, "dernier", None)
                if _res is None:
                    raise RuntimeError("Aucun résultat en mémoire : "
                                       "appelez c.execute() d'abord.")
                return getattr(_res, name)(*args, **kwargs)
            return _relire
        if name in ("lastrowid", "rowcount", "description"):
            _res = getattr(_tls, "dernier", None)
            if _res is not None:
                return getattr(_res, name)
        return getattr(self.cursor, name)


# v7.9.11 — le wrapper veille désormais aussi en local : la même discipline
# des fils pour les deux mondes (l'essai et le Cloud).
c = CursorWrapper(conn.cursor())

def commit_and_sync():
    """v7.9.10 — le commit rattrape lui aussi les micro-coupures : une
    première tentative avortée est rejouée une seconde plus tard ; l'échec
    final reste silencieux et journalisé (l'app ne casse jamais au fidèle).
    v7.9.11 — le commit passe par le MÊME verrou que les requêtes : la
    transaction d'un fil ne peut plus être scellée au beau milieu de
    celle d'un autre."""
    with _verrou_db:
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
    # v7.9.18 — CHAÎNE DE LA DERNIÈRE SÉANCE : à la prière mensuelle, les
    # membres PRÉSENTS PHYSIQUEMENT forment une chaîne — le voisin de droite
    # devient le « prochain » de chacun, qui médite et prie son intention
    # jusqu'à la prochaine séance. L'ordre change à CHAQUE séance (les
    # présences ne garantissent pas les positions précédentes) : chaque
    # enregistrement est une ligne d'historique, la plus récente de l'équipe
    # est la chaîne en vigueur. `ordre` porte les N° méd. dans l'ordre de la
    # chaîne (10,17,09,…) ; `absents` note les « présents spirituellement »
    # (hors chaîne), pour mémoire.
    c.execute("""CREATE TABLE IF NOT EXISTS chaine_seances (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    equipe_id INTEGER NOT NULL,
                    date_seance TEXT,
                    ordre TEXT NOT NULL,
                    absents TEXT,
                    date_enregistrement TEXT)""")
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
    # v7.10.0 — QUESTIONNAIRE DU FEUILLET MENSUEL : les questions et
    # exercices du feuillet du mois, composées par la cellule Communication,
    # répondues par les membres ET les visiteurs dans l'Espace de Prière
    # (🕯️ Thème → Vue d'ensemble, juste sous le feuillet).
    c.execute("""CREATE TABLE IF NOT EXISTS feuillet_questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    annee_debut INTEGER NOT NULL,
                    mois INTEGER NOT NULL,
                    ordre INTEGER,
                    question TEXT NOT NULL,
                    type_reponse TEXT DEFAULT 'texte',
                    choix TEXT,
                    obligatoire INTEGER DEFAULT 0,
                    active INTEGER DEFAULT 1)""")
    c.execute("""CREATE TABLE IF NOT EXISTS feuillet_reponses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question_id INTEGER NOT NULL,
                    annee_debut INTEGER NOT NULL,
                    mois INTEGER NOT NULL,
                    cle TEXT NOT NULL,
                    qui_nom TEXT,
                    qui_type TEXT DEFAULT 'visiteur',
                    reponse TEXT,
                    equipe_id INTEGER,
                    paroisse_id INTEGER,
                    date_reponse TEXT)""")
    # v7.10.0 — ENVOI EN MISSION : les missions préparées par les
    # responsables d'équipe (fiche d'envoi imprimable) et leur retour
    # (fiche de rapport de mission). `participants` porte la liste des
    # envoyés (JSON : nom, matloc, contact, externe) ; `rapport` porte le
    # retour (JSON : déroulement, grâces, difficultés, propositions,
    # participants effectifs).
    c.execute("""CREATE TABLE IF NOT EXISTS missions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    equipe_id INTEGER NOT NULL,
                    paroisse_id INTEGER,
                    titre TEXT NOT NULL,
                    objectif TEXT,
                    date_mission TEXT,
                    lieu TEXT,
                    participants TEXT,
                    statut TEXT DEFAULT 'envoi',
                    date_envoi TEXT,
                    auteur_nom TEXT,
                    rapport TEXT,
                    date_rapport TEXT)""")
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
    # v7.11.1 — L'ALERTE D'UNE SEMAINE : la républication d'un feuillet
    # corrigé rafraîchit `date_publication` ; l'alerte 🔔 du fil, elle, se
    # compte à partir de la PREMIÈRE diffusion et ne reste qu'UNE SEMAINE.
    # La colonne est posée une fois ; les lignes déjà en place la reçoivent
    # à la hauteur de leur date de publication (la meilleure disponible),
    # puis elle ne bouge plus jamais — même après républication.
    safe_migrate("ALTER TABLE feuillets_publications ADD COLUMN premiere_diffusion TEXT")
    try:
        c.execute("""UPDATE feuillets_publications
                     SET premiere_diffusion = date_publication
                     WHERE (premiere_diffusion IS NULL OR premiere_diffusion = '')
                       AND date_publication IS NOT NULL""")
        commit_and_sync()
    except Exception:
        pass
    # v7.11.1 — LES MISSIONS EN PÉRIODE ET EN GROUPES : une mission court du
    # lendemain de la dernière séance de prière jusqu'à la prochaine séance
    # (date_debut / date_fin — date_fin vide = « jusqu'à la prochaine
    # séance ») et une équipe peut se scinder en plusieurs groupes (A…Z).
    # date_mission est gardé : il porte le début, pour les anciens affichages.
    safe_migrate("ALTER TABLE missions ADD COLUMN date_debut TEXT")
    safe_migrate("ALTER TABLE missions ADD COLUMN date_fin TEXT")
    safe_migrate("ALTER TABLE missions ADD COLUMN groupe TEXT")
    try:
        c.execute("""UPDATE missions SET date_debut = date_mission
                     WHERE (date_debut IS NULL OR date_debut = '')
                       AND date_mission IS NOT NULL""")
        c.execute("""UPDATE missions SET groupe = 'A'
                     WHERE groupe IS NULL OR groupe = ''""")
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


# ======================================================================
# v7.10.1 — LA RÈGLE D'OR POUR LES MEMBRES AUSSI
# ======================================================================
# « Personne ne prie sa propre intention. » Jusqu'ici la règle protégeait
# le VISITEUR (son jour de naissance écartait ses intentions à lui) ; côté
# MEMBRE la règle ne le protégeait pas : une intention notée en face de
# son N° dans la chaîne de séance revenait devant LUI dans sa propre
# dizaine. Désormais la fiche du membre (son MatLoc) donne son jour de
# naissance ET son nom : ses propres intentions lui sont masquées — au
# tirage principal comme dans le surplus — et une intention reçue qui se
# révélerait être la sienne n'est pas gardée attachée.


def _nom_cle(nom):
    """Clé de comparaison d'un nom (v7.10.1) : espaces réduits, minuscules,
    mots REMIS EN ORDRE — « Odette ONIBONKOU », « ONIBONKOU Odette » et
    « odette  onibonkou » sont le même nom (la fiche porte « Prénom Nom »,
    la chaîne de séance note « Nom Prénom » : l'ordre ne doit pas tromper
    la règle d'or)."""
    return " ".join(sorted(t.lower() for t in str(nom or "").split()))


_FICHES_MEMBRES = {}


def fiche_membre(matloc):
    """(jour_de_naissance, nom_complet) du membre porteur de ce MatLoc
    (v7.10.1) — la règle d'or côté membre. Le jour vient de la date de
    naissance de la fiche (« 1990-05-17 » ou « 17/05/1990 » → 17) ;
    le nom complet joint prénom et nom. Mémoire du processus : une seule
    lecture par MatLoc (une fiche ne change pas pendant la visite).
    Retourne (None, None) quand la fiche est inconnue ou muette."""
    _k = str(matloc or "").upper().strip()
    if not _k:
        return (None, None)
    if _k not in _FICHES_MEMBRES:
        _fiche = (None, None)
        try:
            _r = c.execute("""SELECT date_naissance, prenom, nom
                              FROM membres WHERE matloc=? LIMIT 1""",
                           (_k,)).fetchone()
            if _r:
                _jour = None
                _s = str(_r[0] or "").strip()
                for _tranche in (slice(8, 10), slice(0, 2)):
                    # « 1990-05-17… » → 17, ou « 17/05/1991 » → 17 —
                    # la tranche n'est gardée que si elle dit un vrai jour
                    if len(_s) >= 10 and _s[_tranche].isdigit():
                        _v = int(_s[_tranche])
                        if 1 <= _v <= 31:
                            _jour = _v
                            break
                if _jour is not None and not (1 <= _jour <= 31):
                    _jour = None
                _nomc = " ".join(x for x in (str(_r[1] or "").strip(),
                                             str(_r[2] or "").strip()) if x)
                _fiche = (_jour, _nomc or None)
                # Seule une fiche TROUVÉE est retenue : un MatLoc encore
                # inconnu (membre créé à l'instant) reste interrogable.
                _FICHES_MEMBRES[_k] = _fiche
        except Exception as e:
            logger.warning(f"fiche_membre : {e!r}")
    return _FICHES_MEMBRES.get(_k, (None, None))


def _est_propre_a(qui, auteur, jour_ligne, nom_exclu, jour_exclu):
    """1 si cette intention (qui / auteur / jour de naissance notés sur la
    ligne) appartient AU LECTEUR lui-même (v7.10.1) : le nom correspond à
    celui de sa fiche, ou son jour de naissance correspond à celui noté
    sur l'intention. La règle d'or : personne ne prie la sienne."""
    if nom_exclu:
        _cible = _nom_cle(nom_exclu)
        if _cible and (_nom_cle(qui) == _cible or _nom_cle(auteur) == _cible):
            return 1
    if (jour_exclu is not None and jour_ligne is not None
            and int(jour_ligne) == int(jour_exclu)):
        return 1
    return 0


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
        # v7.10.1 — LA RÈGLE D'OR POUR TOUS : le lecteur (visiteur par son
        # jour, membre par sa fiche — jour ET nom) ne doit jamais recevoir
        # la sienne. Ces deux clés suivent tout le tirage ci-dessous.
        _jour_exclu = None
        _nom_exclu = None
        if matloc:
            _jour_exclu, _nom_exclu = fiche_membre(matloc)
        elif jour_visiteur is not None:
            _jour_exclu = int(jour_visiteur)
        # v7.9.4 — L'ATTACHEMENT D'ABORD : l'intention déjà reçue reste LA
        # SIENNE pendant toute sa période (membre : période désignée ;
        # visiteur : 20 jours), quel que soit le renouvellement de la réserve.
        # v7.10.1 — sauf si cette intention attachée se révèle être la
        # PROPRE intention du lecteur (reçue avant la règle d'or) : elle
        # n'est pas montrée, le tirage poursuit et la remplace tout seul.
        _cle = None
        if matloc:
            _cle = "M:" + str(matloc)
        elif jour_visiteur is not None:
            _n = _numero_med_normale(jour_visiteur)
            _cle = ("J:" + str(_n)) if _n else None
        if _cle:
            _att = prochain_attache(_cle)
            if _att and str(_att[0] or "").strip():
                if not _est_propre_a(_att[1], None, None, _nom_exclu, _jour_exclu):
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
            # La règle d'or : le lecteur ne prie jamais sa propre intention
            # (v7.10.1 — pour le membre aussi : jour ET nom de sa fiche).
            if _est_propre_a(None, _nom, _jn, _nom_exclu, _jour_exclu):
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


# v7.10.1 — LES TABLES RECONNUES UNE FOIS POUR TOUTE LA JOURNÉE D'OUVERTURE :
# chaque contrôle doux (« cette table existe-t-elle ? ») repartait à CHAQUE
# page, chez l'hébergeur en allers-retours lointains — jusqu'à vingt
# tentatives perdues rien qu'à l'entrée dans la dizaine : c'était la
# lenteur ressentie à l'ouverture de l'Espace et au clic « Égrener la
# dizaine ». Désormais la vérification complète ne se pose qu'UNE FOIS par
# processus ; ensuite la maison connaît ses murs par cœur.
_TABLES_RECONNUES = set()


def _table_reconnue(nom_table):
    """1 si la table a déjà été vérifiée présente dans CE processus."""
    return nom_table in _TABLES_RECONNUES


def _table_averee(nom_table):
    """Note que la table a été vérifiée (présente ou posée) ce processus."""
    _TABLES_RECONNUES.add(nom_table)


def _assurer_dizaines_journal():
    """Création douce de dizaines_journal (bases distantes anciennes)."""
    if _table_reconnue("dizaines_journal"):
        return
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
    _table_averee("dizaines_journal")


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


def tableau_pointages_equipe(nb_jours=14, equipe_id=None):
    """📋 LE TABLEAU DE LA CHAÎNE (v7.9.11) — la grille jour × membre des
    nb_jours derniers jours : « ✅ » dans la case du membre qui a égrené sa
    méditation ce jour-là, vide sinon. La ligne du jour vit en tête ; à
    00h00 elle s'archive d'elle-même et les lignes passées demeurent
    consultables à souhait (le journal complet est relu, rien n'est
    jamais effacé). Retourne (jours, membres, grille, totaux) :
      jours   → [iso, ...] du plus récent au plus ancien ;
      membres → [(matloc, libellé), ...] des actifs, ordre alphabétique
                (libellés rendus uniques si deux prénoms se ressemblent) ;
      grille  → {(jour, matloc), …} — l'ensemble des cases cochées ;
      totaux  → {matloc: n} — les ✅ de la période, membre par membre."""
    try:
        _assurer_dizaines_journal()
        _fin = date.today()
        _deb = date.fromordinal(_fin.toordinal() - nb_jours + 1)
        _ph, _prm = ("AND equipe_id=?", [equipe_id]) if equipe_id else ("", [])
        _cases = c.execute(f"""SELECT jour, matloc FROM dizaines_journal
                               WHERE type='membre' AND jour>=? {_ph}""",
                           (_deb.isoformat(), *_prm)).fetchall()
        _grille = {(str(r[0]), str(r[1]).upper().strip()) for r in _cases
                   if r[0] and r[1]}
        _membres = [(str(m[0]).upper().strip(),
                     (f"{m[2] or ''} {m[1] or ''}".strip() or "Membre"))
                    for m in c.execute(
                        """SELECT matloc, nom, prenom FROM membres
                           WHERE equipe_id=? AND statut='actif'
                           ORDER BY nom, prenom""", (equipe_id,)).fetchall()
                    if m[0]]
        # libellés uniques (deux prénoms identiques dans la même équipe)
        _vus, _membres_uniq = {}, []
        for _mat, _lib in _membres:
            _n = _vus.get(_lib, 0) + 1
            _vus[_lib] = _n
            _membres_uniq.append((_mat, _lib if _n == 1 else f"{_lib} ({_n})"))
        _jours = [date.fromordinal(_fin.toordinal() - _i).isoformat()
                  for _i in range(nb_jours)]
        _totaux = {m: 0 for m, _ in _membres_uniq}
        for (_j, _m) in _grille:
            if _m in _totaux:
                _totaux[_m] += 1
        return (_jours, _membres_uniq, _grille, _totaux)
    except Exception as e:
        logger.warning(f"tableau_pointages_equipe : {e!r}")
        return ([], [], {}, {})


def tableau_pointages_visiteurs(nb_jours=14):
    """🔥 LE TABLEAU DES VISITEURS (v7.9.11) — les passages anonymes,
    jour par jour, sur les nb_jours derniers jours. Les visiteurs
    n'appartiennent à aucune équipe : la comptée demeure globale (elle
    est la communauté toute entière). Retourne [(jour, n_visiteurs), …]
    du plus récent au plus ancien."""
    try:
        _serie = serie_dizaines(nb_jours)          # (jour, membres, visiteurs)
        return [(j, vv) for (j, _mv, vv) in reversed(_serie)]
    except Exception as e:
        logger.warning(f"tableau_pointages_visiteurs : {e!r}")
        return []


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
    doux (idempotent) : une base Cloud née avant v7.9.4 doit rester lisible.
    v7.10.1 — le contrôle complet ne se pose qu'UNE FOIS par processus
    (la lenteur des pages venait de ces allers-retours répétés)."""
    if _table_reconnue("intentions_reserve"):
        return
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
    # v7.12.0 — auteur_contact : le contact laissé par le fidèle (WhatsApp /
    # e-mail) voyage avec son intention en réserve — c'est lui qui permet
    # d'alerter le visiteur de la chaîne sur son téléphone (rappels 4×/jour).
    for _col in ("active INTEGER DEFAULT 1", "qui TEXT", "jour_naissance INTEGER",
                 "publiee INTEGER DEFAULT 1", "date_publication TEXT",
                 "auteur_contact TEXT"):
        try:
            c.execute(f"ALTER TABLE intentions_reserve ADD COLUMN {_col}")
            commit_and_sync()
        except Exception:
            pass  # colonne déjà présente
    _retroremplir_contact_reserve()
    _table_averee("intentions_reserve")


def _assurer_table_du_jour():
    """Création douce de intentions_du_jour — LA ZONE DU JOUR (v7.9.4) :
    elle reçoit toutes les intentions confiées dans la journée ; le
    lendemain, chacune entre dans la réserve (traiter_intentions_du_jour).
    v7.10.1 — le contrôle ne se pose qu'UNE FOIS par processus."""
    if _table_reconnue("intentions_du_jour"):
        return
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
    _table_averee("intentions_du_jour")


def _assurer_table_attributions():
    """Création douce de attributions_prochain (v7.9.4) — l'intention du
    prochain reçue reste attachée à son lecteur pendant sa période.
    v7.10.1 — le contrôle ne se pose qu'UNE FOIS par processus."""
    if _table_reconnue("attributions_prochain"):
        return
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
    _table_averee("attributions_prochain")


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
                                       jour_naissance, equipe_id, paroisse_id,
                                       auteur_contact
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
        for (_zid, _txt, _nom, _anon, _jn, _eqi, _pri, _ctc) in _attente:
            _slot = _slots[0]
            _slots = _slots[1:] + [_slot]     # pioche mélangée : ordre aléatoire
            if _slot not in _remplace:
                c.execute("""UPDATE intentions_reserve SET active=0
                             WHERE numero_med=? AND active=1""", (_slot,))
                _remplace.add(_slot)
            # v7.12.0 — le contact du fidèle voyage avec son intention : la
            # chaîne saura l'alerter sur son téléphone pendant ses 20 jours.
            c.execute("""INSERT INTO intentions_reserve
                         (numero_med, texte, auteur_nom, equipe_id, paroisse_id,
                          date_ajout, active, qui, jour_naissance, publiee,
                          date_publication, auteur_contact)
                         VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, 0, ?, ?)""",
                      (_slot, _txt, None if _anon else ((str(_nom).strip() or None) if _nom else None),
                       _eqi, _pri, _auj, "cet anonyme" if _anon else "notre prochain",
                       int(_jn) if _jn else None, _demain,
                       (str(_ctc).strip() or None) if _ctc else None))
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


# ======================================================================
# v7.9.20 — LA DURÉE DE VIE DES INTENTIONS EN RÉSERVE
# ======================================================================
# « Une intention est censée avoir une durée de 20 jours après sa prise
# en charge quand elle vient du visiteur, et jusqu'à la prochaine séance
# de la prière mensuelle pour le membre. Elle doit par conséquent être
# supprimée de la réserve après 00h00 de la date échéance, ou à la
# nouvelle saisie. » —
#   • VISITEUR (passée par la 🕯️ Zone du jour) : 20 jours après sa prise
#     en charge (date_ajout) — elle quitte la réserve à 00h00 du 21ᵉ jour ;
#   • MEMBRE (posée en face de son N° dans la ⛓️ Chaîne) : elle vit
#     jusqu'à la NOUVELLE saisie — enregistrer_chaine_seance la libère
#     (celles notées à CETTE séance suivent juste après, date_ajout du
#     jour : elles ne sont pas touchées) ;
#   • les vieilles lignes orphelines (d'avant les réserves d'équipe, sans
#     équipe notée) suivent la règle des 20 jours du visiteur.
# Le réveil est paresseux : une seule exécution par jour et par processus,
# appelée aux lectures de la réserve comme aux tirages. Les lignes
# libérées passent active=0 (elles quittent toutes les vues et les
# compteurs, comme l'ancienne rotation).

DUREE_RESERVE_VISITEUR = 20

_RESERVE_PURGE_FAIT_LE = None


def purger_reserve_expiree(force=False):
    """LE RÉVEIL DE LA RÉSERVE (v7.9.20) : libère les intentions dont la
    durée de vie est échue — celles des VISITEURS 20 jours après leur prise
    en charge (00h00 du 21ᵉ jour) et les vieilles lignes orphelines ; celles
    des MEMBRES sont libérées à la nouvelle saisie de la chaîne (voir
    enregistrer_chaine_seance). Paresseux et idempotent : une seule
    exécution par jour et par processus (sauf force=True), silencieux.
    Retourne le nombre d'intentions libérées."""
    global _RESERVE_PURGE_FAIT_LE
    _auj = date.today().isoformat()
    if not force and _RESERVE_PURGE_FAIT_LE == _auj:
        return 0
    try:
        _assurer_table_reserve()
        _limite = date.fromordinal(
            date.today().toordinal() - DUREE_RESERVE_VISITEUR).isoformat()
        _cur = c.execute("""UPDATE intentions_reserve SET active=0
                            WHERE active=1
                              AND date_ajout IS NOT NULL
                              AND date_ajout <= ?
                              AND (publiee IS NOT NULL
                                   OR qui IN ('cet anonyme', 'notre prochain')
                                   OR equipe_id IS NULL)""", (_limite,))
        commit_and_sync()
        _RESERVE_PURGE_FAIT_LE = _auj
        return int(getattr(_cur, "rowcount", 0) or 0)
    except Exception as e:
        logger.warning(f"purger_reserve_expiree : {e!r}")
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
                                   equipe_id, paroisse_id, auteur_contact
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
                      date_ajout, active, qui, jour_naissance, publiee,
                      date_publication, auteur_contact)
                     VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, 0, ?, ?)""",
                  (_slot, _txt,
                   None if _anon else ((str(_row[1]).strip() or None) if _row[1] else None),
                   _row[4], _row[5], _auj.isoformat(),
                   "cet anonyme" if _anon else "notre prochain",
                   int(_row[3]) if _row[3] else None,
                   _demain,
                   (str(_row[6]).strip() or None) if _row[6] else None))
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
    v7.9.4 — UNE intention par N° méd. (règle d'origine).
    v7.9.19 — LE SURPLUS EST LE BIENVENU : un N° méd. peut porter plusieurs
    intentions. Le membre ou le visiteur qui médite CE N° reçoit alors
    TOUTES les intentions du N° : la principale + le surplus (voir
    intentions_reserve_surplus). Aucun ajout n'est plus refusé pour cause
    d'emplacement déjà pourvu.
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
        _deja = c.execute("""SELECT COUNT(*) FROM intentions_reserve
                             WHERE numero_med=? AND active=1""",
                          (_num,)).fetchone()[0]
        c.execute("""INSERT INTO intentions_reserve
                     (numero_med, texte, auteur_nom, equipe_id, paroisse_id,
                      date_ajout, active, qui, jour_naissance)
                     VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)""",
                  (_num, _txt, (str(auteur_nom).strip() or None) if auteur_nom else None,
                   equipe_id, paroisse_id, date.today().isoformat(),
                   (str(qui).strip() or None) if qui else None,
                   int(jour_naissance) if jour_naissance else None))
        commit_and_sync()
        if _deja:
            return (True, "📚 Intention ajoutée à la réserve du N° méd. " + str(_num)
                           + " — il porte maintenant " + str(_deja + 1)
                           + " intentions : le membre ou le visiteur qui médite ce "
                             "N° portera aussi ce surplus.")
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
    normal ; plus si les demandes abondent).
    v7.9.20 — le réveil de la durée de vie passe d'abord (les intentions
    échues ne comptent plus)."""
    _d = {n: 0 for n in range(1, 21)}
    try:
        _assurer_table_reserve()
        purger_reserve_expiree()
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
    (id, numero_med, texte, auteur_nom, equipe_id, date_ajout).
    v7.9.20 — le réveil de la durée de vie passe d'abord."""
    _assurer_table_reserve()
    purger_reserve_expiree()
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


# v7.10.3 — la fonction d'étiquetage par paroisse (reserve_lignes_paroisse_
# nommee, v7.10.2) est retirée : « les intentions, c'est une affaire de
# paroisse, de ses membres et visiteurs — le diocèse n'a rien à voir
# dedans. » La réserve se lit comme avant, sans noms de paroisses.


# ─────────────────────────────────────────────────────────────────────────────
# v7.9.18 — CHAÎNE DE LA DERNIÈRE SÉANCE
# « Au cours d'une prière mensuelle, les membres présents physiquement
# constituent une chaîne : le voisin de droite est le prochain de l'autre,
# et la prochaine séance ne garantit pas les positions précédentes. »
# Chaque séance enregistre l'ordre des présents (N° méd.) ; l'app en tire la
# traduction : « X aura pour prochain Y — N° méd. Z, méditera et priera son
# intention jusqu'à la prochaine séance. » La chaîne se referme sur le
# premier (le dernier maillon reprend le premier).
# ─────────────────────────────────────────────────────────────────────────────
def _assurer_table_chaine_seances():
    """Création douce de chaine_seances (bases distantes anciennes).
    v7.10.1 — le contrôle ne se pose qu'UNE FOIS par processus."""
    if _table_reconnue("chaine_seances"):
        return
    try:
        c.execute("SELECT id FROM chaine_seances LIMIT 1")
    except Exception:
        try:
            c.execute("""CREATE TABLE IF NOT EXISTS chaine_seances (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            equipe_id INTEGER NOT NULL,
                            date_seance TEXT,
                            ordre TEXT NOT NULL,
                            absents TEXT,
                            date_enregistrement TEXT)""")
            commit_and_sync()
        except Exception as e:
            logger.warning(f"_assurer_table_chaine_seances : {e!r}")
    _table_averee("chaine_seances")


def enregistrer_chaine_seance(equipe_id, date_seance, ordre_nums, absents_nums=None):
    """Enregistre la chaîne d'une séance (v7.9.18). ordre_nums : liste d'entiers
    (N° méd.) dans l'ordre de la chaîne — le dernier reprend le premier.
    absents_nums : liste optionnelle des « présents spirituellement » (hors
    chaîne). Retourne (ok, message) prêt à afficher."""
    _assurer_table_chaine_seances()
    try:
        _ordre = [int(n) for n in (ordre_nums or [])]
    except (TypeError, ValueError):
        return (False, "Les N° méd. de la chaîne sont illisibles.")
    if not _ordre:
        return (False, "La chaîne est vide : notez au moins deux membres présents.")
    if len(_ordre) == 1:
        return (False, "Une chaîne relie au moins deux membres présents.")
    _abs = []
    try:
        _abs = [int(n) for n in (absents_nums or [])]
    except (TypeError, ValueError):
        return (False, "Les N° méd. des présents spirituellement sont illisibles.")
    try:
        c.execute("""INSERT INTO chaine_seances
                     (equipe_id, date_seance, ordre, absents, date_enregistrement)
                     VALUES (?,?,?,?,?)""",
                  (int(equipe_id),
                   str(date_seance or date.today().isoformat()),
                   ",".join(str(n) for n in _ordre),
                   ",".join(str(n) for n in _abs) if _abs else None,
                   datetime.now().strftime("%Y-%m-%d %H:%M")))
        # v7.9.20 — LA NOUVELLE SAISIE LIBÈRE LES INTENTIONS DES MEMBRES :
        # celles posées dans la chaîne précédente ont vécu « jusqu'à la
        # prochaine séance » — la séance venue, elles quittent la réserve
        # (celles notées à CETTE séance suivent juste après, avec date_ajout
        # du jour : elles ne sont pas touchées ; celles du jour même, d'une
        # correction de saisie non plus). Les intentions des VISITEURS ne
        # bougent pas : elles suivent leur règle à elles (20 jours).
        try:
            _lib = c.execute("""UPDATE intentions_reserve SET active=0
                                WHERE equipe_id=? AND active=1
                                  AND (date_ajout IS NULL OR date_ajout < ?)
                                  AND publiee IS NULL
                                  AND (qui IS NULL OR qui NOT IN
                                       ('cet anonyme', 'notre prochain'))""",
                              (int(equipe_id), date.today().isoformat()))
            _n_lib = int(getattr(_lib, "rowcount", 0) or 0)
        except Exception as e:
            logger.warning(f"enregistrer_chaine_seance (libération) : {e!r}")
            _n_lib = 0
        commit_and_sync()
        # v7.9.19 — la phrase demandée : « X prie pour Y — N° méd. Z. »
        _msg = ("Chaîne de la séance enregistrée : chaque membre prie pour "
                "son prochain jusqu'à la prochaine séance. ⛓️")
        if _n_lib:
            _msg += (" Les intentions de la précédente séance ("
                     + str(_n_lib) + ") ont quitté la réserve.")
        return (True, _msg)
    except Exception as e:
        logger.warning(f"enregistrer_chaine_seance : {e!r}")
        return (False, "L'enregistrement a échoué (erreur technique journalisée).")


def derniere_chaine_seance(equipe_id):
    """La chaîne la plus récente de l'équipe (v7.9.18) — c'est elle qui est
    « en vigueur » jusqu'à la prochaine séance. Retourne
    (id, date_seance, ordre, absents, date_enregistrement) ou None."""
    _assurer_table_chaine_seances()
    try:
        return c.execute("""SELECT id, date_seance, ordre, absents, date_enregistrement
                            FROM chaine_seances WHERE equipe_id=?
                            ORDER BY date_seance DESC, id DESC LIMIT 1""",
                         (int(equipe_id),)).fetchone()
    except Exception as e:
        logger.warning(f"derniere_chaine_seance : {e!r}")
        return None


def historique_chaines_seance(equipe_id, limite=12):
    """Historique des chaînes d'une équipe, la plus récente d'abord
    (v7.9.18) — les anciennes séances restent consultables."""
    _assurer_table_chaine_seances()
    try:
        return c.execute("""SELECT id, date_seance, ordre, absents, date_enregistrement
                            FROM chaine_seances WHERE equipe_id=?
                            ORDER BY date_seance DESC, id DESC LIMIT ?""",
                         (int(equipe_id), int(limite))).fetchall()
    except Exception as e:
        logger.warning(f"historique_chaines_seance : {e!r}")
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
        # v7.9.20 — la durée de vie passe d'abord : une intention échue ne
        # nourrit plus le tirage.
        publier_reserve_due()
        purger_reserve_expiree()
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


def intentions_reserve_du_numero(numero_med, texte_exclu=None, jour_exclu=None,
                                 nom_exclu=None):
    """TOUTES les intentions d'un N° méd. (v7.9.19) — la réserve accepte
    désormais plusieurs intentions au même N° (le surplus). Cette fonction
    les rend TOUTES : liste de (texte, qui), les plus anciennes d'abord.
    texte_exclu : retire de la liste l'intention déjà montrée à part (la
    ligne principale du tirage) — le lecteur ne la lit pas deux fois.
    jour_exclu : règle d'or (le lecteur ne voit jamais la sienne).
    nom_exclu : règle d'or côté MEMBRE (v7.10.1) — le nom de sa fiche
    écarte les intentions notées à son nom dans la réserve.
    Seules les intentions ACTIVES et PUBLIÉES sont rendues."""
    _num = _numero_med_normale(numero_med)
    if _num is None:
        return []
    try:
        _assurer_table_reserve()
        publier_reserve_due()
        purger_reserve_expiree()
        rows = c.execute("""SELECT texte, qui, auteur_nom, jour_naissance
                            FROM intentions_reserve
                            WHERE numero_med=? AND active=1
                              AND (publiee IS NULL OR publiee<>0)
                            ORDER BY id ASC""", (_num,)).fetchall()
    except Exception as e:
        logger.warning(f"intentions_reserve_du_numero : {e!r}")
        return []
    _exclu = str(texte_exclu or "").strip()
    _sortie = []
    for (_txt, _qui, _auteur, _jn) in rows:
        if jour_exclu is not None and _jn is not None and int(_jn) == int(jour_exclu):
            continue
        if nom_exclu and (_nom_cle(_qui) == _nom_cle(nom_exclu)
                          or _nom_cle(_auteur) == _nom_cle(nom_exclu)):
            continue
        if _exclu and str(_txt or "").strip() == _exclu:
            continue
        _q = (str(_qui or "").strip() or str(_auteur or "").strip() or "notre prochain")
        _sortie.append((str(_txt or "").strip(), _q))
    return _sortie


def intentions_reserve_surplus(jour_visiteur=None, matloc=None, texte_exclu=None):
    """LE SURPLUS POUR LE LECTEUR (v7.9.19) : « Si un N° méd. contient plus
    d'une intention, le membre comme le visiteur qui médite ce N° méd. verra
    ses intentions augmentées selon le surplus. » Retrouve le N° méd. du
    lecteur (son jour de naissance pour un visiteur, sa fiche membre pour un
    membre) et rend TOUTES les intentions de ce N°, SAUF la ligne principale
    déjà affichée (texte_exclu) et SES PROPRES intentions (règle d'or) :
    pour le visiteur, son jour de naissance ; pour le membre, son jour ET
    son nom de fiche (v7.10.1 — une intention notée à son nom dans la
    réserve ne lui revient plus). Retourne une liste de (texte, qui)."""
    _num = None
    _jour_exclu = jour_visiteur
    _nom_exclu = None
    if matloc:
        _jour_exclu, _nom_exclu = fiche_membre(matloc)
        try:
            _row = c.execute("""SELECT numero_meditation FROM membres
                                WHERE matloc=? LIMIT 1""",
                             (str(matloc).upper().strip(),)).fetchone()
            if _row:
                _num = _numero_med_normale(_row[0])
        except Exception:
            _num = None
    elif jour_visiteur is not None:
        _num = _numero_med_normale(jour_visiteur)
    if _num is None:
        return []
    return intentions_reserve_du_numero(_num, texte_exclu=texte_exclu,
                                        jour_exclu=_jour_exclu,
                                        nom_exclu=_nom_exclu)


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


# ======================================================================
# v7.9.20 — LA MÉMOIRE D'UN JOUR DES CARTES (« 🔔 feuillet mensuel »,
# « 📿 Ta dizaine du jour »)
# ======================================================================
# Les cartes de l'Espace de Prière se referment pour la journée quand le
# fidèle les marque (« 📌 Marquer l'alerte comme lue », « J'ai honoré mon
# engagement de ce jour »). Jusqu'ici la mémoire vivait dans la session et
# dans un cookie du navigateur : au rechargement, la session est vidée et,
# quand l'Espace est vu depuis une page extérieure (le site), le navigateur
# refuse les cookies dits « tierce partie » — la carte revenait donc, sans
# cesse. Désormais la mémoire vit EN BASE : elle tient au rechargement
# comme à la navigation ; la carte revient le lendemain (ou quand un
# NOUVEAU feuillet paraît — la clé porte alors un autre nom). Le lecteur
# est reconnu par une clé sans cookie ni session (MatLoc du membre,
# empreinte hachée de la consultation pour un visiteur — voir
# _cle_lecteur_pdr dans views/view_espace_membre.py) : aucune donnée
# personnelle n'est gardée, et le ménage des jours passés part à chaque
# écriture.


def _assurer_table_cartes_vues():
    """Création douce de cartes_vues (bases distantes anciennes).
    v7.10.1 — le contrôle ne se pose qu'UNE FOIS par processus."""
    if _table_reconnue("cartes_vues"):
        return
    try:
        c.execute("SELECT 1 FROM cartes_vues LIMIT 1")
    except Exception:
        try:
            c.execute("""CREATE TABLE IF NOT EXISTS cartes_vues (
                            cle TEXT NOT NULL,
                            carte TEXT NOT NULL,
                            jour TEXT NOT NULL,
                            UNIQUE(cle, carte, jour))""")
            commit_and_sync()
        except Exception as e:
            logger.warning(f"_assurer_table_cartes_vues : {e!r}")
    _table_averee("cartes_vues")


def marquer_carte_vue(cle, carte):
    """Note que CE lecteur (clé) a marqué CETTE carte aujourd'hui (v7.9.20)
    — la mémoire d'un jour, tenue en base, qui survit au rechargement.
    Le ménage des jours passés part en même temps. Silencieuse : jamais de
    plantage pour le fidèle. Retourne True si la mémoire est notée."""
    _cle = str(cle or "").strip()
    _carte = str(carte or "").strip()
    if not _cle or not _carte:
        return False
    try:
        _assurer_table_cartes_vues()
        _auj = date.today().isoformat()
        c.execute("DELETE FROM cartes_vues WHERE jour < ?", (_auj,))
        c.execute("INSERT OR IGNORE INTO cartes_vues (cle, carte, jour) "
                  "VALUES (?, ?, ?)", (_cle, _carte, _auj))
        commit_and_sync()
        return True
    except Exception as e:
        logger.warning(f"marquer_carte_vue : {e!r}")
        return False


def carte_deja_vue(cle, carte):
    """1 si CE lecteur a déjà marqué CETTE carte aujourd'hui, 0 sinon
    (v7.9.20) — la mémoire d'un jour, tenue en base."""
    _cle = str(cle or "").strip()
    _carte = str(carte or "").strip()
    if not _cle or not _carte:
        return 0
    try:
        _assurer_table_cartes_vues()
        return 1 if c.execute(
            "SELECT 1 FROM cartes_vues WHERE cle=? AND carte=? AND jour=? LIMIT 1",
            (_cle, _carte, date.today().isoformat())).fetchone() else 0
    except Exception as e:
        logger.warning(f"carte_deja_vue : {e!r}")
        return 0


def dizaine_visiteur_pointee(jrnais):
    """1 si un VISITEUR de ce jour de naissance a déjà compté sa dizaine
    aujourd'hui (v7.9.20) — pour retrouver « ✅ Merci Sainte Mère … » après
    un rechargement, sans jamais compter deux fois le même passage."""
    try:
        _j = int(jrnais)
    except (TypeError, ValueError):
        return 0
    try:
        _assurer_dizaines_journal()
        return 1 if c.execute(
            """SELECT 1 FROM dizaines_journal
               WHERE type='visiteur' AND jrnais=? AND jour=? LIMIT 1""",
            (_j, date.today().isoformat())).fetchone() else 0
    except Exception as e:
        logger.warning(f"dizaine_visiteur_pointee : {e!r}")
        return 0


# ====================================================================
# v7.10.0 — LA RÉCUPÉRATION DES DIZAINES PRIÉES HORS LIGNE
# L'application de méditation du quotidien (hors internet) confie au
# Gestionnaire la mémoire des jours priés : chaque jour retrouvé dans le
# fichier rejoint le journal des dizaines, comme si le fidèle avait
# cliqué « ✕ Terminer » ce jour-là. La récupération est IDEMPOTENTE —
# repasser le même fichier n'ajoute jamais deux fois la même journée
# (membre : UNIQUE(matloc, jour) ; visiteur : contrôle (jrnais, jour)).
# Les journées à venir ne sont jamais acceptées (on ne prie pas
# demain), et une récupération ne dépasse jamais MAX_IMPORT jours.
# ====================================================================

MAX_IMPORT_DIZAINES = 400


def importer_dizaines_hors_ligne(matloc=None, nom=None, jrnais=None,
                                 equipe_id=None, paroisse_id=None,
                                 est_membre=True, jours=None):
    """Reçoit la liste des jours priés hors ligne (ISO AAAA-MM-JJ) et les
    note dans le journal des dizaines. Retourne (ajoutés, déjà comptés,
    ignorés). Silencieuse sur les lignes incompréhensibles : seuls les
    jours véritables entrent."""
    _ajoutes, _deja, _ignores = 0, 0, 0
    try:
        _assurer_dizaines_journal()
    except Exception as e:
        logger.warning(f"importer_dizaines_hors_ligne : {e!r}")
        return (0, 0, 0)
    _auj = date.today().isoformat()
    _propres, _vus = [], set()
    for j in (jours or []):
        _j = str(j or "").strip()
        if not _j or _j in _vus:
            continue
        _vus.add(_j)
        # ni le futur, ni ce qui n'est pas une date honnête
        try:
            _d = date.fromisoformat(_j)
        except ValueError:
            _ignores += 1
            continue
        if _j > _auj:
            _ignores += 1
            continue
        _propres.append(_j)
    if len(_propres) > MAX_IMPORT_DIZAINES:
        _ignores += len(_propres) - MAX_IMPORT_DIZAINES
        _propres = _propres[:MAX_IMPORT_DIZAINES]
    try:
        if est_membre:
            _mat = str(matloc or "").strip().upper()
            if not _mat:
                return (0, 0, len(_propres) + _ignores)
            _la = c.execute(
                "SELECT jour FROM dizaines_journal WHERE matloc=?",
                (_mat,)).fetchall()
            _la = {str(r[0]) for r in _la}
            for _j in _propres:
                if _j in _la:
                    _deja += 1
                    continue
                c.execute("""INSERT INTO dizaines_journal
                             (matloc, nom, type, jrnais, equipe_id,
                              paroisse_id, jour, heure)
                             VALUES (?, ?, 'membre', NULL, ?, ?, ?, ?)""",
                          (_mat, nom or None, equipe_id, paroisse_id, _j,
                           datetime.now().strftime("%H:%M")))
                _la.add(_j)
                _ajoutes += 1
        else:
            try:
                _jrn = int(jrnais)
            except (TypeError, ValueError):
                return (0, 0, len(_propres) + _ignores)
            for _j in _propres:
                _pris = c.execute(
                    """SELECT 1 FROM dizaines_journal
                       WHERE type='visiteur' AND jrnais=? AND jour=?
                       LIMIT 1""", (_jrn, _j)).fetchone()
                if _pris:
                    _deja += 1
                    continue
                c.execute("""INSERT INTO dizaines_journal
                             (matloc, nom, type, jrnais, equipe_id,
                              paroisse_id, jour, heure)
                             VALUES (NULL, NULL, 'visiteur', ?, ?, ?, ?, ?)""",
                          (_jrn, equipe_id, paroisse_id, _j,
                           datetime.now().strftime("%H:%M")))
                _ajoutes += 1
        if _ajoutes:
            commit_and_sync()
        return (_ajoutes, _deja, _ignores)
    except Exception as e:
        logger.warning(f"importer_dizaines_hors_ligne : {e!r}")
        return (0, _deja, _ignores)


# ====================================================================
# v7.10.0 — LE QUESTIONNAIRE DU FEUILLET MENSUEL
# Chaque mois, la cellule Communication reprend les questions et les
# exercices du feuillet reçu, et les propose en questionnaire aux
# MEMBRES comme aux VISITEURS (page 🕯️ Thème → Vue d'ensemble, sous le
# feuillet). Un membre répond sous son MatLoc (il retrouve et peut
# corriger ses réponses) ; un visiteur signe du nom qu'il choisit.
# Répondre à nouveau remplace les réponses précédentes du même lecteur
# — jamais celles des autres.
# ====================================================================

TYPES_REPONSE = {"texte": "✍️ Texte libre", "oui_non": "🔘 Oui ou Non",
                 "choix": "🔠 Choix proposés"}


def _assurer_tables_questionnaire():
    """Création douce des deux tables du questionnaire (bases distantes
    anciennes créées avant la v7.10.0).
    v7.10.1 — le contrôle ne se pose qu'UNE FOIS par processus."""
    if _table_reconnue("feuillet_questions"):
        return True
    _ok = True
    for _t in ("feuillet_questions", "feuillet_reponses"):
        try:
            c.execute(f"SELECT 1 FROM {_t} LIMIT 1")
        except Exception:
            try:
                c.execute("""CREATE TABLE IF NOT EXISTS feuillet_questions (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                annee_debut INTEGER NOT NULL,
                                mois INTEGER NOT NULL,
                                ordre INTEGER,
                                question TEXT NOT NULL,
                                type_reponse TEXT DEFAULT 'texte',
                                choix TEXT,
                                obligatoire INTEGER DEFAULT 0,
                                active INTEGER DEFAULT 1)""")
                c.execute("""CREATE TABLE IF NOT EXISTS feuillet_reponses (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                question_id INTEGER NOT NULL,
                                annee_debut INTEGER NOT NULL,
                                mois INTEGER NOT NULL,
                                cle TEXT NOT NULL,
                                qui_nom TEXT,
                                qui_type TEXT DEFAULT 'visiteur',
                                reponse TEXT,
                                equipe_id INTEGER,
                                paroisse_id INTEGER,
                                date_reponse TEXT)""")
                commit_and_sync()
            except Exception as e:
                logger.warning(f"_assurer_tables_questionnaire : {e!r}")
                _ok = False
    if _ok:
        _table_averee("feuillet_questions")
    return _ok


def feuillet_questions_lister(annee_debut, mois, actives_seules=True):
    """[(id, ordre, question, type_reponse, choix, obligatoire, active)]
    du mois pastoral demandé, dans l'ordre composé."""
    try:
        _assurer_tables_questionnaire()
        _ph = " AND active=1" if actives_seules else ""
        return c.execute(
            f"""SELECT id, ordre, question, type_reponse, choix,
                       obligatoire, active
                FROM feuillet_questions
                WHERE annee_debut=? AND mois=?{_ph}
                ORDER BY COALESCE(ordre, 9999), id""",
            (int(annee_debut), int(mois))).fetchall()
    except Exception as e:
        logger.warning(f"feuillet_questions_lister : {e!r}")
        return []


def feuillet_questionnaire_existe(annee_debut, mois):
    """1 si le mois pastoral porte au moins UNE question active."""
    return 1 if feuillet_questions_lister(annee_debut, mois, True) else 0


# ─────────────────────────────────────────────────────────────────────────────
# v7.10.2 — LE QUESTIONNAIRE SOUMIS AU DIOCÈSE
# « Le questionnaire du feuillet, n'est-il pas soumis au diocèse ? » —
# Si, désormais. Comme le feuillet lui-même (v7.8.6) : le Service
# Communication prépare les questions, puis « 📨 Soumettre le questionnaire
# au diocèse » ; le diocèse SEUL valide (« ✅ Publier » au SAS), et rien ne
# parvient aux fidèles avant. La validation du mois = une soumission
# type_contenu='questionnaire' passée à statut='publie' (convention :
# date_evenement = année pastorale, lieu = mois pastoral, comme le feuillet).
# ─────────────────────────────────────────────────────────────────────────────

def feuillet_questionnaire_soumission(annee_debut, mois):
    """La DERNIÈRE soumission du questionnaire pour ce mois pastoral :
    (id, statut, motif_refus, date_soumission, date_decision, date_publication_prevue)
    ou None si le questionnaire n'a jamais été soumis."""
    try:
        return c.execute("""SELECT id, statut, motif_refus, date_soumission,
                                   date_decision, date_publication_prevue
                            FROM soumissions_comm
                            WHERE type_contenu='questionnaire'
                              AND date_evenement=? AND lieu=?
                            ORDER BY id DESC LIMIT 1""",
                         (str(int(annee_debut)), str(int(mois)))).fetchone()
    except Exception as e:
        logger.warning(f"feuillet_questionnaire_soumission : {e!r}")
        return None


def feuillet_questionnaire_publie(annee_debut, mois):
    """1 si le diocèse a VALIDÉ le questionnaire de ce mois pastoral (au
    moins une soumission 'questionnaire' du mois passée à 'publie'). C'est
    le voile côté fidèles : tant qu'il n'est pas levé, le questionnaire ne
    paraît pas dans l'Espace de Prière."""
    try:
        return bool(c.execute("""SELECT 1 FROM soumissions_comm
                                 WHERE type_contenu='questionnaire'
                                   AND date_evenement=? AND lieu=?
                                   AND statut='publie'
                                 ORDER BY id DESC LIMIT 1""",
                              (str(int(annee_debut)),
                               str(int(mois)))).fetchone())
    except Exception as e:
        logger.warning(f"feuillet_questionnaire_publie : {e!r}")
        return False


def feuillet_questionnaire_soumettre(annee_debut, mois, resume, auteur_id=None,
                                     version_corrigee=False):
    """Soumet le questionnaire du mois au diocèse (v7.10.2) : une ligne
    type_contenu='questionnaire', statut='attente', avec un résumé lisible
    des questions en contenu_texte. Retourne (ok, message prêt à afficher)."""
    _mois_noms = ["Septembre", "Octobre", "Novembre", "Décembre", "Janvier",
                  "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août"]
    _m = int(mois) if 1 <= int(mois) <= 12 else 1
    _titre = (f"Questionnaire du feuillet N°{_m} — {_mois_noms[_m - 1]} "
              f"{int(annee_debut)}")
    if version_corrigee:
        _titre += " (version corrigée)"
    try:
        _assurer_tables_questionnaire()
        c.execute("""INSERT INTO soumissions_comm
                     (auteur_id, type_contenu, titre, contenu_texte,
                      image_url, fichier_url, video_url, date_evenement,
                      lieu, statut, date_soumission, paroisse_cible)
                     VALUES (?, 'questionnaire', ?, ?, NULL, NULL, NULL,
                             ?, ?, 'attente', ?, NULL)""",
                  (auteur_id, _titre, str(resume or ""),
                   str(int(annee_debut)), str(int(mois)),
                   date.today().isoformat()))
        commit_and_sync()
        return (True, "Questionnaire soumis au diocèse. ✅ Rien ne sera montré "
                      "aux fidèles sans sa validation — la soumission apparaît "
                      "dans « 🟡 En attente de validation » côté diocèse.")
    except Exception as e:
        logger.warning(f"feuillet_questionnaire_soumettre : {e!r}")
        return (False, "La soumission n'a pas pu être notée — réessaie.")


def feuillet_question_ajouter(annee_debut, mois, question,
                              type_reponse="texte", choix=None,
                              obligatoire=0):
    """Ajoute une question en fin de liste. Retourne son id (ou None)."""
    _q = str(question or "").strip()
    if not _q:
        return None
    try:
        _assurer_tables_questionnaire()
        _n = c.execute("""SELECT COUNT(*) FROM feuillet_questions
                          WHERE annee_debut=? AND mois=?""",
                       (int(annee_debut), int(mois))).fetchone()[0]
        _t = type_reponse if type_reponse in TYPES_REPONSE else "texte"
        _ch = str(choix or "").strip() if _t == "choix" else None
        if _t == "choix" and not _ch:
            _t, _ch = "texte", None
        c.execute("""INSERT INTO feuillet_questions
                     (annee_debut, mois, ordre, question, type_reponse,
                      choix, obligatoire, active)
                     VALUES (?, ?, ?, ?, ?, ?, ?, 1)""",
                  (int(annee_debut), int(mois), _n + 1, _q, _t, _ch,
                   1 if obligatoire else 0))
        commit_and_sync()
        return c.execute("""SELECT id FROM feuillet_questions
                            WHERE annee_debut=? AND mois=? AND question=?
                            ORDER BY id DESC LIMIT 1""",
                         (int(annee_debut), int(mois), _q)).fetchone()[0]
    except Exception as e:
        logger.warning(f"feuillet_question_ajouter : {e!r}")
        return None


def feuillet_question_modifier(id_question, question=None, type_reponse=None,
                               choix=None, obligatoire=None, active=None):
    """Modifie ce qui est fourni ; le reste demeure. Retourne True si écrit."""
    try:
        _assurer_tables_questionnaire()
        _row = c.execute("""SELECT annee_debut, mois, question, type_reponse,
                            choix, obligatoire, active FROM feuillet_questions
                            WHERE id=?""", (int(id_question),)).fetchone()
        if not _row:
            return False
        _q = str(question).strip() if question is not None else _row[2]
        if not _q:
            return False
        _t = type_reponse if type_reponse in TYPES_REPONSE else _row[3]
        _ch = str(choix).strip() if choix is not None else _row[4]
        if _t == "choix" and not _ch:
            _t = "texte"
        if _t != "choix":
            _ch = None
        _ob = _row[5] if obligatoire is None else (1 if obligatoire else 0)
        _ac = _row[6] if active is None else (1 if active else 0)
        c.execute("""UPDATE feuillet_questions
                     SET question=?, type_reponse=?, choix=?, obligatoire=?,
                         active=? WHERE id=?""",
                  (_q, _t, _ch, _ob, _ac, int(id_question)))
        commit_and_sync()
        return True
    except Exception as e:
        logger.warning(f"feuillet_question_modifier : {e!r}")
        return False


def feuillet_question_supprimer(id_question):
    """Retire la question ET les réponses qu'elle avait recueillies."""
    try:
        _assurer_tables_questionnaire()
        c.execute("DELETE FROM feuillet_reponses WHERE question_id=?",
                  (int(id_question),))
        c.execute("DELETE FROM feuillet_questions WHERE id=?",
                  (int(id_question),))
        commit_and_sync()
        return True
    except Exception as e:
        logger.warning(f"feuillet_question_supprimer : {e!r}")
        return False


def feuillet_question_deplacer(id_question, direction="haut"):
    """Échange la place de la question avec sa voisine (ordre composé)."""
    try:
        _assurer_tables_questionnaire()
        _row = c.execute("""SELECT id, annee_debut, mois, ordre
                            FROM feuillet_questions WHERE id=?""",
                         (int(id_question),)).fetchone()
        if not _row:
            return False
        _qid, _an, _mo, _or = _row
        _toutes = c.execute("""SELECT id, ordre FROM feuillet_questions
                               WHERE annee_debut=? AND mois=?
                               ORDER BY COALESCE(ordre, 9999), id""",
                            (_an, _mo)).fetchall()
        _idx = next((i for i, r in enumerate(_toutes) if r[0] == _qid), None)
        if _idx is None:
            return False
        _autre = _idx - 1 if direction == "haut" else _idx + 1
        if _autre < 0 or _autre >= len(_toutes):
            return False
        _id2 = _toutes[_autre][0]
        c.execute("UPDATE feuillet_questions SET ordre=? WHERE id=?",
                  (_idx + 1, _id2))
        c.execute("UPDATE feuillet_questions SET ordre=? WHERE id=?",
                  (_autre + 1, _qid))
        commit_and_sync()
        return True
    except Exception as e:
        logger.warning(f"feuillet_question_deplacer : {e!r}")
        return False


def feuillet_questions_detecter(annee_debut, mois):
    """🔎 Les lignes en forme de question ou d'exercice repérées DANS le
    feuillet du mois (sections déjà saisies) : [(question, titre_section)].
    Le texte reste la référence — la cellule garde la main sur ce qu'elle
    reprend vraiment."""
    try:
        rows = c.execute("""SELECT titre, contenu FROM feuillet_sections
                            WHERE annee_debut=? AND mois=?
                            ORDER BY ordre""",
                         (int(annee_debut), int(mois))).fetchall()
    except Exception as e:
        logger.warning(f"feuillet_questions_detecter : {e!r}")
        return []
    _trouvees, _vus = [], set()
    for _titre, _contenu in rows:
        for _l in (_contenu or "").split("\n"):
            _l = _l.strip().lstrip("*").lstrip("•").lstrip("-").strip()
            if len(_l) < 8 or len(_l) > 320 or "?" not in _l:
                continue
            # retire un éventuel numéro de liste en tête (« 1. », « 2) »…)
            _l = re.sub(r"^\s*\d{1,2}\s*[.)]\s*", "", _l).strip()
            if not _l or _l.lower() in _vus:
                continue
            _vus.add(_l.lower())
            _trouvees.append((_l, (_titre or "").strip()))
    return _trouvees


def feuillet_reponses_enregistrer(annee_debut, mois, reponses, cle,
                                  qui_nom=None, qui_type="visiteur",
                                  equipe_id=None, paroisse_id=None):
    """Reçoit {question_id: réponse} du lecteur (clé) — remplace SES
    réponses du mois (les siennes seulement) et note la date du jour.
    Retourne le nombre de réponses notées (0 si rien à écrire)."""
    _cle = str(cle or "").strip()
    _propres = {int(k): str(v or "").strip()
                for k, v in (reponses or {}).items()
                if str(v or "").strip()}
    if not _cle or not _propres:
        return 0
    try:
        _assurer_tables_questionnaire()
        _ids_valides = {r[0] for r in c.execute(
            """SELECT id FROM feuillet_questions
               WHERE annee_debut=? AND mois=?""",
            (int(annee_debut), int(mois))).fetchall()}
        _propres = {k: v for k, v in _propres.items() if k in _ids_valides}
        if not _propres:
            return 0
        c.execute("""DELETE FROM feuillet_reponses
                     WHERE cle=? AND annee_debut=? AND mois=?""",
                  (_cle, int(annee_debut), int(mois)))
        _auj = date.today().isoformat()
        for _qid, _rep in _propres.items():
            c.execute("""INSERT INTO feuillet_reponses
                         (question_id, annee_debut, mois, cle, qui_nom,
                          qui_type, reponse, equipe_id, paroisse_id,
                          date_reponse)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                      (_qid, int(annee_debut), int(mois), _cle,
                       (qui_nom or None), (qui_type or "visiteur"), _rep,
                       equipe_id, paroisse_id, _auj))
        commit_and_sync()
        return len(_propres)
    except Exception as e:
        logger.warning(f"feuillet_reponses_enregistrer : {e!r}")
        return 0


def feuillet_reponses_de_cle(annee_debut, mois, cle):
    """{question_id: réponse} du lecteur (clé) pour CE mois — pour
    retrouver ses réponses et lui laisser la main de les corriger."""
    _cle = str(cle or "").strip()
    if not _cle:
        return {}
    try:
        _assurer_tables_questionnaire()
        return {r[0]: r[1] for r in c.execute(
            """SELECT question_id, reponse FROM feuillet_reponses
               WHERE cle=? AND annee_debut=? AND mois=?""",
            (_cle, int(annee_debut), int(mois))).fetchall()}
    except Exception as e:
        logger.warning(f"feuillet_reponses_de_cle : {e!r}")
        return {}


def feuillet_reponses_resume(annee_debut, mois):
    """Pour la lecture des réponses reçues : [(id, ordre, question,
    type_reponse, choix, [(qui_nom, qui_type, reponse, date)])], question
    par question, dans l'ordre composé (questions actives ET retirées qui
    avaient reçu des réponses)."""
    try:
        _assurer_tables_questionnaire()
        _qs = c.execute("""SELECT id, ordre, question, type_reponse, choix
                           FROM feuillet_questions
                           WHERE annee_debut=? AND mois=?""",
                        (int(annee_debut), int(mois))).fetchall()
        _noms = {r[0]: (r[1] or "") for r in c.execute(
            """SELECT id, titre FROM feuillet_sections
               WHERE annee_debut=? AND mois=?""",
            (int(annee_debut), int(mois))).fetchall()}
        _out = []
        for _q in _qs:
            _reps = [(r[0], r[1], r[2], r[3]) for r in c.execute(
                """SELECT qui_nom, qui_type, reponse, date_reponse
                   FROM feuillet_reponses WHERE question_id=?
                   ORDER BY date_reponse ASC, id ASC""",
                (_q[0],)).fetchall()]
            _out.append((_q[0], _q[1], _q[2], _q[3], _q[4], _reps))
        # questions retirées mais qui avaient reçu des réponses : la
        # mémoire des fidèles ne disparaît pas de la lecture
        _ids_vus = {q[0] for q in _out}
        _orph = [(r[0],) for r in c.execute(
            """SELECT DISTINCT question_id FROM feuillet_reponses
               WHERE annee_debut=? AND mois=?""",
            (int(annee_debut), int(mois))).fetchall() if r[0] not in _ids_vus]
        for (_qid,) in _orph:
            _reps = [(r[0], r[1], r[2], r[3]) for r in c.execute(
                """SELECT qui_nom, qui_type, reponse, date_reponse
                   FROM feuillet_reponses WHERE question_id=?
                   ORDER BY date_reponse ASC, id ASC""",
                (_qid,)).fetchall()]
            if _reps:
                _out.append((_qid, 9999, "(question retirée du mois)",
                             "texte", None, _reps))
        return sorted(_out, key=lambda q: (q[1] if q[1] is not None else 9999,
                                           q[0]))
    except Exception as e:
        logger.warning(f"feuillet_reponses_resume : {e!r}")
        return []


# ====================================================================
# v7.10.0 — L'ENVOI EN MISSION
# Le responsable d'équipe prépare une mission : titre, objectif, date,
# lieu et la liste des personnes envoyées (de l'équipe ou venues
# d'ailleurs). Le Gestionnaire en tire la FICHE D'ENVOI EN MISSION
# imprimable ; après la mission, la FICHE DE RAPPORT DE MISSION recueille
# le retour (déroulement, grâces, difficultés, propositions).
# ====================================================================

def mission_creer(equipe_id, paroisse_id, titre, objectif,
                  date_mission=None, lieu=None, participants=None,
                  auteur_nom=None, date_debut=None, date_fin=None,
                  groupe=None):
    """Ouvre une mission. `participants` = liste de dicts
    {nom, matloc, contact, externe}. v7.11.1 — la mission se déroule sur
    UNE PÉRIODE : `date_debut` (le lendemain de la dernière séance de
    prière mensuelle) jusqu'à `date_fin` (vide = « jusqu'à la prochaine
    séance »), et `groupe` (A…Z) porte le groupe envoyé quand l'équipe se
    scinde. `date_mission` reste alimenté avec le début pour les anciens
    affichages. Retourne l'id (ou None)."""
    _t = str(titre or "").strip()
    if not _t or not equipe_id:
        return None
    _deb = str(date_debut or date_mission or "").strip() or None
    _fin = str(date_fin or "").strip() or None
    _grp = str(groupe or "").strip().upper()[:1] or "A"
    if not ("A" <= _grp <= "Z"):
        _grp = "A"
    try:
        c.execute("""INSERT INTO missions
                     (equipe_id, paroisse_id, titre, objectif, date_mission,
                      lieu, participants, statut, date_envoi, auteur_nom,
                      date_debut, date_fin, groupe)
                     VALUES (?, ?, ?, ?, ?, ?, ?, 'envoi', ?, ?, ?, ?, ?)""",
                  (int(equipe_id),
                   int(paroisse_id) if paroisse_id else None,
                   _t, (str(objectif).strip() or None),
                   _deb,
                   (str(lieu).strip() or None),
                   json.dumps(participants or [], ensure_ascii=False),
                   date.today().isoformat(),
                   (str(auteur_nom).strip() or None),
                   _deb, _fin, _grp))
        commit_and_sync()
        return c.execute("""SELECT id FROM missions WHERE equipe_id=?
                            ORDER BY id DESC LIMIT 1""",
                         (int(equipe_id),)).fetchone()[0]
    except Exception as e:
        logger.warning(f"mission_creer : {e!r}")
        return None


def missions_equipe(equipe_id, tous=False):
    """[(id, titre, objectif, date_mission, lieu, participants_json,
    statut, date_envoi, auteur_nom, rapport_json, date_rapport,
    date_debut, date_fin, groupe)] de l'équipe, la plus récente d'abord.
    v7.11.1 — la période (date_debut → date_fin, vide = « jusqu'à la
    prochaine séance ») et le groupe (A…Z) voyagent avec la mission.
    tous=False : missions non retirées."""
    try:
        _ph = "" if tous else " AND statut != 'retiree'"
        return c.execute(
            f"""SELECT id, titre, objectif, date_mission, lieu, participants,
                       statut, date_envoi, auteur_nom, rapport, date_rapport,
                       date_debut, date_fin, groupe
                FROM missions WHERE equipe_id=?{_ph}
                ORDER BY id DESC""", (int(equipe_id),)).fetchall()
    except Exception as e:
        logger.warning(f"missions_equipe : {e!r}")
        return []


def mission_prochaine_seance(equipe_id, apres):
    """v7.11.1 — la première séance de prière enregistrée APRÈS le jour
    `apres` (chaîne de séance = la séance mensuelle de l'équipe). C'est
    elle qui referme la période d'une mission laissée « jusqu'à la
    prochaine séance » : dès que la séance suivante est enregistrée, la
    mission connaît sa fin. Retourne la date (str ISO) ou None."""
    if not apres:
        return None
    try:
        _assurer_table_chaine_seances()
        _r = c.execute("""SELECT MIN(date_seance) FROM chaine_seances
                          WHERE equipe_id=? AND date_seance > ?""",
                       (int(equipe_id), str(apres))).fetchone()
        return _r[0] if _r and _r[0] else None
    except Exception as e:
        logger.warning(f"mission_prochaine_seance : {e!r}")
        return None


def mission_rapport_enregistrer(id_mission, rapport):
    """Range le retour de mission (dict → JSON) et passe la mission à
    « rapportee ». Retourne True si écrit."""
    try:
        c.execute("""UPDATE missions SET rapport=?, statut='rapportee',
                     date_rapport=? WHERE id=?""",
                  (json.dumps(rapport or {}, ensure_ascii=False),
                   date.today().isoformat(), int(id_mission)))
        commit_and_sync()
        return True
    except Exception as e:
        logger.warning(f"mission_rapport_enregistrer : {e!r}")
        return False


def mission_supprimer(id_mission):
    """Retire définitivement une mission (essai erroné)."""
    try:
        c.execute("DELETE FROM missions WHERE id=?", (int(id_mission),))
        commit_and_sync()
        return True
    except Exception as e:
        logger.warning(f"mission_supprimer : {e!r}")
        return False


# ======================================================================
# v7.12.0 — LA CHAÎNE ALERTE SUR LES TÉLÉPHONES
# ======================================================================
# « La mise à jour de la liste de ceux qui n'ont pas encore fait leur
# dizaine et le rappel se feront 4 fois dans la journée : 06h00 - 12h00 -
# 18h00 - 21h00. » Et : « tout visiteur ayant déposé une intention sera
# identifié individuellement comme les membres (les anonymes → Anonyme 1,
# Anonyme 2, Anonyme 3, … selon l'index du dénombrement). »
# Trois pièces s'ajoutent au cœur :
#   ① LE DÉNOMBREMENT des visiteurs de la chaîne — chaque fidèle porteur
#      d'une intention vivante (zone du jour non traitée + réserve active
#      et publiée) reçoit son rang d'entrée dans la chaîne : les anonymes
#      s'appellent Anonyme 1, Anonyme 2, Anonyme 3… ; les signés gardent
#      leur nom. Le contact laissé à l'envoi (WhatsApp / e-mail) voyage
#      avec l'intention (colonne auteur_contact, rétro-remplie) ;
#   ② LES RONDES — 4 fois par jour, la liste des dizaines en attente est
#      mise à jour et le rappel part (table dizaines_rondes, une ronde
#      servie une seule fois quel que soit le nombre de sessions) ;
#   ③ LES ABONNEMENTS PUSH — le téléphone qui a accepté les notifications
#      est connu (push_abonnements) ; les clés VAPID naissent et vivent
#      en base (parametres_app), aucune configuration à faire.
# ----------------------------------------------------------------------

_CONTACT_RESERVE_FAIT_LE = None


def _retroremplir_contact_reserve():
    """v7.12.0 — les intentions déjà en réserve (nées avant la colonne
    auteur_contact) retrouvent le contact laissé par leur fidèle dans la
    zone du jour (le plus récent du même jour de naissance). Une seule
    passe par processus, silencieuse."""
    global _CONTACT_RESERVE_FAIT_LE
    _auj = date.today().isoformat()
    if _CONTACT_RESERVE_FAIT_LE == _auj:
        return
    try:
        c.execute("""UPDATE intentions_reserve SET auteur_contact = (
                        SELECT z.auteur_contact FROM intentions_du_jour z
                        WHERE z.jour_naissance = intentions_reserve.jour_naissance
                          AND z.auteur_contact IS NOT NULL
                        ORDER BY z.id DESC LIMIT 1)
                     WHERE auteur_contact IS NULL AND jour_naissance IS NOT NULL""")
        commit_and_sync()
        _CONTACT_RESERVE_FAIT_LE = _auj
    except Exception as e:
        logger.warning(f"_retroremplir_contact_reserve : {e!r}")


def denombrement_visiteurs_chaine(equipe_id=None, paroisse_id=None):
    """📿 LE DÉNOMBREMENT DE LA CHAÎNE (v7.12.0) — tous les visiteurs qui
    portent actuellement une intention vivante (zone du jour non traitée +
    réserve active et publiée), dans l'ordre où leur intention est entrée
    dans la chaîne : le rang N est LEUR numéro (« Anonyme 1, Anonyme 2… »,
    stable d'un jour à l'autre ; les visiteurs signés gardent leur nom).
    Retourne [(n, jrnais, libellé, contact, source, id_ligne)] — un rang
    par JOUR DE NAISSANCE (la clé discrète de la chaîne ; si un même jour
    a confié plusieurs intentions, une seule ligne compte son rang).
    Scope : équipe OU paroisse (None = toute la chaîne)."""
    _assurer_table_reserve()
    _assurer_table_du_jour()
    _eq_scope, _par_scope = "", ""
    if equipe_id is not None:
        _eq_scope = " AND equipe_id=?"
        _par_scope = " AND equipe_id=?"
    elif paroisse_id is not None:
        _eq_scope = " AND paroisse_id=?"
        _par_scope = " AND paroisse_id=?"
    # DEUX branches (réserve + zone du jour) : la valeur du scope part DEUX fois
    _prm = []
    if equipe_id is not None:
        _prm = [int(equipe_id), int(equipe_id)]
    elif paroisse_id is not None:
        _prm = [int(paroisse_id), int(paroisse_id)]
    try:
        _brutes = c.execute(f"""
            SELECT 'R' AS src, id, auteur_nom, qui, jour_naissance,
                   auteur_contact, date_ajout AS d
            FROM intentions_reserve
            WHERE active=1
              AND (COALESCE(publiee,1)=1
                   OR (publiee=0 AND date_publication IS NOT NULL))
              AND jour_naissance IS NOT NULL{_eq_scope}
            UNION ALL
            SELECT 'Z' AS src, id, auteur_nom, NULL AS qui, jour_naissance,
                   auteur_contact, date_reception AS d
            FROM intentions_du_jour
            WHERE traitee=0 AND jour_naissance IS NOT NULL{_par_scope}
            ORDER BY d ASC, src ASC, id ASC""", tuple(_prm)).fetchall()
    except Exception as e:
        logger.warning(f"denombrement_visiteurs_chaine : {e!r}")
        return []
    _vus, _sortie = {}, []
    for (_src, _id, _nom, _qui, _jn, _ctc, _d) in _brutes:
        _jn = int(_jn) if _jn else 0
        if not _jn or _jn in _vus:
            continue          # un rang par jour de naissance (le plus ancien gagne)
        _vus[_jn] = True
        _n = len(_sortie) + 1
        _lib = (f"Anonyme {_n}" if (_nom is None or str(_qui or "") == "cet anonyme")
                else (str(_nom).strip() or f"Visiteur {_n}"))
        _sortie.append((_n, _jn, _lib,
                        (str(_ctc).strip() if _ctc else "") or "",
                        _src, _id))
    return _sortie


def dizaines_du_jour_attente(equipe_id=None, paroisse_id=None):
    """📿 LA LISTE DES DIZAINES EN ATTENTE (v7.12.0) — (membres, visiteurs)
    qui n'ont PAS encore fait leur dizaine aujourd'hui. Les membres sont
    les actifs de l'équipe (ou de la paroisse) ; les visiteurs sont les
    porteurs d'une intention vivante, identifiés par le dénombrement
    (Anonyme 1, Anonyme 2… — voir denombrement_visiteurs_chaine).
    membres   → [(nom, prénom, whatsapp, équipe, paroisse, matloc)]
    visiteurs → [(n, libellé, contact, jrnais)]"""
    _assurer_dizaines_journal()
    _jour = date.today().isoformat()
    _membres = []
    try:
        if equipe_id:
            _ph, _prm = "AND m.equipe_id=?", [int(equipe_id)]
        elif paroisse_id:
            _ph, _prm = "AND m.paroisse_id=?", [int(paroisse_id)]
        else:
            _ph, _prm = "", []
        _membres = c.execute(
            f"""SELECT m.nom, m.prenom, m.whatsapp,
                       COALESCE(e.nom_equipe, '—'), COALESCE(p.nom, '—'), m.matloc
                FROM membres m
                LEFT JOIN equipes e ON m.equipe_id=e.id
                LEFT JOIN paroisses p ON m.paroisse_id=p.id
                WHERE m.statut='actif' {_ph}
                  AND NOT EXISTS (
                      SELECT 1 FROM dizaines_journal d
                      WHERE d.type='membre' AND d.jour=?
                        AND UPPER(TRIM(d.matloc)) = UPPER(TRIM(m.matloc)))
                ORDER BY e.nom_equipe, m.nom, m.prenom""",
            (*_prm, _jour)).fetchall()
    except Exception as e:
        logger.warning(f"dizaines_du_jour_attente (membres) : {e!r}")
        _membres = []
    _visiteurs = []
    try:
        for (_n, _jn, _lib, _ctc, _src, _id) in denombrement_visiteurs_chaine(
                equipe_id, paroisse_id):
            _pointe = c.execute(
                """SELECT 1 FROM dizaines_journal
                   WHERE type='visiteur' AND jour=? AND jrnais=? LIMIT 1""",
                (_jour, _jn)).fetchone()
            if _pointe:
                continue
            _visiteurs.append((_n, _lib, _ctc, _jn))
    except Exception as e:
        logger.warning(f"dizaines_du_jour_attente (visiteurs) : {e!r}")
    return (_membres, _visiteurs)


# ── LES RONDES DE LA JOURNÉE (4 fois par jour) ──────────────────────────
HEURES_RONDES = ("06:00", "12:00", "18:00", "21:00")


def _assurer_dizaines_rondes():
    """Création douce de dizaines_rondes (bases distantes anciennes)."""
    if _table_reconnue("dizaines_rondes"):
        return
    try:
        c.execute("SELECT id FROM dizaines_rondes LIMIT 1")
    except Exception:
        c.execute("""CREATE TABLE IF NOT EXISTS dizaines_rondes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        jour TEXT NOT NULL,
                        heure_rappel TEXT NOT NULL,
                        servie_le TEXT,
                        nb_membres INTEGER DEFAULT 0,
                        nb_visiteurs INTEGER DEFAULT 0,
                        push_ok INTEGER DEFAULT 0,
                        push_ko INTEGER DEFAULT 0,
                        UNIQUE(jour, heure_rappel))""")
        commit_and_sync()
    _table_averee("dizaines_rondes")


def dizaines_ronde_reserver(jour, heure_rappel):
    """Réserve la ronde (jour, heure) pour CE processus : le INSERT
    n'aboutit qu'UNE fois quel que soit le nombre de sessions réveillées
    (la ligne existe déjà → 0 ligne insérée → ce n'est pas nous).
    True = c'est nous qui servons la ronde."""
    _assurer_dizaines_rondes()
    try:
        _cur = c.execute("""INSERT OR IGNORE INTO dizaines_rondes
                            (jour, heure_rappel) VALUES (?, ?)""",
                         (str(jour), str(heure_rappel)))
        commit_and_sync()
        return bool(getattr(_cur, "rowcount", 0))
    except Exception as e:
        logger.warning(f"dizaines_ronde_reserver : {e!r}")
        return False


def dizaines_ronde_completer(jour, heure_rappel, servie_le,
                             nb_membres=0, nb_visiteurs=0,
                             push_ok=0, push_ko=0):
    """Note le résultat de la ronde (comptages + pushes partis)."""
    _assurer_dizaines_rondes()
    try:
        c.execute("""UPDATE dizaines_rondes SET servie_le=?, nb_membres=?,
                     nb_visiteurs=?, push_ok=?, push_ko=?
                     WHERE jour=? AND heure_rappel=?""",
                  (str(servie_le), int(nb_membres), int(nb_visiteurs),
                   int(push_ok), int(push_ko), str(jour), str(heure_rappel)))
        commit_and_sync()
        return True
    except Exception as e:
        logger.warning(f"dizaines_ronde_completer : {e!r}")
        return False


def dizaines_ronde_derniere():
    """La dernière ronde servie [(jour, heure, servie_le, membres,
    visiteurs, push_ok, push_ko)], la plus récente d'abord (5 max)."""
    _assurer_dizaines_rondes()
    try:
        return c.execute("""SELECT jour, heure_rappel, servie_le, nb_membres,
                                   nb_visiteurs, push_ok, push_ko
                            FROM dizaines_rondes WHERE servie_le IS NOT NULL
                            ORDER BY jour DESC, heure_rappel DESC LIMIT 5"""
                         ).fetchall()
    except Exception as e:
        logger.warning(f"dizaines_ronde_derniere : {e!r}")
        return []


# ── LES ABONNEMENTS PUSH (le téléphone qui a dit oui) ───────────────────
def _assurer_push_abonnements():
    """Création douce de push_abonnements (bases distantes anciennes)."""
    if _table_reconnue("push_abonnements"):
        return
    try:
        c.execute("SELECT id FROM push_abonnements LIMIT 1")
    except Exception:
        c.execute("""CREATE TABLE IF NOT EXISTS push_abonnements (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        cle_lecteur TEXT,
                        matloc TEXT,
                        jrnais INTEGER,
                        endpoint TEXT UNIQUE,
                        p256dh TEXT,
                        auth TEXT,
                        cree_le TEXT)""")
        commit_and_sync()
    _table_averee("push_abonnements")


def push_abonnement_enregistrer(cle_lecteur, endpoint, p256dh, auth,
                                matloc=None, jrnais=None):
    """Note (ou rafraîchit) l'abonnement d'un téléphone. Un même lecteur ne
    garde qu'une seule ligne : l'ancienne s'efface quand le téléphone
    redit oui. Retourne True si écrit."""
    _assurer_push_abonnements()
    try:
        c.execute("DELETE FROM push_abonnements WHERE cle_lecteur=?",
                  (str(cle_lecteur or ""),))
        c.execute("""INSERT OR REPLACE INTO push_abonnements
                     (cle_lecteur, matloc, jrnais, endpoint, p256dh, auth, cree_le)
                     VALUES (?, ?, ?, ?, ?, ?, ?)""",
                  (str(cle_lecteur or ""),
                   (str(matloc).upper().strip() if matloc else None),
                   int(jrnais) if jrnais else None,
                   str(endpoint or ""), str(p256dh or ""), str(auth or ""),
                   datetime.now().isoformat(timespec="seconds")))
        commit_and_sync()
        return True
    except Exception as e:
        logger.warning(f"push_abonnement_enregistrer : {e!r}")
        return False


def push_abonnement_note_jrnais(cle_lecteur, jrnais):
    """Le visiteur a dévoilé son jour de naissance (dizaine ou intention) :
    l'abonnement de CE téléphone connaît désormais sa clé de chaîne — les
    rondes sauront s'il a déjà prié."""
    _assurer_push_abonnements()
    try:
        c.execute("""UPDATE push_abonnements SET jrnais=?
                     WHERE cle_lecteur=?""",
                  (int(jrnais), str(cle_lecteur or "")))
        commit_and_sync()
        return True
    except Exception as e:
        logger.warning(f"push_abonnement_note_jrnais : {e!r}")
        return False


def push_abonnements_actifs():
    """Tous les abonnements vivants [(id, cle_lecteur, matloc, jrnais,
    endpoint, p256dh, auth)]."""
    _assurer_push_abonnements()
    try:
        return c.execute("""SELECT id, cle_lecteur, matloc, jrnais, endpoint,
                                   p256dh, auth FROM push_abonnements
                            ORDER BY id""").fetchall()
    except Exception as e:
        logger.warning(f"push_abonnements_actifs : {e!r}")
        return []


def push_abonnement_supprimer(endpoint):
    """Retire un abonnement mort (le service d'envoi ne veut plus de lui)."""
    _assurer_push_abonnements()
    try:
        c.execute("DELETE FROM push_abonnements WHERE endpoint=?",
                  (str(endpoint or ""),))
        commit_and_sync()
        return True
    except Exception as e:
        logger.warning(f"push_abonnement_supprimer : {e!r}")
        return False


def push_abonnement_de_cle(cle_lecteur):
    """1 si CE téléphone (clé du lecteur) a déjà dit oui aux rappels."""
    _assurer_push_abonnements()
    try:
        return 1 if c.execute(
            "SELECT 1 FROM push_abonnements WHERE cle_lecteur=? LIMIT 1",
            (str(cle_lecteur or ""),)).fetchone() else 0
    except Exception as e:
        logger.warning(f"push_abonnement_de_cle : {e!r}")
        return 0


# ── LES PARAMÈTRES DE LA MAISON (les clés VAPID y naissent) ─────────────
def _assurer_parametres():
    """Création douce de parametres_app (bases distantes anciennes)."""
    if _table_reconnue("parametres_app"):
        return
    try:
        c.execute("SELECT cle FROM parametres_app LIMIT 1")
    except Exception:
        c.execute("""CREATE TABLE IF NOT EXISTS parametres_app (
                        cle TEXT PRIMARY KEY,
                        valeur TEXT)""")
        commit_and_sync()
    _table_averee("parametres_app")


def parametre_lire(cle):
    """Lit un paramètre de la maison (None s'il n'existe pas)."""
    _assurer_parametres()
    try:
        _r = c.execute("SELECT valeur FROM parametres_app WHERE cle=?",
                       (str(cle),)).fetchone()
        return _r[0] if _r else None
    except Exception as e:
        logger.warning(f"parametre_lire : {e!r}")
        return None


def parametre_ecrire(cle, valeur):
    """Écrit un paramètre de la maison (idempotent)."""
    _assurer_parametres()
    try:
        c.execute("""INSERT INTO parametres_app (cle, valeur) VALUES (?, ?)
                     ON CONFLICT(cle) DO UPDATE SET valeur=excluded.valeur""",
                  (str(cle), str(valeur)))
        commit_and_sync()
        return True
    except Exception as e:
        logger.warning(f"parametre_ecrire : {e!r}")
        return False
