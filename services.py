import os
import hashlib
import random
import string
import io
import urllib.parse
import requests
import pandas as pd
from datetime import date
from PIL import Image
# CORRECTION : Importation de 'conn' nécessaire pour les exports Excel propres
from database import c, conn, commit_and_sync

USE_CLOUDINARY = False
try:
    import streamlit as st
    import cloudinary
    import cloudinary.uploader
    cloudinary.config(cloud_name=st.secrets.get("CLOUDINARY_CLOUD_NAME"), api_key=st.secrets.get("CLOUDINARY_API_KEY"), api_secret=st.secrets.get("CLOUDINARY_API_SECRET"), secure=True)
    if st.secrets.get("CLOUDINARY_CLOUD_NAME"): USE_CLOUDINARY = True
except Exception:
    pass

# ATTENTION SÉCURITÉ : Le SHA256 pur est obsolète pour les mots de passe. 
# En attendant de voir ton fichier d'authentification, on garde cette fonction,
# mais il faudra la remplacer par un vrai hachage (ex: bcrypt ou argon2).
def hash_password(p): return hashlib.sha256(p.encode()).hexdigest()

def generer_mot_de_passe(l=8): return ''.join(random.choices(string.ascii_letters + string.digits, k=l))

def safe_date(v):
    if isinstance(v, date): return v
    if isinstance(v, str):
        try: return date.fromisoformat(v)
        except: return None
    return None

def periode_affichage(a): return f"Sept {a} – Sept {a+1}"

def afficher_situation(s): return {"Déplacé": "a déménagé", "Radié": "indisponible", "Défunt": "est décédé(e)", "Transféré": "a été transféré(e)"}.get(s, s)

def sans_accents(t):
    t = t.lower()
    for a, l in {'é':'e','è':'e','ê':'e','à':'a','â':'a','î':'i','ô':'o','ù':'u','û':'u','ç':'c'}.items(): t = t.replace(a, l)
    return t

def generer_matricule_unique():
    while True:
        suffixe = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
        mat = f"GBA-{suffixe}"
        if c.execute("SELECT COUNT(*) FROM membres WHERE matloc=?", (mat,)).fetchone()[0] == 0: 
            return mat

def sauvegarder_photo(fichier, matricule):
    if fichier:
        # CORRECTION : Sécurité pour éviter un crash si l'utilisateur upload un fichier non-image (PDF, txt...)
        try:
            img = Image.open(fichier)
            if USE_CLOUDINARY:
                res = cloudinary.uploader.upload(fichier, public_id=f"rosaire_membres/{matricule}", overwrite=True, transformation=[{"width": 300, "height": 300, "crop": "fill"}])
                return res['secure_url']
            else:
                os.makedirs("photos", exist_ok=True)
                chemin = f"photos/{matricule}.jpg"
                img = img.resize((300, 300))
                img.save(chemin, "JPEG", quality=60)
                return chemin
        except Exception:
            return None
    return None

def supprimer_photo(path):
    if not path: return
    if USE_CLOUDINARY and path.startswith("http"):
        try:
            import cloudinary.uploader
            parts = path.split('/upload/')[-1]
            if parts.startswith('v'): parts = '/'.join(parts.split('/')[1:])
            cloudinary.uploader.destroy(os.path.splitext(parts)[0])
        except Exception:
            pass
    elif not path.startswith("http") and os.path.exists(path): 
        os.remove(path)

def archiver_membre(membre_id, situation, annee_debut, annee_fin, commentaire, auteur_id, auteur_nom, auteur_role, paroisse_id=None, equipe_id=None):
    # CORRECTION : Gestion sécurisée des valeurs NULL pour éviter un crash (TypeError)
    if not equipe_id:
        res = c.execute("SELECT equipe_id FROM membres WHERE id=?", (membre_id,)).fetchone()
        equipe_id = res[0] if res and res[0] else None
        
    if not paroisse_id and equipe_id:
        res = c.execute("SELECT paroisse_id FROM equipes WHERE id=?", (equipe_id,)).fetchone()
        paroisse_id = res[0] if res and res[0] else None

    c.execute("UPDATE membres SET statut='archive' WHERE id=?", (membre_id,))
    c.execute('''INSERT INTO archives (membre_id, situation, date_debut, date_fin, commentaire, auteur_id, auteur_nom, auteur_role, paroisse_id, equipe_id)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (membre_id, situation, date(annee_debut, 10, 1), date(annee_fin, 10, 1), commentaire, auteur_id, auteur_nom, auteur_role, paroisse_id, equipe_id))
    commit_and_sync()

def enregistrer_abonnement(membre_id, annee_debut, montant=0, type_abonnement='abonnement'):
    existant = c.execute("SELECT id FROM abonnements WHERE membre_id=? AND annee_debut=?", (membre_id, annee_debut)).fetchone()
    if existant:
        c.execute("UPDATE abonnements SET date_paiement=?, montant=?, type_abonnement=?, statut='paye' WHERE id=?", (date.today().isoformat(), montant, type_abonnement, existant[0]))
    else:
        c.execute('''INSERT INTO abonnements (membre_id, annee_debut, date_paiement, montant, type_abonnement, statut) VALUES (?, ?, ?, ?, ?, ?)''',
                  (membre_id, annee_debut, date.today().isoformat(), montant, type_abonnement, 'paye'))
    commit_and_sync()

def verifier_abonnement(m, a): 
    return c.execute("SELECT id FROM abonnements WHERE membre_id=? AND annee_debut=? AND statut='paye'", (m, a)).fetchone() is not None

def envoyer_notification_telegram(message):
    try:
        import streamlit as st
        token, chat_id = st.secrets.get("TELEGRAM_BOT_TOKEN"), st.secrets.get("TELEGRAM_CHAT_ID")
        if token and chat_id: 
            requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"})
    except Exception:
        pass

def lien_whatsapp(num, msg):
    if not num: return None
    num = ''.join(ch for ch in num if ch.isdigit() or ch == '+')
    if not num.startswith('+') and len(num) == 10: num = '225' + num
    # CORRECTION : Remplacer les antislashs littéraux par de vrais sauts de ligne pour WhatsApp
    msg = msg.replace('\\n', '\n')
    return f"https://wa.me/{num}?text={urllib.parse.quote(msg)}"

def exporter_excel_diocese():
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        queries = [
            ("Paroisses", "SELECT id, nom, commune, ville, responsable, bureau FROM paroisses"),
            ("Equipes", "SELECT e.id, e.nom_equipe, e.responsable, e.bureau, p.nom as paroisse FROM equipes e JOIN paroisses p ON e.paroisse_id = p.id"),
            ("Membres actifs", "SELECT m.matloc as MatLoc, m.matricule as Matricule, m.nom, m.prenom, m.date_naissance, m.whatsapp, m.date_adhesion, p.nom as paroisse, e.nom_equipe as equipe FROM membres m JOIN paroisses p ON m.paroisse_id = p.id JOIN equipes e ON m.equipe_id = e.id WHERE m.statut = 'actif' ORDER BY p.nom, e.nom_equipe"),
            ("Abonnements", "SELECT a.id, m.matricule, m.nom, m.prenom, a.annee_debut, a.date_paiement, a.montant, a.type_abonnement FROM abonnements a JOIN membres m ON a.membre_id = m.id ORDER BY a.annee_debut DESC"),
            ("Archives", "SELECT m.matloc as MatLoc, m.nom, m.prenom, a.situation, a.date_debut, a.date_fin, a.commentaire, p.nom as paroisse, e.nom_equipe as equipe FROM archives a JOIN membres m ON a.membre_id = m.id LEFT JOIN equipes e ON a.equipe_id = e.id LEFT JOIN paroisses p ON e.paroisse_id = p.id ORDER BY a.date_fin DESC")
        ]
        
        for sheet_name, query in queries:
            # CORRECTION MAJEURE : Utilisation de pd.read_sql_query au lieu de fetchall()
            # Cela permet de récupérer automatiquement les noms de colonnes (alias AS) dans l'Excel !
            try:
                df = pd.read_sql_query(query, conn)
                if not df.empty: df.to_excel(writer, sheet_name=sheet_name, index=False)
            except Exception:
                pass # Silencieux si une table n'existe pas encore
                
    output.seek(0)
    return output

def get_periode_pastorale():
    """Retourne l'année de début, la date de début (1er Sept) et la date de fin (31 Août)"""
    today = date.today()
    annee = today.year if today.month >= 9 else today.year - 1
    # CORRECTION CRITIQUE : L'année pastorale se termine le 31 AOÛT, pas le 31 MAI !
    return annee, date(annee, 9, 1), date(annee + 1, 8, 31)

def est_cloture(entite_type, entite_id, annee_debut):
    """Vérifie si une période est archivée"""
    from database import c
    return c.execute("SELECT id FROM periodes_cloturees WHERE entite_type=? AND entite_id=? AND annee_debut=?", (entite_type, entite_id, annee_debut)).fetchone() is not None

def cloturer_periode(entite_type, entite_id, annee_debut, auteur_nom):
    """Enregistre la clôture d'une année pastorale"""
    from database import c, commit_and_sync
    if not est_cloture(entite_type, entite_id, annee_debut):
        c.execute("INSERT INTO periodes_cloturees (entite_type, entite_id, annee_debut, date_cloture, auteur_nom) VALUES (?, ?, ?, ?, ?)",
                  (entite_type, entite_id, annee_debut, date.today().isoformat(), auteur_nom))
        commit_and_sync()
        return True
    return False

def sauvegarder_audio(fichier):
    """Envoie un fichier audio (MP3) sur Cloudinary et retourne l'URL"""
    if fichier:
        try:
            import streamlit as st
            import cloudinary.uploader
            # Cloudinary traite l'audio comme une ressource "video"
            nom_fichier = fichier.name.split('.')[0]
            res = cloudinary.uploader.upload(fichier, resource_type="video", public_id=f"rosaire_audio/{nom_fichier}", overwrite=True)
            return res['secure_url']
        except Exception as e:
            print(f"Erreur upload audio: {e}")
            return None
    return None
