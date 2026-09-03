import os
import hashlib
import secrets
import string
import io
import unicodedata
import urllib.parse
import requests
import pandas as pd
from datetime import date
from PIL import Image
import streamlit as st

import database                       # FIX : module (référence conn toujours à jour)
from database import c, commit_and_sync

# ============================================================
# CONSTANTES GLOBALES (source unique — ne plus dupliquer dans les vues)
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
    """À appeler une fois par run (le pop est idempotent si appelé 2x).
    Pattern obligatoire : un st.success suivi de st.rerun() n'est JAMAIS rendu."""
    msg_ok = st.session_state.pop("flash_success", None)
    if msg_ok:
        st.success(msg_ok)
    msg_warn = st.session_state.pop("flash_warning", None)
    if msg_warn:
        st.warning(msg_warn)


# ============================================================
# SÉCURITÉ & IDENTIFIANTS
# ============================================================
# TODO futur : migrer vers pbkdf2_hmac + salt, avec re-hash progressif au login.
def hash_password(p): return hashlib.sha256(p.encode()).hexdigest()

def generer_mot_de_passe(l=8):
    # FIX : secrets (crypto-sûr) au lieu de random (prévisible)
    return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(l))

def generer_matricule_unique():
    while True:
        suffixe = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(5))
        mat = f"GBA-{suffixe}"
        if c.execute("SELECT COUNT(*) FROM membres WHERE matloc=?", (mat,)).fetchone()[0] == 0:
            return mat

def get_max_membres(equipe_id):
    """SOURCE UNIQUE de vérité (remplace les 2 copies divergentes des vues).
    Règle : 20 pour ND Assomption Koumassi, 12 sinon.
    NB : la colonne equipes.max_membres (DEFAULT 10) ne correspond pas à la
    règle métier (12) — ne pas la lire tant qu'aucune interface de réglage
    n'existe, sous peine de réduire tous les quotas à 10."""
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
    """Parse une date depuis str/date/datetime. Tolère 'YYYY-MM-DD HH:MM:SS'."""
    if not valeur:
        return None
    if isinstance(valeur, date):
        return valeur
    s = str(valeur).strip().split(' ')[0].split('T')[0]  # FIX : coupe l'heure
    s = s.replace('-', '/').replace('\\', '/')
    try:
        parties = s.split('/')
        if len(parties) == 3:
            return date(int(parties[0]), int(parties[1]), int(parties[2]))
    except (ValueError, TypeError):   # FIX : except ciblé
        pass
    return None

def periode_affichage(a): return f"Sept {a} – Août {a+1}"   # FIX : Août (pas Sept)

def afficher_situation(s): return {"Déplacé": "a déménagé", "Radié": "indisponible", "Défunt": "est décédé(e)", "Transféré": "a été transféré(e)"}.get(s, s)

def sans_accents(t):
    # FIX : version standard Unicode (gère œ, ñ, ü, ë...)
    return unicodedata.normalize('NFD', str(t).lower()).encode('ascii', 'ignore').decode('utf-8')

def lien_whatsapp(num, msg):
    if not num: return None
    num = ''.join(ch for ch in num if ch.isdigit() or ch == '+')
    if not num.startswith('+') and len(num) == 10: num = '225' + num
    msg = msg.replace('\\n', '\n')
    # FIX : wa.me sans le "+"
    return f"https://wa.me/{num.lstrip('+')}?text={urllib.parse.quote(msg)}"

def envoyer_notification_telegram(message):
    try:
        token, chat_id = st.secrets.get("TELEGRAM_BOT_TOKEN"), st.secrets.get("TELEGRAM_CHAT_ID")
        if token and chat_id:
            # FIX : timeout — un Telegram lent ne doit pas geler le thread
            requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"}, timeout=10)
    except Exception:
        pass


# ============================================================
# MEDIAS (Cloudinary / local)
# ============================================================
def sauvegarder_photo(fichier, matricule):
    if not fichier:
        return None
    try:
        img = Image.open(fichier)
        img.load()  # FIX : force la lecture complète
        if USE_CLOUDINARY:
            fichier.seek(0)  # FIX BUG MAJEUR : rembobiner après PIL, sinon upload tronqué
            res = cloudinary.uploader.upload(fichier, public_id=f"rosaire_membres/{matricule}",
                                             overwrite=True,
                                             transformation=[{"width": 300, "height": 300, "crop": "fill"}])
            return res['secure_url']
        os.makedirs("photos", exist_ok=True)
        chemin = f"photos/{matricule}.jpg"
        # FIX : les PNG transparents (RGBA) crashent en JPEG
        if img.mode in ('RGBA', 'P', 'LA'):
            img = img.convert('RGB')
        img.thumbnail((300, 300))  # FIX : préserve le ratio
        img.save(chemin, "JPEG", quality=60)
        return chemin
    except Exception as e:
        print(f"Erreur sauvegarde photo {matricule}: {e}")
        return None

def _public_id_unique(dossier, nom_fichier):
    """public_id lisible + suffixe unique : deux uploads du même nom de fichier
    ne s'écrasent plus jamais (les anciennes publications gardent leur fichier)."""
    base = os.path.splitext(os.path.basename(nom_fichier))[0]
    base = ''.join(ch if ch.isalnum() or ch in '-_' else '_' for ch in base)[:60]
    return f"{dossier}/{base}_{secrets.token_hex(4)}"


def sauvegarder_pdf(fichier):
    """PDF sur Cloudinary (raw). Retourne l'URL sécurisée ou None."""
    if fichier:
        try:
            res = cloudinary.uploader.upload(fichier, resource_type="raw",
                                             public_id=_public_id_unique("rosaire_pdfs", fichier.name),
                                             overwrite=False)
            return res['secure_url']
        except Exception as e:
            print(f"Erreur upload PDF: {e}")
    return None


def sauvegarder_audio(fichier):
    """Audio/vidéo sur Cloudinary (Cloudinary traite l'audio comme une ressource 'video')."""
    if fichier:
        try:
            res = cloudinary.uploader.upload(fichier, resource_type="video",
                                             public_id=_public_id_unique("rosaire_audio", fichier.name),
                                             overwrite=False)
            return res['secure_url']
        except Exception as e:
            print(f"Erreur upload audio: {e}")
    return None


def sauvegarder_illustration(fichier):
    """Image d'illustration, largeur limitée à 800px, ratio préservé."""
    if fichier:
        try:
            res = cloudinary.uploader.upload(fichier,
                                             public_id=_public_id_unique("rosaire_illustrations", fichier.name),
                                             overwrite=False,
                                             transformation=[{"width": 800, "crop": "limit"}])
            return res['secure_url']
        except Exception as e:
            print(f"Erreur upload illustration: {e}")
    return None


def supprimer_photo(path):
    if not path: return
    if USE_CLOUDINARY and path.startswith("http"):
        try:
            import cloudinary.uploader
            parts = path.split('/upload/')[-1]
            if parts.startswith('v'): parts = '/'.join(parts.split('/')[1:])
            # FIX : décoder l'URL — "pentecote%202026" → "pentecote 2026"
            # (le public_id réel chez Cloudinary contient l'espace, pas l'encodage ;
            # sans unquote, le destroy échouait silencieusement → fichiers orphelins)
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
    # FIX : convention unique 1er septembre (cohérent année pastorale — avant : 1er octobre)
    c.execute('''INSERT INTO archives (membre_id, situation, date_debut, date_fin, commentaire, auteur_id, auteur_nom, auteur_role, paroisse_id, equipe_id)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (membre_id, situation, date(annee_debut, 9, 1), date(annee_fin, 9, 1), commentaire, auteur_id, auteur_nom, auteur_role, paroisse_id, equipe_id))
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
# EXPORT EXCEL DIOCÈSE
# ============================================================
def exporter_excel_diocese():
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        queries = [
            ("Paroisses", "SELECT id, nom, commune, ville, responsable, bureau FROM paroisses"),
            ("Equipes", "SELECT e.id, e.nom_equipe, e.responsable, e.bureau, p.nom as paroisse FROM equipes e JOIN paroisses p ON e.paroisse_id = p.id"),
            ("Membres actifs", "SELECT m.matloc as MatLoc, m.matricule as Matricule, m.nom, m.prenom, m.date_naissance, m.whatsapp, m.date_adhesion, p.nom as paroisse, e.nom_equipe as equipe FROM membres m JOIN paroisses p ON m.paroisse_id = p.id JOIN equipes e ON m.equipe_id = e.id WHERE m.statut = 'actif' ORDER BY p.nom, e.nom_equipe"),
            # FIX : m.matloc (l'ancien m.matricule est vide pour tous les membres d'avant migration)
            ("Abonnements", "SELECT a.id, m.matloc as MatLoc, m.nom, m.prenom, a.annee_debut, a.date_paiement, a.montant, a.type_abonnement FROM abonnements a JOIN membres m ON a.membre_id = m.id ORDER BY a.annee_debut DESC"),
            ("Archives", "SELECT m.matloc as MatLoc, m.nom, m.prenom, a.situation, a.date_debut, a.date_fin, a.commentaire, p.nom as paroisse, e.nom_equipe as equipe FROM archives a JOIN membres m ON a.membre_id = m.id LEFT JOIN equipes e ON a.equipe_id = e.id LEFT JOIN paroisses p ON e.paroisse_id = p.id ORDER BY a.date_fin DESC")
        ]
        for sheet_name, query in queries:
            try:
                # FIX : database.conn (et non la variable importée, obsolète après reconnexion Turso)
                df = pd.read_sql_query(query, database.conn)
                if not df.empty: df.to_excel(writer, sheet_name=sheet_name, index=False)
            except Exception as e:
                # FIX : plus de pass silencieux — un export amputé doit se savoir
                print(f"Export '{sheet_name}' échoué: {e}")
    output.seek(0)
    return output
