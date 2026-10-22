import os
import hashlib
import secrets
import string
import io
import unicodedata
import urllib.parse
import logging
import requests
import pandas as pd
from datetime import date, datetime, time, timedelta
from PIL import Image
import streamlit as st

logger = logging.getLogger(__name__)

import database                       # module (référence conn toujours à jour)
from database import c, commit_and_sync

# ============================================================
# CONSTANTES GLOBALES (source unique)
# ============================================================
TYPES_EVENEMENTS = ["Prière mensuelle", "Prière commune", "Prière spéciale", "Pèlerinage", "Réunion", "Autre"]
URL_ESPACE_SPIRITUEL = "https://gestionnaireeqros-4s9fbumnsa6wmyy6dw4rft.streamlit.app"  # SANS "/" final

USE_CLOUDINARY = False
try:
    import cloudinary
    import cloudinary.uploader
    cloudinary.config(cloud_name=st.secrets.get("CLOUDINARY_CLOUD_NAME"),
                      api_key=st.secrets.get("CLOUDINARY_API_KEY"),
                      api_secret=st.secrets.get("CLOUDINARY_API_SECRET"), secure=True)
    if st.secrets.get("CLOUDINARY_CLOUD_NAME"):
        USE_CLOUDINARY = True
except Exception:
    pass


# ============================================================
# MESSAGES FLASH
# ============================================================
def afficher_messages_flash():
    msg_ok = st.session_state.pop("flash_success", None)
    if msg_ok:
        st.success(msg_ok)
    msg_warn = st.session_state.pop("flash_warning", None)
    if msg_warn:
        st.warning(msg_warn)


# ============================================================
# SÉCURITÉ & IDENTIFIANTS
# ============================================================
# TODO futur : pbkdf2_hmac + salt avec re-hash progressif au login.
def hash_password(p):
    """SHA-256 — compatibilité historique uniquement. Pour un NOUVEAU mot de passe,
    utilisez definir_mot_de_passe()."""
    return hashlib.sha256(p.encode()).hexdigest()

def definir_mot_de_passe(p):
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", p.encode(), bytes.fromhex(salt), 200_000)
    return f"pbkdf2${salt}${dk.hex()}"

def verifier_mot_de_passe(p, stocke):
    """Vérifie indifféremment un hachage PBKDF2 (v2) ou SHA-256 (ancien)."""
    if not stocke:
        return False
    if stocke.startswith("pbkdf2$"):
        try:
            _, salt, h = stocke.split("$", 2)
            dk = hashlib.pbkdf2_hmac("sha256", p.encode(), bytes.fromhex(salt), 200_000)
            return secrets.compare_digest(dk.hex(), h)
        except Exception:
            return False
    return secrets.compare_digest(hash_password(p), stocke)

def migrer_hash_si_legacy(user_id, stocke, mot_de_passe_en_clair):
    """Au login réussi d'un compte ancien (SHA-256) : re-hachage PBKDF2 transparent."""
    if stocke and not stocke.startswith("pbkdf2$"):
        try:
            c.execute("UPDATE utilisateurs SET password=? WHERE id=?",
                      (definir_mot_de_passe(mot_de_passe_en_clair), user_id))
            commit_and_sync()
        except Exception:
            pass

def generer_mot_de_passe(l=8):
    return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(l))

def generer_matricule_unique():
    while True:
        suffixe = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(5))
        mat = f"GBA-{suffixe}"
        if c.execute("SELECT COUNT(*) FROM membres WHERE matloc=?", (mat,)).fetchone()[0] == 0:
            return mat

def get_max_membres(equipe_id):
    """SOURCE UNIQUE (remplace les copies divergentes des vues).
    NB : la colonne equipes.max_membres (DEFAULT 10) ne correspond pas à la
    règle métier (12) — ne pas la lire sans interface de réglage."""
    res = c.execute("""SELECT p.nom, p.commune FROM equipes e
                       JOIN paroisses p ON e.paroisse_id = p.id WHERE e.id=?""",
                    (equipe_id,)).fetchone()
    if res:
        nom_paroisse = str(res[0] or '').lower()
        commune = str(res[1] or '').lower()
        if "notre dame" in nom_paroisse and "assomption" in nom_paroisse and "koumassi" in commune:
            return 20
    return 12


# ============================================================
# UTILITAIRES
# ============================================================
def safe_date(valeur):
    if not valeur:
        return None
    if isinstance(valeur, date):
        return valeur
    s = str(valeur).strip().split(' ')[0].split('T')[0]
    s = s.replace('-', '/').replace('\\', '/')
    try:
        parties = s.split('/')
        if len(parties) == 3:
            return date(int(parties[0]), int(parties[1]), int(parties[2]))
    except (ValueError, TypeError):
        pass
    return None

def periode_affichage(a): return f"Sept {a} – Août {a+1}"

def afficher_situation(s): return {"Déplacé": "a déménagé", "Radié": "indisponible", "Défunt": "est décédé(e)", "Transféré": "a été transféré(e)"}.get(s, s)

def sans_accents(t):
    return unicodedata.normalize('NFD', str(t).lower()).encode('ascii', 'ignore').decode('utf-8')

def lien_whatsapp(num, msg):
    if not num: return None
    num = ''.join(ch for ch in num if ch.isdigit() or ch == '+')
    if not num.startswith('+') and len(num) == 10: num = '225' + num
    msg = msg.replace('\\n', '\n')
    return f"https://wa.me/{num.lstrip('+')}?text={urllib.parse.quote(msg)}"

def envoyer_notification_telegram(message):
    """v7.6.6 — n'engloutit plus les échecs : journalise le motif (visible dans
    les logs Streamlit Cloud) et retourne True/False pour le bouton de test."""
    try:
        token, chat_id = st.secrets.get("TELEGRAM_BOT_TOKEN"), st.secrets.get("TELEGRAM_CHAT_ID")
        if not token or not chat_id:
            print("Telegram : secret TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID absent.")
            return False
        reponse = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                                json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"}, timeout=10)
        if reponse.status_code != 200:
            print(f"Telegram : échec HTTP {reponse.status_code} — {reponse.text[:200]}")
            return False
        return True
    except Exception as e:
        print(f"Telegram : exception — {e}")
        return False


# ============================================================
# MEDIAS (Cloudinary / local)
# ============================================================
def _public_id_unique(dossier, nom_fichier):
    """public_id lisible + suffixe unique : deux uploads du même nom de fichier
    ne s'écrasent plus jamais."""
    base = os.path.splitext(os.path.basename(nom_fichier))[0]
    base = ''.join(ch if ch.isalnum() or ch in '-_' else '_' for ch in base)[:60]
    return f"{dossier}/{base}_{secrets.token_hex(4)}"

def sauvegarder_photo(fichier, matricule):
    if not fichier:
        return None
    try:
        img = Image.open(fichier)
        img.load()
        if USE_CLOUDINARY:
            fichier.seek(0)  # rembobiner après PIL, sinon upload tronqué
            res = cloudinary.uploader.upload(fichier, public_id=f"rosaire_membres/{matricule}",
                                             overwrite=True,
                                             transformation=[{"width": 300, "height": 300, "crop": "fill"}])
            return res['secure_url']
        os.makedirs("photos", exist_ok=True)
        chemin = f"photos/{matricule}.jpg"
        if img.mode in ('RGBA', 'P', 'LA'):
            img = img.convert('RGB')
        img.thumbnail((300, 300))
        img.save(chemin, "JPEG", quality=60)
        return chemin
    except Exception as e:
        print(f"Erreur sauvegarde photo {matricule}: {e}")
        return None

def sauvegarder_pdf(fichier):
    if fichier and USE_CLOUDINARY:
        try:
            res = cloudinary.uploader.upload(fichier, resource_type="raw",
                                             public_id=_public_id_unique("rosaire_pdfs", fichier.name),
                                             overwrite=False)
            return res['secure_url']
        except Exception as e:
            print(f"Erreur upload PDF: {e}")
    return None

def sauvegarder_audio(fichier):
    if fichier and USE_CLOUDINARY:
        try:
            res = cloudinary.uploader.upload(fichier, resource_type="video",
                                             public_id=_public_id_unique("rosaire_audio", fichier.name),
                                             overwrite=False)
            return res['secure_url']
        except Exception as e:
            print(f"Erreur upload audio: {e}")
    return None

def sauvegarder_illustration(fichier):
    if fichier and USE_CLOUDINARY:
        try:
            res = cloudinary.uploader.upload(fichier,
                                             public_id=_public_id_unique("rosaire_illustrations", fichier.name),
                                             overwrite=False,
                                             transformation=[{"width": 800, "crop": "limit"}])
            return res['secure_url']
        except Exception as e:
            print(f"Erreur upload illustration: {e}")
    return None

def sauvegarder_video(fichier):
    """Vidéo (MP4/MOV) pour les bandes-annonces d'évènements."""
    if fichier and USE_CLOUDINARY:
        try:
            res = cloudinary.uploader.upload(fichier, resource_type="video",
                                             public_id=_public_id_unique("rosaire_videos", fichier.name),
                                             overwrite=False)
            return res['secure_url']
        except Exception as e:
            print(f"Erreur upload vidéo: {e}")
    return None

def supprimer_photo(path):
    if not path: return
    # COHABITATION : seules les URLs Cloudinary sont détruites chez Cloudinary ;
    # les liens externes (imgbb…) sont laissés intacts.
    if USE_CLOUDINARY and path.startswith("http") and "cloudinary" in path:
        try:
            import cloudinary.uploader
            parts = path.split('/upload/')[-1]
            if parts.startswith('v'): parts = '/'.join(parts.split('/')[1:])
            # Décoder l'URL ("pentecote%202026" -> "pentecote 2026"), sinon le
            # destroy échouait silencieusement sur les noms avec espaces
            public_id = os.path.splitext(urllib.parse.unquote(parts))[0]
            cloudinary.uploader.destroy(public_id)
        except Exception:
            pass
    elif not path.startswith("http") and os.path.exists(path):
        os.remove(path)


# ============================================================
# MÉTIER
# ============================================================
def archiver_membre(membre_id, situation, annee_debut, annee_fin, commentaire, auteur_id, auteur_nom, auteur_role, paroisse_id=None, equipe_id=None):
    if not equipe_id:
        res = c.execute("SELECT equipe_id FROM membres WHERE id=?", (membre_id,)).fetchone()
        equipe_id = res[0] if res and res[0] else None
    if not paroisse_id and equipe_id:
        res = c.execute("SELECT paroisse_id FROM equipes WHERE id=?", (equipe_id,)).fetchone()
        paroisse_id = res[0] if res and res[0] else None

    c.execute("UPDATE membres SET statut='archive' WHERE id=?", (membre_id,))
    # Convention unique : 1er septembre (cohérent année pastorale)
    c.execute('''INSERT INTO archives (membre_id, situation, date_debut, date_fin, commentaire, auteur_id, auteur_nom, auteur_role, paroisse_id, equipe_id)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
(membre_id, situation, date(annee_debut, 9, 1).isoformat(), date(annee_fin, 9, 1).isoformat(), commentaire, auteur_id, auteur_nom, auteur_role, paroisse_id, equipe_id))
    commit_and_sync()

def enregistrer_abonnement(membre_id, annee_debut, montant=0, type_abonnement='abonnement'):
    existant = c.execute("SELECT id FROM abonnements WHERE membre_id=? AND annee_debut=?", (membre_id, annee_debut)).fetchone()
    if existant:
        c.execute("UPDATE abonnements SET date_paiement=?, montant=?, type_abonnement=?, statut='paye' WHERE id=?",
                  (date.today().isoformat(), montant, type_abonnement, existant[0]))
    else:
        c.execute('''INSERT INTO abonnements (membre_id, annee_debut, date_paiement, montant, type_abonnement, statut) VALUES (?, ?, ?, ?, ?, ?)''',
                  (membre_id, annee_debut, date.today().isoformat(), montant, type_abonnement, 'paye'))
    commit_and_sync()

def verifier_abonnement(m, a):
    return c.execute("SELECT id FROM abonnements WHERE membre_id=? AND annee_debut=? AND statut='paye'", (m, a)).fetchone() is not None

def get_periode_pastorale():
    today = date.today()
    annee = today.year if today.month >= 9 else today.year - 1
    return annee, date(annee, 9, 1), date(annee + 1, 8, 31)

def est_cloture(entite_type, entite_id, annee_debut):
    return c.execute("SELECT id FROM periodes_cloturees WHERE entite_type=? AND entite_id=? AND annee_debut=?",
                     (entite_type, entite_id, annee_debut)).fetchone() is not None

def cloturer_periode(entite_type, entite_id, annee_debut, auteur_nom):
    if not est_cloture(entite_type, entite_id, annee_debut):
        c.execute("INSERT INTO periodes_cloturees (entite_type, entite_id, annee_debut, date_cloture, auteur_nom) VALUES (?, ?, ?, ?, ?)",
                  (entite_type, entite_id, annee_debut, date.today().isoformat(), auteur_nom))
        commit_and_sync()
        return True
    return False

# ============================================================
# SESSIONS PERSISTANTES (rester connecté malgré le refresh)
# ============================================================
DUREE_JOURS_TOKEN = 30

def creer_token_session(user_id, menu_initial=None):
    """Fabrique un jeton de session lié au compte (valide 30 jours),
    purge les jetons trop anciens, mémorise la rubrique de départ."""
    from datetime import timedelta
    token = secrets.token_hex(32)
    c.execute("INSERT INTO sessions_persistantes (token, user_id, date_creation, menu_courant) VALUES (?, ?, ?, ?)",
              (token, user_id, date.today().isoformat(), menu_initial))
    try:
        limite = (date.today() - timedelta(days=DUREE_JOURS_TOKEN)).isoformat()
        c.execute("DELETE FROM sessions_persistantes WHERE date_creation < ?", (limite,))
    except Exception:
        pass
    commit_and_sync()
    return token

def verifier_token_session(token):
    """Retourne (id, username, password, role, diocese_id, paroisse_id,
    equipe_id, menu_courant) si le jeton est valide, sinon None."""
    if not token:
        return None
    try:
        ligne = c.execute("""SELECT u.id, u.username, u.password, u.role, u.diocese_id,
                                    u.paroisse_id, u.equipe_id, s.date_creation, s.menu_courant
                             FROM sessions_persistantes s
                             JOIN utilisateurs u ON s.user_id = u.id
                             WHERE s.token=?""", (token,)).fetchone()
    except Exception:
        return None
    if not ligne:
        return None
    from datetime import timedelta
    d_creation = safe_date(ligne[7])
    if not d_creation or (date.today() - d_creation).days > DUREE_JOURS_TOKEN:
        try:
            c.execute("DELETE FROM sessions_persistantes WHERE token=?", (token,))
            commit_and_sync()
        except Exception:
            pass
        return None
    return (ligne[0], ligne[1], ligne[2], ligne[3], ligne[4], ligne[5], ligne[6], ligne[8])

def supprimer_token_session(token):
    """Révoque un jeton (appelé à la déconnexion)."""
    try:
        c.execute("DELETE FROM sessions_persistantes WHERE token=?", (token,))
        commit_and_sync()
    except Exception:
        pass

def synchroniser_menu_session(menu):
    """Mémorise la rubrique courante dans le jeton (s'il existe) — écrit en base
    UNIQUEMENT au changement de rubrique, pas à chaque affichage."""
    if not menu:
        return
    tok = st.query_params.get("t")
    if isinstance(tok, list):
        tok = tok[0] if tok else None
    if not tok:
        return
    if st.session_state.get("_menu_sync") == menu:
        return
    st.session_state["_menu_sync"] = menu
    try:
        c.execute("UPDATE sessions_persistantes SET menu_courant=? WHERE token=?", (menu, tok))
        commit_and_sync()
    except Exception:
        pass

def lire_menu_session():
    """Lit la rubrique mémorisée pour le jeton courant (None sinon)."""
    tok = st.query_params.get("t")
    if isinstance(tok, list):
        tok = tok[0] if tok else None
    if not tok:
        return None
    try:
        r = c.execute("SELECT menu_courant FROM sessions_persistantes WHERE token=?", (tok,)).fetchone()
        return r[0] if r and r[0] else None
    except Exception:
        return None

# v7.6.3 — trio de fonctions dupliqué supprimé (identique au premier bloc plus haut).
# ============================================================
# EXPORT EXCEL DIOCÈSE
# ============================================================
def exporter_excel_diocese():
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        queries = [
            ("Paroisses", "SELECT id, nom, commune, ville, responsable, bureau FROM paroisses"),
            ("Equipes", "SELECT e.id, e.nom_equipe, e.responsable, e.bureau, p.nom as paroisse FROM equipes e JOIN paroisses p ON e.paroisse_id = p.id"),
            ("Membres actifs", "SELECT m.matloc as MatLoc, m.matricule as Matricule, m.nom, m.prenom, m.date_naissance, m.whatsapp, m.date_adhesion, p.nom as paroisse, e.nom_equipe as equipe FROM membres m JOIN paroisses p ON m.paroisse_id = p.id JOIN equipes e ON m.equipe_id = e.id WHERE m.statut = 'actif' ORDER BY p.nom, e.nom_equipe"),
            ("Abonnements", "SELECT a.id, m.matloc as MatLoc, m.nom, m.prenom, a.annee_debut, a.date_paiement, a.montant, a.type_abonnement FROM abonnements a JOIN membres m ON a.membre_id = m.id ORDER BY a.annee_debut DESC"),
            ("Archives", "SELECT m.matloc as MatLoc, m.nom, m.prenom, a.situation, a.date_debut, a.date_fin, a.commentaire, p.nom as paroisse, e.nom_equipe as equipe FROM archives a JOIN membres m ON a.membre_id = m.id LEFT JOIN equipes e ON a.equipe_id = e.id LEFT JOIN paroisses p ON e.paroisse_id = p.id ORDER BY a.date_fin DESC")
        ]
        for sheet_name, query in queries:
            try:
                # FIX ROBUSTE : exécution via le curseur (c) au lieu de
                # pd.read_sql_query(database.conn). Le curseur gère déjà
                # reconnexion/retries, et fonctionne avec sqlite3 ET libsql —
                # pandas s'attendait à une connexion sqlite3/SQLAlchemy
                # standard et échouait de façon obscure sur Turso.
                rows = c.execute(query).fetchall()
                cols = [d[0] for d in c.description] if c.description else []
                df = pd.DataFrame(rows, columns=cols)
                if not df.empty:
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
            except Exception as e:
                print(f"Export '{sheet_name}' échoué: {e}")
    output.seek(0)
    return output

# ============================================================
# STATISTIQUES DE FRÉQUENTATION
# ============================================================
def compter_visite(page):
    """Enregistre une visite (une ligne par session ouverte).
    La table est créée au besoin ; aucun échec ne doit casser la page."""
    try:
        c.execute("""CREATE TABLE IF NOT EXISTS stats_visites (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        page TEXT, date_visite DATE)""")
        c.execute("INSERT INTO stats_visites (page, date_visite) VALUES (?, ?)",
                  (page, date.today().isoformat()))
        commit_and_sync()
    except Exception as e:
        print(f"Compteur de visites ({page}) : {e}")


def stats_visites_pivot(nb_jours=30):
    """Pivot date × page des visites des nb_jours derniers jours."""
    from datetime import timedelta
    debut = (date.today() - timedelta(days=nb_jours - 1)).isoformat()
    try:
        rows = c.execute("""SELECT date_visite, page, COUNT(*) FROM stats_visites
                            WHERE date_visite >= ?
                            GROUP BY date_visite, page
                            ORDER BY date_visite""", (debut,)).fetchall()
    except Exception:
        return pd.DataFrame()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["date", "page", "visites"])
    return df.pivot_table(index="date", columns="page", values="visites", aggfunc="sum").fillna(0)


# ============================================================
# PUBLICATIONS PROGRAMMÉES (v7.8.8, durci v7.9.2)
# Le diocèse valide en choisissant « publier maintenant » OU une date.
# Streamlit n'a pas de tâche de fond : chaque chargement de page sert
# de réveil (lazy cron) et publie ce qui est arrivé à échéance.
#
# v7.9.2 — après le signalement « des publications programmées publiées
# avant l'échéance », le réveil est BLINDÉ et DEVENU TRANSPARENT :
#   1. double protection temporelle — le filtre SQL string-safe ET un
#      re-parsing Python de date_publication_prevue (une ligne au format
#      inattendu est JAMAILS publiée, elle est journalisée et sautée) ;
#   2. réclamation anti-course — deux sessions ouvertes en même temps ne
#      peuvent plus publier chacune leur copie (l'UPDATE de réclamation
#      doit toucher EXACTEMENT 1 ligne) ;
#   3. auto-réparation — une réclamation bloquée par un crash est rendue
#      à la file après 10 minutes ;
#   4. traçabilité — date_decision + auteur_decision enregistrent QUI a
#      publié QUAND (clic diocèse ou automatisme), affichés dans
#      « 📔 Historique des décisions ».
# ============================================================
AUTEUR_DECISION_AUTO = "⏰ publication automatique — programmation respectée"
AUTEUR_DECISION_ECHEC = "⏰ publication automatique — ÉCHOUÉE (contenu incomplet ?) — à relire"


def _migrer_colonnes_programmation():
    """Colonnes de programmation + traçabilité (v7.9.2) sur soumissions_comm :
    date_publication_prevue (YYYY-MM-DD HH:MM), date_decision, auteur_decision.
    Chaque colonne est REVÉRIFIÉE après migration : si elle manque encore
    (verrou d'une transaction en cours, micro-coupure), c'est journalisé —
    le prochain réveil refera la tentative (idempotent)."""
    try:
        c.execute("SELECT date_publication_prevue FROM soumissions_comm LIMIT 1")
    except Exception:
        database.safe_migrate(
            "ALTER TABLE soumissions_comm ADD COLUMN date_publication_prevue TEXT")
    for _col in ("date_decision", "auteur_decision"):
        try:
            c.execute(f"SELECT {_col} FROM soumissions_comm LIMIT 1")
        except Exception:
            database.safe_migrate(f"ALTER TABLE soumissions_comm ADD COLUMN {_col} TEXT")
            try:
                c.execute(f"SELECT {_col} FROM soumissions_comm LIMIT 1")
            except Exception as e_verif:
                logger.warning(f"publications programmées : colonne {_col} toujours "
                               f"absente, nouvelle tentative au prochain réveil ({e_verif!r})")


def _lire_prevue(txt):
    """Re-parse robuste de date_publication_prevue (v7.9.2). Retourne un
    datetime, ou None si le format est inattendu — dans ce cas la ligne
    n'est JAMAIS publiée automatiquement (principe : ne rien diffuser
    qu'on ne sait pas dater)."""
    _t = str(txt or "").strip()
    for _fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M"):
        try:
            return datetime.strptime(_t, _fmt)
        except (ValueError, TypeError):
            continue
    return None


def publier_soumission(s):
    """Publie une soumission du Service Communication dans les tables
    publiques — FACTORISÉ (v7.8.8) pour servir AUSSI bien le clic du diocèse
    au SAS que le réveil des publications programmées.
    s = (id, type_contenu, titre, contenu_texte, image_url, fichier_url,
         video_url, date_evenement, lieu, date_soumission, paroisse_cible).
    Retourne True si publié, False si la publication est impossible
    (contenu incomplet : feuillet sans sections, année illisible…)."""
    _cible = s[10] if len(s) > 10 else None
    _auj = date.today().isoformat()
    try:
        if s[1] in ("priere", "meditation"):
            c.execute("""INSERT INTO espace_spirituel
                         (type_contenu, titre, contenu_texte, image_url,
                          fichier_url, date_publication, auteur_nom, paroisse_cible)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                      (s[1], s[2], s[3], s[4], s[5], _auj,
                       "Service Communication", _cible))
        elif s[1] == "audio":
            c.execute("""INSERT INTO espace_spirituel
                         (type_contenu, titre, fichier_url, date_publication,
                          auteur_nom, paroisse_cible) VALUES (?, ?, ?, ?, ?, ?)""",
                      ("audio", s[2], s[5], _auj, "Service Communication", _cible))
        elif s[1] == "annonce_defilante":
            cible_b = s[5] if s[5] in ("membre", "defaut") else None
            c.execute("""INSERT INTO espace_spirituel
                         (type_contenu, titre, contenu_texte, fichier_url,
                          date_publication, auteur_nom, paroisse_cible)
                         VALUES (?, ?, ?, ?, ?, ?, ?)""",
                      ("annonce_defilante", s[2] or "Bande défilante", s[3], cible_b,
                       _auj, "Service Communication", _cible))
        elif s[1] == "actualite":
            c.execute("""INSERT INTO espace_spirituel
                         (type_contenu, titre, contenu_texte, image_url, fichier_url,
                          date_publication, auteur_nom, paroisse_cible, date_evenement, lieu)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                      ("actualite", s[2], s[3], s[4], s[6], _auj,
                       "Service Communication", _cible, s[7], s[8]))
        elif s[1] == "theme_pastoral":
            try:
                _an = int(s[7]) if s[7] else None
            except (ValueError, TypeError):
                _an = None
            try:
                _mys = int(s[8]) if s[8] else 5
            except (ValueError, TypeError):
                _mys = 5
            if not _an:
                return False
            c.execute("UPDATE themes_pastoraux SET actif=0")
            _ex = c.execute("SELECT id FROM themes_pastoraux WHERE annee_debut=?", (_an,)).fetchone()
            if _ex:
                c.execute("""UPDATE themes_pastoraux
                             SET texte_theme=?, mystere_principal=?, actif=1,
                                 affiche_url=COALESCE(?, affiche_url) WHERE id=?""",
                          (s[3], _mys, s[4], _ex[0]))
            else:
                c.execute("""INSERT INTO themes_pastoraux
                             (annee_debut, texte_theme, mystere_principal, actif, affiche_url)
                             VALUES (?, ?, ?, 1, ?)""", (_an, s[3], _mys, s[4]))
        elif s[1] == "feuillet":
            # Convention v7.8.6 : date_evenement = année pastorale, lieu = mois
            try:
                _an_fp = int(s[7]) if s[7] else None
            except (ValueError, TypeError):
                _an_fp = None
            try:
                _mois_fp = int(s[8]) if s[8] else None
            except (ValueError, TypeError):
                _mois_fp = None
            if not _an_fp or not _mois_fp or not (1 <= _mois_fp <= 12):
                return False
            _n_secs = c.execute("""SELECT COUNT(*) FROM feuillet_sections
                                   WHERE annee_debut=? AND mois=?""",
                                (_an_fp, _mois_fp)).fetchone()[0]
            if _n_secs == 0:
                return False
            # v7.8.11 — UPDATE puis INSERT (au lieu d'ON CONFLICT) : robuste
            # même sur une base ancienne sans contrainte UNIQUE, et la date de
            # publication est TOUJOURS rafraîchie à chaque republication.
            _cur = c.execute("""UPDATE feuillets_publications
                                SET numero=?, date_publication=?
                                WHERE annee_debut=? AND mois=?""",
                          (_mois_fp, _auj, _an_fp, _mois_fp))
            if (_cur.rowcount or 0) == 0:
                c.execute("""INSERT INTO feuillets_publications
                             (annee_debut, mois, numero, date_publication)
                             VALUES (?, ?, ?, ?)""",
                          (_an_fp, _mois_fp, _mois_fp, _auj))
        elif s[1] == "evenement":  # ancien type, gardé pour l'historique
            c.execute("""INSERT INTO evenements
                         (type_evenement, date_evenement, lieu, affiche_url,
                          video_url, auteur_nom, paroisse_cible)
                         VALUES (?, ?, ?, ?, ?, ?, ?)""",
                      (s[2], s[7], s[8], s[4], s[6], "Service Communication", _cible))
        else:
            return False
        return True
    except Exception:
        return False


def executer_publications_programmees():
    """v7.8.8 — RÉVEIL : publie les soumissions « programme » dont l'heure
    prévue est atteinte (lazy cron — appelé au chargement de l'application).
    Durci v7.9.2 : réclamation anti-course (une seule session publie),
    re-vérification Python de l'échéance (aujourd'hui < date_publication_prevue
    → la ligne est laissée en place, JAMAIS publiée avant l'heure),
    auto-réparation des réclamations bloquées, traçabilité de la décision,
    et AUCUNE exception ne remonte vers la page qui l'appelle."""
    try:
        _migrer_colonnes_programmation()
        _maint_s = datetime.now().strftime("%Y-%m-%d %H:%M")
        # Auto-réparation : une réclamation datée de plus de 10 minutes
        # (crash entre la réclamation et la publication) retourne à la file.
        _limite = (datetime.now() - timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M")
        c.execute("""UPDATE soumissions_comm SET statut='programme'
                     WHERE statut='prog_auto_en_cours'
                       AND date_decision IS NOT NULL AND date_decision <= ?""",
                  (_limite,))
        rows = c.execute("""SELECT id, type_contenu, titre, contenu_texte, image_url,
                                   fichier_url, video_url, date_evenement, lieu,
                                   date_soumission, paroisse_cible, date_publication_prevue
                            FROM soumissions_comm
                            WHERE statut='programme'
                              AND date_publication_prevue IS NOT NULL
                              AND date_publication_prevue <= ?
                            ORDER BY date_publication_prevue ASC""",
                         (_maint_s,)).fetchall()
        # 2e verrou — re-parse Python : aucun format inattendu ne part.
        rows = [r for r in rows if _lire_prevue(r[11]) is not None]
        if not rows:
            return
    except Exception as e:
        logger.warning(f"publications programmées : balayage impossible ({e!r})")
        return
    _maint_s2 = datetime.now().strftime("%Y-%m-%d %H:%M")
    _n = 0
    for s in rows:
        try:
            # RÉCLAMATION anti-course : la mise à jour doit toucher
            # EXACTEMENT 1 ligne ; sinon une autre session l'a prise.
            _cur = c.execute("""UPDATE soumissions_comm
                                SET statut='prog_auto_en_cours', date_decision=?
                                WHERE id=? AND statut='programme'
                                  AND date_publication_prevue IS NOT NULL
                                  AND date_publication_prevue <= ?""",
                             (_maint_s2, s[0], _maint_s2))
            if (_cur.rowcount or 0) != 1:
                continue
            if publier_soumission(s):
                c.execute("""UPDATE soumissions_comm SET statut='publie',
                             auteur_decision=? WHERE id=?""",
                          (AUTEUR_DECISION_AUTO, s[0]))
                _n += 1
                try:
                    envoyer_notification_telegram(
                        "🗓️ <b>Diocèse</b> — publication programmée EFFECTUÉE à l'heure dite : "
                        + (s[2] or "(sans titre)"))
                except Exception:
                    pass
            else:
                # Échec technique (feuillet sans section, année illisible…) :
                # retour au SAS plutôt qu'un blocage invisible.
                c.execute("""UPDATE soumissions_comm SET statut='attente',
                             motif_refus='Publication programmée échouée (contenu incomplet ?) — à relire.',
                             date_publication_prevue=NULL, auteur_decision=? WHERE id=?""",
                          (AUTEUR_DECISION_ECHEC, s[0]))
        except Exception as e:
            # Une ligne en échec ne doit JAMAIS casser le balayage (ni la page).
            logger.warning(f"publications programmées : #{s[0]} — {e!r}")
    if _n:
        try:
            commit_and_sync()
        except Exception as e:
            logger.warning(f"publications programmées : commit ({e!r})")

