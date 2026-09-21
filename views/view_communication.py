# ====================================================================
# views/view_communication.py — VERSION 1.2
# Vue cloisonnée du Service Communication (R4 : la cellule ne publie
# JAMAIS seule — elle SOUMET ; le diocèse valide dans 🕊️ Espace spirituel
# → onglet 📡 Communication).
# Marqueurs : Ctrl+F → "VERSION 1.2", "show_communication".
# ====================================================================
import streamlit as st
from datetime import date
from database import c, commit_and_sync
from services import (sauvegarder_illustration, sauvegarder_audio,
                      envoyer_notification_telegram)


def _assurer_table():
    """Crée la table des soumissions si absente (idempotent, sans risque)."""
    c.execute("""CREATE TABLE IF NOT EXISTS soumissions_comm (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    auteur_id INTEGER,
                    type_contenu TEXT,
                    titre TEXT,
                    contenu_texte TEXT,
                    image_url TEXT,
                    fichier_url TEXT,
                    video_url TEXT,
                    date_evenement TEXT,
                    lieu TEXT,
                    statut TEXT DEFAULT 'attente',
                    motif_refus TEXT,
                    date_soumission TEXT)""")
    commit_and_sync()


TYPES_EVENEMENT = ["Prière mensuelle", "Prière commune", "Prière spéciale",
                   "Pèlerinage", "Réunion"]

LIBELLES = {"priere": "🙏 Prière", "meditation": "📖 Méditation",
            "audio": "🎵 Musique", "annonce_defilante": "📻 Bande défilante",
            "evenement": "📅 Évènement"}

STATUTS = {"attente": "🟡 En attente de validation du diocèse",
           "publie": "✅ Publiée par le diocèse",
           "refuse": "❌ Refusée par le diocèse"}


def _soumettre(d):
    """v3 — RÈGLE MÉTIER DÉFINITIVE : la cellule ne publie JAMAIS d'elle-même.
    L'accord du diocèse est obligatoire et nécessaire (sas de validation).
    La finalité des contenus validés reste l'évangélisation élargie (espace
    communautaire public, QR, affiches). La table porte le flux :
    attente → publie / refuse."""
    c.execute("""INSERT INTO soumissions_comm
                 (auteur_id, type_contenu, titre, contenu_texte, image_url,
                  fichier_url, video_url, date_evenement, lieu, statut,
                  date_soumission)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'attente', ?)""",
              (st.session_state.get('user_id'), d.get("type_contenu"),
               d.get("titre"), d.get("contenu_texte"), d.get("image_url"),
               d.get("fichier_url"), d.get("video_url"),
               d.get("date_evenement"), d.get("lieu"),
               date.today().isoformat()))
    commit_and_sync()
    try:
        envoyer_notification_telegram(
            "📡 <b>Service Communication</b> — nouvelle soumission À VALIDER : "
            + (d.get("titre") or "(sans titre)"))
    except Exception:
        pass
    st.success("📨 Soumission transmise au diocèse. Rien ne sera publié sans sa validation.")


def _bandeau():
    st.markdown('<div style="background:linear-gradient(135deg,#1A237E 0%,#283593 100%);'
                ' padding:18px; border-radius:15px; text-align:center; margin-bottom:15px;">'
                '<div style="color:#FFD700; font-size:1.15rem; font-weight:bold;">'
                '📡 Service Communication — Diocèse de Grand-Bassam</div>'
                '<div style="color:#e8eaf6; font-size:0.85rem; margin-top:4px;">'
                'Je prépare, le diocèse publie — chaque contenu passe par sa validation</div></div>',
                unsafe_allow_html=True)


def show_communication():
    _assurer_table()
    _bandeau()

    t_pm, t_mu, t_bd, t_ev, t_hist = st.tabs(
        ["🙏 Prière / Méditation", "🎵 Musique", "📻 Bande défilante",
         "📅 Évènement", "📔 Journal des publications"])

    # ---------------- PRIÈRE / MÉDITATION ----------------
    with t_pm:
        with st.form("form_pm", clear_on_submit=True):
            type_pm = st.selectbox("Type de contenu", ["Prière", "Méditation"])
            titre = st.text_input("Titre")
            contenu = st.text_area("Contenu du texte")
            img = st.file_uploader("Illustration (photo — facultatif)", type=["jpg", "jpeg", "png"])
            pdf_url = st.text_input("Lien PDF (facultatif — https://...)")
            if st.form_submit_button("📨 Soumettre au diocèse", type="primary"):
                if not titre.strip() or not contenu.strip():
                    st.error("Le titre et le contenu sont obligatoires.")
                else:
                    img_url = sauvegarder_illustration(img) if img else None
                    _soumettre({
                        "type_contenu": "priere" if type_pm == "Prière" else "meditation",
                        "titre": titre.strip(), "contenu_texte": contenu.strip(),
                        "image_url": img_url, "fichier_url": pdf_url.strip() or None})

    # ---------------- MUSIQUE ----------------
    with t_mu:
        with st.form("form_mu", clear_on_submit=True):
            titre_mu = st.text_input("Titre du morceau")
            audio = st.file_uploader("Fichier audio (MP3)", type=["mp3", "wav", "m4a"])
            if st.form_submit_button("📨 Soumettre au diocèse", type="primary"):
                if not titre_mu.strip() or audio is None:
                    st.error("Le titre et le fichier audio sont obligatoires.")
                else:
                    url_mu = sauvegarder_audio(audio)
                    if url_mu:
                        _soumettre({"type_contenu": "audio", "titre": titre_mu.strip(),
                                    "fichier_url": url_mu})
                    else:
                        st.error("L'envoi du fichier a échoué. Réessayez.")

    # ---------------- BANDE DÉFILANTE ----------------
    with t_bd:
        with st.form("form_bd", clear_on_submit=True):
            texte_bd = st.text_area("Texte de l'annonce défilante (court et percutant)",
                                    max_chars=250)
            cible = st.selectbox("Cible de l'annonce",
                                 ["🌍 Public (tous)", "👤 Membres uniquement"])
            if st.form_submit_button("📨 Soumettre au diocèse", type="primary"):
                if not texte_bd.strip():
                    st.error("Le texte est obligatoire.")
                else:
                    _soumettre({"type_contenu": "annonce_defilante",
                                "titre": "Bande défilante",
                                "contenu_texte": texte_bd.strip(),
                                "fichier_url": "membre" if cible.startswith("👤") else None})

    # ---------------- ÉVÈNEMENT ----------------
    with t_ev:
        with st.form("form_ev", clear_on_submit=True):
            st.caption("ℹ️ Rappel : un évènement ciblé apparaît au Coin Affiche — il n'entre jamais dans les agendas ni ne déclenche de Réponse de Communion (chaîne normale des transmissions).")
            type_ev = st.selectbox("Type d'évènement", TYPES_EVENEMENT)
            c1, c2 = st.columns(2)
            with c1:
                d_ev = st.date_input("Date de l'évènement")
            with c2:
                lieu_ev = st.text_input("Lieu")
            affiche = st.file_uploader("Affiche (photo — facultatif)", type=["jpg", "jpeg", "png"])
            video_url = st.text_input("Lien vidéo (facultatif — https://...)")
            if st.form_submit_button("📨 Soumettre au diocèse", type="primary"):
                img_ev = sauvegarder_illustration(affiche) if affiche else None
                _soumettre({"type_contenu": "evenement", "titre": type_ev,
                            "date_evenement": d_ev.isoformat(),
                            "lieu": lieu_ev.strip() or None,
                            "image_url": img_ev,
                            "video_url": video_url.strip() or None})

    # ---------------- JOURNAL DES PUBLICATIONS ----------------
    with t_hist:
        lignes = c.execute("""SELECT id, type_contenu, titre, statut, motif_refus,
                                     date_soumission FROM soumissions_comm
                              ORDER BY id DESC LIMIT 30""").fetchall()
        if not lignes:
            st.info("Aucune soumission pour le moment.")
        for s in lignes:
            libelle = LIBELLES.get(s[1], s[1])
            entete = f"{libelle} — {s[2] or '(sans titre)'} ({s[5]})"
            with st.expander(entete):
                st.write(STATUTS.get(s[3], s[3]))
                if s[3] == "refuse" and s[4]:
                    st.error("Motif du refus : " + s[4])
