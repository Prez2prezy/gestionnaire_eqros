# ====================================================================
# views/view_communication_validation.py — VERSION 1.0
# Le sceau du diocèse : chaque soumission du Service Communication est
# relue, puis PUBLIÉE (tables publiques) ou REFUSÉE avec motif.
# ====================================================================
import streamlit as st
from datetime import date
from database import c, commit_and_sync
from services import envoyer_notification_telegram

LIBELLES = {"priere": "🙏 Prière", "meditation": "📖 Méditation",
            "audio": "🎵 Musique", "annonce_defilante": "📻 Bande défilante",
            "evenement": "📅 Évènement"}


def _assurer_colonnes_cible():
    """Migration douce : paroisse_cible sur soumissions + tables publiques."""
    for _t in ("soumissions_comm", "espace_spirituel", "evenements"):
        try:
            c.execute(f"SELECT paroisse_cible FROM {_t} LIMIT 1")
        except Exception:
            try:
                c.execute(f"ALTER TABLE {_t} ADD COLUMN paroisse_cible INTEGER")
                commit_and_sync()
            except Exception:
                pass


def _nom_paroisse(pid):
    if not pid:
        return None
    r = c.execute("SELECT nom FROM paroisses WHERE id=?", (pid,)).fetchone()
    return r[0] if r else None


def _notifier(soumission, action):
    try:
        if action == "publie":
            envoyer_notification_telegram(
                "🕊️ <b>Diocèse</b> — soumission PUBLIÉE : " + (soumission[2] or "(sans titre)"))
        else:
            envoyer_notification_telegram(
                "🕊️ <b>Diocèse</b> — soumission REFUSÉE : " + (soumission[2] or "(sans titre)"))
    except Exception:
        pass


def show_validation_communication():
    _assurer_colonnes_cible()
    st.markdown('<h2 style="color:#1A237E;">🕊️ Soumissions du Service Communication</h2>', unsafe_allow_html=True)
    st.caption("Le Service Communication prépare — VOUS seul publiez. Chaque contenu validé "
               "rejoint l'Espace de Prière (évangélisation élargie : visible de toute la "
               "communauté, membres et visiteurs).")

    en_attente = c.execute("""SELECT id, type_contenu, titre, contenu_texte, image_url,
                                     fichier_url, video_url, date_evenement, lieu,
                                     date_soumission, paroisse_cible
                              FROM soumissions_comm WHERE statut='attente'
                              ORDER BY id ASC""").fetchall()

    st.markdown(f"### 🟡 En attente de validation ({len(en_attente)})")
    if not en_attente:
        st.info("Aucune soumission en attente. La cellule n'a rien préparé pour l'instant.")
    for s in en_attente:
        libelle = LIBELLES.get(s[1], s[1])
        with st.expander(f"{libelle} — {s[2] or '(sans titre)'} ({s[9]})"):
            if s[3]:
                st.markdown("**Texte :**")
                st.markdown(s[3])
            if s[4]:
                try: st.image(s[4], width=300)
                except Exception: pass
            if s[5] and str(s[5]).startswith("http"):
                st.markdown(f"📄 [Document joint]({s[5]})")
            if s[6] and str(s[6]).startswith("http"):
                st.markdown(f"🎬 [Vidéo jointe]({s[6]})")
            if s[1] == "evenement":
                st.write(f"📅 **Date :** {s[7] or 'à définir'} — 📍 **Lieu :** {s[8] or 'à définir'}")
            _nom_c = _nom_paroisse(s[10]) if len(s) > 10 else None
            st.info("🎯 Cible : " + (_nom_c if _nom_c else "🌍 Diocèse (tous)"))

            c_pub, c_ref = st.columns(2)
            with c_pub:
                if st.button("✅ Publier", key=f"pub_{s[0]}", type="primary", use_container_width=True):
                    if s[1] in ("priere", "meditation"):
                        c.execute("""INSERT INTO espace_spirituel
                                     (type_contenu, titre, contenu_texte, image_url,
                                      fichier_url, date_publication, auteur_nom, paroisse_cible)
                                     VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                                  (s[1], s[2], s[3], s[4], s[5],
                                   date.today().isoformat(), "Service Communication",
                                   s[10] if len(s) > 10 else None))
                    elif s[1] == "audio":
                        c.execute("""INSERT INTO espace_spirituel
                                     (type_contenu, titre, fichier_url, date_publication, auteur_nom, paroisse_cible)
                                     VALUES (?, ?, ?, ?, ?, ?)""",
                                  ("audio", s[2], s[5], date.today().isoformat(), "Service Communication",
                                   s[10] if len(s) > 10 else None))
                    elif s[1] == "annonce_defilante":
                        cible = s[5] if s[5] in ("membre", "defaut") else None
                        c.execute("""INSERT INTO espace_spirituel
                                     (type_contenu, titre, contenu_texte, fichier_url, date_publication, auteur_nom, paroisse_cible)
                                     VALUES (?, ?, ?, ?, ?, ?, ?)""",
                                  ("annonce_defilante", s[2] or "Bande défilante", s[3], cible,
                                   date.today().isoformat(), "Service Communication",
                                   s[10] if len(s) > 10 else None))
                    elif s[1] == "evenement":
                        c.execute("""INSERT INTO evenements
                                     (type_evenement, date_evenement, lieu, affiche_url, video_url, auteur_nom, paroisse_cible)
                                     VALUES (?, ?, ?, ?, ?, ?, ?)""",
                                  (s[2], s[7], s[8], s[4], s[6], "Service Communication",
                                   s[10] if len(s) > 10 else None))
                    c.execute("UPDATE soumissions_comm SET statut='publie' WHERE id=?", (s[0],))
                    commit_and_sync()
                    _notifier(s, "publie")
                    st.session_state["flash_success"] = "Contenu publié ! La communauté en profite dès maintenant. ✅"
                    st.rerun()
            with c_ref:
                if st.button("❌ Refuser", key=f"ref_{s[0]}", use_container_width=True):
                    st.session_state[f"refus_encours_{s[0]}"] = True
                    st.rerun()
            if st.session_state.get(f"refus_encours_{s[0]}"):
                motif = st.text_area("Motif du refus (communiqué à la cellule)", key=f"motif_{s[0]}")
                c_ok, c_ann = st.columns(2)
                with c_ok:
                    if st.button("Confirmer le refus", key=f"refok_{s[0]}", type="primary"):
                        c.execute("UPDATE soumissions_comm SET statut='refuse', motif_refus=? WHERE id=?",
                                  (motif.strip() or "Sans motif précisé", s[0]))
                        commit_and_sync()
                        _notifier(s, "refuse")
                        st.session_state.pop(f"refus_encours_{s[0]}", None)
                        st.session_state["flash_warning"] = "Soumission refusée — la cellule en est informée."
                        st.rerun()
                with c_ann:
                    if st.button("Annuler", key=f"refann_{s[0]}"):
                        st.session_state.pop(f"refus_encours_{s[0]}", None)
                        st.rerun()

    st.markdown("---")
    st.markdown("### 📔 Historique des décisions")
    historique = c.execute("""SELECT id, type_contenu, titre, statut, motif_refus, date_soumission
                              FROM soumissions_comm WHERE statut != 'attente'
                              ORDER BY id DESC LIMIT 30""").fetchall()
    if not historique:
        st.caption("Aucune décision pour l'instant.")
    for h in historique:
        libelle = LIBELLES.get(h[1], h[1])
        marqueur = "✅" if h[3] == "publie" else "❌"
        with st.expander(f"{marqueur} {libelle} — {h[2] or '(sans titre)'} ({h[5]})"):
            st.write("Décision : **publiée**" if h[3] == "publie" else "Décision : **refusée**")
            if h[3] == "refuse" and h[4]:
                st.error("Motif : " + h[4])
