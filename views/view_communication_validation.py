# ====================================================================
# views/view_communication_validation.py — VERSION 1.0
# Le sceau du diocèse : chaque soumission du Service Communication est
# relue, puis PUBLIÉE (tables publiques) ou REFUSÉE avec motif.
# ====================================================================
import streamlit as st
import html
from datetime import date, datetime, time
from database import c, commit_and_sync, safe_migrate
from services import envoyer_notification_telegram, publier_soumission


LIBELLES = {"priere": "🙏 Prière", "meditation": "📖 Méditation",
            "audio": "🎵 Musique", "annonce_defilante": "📺 Bande défilante",
            "actualite": "📰 Actualité (affiche/BA)",
            "theme_pastoral": "🕯️ Thème pastoral",
            "evenement": "📅 Évènement (historique)",
            "feuillet": "📖 Feuillet mensuel de prière"}


def _assurer_colonnes_cible():
    """Migration douce : paroisse_cible sur soumissions + tables publiques.
    v7.6.4 — même leçon que database.py (PATCH 26) : les ALTER passent par
    safe_migrate (connexion JETABLE), jamais par le curseur partagé.
    On ne tente l'ALTER que si la vérification rapide a échoué (base neuve)."""
    for _t in ("soumissions_comm", "espace_spirituel", "evenements"):
        try:
            c.execute(f"SELECT paroisse_cible FROM {_t} LIMIT 1")
        except Exception:
            safe_migrate(f"ALTER TABLE {_t} ADD COLUMN paroisse_cible INTEGER")
    # Colonnes de l'actualité validée (date et lieu informatifs)
    for _col in ("date_evenement", "lieu"):
        try:
            c.execute(f"SELECT {_col} FROM espace_spirituel LIMIT 1")
        except Exception:
            safe_migrate(f"ALTER TABLE espace_spirituel ADD COLUMN {_col} TEXT")
    # v7.8.8 — date de publication programmée (lazy cron côté app)
    try:
        c.execute("SELECT date_publication_prevue FROM soumissions_comm LIMIT 1")
    except Exception:
        safe_migrate("ALTER TABLE soumissions_comm ADD COLUMN date_publication_prevue TEXT")
    # v7.9.2 — traçabilité des décisions (qui a publié, quand)
    for _col in ("date_decision", "auteur_decision"):
        try:
            c.execute(f"SELECT {_col} FROM soumissions_comm LIMIT 1")
        except Exception:
            safe_migrate(f"ALTER TABLE soumissions_comm ADD COLUMN {_col} TEXT")
    # Affiches du thème et des sous-thèmes (auto-réparation)
    for _t in ("themes_pastoraux", "sous_themes"):
        try:
            c.execute(f"SELECT affiche_url FROM {_t} LIMIT 1")
        except Exception:
            safe_migrate(f"ALTER TABLE {_t} ADD COLUMN affiche_url TEXT")


def _nom_paroisse(pid):
    if not pid:
        return None
    r = c.execute("SELECT nom FROM paroisses WHERE id=?", (pid,)).fetchone()
    return r[0] if r else None


def _deja_publie(s):
    """v7.9.0 — cette soumission a-t-elle DÉJÀ été publiée ? Détecte les
    soumissions restées « attente » alors que leur contenu a déjà rejoint
    les tables publiques (clic double, commit Hrana perdu, publication
    programmée...). Retourne (booléen, libellé de la table cible)."""
    try:
        _t, _titre = s[1], (s[2] or "").strip()
        if _t in ("priere", "meditation", "audio", "annonce_defilante", "actualite"):
            _ex = c.execute("""SELECT 1 FROM espace_spirituel
                               WHERE type_contenu=? AND TRIM(COALESCE(titre,''))=?
                               LIMIT 1""", (_t, _titre)).fetchone()
            return (bool(_ex), "Espace de Prière")
        if _t == "evenement":
            _ex = c.execute("""SELECT 1 FROM evenements
                               WHERE TRIM(COALESCE(type_evenement,''))=?
                                 AND COALESCE(date_evenement,'')=?
                               LIMIT 1""", (_titre, s[7] or "")).fetchone()
            return (bool(_ex), "Agenda des évènements")
        if _t == "theme_pastoral":
            _ex = c.execute("""SELECT 1 FROM themes_pastoraux
                               WHERE TRIM(COALESCE(texte_theme,''))=? LIMIT 1""",
                            ((s[3] or "").strip(),)).fetchone()
            return (bool(_ex), "Thème pastoral")
        if _t == "feuillet":
            _an, _mois = int(s[7] or 0), int(s[8] or 0)
            _ex = c.execute("""SELECT 1 FROM feuillets_publications
                               WHERE annee_debut=? AND mois=? LIMIT 1""",
                            (_an, _mois)).fetchone()
            return (bool(_ex), "Feuillet mensuel")
    except Exception:
        return (False, "")
    return (False, "")


def _notifier(soumission, action):
    try:
        if action == "publie":
            envoyer_notification_telegram(
                "🕊️ <b>Diocèse</b> — soumission PUBLIÉE : " + html.escape(soumission[2] or "(sans titre)"))
        else:
            envoyer_notification_telegram(
                "🕊️ <b>Diocèse</b> — soumission REFUSÉE : " + html.escape(soumission[2] or "(sans titre)"))
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

    # v7.9.0 — Séparation des VRAIES nouveautés et des soumissions dont le
    # contenu a DÉJÀ été publié (elles n'ont jamais dû rester ici) : le
    # compteur redevient exact et rien n'est republié en doublon.
    _doublons = [s for s in en_attente if _deja_publie(s)[0]]
    _vrais = [s for s in en_attente if not _deja_publie(s)[0]]

    if _doublons:
        st.warning("🧹 " + str(len(_doublons)) + " soumission(s) « en attente » ont en réalité "
                   "DÉJÀ ÉTÉ PUBLIÉES (clic double ou micro-coupure au moment de la validation). "
                   "Elles n'attendent que d'être rangées — republier créerait un doublon.")

    st.markdown(f"### 🟡 En attente de validation ({len(_vrais)})")
    if not _vrais:
        st.info("Aucune soumission en attente. La cellule n'a rien préparé pour l'instant.")
    for s in _vrais:
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
            if s[1] == "actualite":
                st.write(f"📅 **Date informative :** {s[7] or '—'} — 📍 **Lieu :** {s[8] or '—'}")
            if s[1] == "theme_pastoral":
                try:
                    _an = int(s[7]) if s[7] else None
                except (ValueError, TypeError):
                    _an = None
                st.info("🕯️ Thème de l'année pastorale " + (f"{_an} - {_an + 1}" if _an else "à préciser")
                        + f" — Mystère porteur N°{s[8] or '?'}")
            if s[1] == "feuillet":
                # v7.8.6 — convention de soumission : date_evenement = année
                # pastorale, lieu = mois pastoral (1-12, Septembre = 1).
                _an_f, _mois_f = None, None
                try:
                    _an_f = int(s[7]) if s[7] else None
                except (ValueError, TypeError):
                    _an_f = None
                try:
                    _mois_f = int(s[8]) if s[8] else None
                except (ValueError, TypeError):
                    _mois_f = None
                MOIS_PAST = ["Septembre", "Octobre", "Novembre", "Décembre", "Janvier",
                             "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août"]
                _mois_lbl_f = MOIS_PAST[_mois_f - 1] if _mois_f and 1 <= _mois_f <= 12 else "?"
                _an_civ = (_an_f + 1) if _mois_f and _mois_f >= 5 else _an_f  # Janvier → août : année civile +1
                st.info(f"📖 Feuillet N°{_mois_f or '?'} — {_mois_lbl_f} {_an_civ or _an_f or '?'} "
                        f"(année pastorale {_an_f or '?'})")
                try:
                    _secs_sas = c.execute("""SELECT ordre, titre FROM feuillet_sections
                                             WHERE annee_debut=? AND mois=? ORDER BY ordre""",
                                          (_an_f, _mois_f)).fetchall()
                except Exception:
                    _secs_sas = []
                if _secs_sas:
                    st.success(f"✅ {len(_secs_sas)} section(s) saisie(s) : "
                               + " · ".join(f"{o}. {t or ''}" for o, t in _secs_sas))
                else:
                    st.error("⚠️ Aucune section saisie pour ce mois : la publication "
                             "est impossible (le clic mènerait à une vitrine vide).")

            _nom_c = _nom_paroisse(s[10]) if len(s) > 10 else None
            st.info("🎯 Cible : " + (_nom_c if _nom_c else "🌍 Diocèse (tous)"))

            # --- v7.8.8 : PROGRAMMATION DE LA PUBLICATION ---
            # Publier maintenant OU programmer : le contenu reste invisible
            # jusqu'à la date/heure choisie, puis est publié automatiquement
            # (réveil au chargement de l'app — Abidjan = UTC, pas de décalage).
            # v7.9.2 — aperçu LIVE de l'échéance choisie avant de cliquer :
            # fini les programmations au mauvais jour par inadvertance.
            with st.expander("🗓️ Programmer la publication (au lieu de publier maintenant)"):
                _d_prog = st.date_input("Date de publication", value=date.today(), key=f"dp_{s[0]}")
                _h_prog = st.time_input("Heure de publication", value=time(8, 0), key=f"hp_{s[0]}")
                _dt_aper = datetime.combine(_d_prog, _h_prog)
                _j_aper = (_dt_aper.date() - date.today()).days
                st.caption("→ **Résumé :** publication le "
                           + _dt_aper.strftime("%d/%m/%Y à %H:%M") + " ("
                           + ("aujourd'hui" if _j_aper == 0 else "dans " + str(_j_aper) + " jour(s)")
                           + "). Le contenu rejoindra l'Espace de Prière à cette date et heure, sans nouveau "
                           "clic (publication automatique dès qu'une page de l'application est ouverte "
                           "après l'échéance — heure du serveur, Abidjan = UTC). « ✅ Publier » ci-dessous "
                           "RESTE une publication immédiate : utilisez le bouton de ce cadre pour programmer.")
                if st.button("🗓️ Programmer la publication", key=f"prog_{s[0]}", type="primary",
                             use_container_width=True):
                    _dt = datetime.combine(_d_prog, _h_prog)
                    if _dt <= datetime.now():
                        st.error("La date/heure choisie est déjà passée : choisissez un moment futur.")
                    else:
                        c.execute("""UPDATE soumissions_comm SET statut='programme',
                                     date_publication_prevue=?, auteur_decision=NULL WHERE id=?""",
                                  (_dt.strftime("%Y-%m-%d %H:%M"), s[0]))
                        commit_and_sync()
                        try:
                            envoyer_notification_telegram(
                                "🗓️ <b>Diocèse</b> — publication PROGRAMMÉE pour le "
                                + _dt.strftime("%d/%m/%Y à %H:%M") + " : "
                                + html.escape(s[2] or "(sans titre)"))
                        except Exception:
                            pass
                        _j_flash = (_dt.date() - date.today()).days
                        st.session_state["flash_success"] = (
                            "Publication programmée pour le "
                            + _dt.strftime("%d/%m/%Y à %H:%M")
                            + (" (dans " + str(_j_flash) + " jour(s))" if _j_flash else " (aujourd'hui)")
                            + ". Rien ne sera publié avant cette heure — le suivi est dans « 🗓️ Programmées ». 🗓️")
                        st.rerun()

            c_pub, c_ref = st.columns(2)
            with c_pub:
                if st.button("✅ Publier", key=f"pub_{s[0]}", type="primary", use_container_width=True):
                    _ok = True
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
                    elif s[1] == "actualite":
                        c.execute("""INSERT INTO espace_spirituel
                                     (type_contenu, titre, contenu_texte, image_url, fichier_url,
                                      date_publication, auteur_nom, paroisse_cible, date_evenement, lieu)
                                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                                  ("actualite", s[2], s[3], s[4], s[6],
                                   date.today().isoformat(), "Service Communication",
                                   s[10] if len(s) > 10 else None, s[7], s[8]))
                    elif s[1] == "theme_pastoral":
                        try:
                            _an = int(s[7]) if s[7] else None
                        except (ValueError, TypeError):
                            _an = None
                        try:
                            _mys = int(s[8]) if s[8] else 5
                        except (ValueError, TypeError):
                            _mys = 5
                        if _an:
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
                        else:
                            st.error("Année pastorale illisible : utilisez « ❌ Refuser ».")
                            _ok = False
                    elif s[1] == "feuillet":
                        # v7.8.6 — publication du feuillet : le diocèse seul
                        # valide ; l'alerte « 📖 Nouveau feuillet » part alors
                        # dans le fil d'actualité de l'Espace de Prière.
                        try:
                            _an_fp = int(s[7]) if s[7] else None
                        except (ValueError, TypeError):
                            _an_fp = None
                        try:
                            _mois_fp = int(s[8]) if s[8] else None
                        except (ValueError, TypeError):
                            _mois_fp = None
                        if not _an_fp or not _mois_fp or not (1 <= _mois_fp <= 12):
                            st.error("Mois/année du feuillet illisibles : utilisez « ❌ Refuser ».")
                            _ok = False
                        else:
                            _n_secs = c.execute("""SELECT COUNT(*) FROM feuillet_sections
                                                   WHERE annee_debut=? AND mois=?""",
                                                (_an_fp, _mois_fp)).fetchone()[0]
                            if _n_secs == 0:
                                st.error("Aucune section saisie pour ce mois : publication impossible.")
                                _ok = False
                            else:
                                # v7.8.11 — UPDATE puis INSERT (au lieu
                                # d'ON CONFLICT) : robuste même sur une base
                                # ancienne sans contrainte UNIQUE, et la date
                                # de publication est TOUJOURS rafraîchie à la
                                # republication d'une version corrigée.
                                _cur = c.execute(
                                    """UPDATE feuillets_publications
                                       SET numero=?, date_publication=?
                                       WHERE annee_debut=? AND mois=?""",
                                    (_mois_fp, date.today().isoformat(),
                                     _an_fp, _mois_fp))
                                if (_cur.rowcount or 0) == 0:
                                    c.execute(
                                        """INSERT INTO feuillets_publications
                                           (annee_debut, mois, numero, date_publication)
                                           VALUES (?, ?, ?, ?)""",
                                        (_an_fp, _mois_fp, _mois_fp,
                                         date.today().isoformat()))
                    elif s[1] == "evenement":  # ancien type (onglet supprimé), gardé pour l'historique
                        c.execute("""INSERT INTO evenements
                                     (type_evenement, date_evenement, lieu, affiche_url, video_url, auteur_nom, paroisse_cible)
                                     VALUES (?, ?, ?, ?, ?, ?, ?)""",
                                  (s[2], s[7], s[8], s[4], s[6], "Service Communication",
                                   s[10] if len(s) > 10 else None))
                    if _ok:
                        # v7.9.2 — traçabilité : la décision manuelle est datée
                        _cur = c.execute("""UPDATE soumissions_comm SET statut='publie',
                                            date_decision=?, auteur_decision=? WHERE id=?""",
                                         (datetime.now().strftime("%Y-%m-%d %H:%M"),
                                          "👤 diocèse — clic « ✅ Publier »", s[0]))
                        commit_and_sync()
                        # v7.9.0 — preuve du rangement : si la mise à jour
                        # n'a touché AUCUNE ligne (micro-coupure Turso), on
                        # le DIT au lieu d'afficher un succès mensonger.
                        if (_cur.rowcount or 0) == 0:
                            st.error("⚠️ La publication a réussi mais le rangement de la "
                                     "soumission n'a pas pu être enregistré : elle "
                                     "réapparaîtra ci-dessous comme « déjà publiée ». "
                                     "Utilisez alors « ✅ Marquer comme publié ».")
                            st.stop()
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
    # ---------- v7.9.0 : DÉJÀ PUBLIÉS — À RANGER ----------
    if _doublons:
        st.markdown(f"### 🧹 Déjà publiés — à ranger ({len(_doublons)})")
        st.caption("Ces contenus figurent déjà dans l'Espace de Prière (ou l'agenda). "
                   "Aucun danger à les marquer : RIEN n'est republié, seule la liste "
                   "d'attente est nettoyée.")
        for s in _doublons:
            _tbl = _deja_publie(s)[1]
            libelle = LIBELLES.get(s[1], s[1])
            with st.expander(f"✅ {libelle} — {s[2] or '(sans titre)'} ({s[9]}) — déjà dans {_tbl}"):
                if s[3]:
                    st.markdown("**Texte :**")
                    st.markdown(s[3])
                if st.button("✅ Marquer comme publié (sans republier)", key=f"mark_{s[0]}",
                             type="primary", use_container_width=True):
                    c.execute("""UPDATE soumissions_comm SET statut='publie',
                                 date_decision=?, auteur_decision=? WHERE id=?""",
                              (datetime.now().strftime("%Y-%m-%d %H:%M"),
                               "👤 diocèse — rangement « déjà publié » (rien republié)", s[0]))
                    commit_and_sync()
                    st.session_state["flash_success"] = "Rangé ! La file d'attente est exacte à nouveau. 🧹"
                    st.rerun()
        st.markdown("---")
    # ---------- v7.8.8 : PUBLICATIONS PROGRAMMÉES ----------
    _programmees = []
    try:
        _programmees = c.execute("""SELECT id, type_contenu, titre, contenu_texte, image_url,
                                           fichier_url, video_url, date_evenement, lieu,
                                           date_soumission, paroisse_cible, date_publication_prevue
                                    FROM soumissions_comm WHERE statut='programme'
                                    ORDER BY date_publication_prevue ASC""").fetchall()
    except Exception:
        _programmees = []
    st.markdown(f"### 🗓️ Programmées ({len(_programmees)})")
    if not _programmees:
        st.caption("Aucune publication programmée. Utilisez « 🗓️ Programmer la publication » "
                   "dans une soumission en attente pour la diffuser à une date/heure choisie.")
    for s in _programmees:
        libelle = LIBELLES.get(s[1], s[1])
        # v7.9.2 — compte à rebours visible : l'échéance SE VOIT, et le
        # contenu ne peut pas partir avant (double verrou côté réveil).
        _j_avant, _h_avant = None, None
        try:
            _dt_prev = datetime.strptime(str(s[11]), "%Y-%m-%d %H:%M")
            _delta = _dt_prev - datetime.now()
            _j_avant = max(0, _delta.days)
            _h_avant = max(0, _delta.seconds // 3600)
        except (ValueError, TypeError):
            pass
        _cd = (f" ⏳ dans {_j_avant} j {_h_avant} h" if _j_avant is not None else "")
        with st.expander(f"🗓️ {libelle} — {s[2] or '(sans titre)'} → le {s[11]}{_cd}"):
            if s[3]:
                st.markdown("**Texte :**")
                st.markdown(s[3])
            if s[4]:
                try: st.image(s[4], width=300)
                except Exception: pass
            st.info(f"⏰ Publication automatique prévue le **{s[11]}**{_cd} "
                    "(dès qu'une page de l'application est ouverte après cette heure). "
                    "Aucun contenu ne part AVANT cette échéance.")
            ca, cb = st.columns(2)
            with ca:
                if st.button("▶️ Publier maintenant", key=f"pnow_{s[0]}",
                             type="primary", use_container_width=True):
                    if publier_soumission(s):
                        c.execute("""UPDATE soumissions_comm SET statut='publie',
                                     date_decision=?, auteur_decision=? WHERE id=?""",
                                  (datetime.now().strftime("%Y-%m-%d %H:%M"),
                                   "👤 diocèse — clic « ▶️ Publier maintenant » (programmation annulée)", s[0]))
                        commit_and_sync()
                        _notifier(s, "publie")
                        st.session_state["flash_success"] = "Contenu publié immédiatement (programmation annulée). ✅"
                        st.rerun()
                    else:
                        st.error("Publication impossible (contenu incomplet). Utilisez « ↩️ Revenir en attente » puis corrigez ou refusez.")
            with cb:
                if st.button("↩️ Revenir en attente", key=f"patt_{s[0]}", use_container_width=True):
                    c.execute("UPDATE soumissions_comm SET statut='attente', date_publication_prevue=NULL WHERE id=?", (s[0],))
                    commit_and_sync()
                    st.session_state["flash_success"] = "Programmation annulée — la soumission est de retour dans la file d'attente."
                    st.rerun()

    st.markdown("---")
    st.markdown("### 📔 Historique des décisions")
    historique = c.execute("""SELECT id, type_contenu, titre, statut, motif_refus, date_soumission,
                                     date_decision, auteur_decision
                              FROM soumissions_comm WHERE statut IN ('publie','refuse')
                              ORDER BY id DESC LIMIT 30""").fetchall()
    if not historique:
        st.caption("Aucune décision pour l'instant.")
    for h in historique:
        libelle = LIBELLES.get(h[1], h[1])
        marqueur = "✅" if h[3] == "publie" else "❌"
        # v7.9.2 — la décision est DATÉE et SIGNÉE : on voit si la publication
        # a été faite au clic du diocèse ou à l'échéance programmée.
        _detail_dec = ""
        if h[3] == "publie" and (h[6] or h[7]):
            _detail_dec = " — publiée le " + (h[6] or "?")
            if h[7]:
                _detail_dec += " · " + str(h[7])
        with st.expander(f"{marqueur} {libelle} — {h[2] or '(sans titre)'} ({h[5]})"):
            if h[3] == "publie":
                st.write("Décision : **publiée**" + _detail_dec)
            else:
                st.write("Décision : **refusée**")
                if h[4]:
                    st.error("Motif : " + h[4])

    # --- v7.8.5 : la « 🕯️ Gestion du thème » quitte le SAS ---
    st.markdown("---")
    st.caption("🕯️ Le feuillet mensuel en Équipe (ex-zone 2️⃣ bis) est désormais géré par le "
               "Service Communication (onglet 🕯️ Thème pastoral). Les zones « thème de "
               "l'année », « 12 sous-thèmes mensuels » et « liens des 20 mystères » sont "
               "retirées : le contenu du mois est porté par le feuillet.")

    # --- 🧪 TEST DE NOTIFICATION TELEGRAM (v7.6.6, replacé ici v7.8.5) ---
    st.markdown("---")
    with st.expander("🧪 Test de notification Telegram"):
        st.caption("Vérifie que les messages « soumission » et « publication » repartent bien.")
        if st.button("📨 Envoyer un message de test", key="test_telegram"):
            if envoyer_notification_telegram("🧪 Message de test — notifications des Équipes du Rosaire ✅"):
                st.success("Message envoyé ! Regardez votre Telegram. 📲")
            else:
                st.error("Échec. Vérifiez (1) les secrets TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID "
                         "(Streamlit Cloud → Manage app → Settings → Secrets) et (2) les logs "
                         "(Manage app → Logs) : le motif exact de l'échec y est désormais écrit.")
