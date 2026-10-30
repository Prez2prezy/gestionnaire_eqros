# ====================================================================
# views/view_diocese.py — VERSION 4.0 (reconstruction une pièce)
# Base : la version riche validée (messages flash, clés composites,
# re-SELECT Turso, PDF Cloudinary, nettoyage Cloudinary, bandes défilantes,
# graphe Fréquentation) + les acquis de session (WhatsApp responsables +
# expédition, QR paroissial dans Gérer paroisses, sceau Communication en
# onglet, migrations douces, Voir diocèse enrichi).
# RECADRAGE UTILISATEUR : « ➕ Publier du contenu » SUPPRIMÉ — tout contenu
# spirituel passe par la cellule Communication (prépare) et le sceau du
# diocèse (valide). Bandes défilantes = onglet dédié du diocèse.
# Marqueurs : Ctrl+F → "VERSION 4.0", "gerer_qr_paroissiaux" absent,
# "show_validation_communication" présent.
# ====================================================================
import os
import shutil
import html
import streamlit as st
import pandas as pd
import io
from datetime import date
# v7.9.10 — LA ZONE DU JOUR DÉMÉNAGE : « Les intentions c'est une affaire
# des paroisses et de ses équipes. » L'écran vit désormais dans
# view_paroisse.py (🙏 Coins des Intentions / 📌 Suivi et Agenda - Paroisse).
# v7.10.3 — LA RÉSERVE AUSSI : « les intentions, c'est une affaire de
# paroisse, de ses membres et visiteurs — le diocèse n'a rien à voir
# dedans. » La rubrique de réserve quitte ce menu ; la réserve vit dans la
# vue paroisse et dans les équipes, comme la Zone du jour depuis la v7.9.10.
from database import (c, commit_and_sync, safe_migrate,
                      feuillet_questionnaire_soumission,
                      feuillet_questionnaire_existe,
                      feuillet_questions_lister)
from services import (hash_password, generer_mot_de_passe, safe_date, afficher_situation,
                      exporter_excel_diocese, periode_affichage, get_periode_pastorale,
                      supprimer_photo, afficher_messages_flash, lien_whatsapp, URL_ESPACE_SPIRITUEL,
                      synchroniser_menu_session, lire_menu_session,
                      urls_galerie, supprimer_photos_galerie, sauvegarder_illustration,
                      sauvegarder_photo_locale)
from components import (ajouter_evenement_agenda, afficher_agenda_complet_universel,
                        afficher_whatsapp_tabs, afficher_historique_paroisse,
                        afficher_etat_presences_paroisse, _qrcode_png_bytes,
                        afficher_reponses_questionnaire_feuillet)


def _gestionnaire_archives_espace(texte_intro, types_contenus, prefixe):
    """v7.6.7 — Gestionnaire à coches réutilisable : liste les contenus des
    types donnés et permet une suppression MULTIPLE avec confirmation.
    Utilisé par les onglets « Prières 🙏 / Méditations 📖 » et « Musiques 🎵 »."""
    st.caption(texte_intro)
    _ph = ",".join("?" * len(types_contenus))
    _lignes = c.execute(f"""SELECT id, type_contenu, titre, date_publication, image_url, fichier_url, paroisse_cible
                            FROM espace_spirituel
                            WHERE type_contenu IN ({_ph})
                            ORDER BY type_contenu, date_publication DESC, id DESC""", types_contenus).fetchall()
    if not _lignes:
        st.info("Aucun élément dans cette catégorie.")
        return
    st.caption(f"📋 {len(_lignes)} élément(s).")
    _paroisses_map = {p[0]: p[1] for p in c.execute("SELECT id, nom FROM paroisses").fetchall()}
    _icone = {"priere": "🙏", "meditation": "📖", "audio": "🎵", "actualite": "📰"}
    _cochees = []
    for cont in _lignes:
        _cible_lbl = f" 🏘️ {_paroisses_map[cont[6]]}" if cont[6] and cont[6] in _paroisses_map else ""
        c_chk, c_txt = st.columns([1, 12])
        with c_chk:
            _coche = st.checkbox("", key=f"chk_{prefixe}_{cont[0]}")
        with c_txt:
            st.write(f"{_icone.get(cont[1], '📌')} **{cont[2] or '(sans titre)'}** — *{cont[1]}* · {cont[3]}{_cible_lbl}")
        if _coche:
            _cochees.append(cont)
    if not _cochees:
        st.session_state.pop(f"confirm_sup_{prefixe}", None)
    elif not st.session_state.get(f"confirm_sup_{prefixe}"):
        st.warning(f"⚠️ {len(_cochees)} élément(s) sélectionné(s) pour suppression.")
        if st.button("🗑️ Supprimer la sélection…", key=f"btn_sup_{prefixe}", type="primary"):
            st.session_state[f"confirm_sup_{prefixe}"] = True
            st.rerun()
    else:
        st.error("🔴 CONFIRMATION — les éléments cochés seront supprimés DÉFINITIVEMENT :")
        for cont in _cochees:
            st.write(f"• {_icone.get(cont[1], '📌')} {cont[2] or '(sans titre)'} ({cont[1]})")
        c_ok, c_ann, _r = st.columns([1.6, 1, 3])
        with c_ok:
            if st.button("✅ Oui, supprimer définitivement", key=f"btn_sup_{prefixe}_ok", type="primary"):
                for cont in _cochees:
                    for url in (cont[4], cont[5]):
                        if url and url.startswith("http"):
                            supprimer_photo(url)
                _ids = [x[0] for x in _cochees]
                _ph_del = ",".join("?" * len(_ids))
                c.execute(f"DELETE FROM espace_spirituel WHERE id IN ({_ph_del})", _ids)
                commit_and_sync()
                for cont in _cochees:
                    st.session_state.pop(f"chk_{prefixe}_{cont[0]}", None)
                st.session_state.pop(f"confirm_sup_{prefixe}", None)
                st.session_state["flash_success"] = f"{len(_ids)} élément(s) supprimé(s). 🗑️"
                st.rerun()
        with c_ann:
            if st.button("❌ Annuler", key=f"btn_sup_{prefixe}_non"):
                st.session_state.pop(f"confirm_sup_{prefixe}", None)
                st.rerun()

def _gestionnaire_archives_galerie():
    """v7.9.2 — ARCHIVE de la Galerie + APRÈS publication : l'onglet
    « 🖼️ Galerie + » de « 📋 Contenu existant » (entre « 🙏 Prières /
    📖 Méditations » et « 🎵 Musiques »). Même mécanique à coches avec
    confirmation que les onglets voisins — la photo distante (Cloudinary /
    imgbb) est supprimée avec l'entrée."""
    st.caption("Archive de la rubrique « 🖼️ Galerie + » de l'Espace de Prière — "
               "les Souvenirs 🏞️ et Témoignages 💬 publiés. Cochez puis supprimez "
               "en un seul clic (avec confirmation).")
    _vue_gal_a = st.radio("Sous-rubrique", ["🏞️ Souvenirs", "💬 Témoignages"],
                          key="dio_galerie_arch", horizontal=True,
                          label_visibility="collapsed")
    _rub_gal_a = "souvenirs" if _vue_gal_a.startswith("🏞") else "temoignages"
    _lignes = c.execute("""SELECT id, rubrique, titre, texte, image_url, date_event,
                                  lieu, auteur_nom, date_publication
                           FROM galerie_plus WHERE rubrique=?
                           ORDER BY COALESCE(date_event, date_publication) DESC, id DESC""",
                        (_rub_gal_a,)).fetchall()
    if not _lignes:
        st.info("Aucun élément publié dans cette sous-rubrique.")
        return
    st.caption(f"📋 {len(_lignes)} élément(s) publié(s).")
    _cochees = []
    for (gid, grub, gtitre, gtxt, gimg, gdevt, glieu, gauteur, gdpub) in _lignes:
        _d_aff = gdevt or gdpub
        c_chk, c_txt = st.columns([1, 12])
        with c_chk:
            _coche = st.checkbox("", key=f"chk_gal_{gid}")
        with c_txt:
            st.write(f"{'🏞️' if _rub_gal_a == 'souvenirs' else '💬'} **{gtitre or '(sans titre)'}**"
                     f" — {_d_aff or 'sans date'}"
                     + (f" · 📍 {glieu}" if glieu else "")
                     + (f" · ✍️ {gauteur}" if gauteur else ""))
        if _coche:
            _cochees.append((gid, gtitre, gimg))
    if not _cochees:
        st.session_state.pop("confirm_sup_gal", None)
    elif not st.session_state.get("confirm_sup_gal"):
        st.warning(f"⚠️ {len(_cochees)} élément(s) sélectionné(s) pour suppression.")
        if st.button("🗑️ Supprimer la sélection…", key="btn_sup_gal", type="primary"):
            st.session_state["confirm_sup_gal"] = True
            st.rerun()
    else:
        st.error("🔴 CONFIRMATION — les éléments cochés seront supprimés DÉFINITIVEMENT "
                 "(et retirés de l'Espace de Prière) :")
        for (gid, gtitre, gimg) in _cochees:
            st.write(f"• 🖼️ {gtitre or '(sans titre)'}")
        c_ok, c_ann, _r = st.columns([1.6, 1, 3])
        with c_ok:
            if st.button("✅ Oui, supprimer définitivement", key="btn_sup_gal_ok", type="primary"):
                for (gid, gtitre, gimg) in _cochees:
                    # v7.9.18 — TOUTES les photos de l'entrée (une entrée peut
                    # en porter plusieurs depuis la v7.9.18)
                    supprimer_photos_galerie(gimg)
                _ids = [x[0] for x in _cochees]
                _ph_del = ",".join("?" * len(_ids))
                c.execute(f"DELETE FROM galerie_plus WHERE id IN ({_ph_del})", _ids)
                commit_and_sync()
                for (gid, gtitre, gimg) in _cochees:
                    st.session_state.pop(f"chk_gal_{gid}", None)
                st.session_state.pop("confirm_sup_gal", None)
                st.session_state["flash_success"] = f"{len(_ids)} élément(s) retiré(s) de la Galerie +. 🗑️"
                st.rerun()
        with c_ann:
            if st.button("❌ Annuler", key="btn_sup_gal_non"):
                st.session_state.pop("confirm_sup_gal", None)
                st.rerun()


# ====================================================================
# v7.10.4 — L'ONGLET « 🕯️ THÈME » DE « 📋 CONTENU EXISTANT »
# La gestion APRÈS publication du feuillet mensuel et de son questionnaire.
# « Une fois publié, où s'affiche le questionnaire ? » — sous le feuillet, en
# Vue d'ensemble (membres et visiteurs y répondent). « Où vont les réponses,
# qui les voit ? » — elles s'assemblent ICI, question par question, mois par
# mois, pour la cellule et le diocèse seuls : côté fidèles, chacun ne
# retrouve que les siennes. La parution reste au SAS ; les retouches de
# questions restent en « 1 Bis. » (📡 Communication).
# ====================================================================
_MOIS_PASTORAUX_CAP = ["Septembre", "Octobre", "Novembre", "Décembre", "Janvier",
                       "Février", "Mars", "Avril", "Mai", "Juin", "Juillet",
                       "Août"]


def _gestionnaire_theme_publie():
    """v7.10.4 — l'onglet « 🕯️ Thème » de « 📋 Contenu existant » : l'état du
    mois (feuillet + questionnaire), les questions telles que les fidèles les
    voient, et la lecture des réponses reçues (carnet Excel compris)."""
    st.caption("Le feuillet du mois et son questionnaire APRÈS publication : "
               "ce que voient les fidèles, les questions telles que parues et "
               "les réponses reçues — mois par mois, feuillet du moment comme "
               "mois passés. Les retouches de questions se font dans « 📡 "
               "Communication » (zone « 1 Bis. ») ; la parution reste au SAS.")

    # ── les mois connus : feuillets publiés + mois portant un questionnaire ──
    _mois_connus = {}
    try:
        for (a, m, num, dp) in c.execute(
                """SELECT annee_debut, mois, numero, date_publication
                   FROM feuillets_publications""").fetchall():
            _mois_connus[(int(a), int(m))] = {"numero": num,
                                              "date_publication": dp}
    except Exception:
        pass
    try:
        for (a, m) in c.execute(
                """SELECT DISTINCT annee_debut, mois FROM feuillet_questions"""
        ).fetchall():
            # marqueur explicite (un dict vide serait faux) : ce mois porte
            # un questionnaire même sans feuillet publié
            _mois_connus.setdefault((int(a), int(m)),
                                    {"questionnaire": True})
    except Exception:
        pass
    _an_cour, _deb, _fin = get_periode_pastorale()
    _mois_cour = ((date.today().month - 9) % 12) + 1
    _mois_connus.setdefault((_an_cour, _mois_cour), {})

    if not _mois_connus:
        st.info("Aucun mois du thème à relire pour le moment.")
        return
    _cles = sorted(_mois_connus.keys(), key=lambda t: (t[0], t[1]),
                   reverse=True)
    _libelles = []
    for (a, m) in _cles:
        _inf = _mois_connus[(a, m)]
        _civ = a if m <= 4 else a + 1
        _lbl = ("N° " + str(_inf.get("numero") or m) + " — "
                + _MOIS_PASTORAUX_CAP[m - 1] + " " + str(_civ))
        _etq = []
        if _inf.get("date_publication"):
            _etq.append("📖 feuillet publié")
        # v7.11.0 — l'étiquette « 📝 questionnaire » ne se pose que sur les
        # mois qui PORTENT un questionnaire (questions ou soumission) —
        # avant, tous les mois la portaient, même sans rien à relire.
        try:
            _a_q = bool(_inf.get("questionnaire")) or \
                bool(feuillet_questionnaire_existe(a, m)) or \
                bool(feuillet_questionnaire_soumission(a, m))
        except Exception:
            _a_q = bool(_inf.get("questionnaire"))
        if _a_q:
            _etq.append("📝 questionnaire")
        if a == _an_cour and m == _mois_cour:
            _etq.append("⭐ mois en cours")
        _libelles.append(_lbl + ((" · " + " · ".join(_etq)) if _etq else ""))
    _choix = st.selectbox("Mois à relire", _libelles, key="dio_theme_mois")
    _an, _mo = _cles[_libelles.index(_choix)]
    _inf_mois = _mois_connus[(_an, _mo)]
    _civ = _an if _mo <= 4 else _an + 1

    st.markdown("### 🕯️ N° " + str(_inf_mois.get("numero") or _mo) + " — "
                + _MOIS_PASTORAUX_CAP[_mo - 1] + " " + str(_civ))

    # ── 1. ce que voient les fidèles : le feuillet ────────────────────────
    _dp = safe_date(_inf_mois.get("date_publication")) \
        if _inf_mois.get("date_publication") else None
    if _dp:
        st.success("📖 Le feuillet de ce mois est publié (le "
                   + _dp.strftime("%d/%m/%Y") + ") — il se lit dans l'Espace "
                   "de Prière, 🕯️ Thème → 🔭 Vue d'ensemble.")
    else:
        st.info("📖 Pas de feuillet publié pour ce mois.")

    # ── 2. le questionnaire : son état de parution ────────────────────────
    _soum = feuillet_questionnaire_soumission(_an, _mo)
    _statut = _soum[1] if _soum else None
    _qs_act = feuillet_questions_lister(_an, _mo, True)
    if _statut == "publie":
        _dpub = safe_date(_soum[4]) if _soum[4] else None
        st.success("📝 Le questionnaire paraît aux fidèles, juste sous le "
                   "feuillet (validé"
                   + (f" le {_dpub.strftime('%d/%m/%Y')}" if _dpub else "")
                   + ") — membres et visiteurs y répondent, et le retrouvent "
                   "à la FIN de la lecture du livret, à chaque relecture.")
    elif _statut == "attente":
        st.info("🟡 Questionnaire soumis — en attente de la validation du "
                "diocèse (SAS). Les fidèles ne le voient pas encore.")
    elif _statut == "programme":
        st.info("🗓️ Parution du questionnaire programmée pour le "
                f"**{_soum[5] or '?'}**.")
    elif _statut == "refuse":
        st.error("❌ Questionnaire non retenu"
                 + (f" — Motif : {_soum[2]}" if _soum[2] else "")
                 + ". Les retouches se font en « 1 Bis. » puis resoumission.")
    else:
        st.info("📝 Pas de questionnaire pour ce mois (ou jamais soumis).")

    # ── 3. les questions telles que les fidèles les voient ────────────────
    if _qs_act:
        st.markdown("#### 📝 Les questions telles que parues ("
                    + str(len(_qs_act)) + ")")
        for (_qid, _ord, _q_txt, _t, _ch, _ob, _ac) in _qs_act:
            _badge = ("✍️ Texte" if _t == "texte"
                      else "🔘 Oui/Non" if _t == "oui_non" else "🔠 Choix")
            st.write("🗨️ **Q" + str(_ord) + ".** " + _q_txt
                     + "  ·  *" + _badge + "*"
                     + ("  ·  obligatoire" if _ob else ""))
        st.caption("Pour retoucher, réordonner ou retirer une question : "
                   "« 📡 Communication » → zone « 1 Bis. Le questionnaire du "
                   "feuillet ».")

    # ── 4. les réponses reçues : ici et nulle part ailleurs ───────────────
    st.markdown("#### 👀 Les réponses données")
    st.caption("Qui les voit ? La cellule Communication et VOUS, dans cet "
               "onglet — jamais les fidèles entre eux : chacun ne retrouve "
               "que SES réponses (elles l'attendent dans le formulaire, il "
               "peut les corriger). Elles demeurent ici mois après mois, et "
               "le carnet les emporte à tout moment.")
    afficher_reponses_questionnaire_feuillet(_an, _mo,
                                             prefixe_cle="dio_theme")


def _galerie_plus_saisie():
    """v7.9.2 — SAISIE / PUBLICATION de la Galerie + : l'onglet
    « 🖼️ Galerie + » de « 📡 Communication » (le menu autonome du diocèse
    disparaît ; la saisie rejoint le Service Communication, l'archive
    après publication rejoint « 📋 Contenu existant »).
    2 sous-rubriques : « 🏞️ Souvenirs » (photos des évènements) et
    « 💬 Témoignages » (grâces reçues). Toute la communauté lit."""
    st.caption("La rubrique « 🖼️ Galerie + » de l'Espace de Prière accueille 2 sous-rubriques : "
               "**🏞️ Souvenirs** (les photos de notre marche ensemble — pèlerinages, prières "
               "mensuelles, moments d'équipe) et **💬 Témoignages** (les grâces reçues, avec "
               "l'accord de ceux qui les vivent). Vous publiez ici ; la communauté lit là.")
    _vue_gal = st.radio("Sous-rubrique", ["🏞️ Souvenirs", "💬 Témoignages"],
                        key="dio_galerie_vue", horizontal=True, label_visibility="collapsed")
    _rub_gal = "souvenirs" if _vue_gal.startswith("🏞") else "temoignages"

    with st.form("form_galerie_plus", clear_on_submit=False):
        _g_gen = st.session_state.get("gal_gen", 0)
        _t_gal = st.text_input("Titre *", key=f"gal_t_{_g_gen}",
                               placeholder="Ex : Pèlerinage diocésain à Assinie"
                               if _rub_gal == "souvenirs" else
                               "Ex : Guérison de mon fils après 3 ans de prière")
        _c_gal1, _c_gal2 = st.columns(2)
        with _c_gal1:
            _d_gal = st.date_input("Date de l'évènement (optionnelle)", value=None,
                                   min_value=date(2015, 1, 1), max_value=date.today(),
                                   key=f"gal_d_{_g_gen}")
            _l_gal = st.text_input("Lieu (optionnel)", placeholder="Ex : Assinie-Mafia",
                                   key=f"gal_l_{_g_gen}")
        with _c_gal2:
            _a_gal = st.text_input("Signé par (optionnel)",
                                   placeholder="Ex : Équipe Sainte Marie" if _rub_gal == "souvenirs"
                                   else "Ex : Marie, paroisse Saint-Joseph",
                                   key=f"gal_a_{_g_gen}")
            _i_gal = st.text_input("…ou collez un LIEN de photo (imgbb…)",
                                   placeholder="https://i.ibb.co/…",
                                   key=f"gal_i_{_g_gen}")
            # v7.9.19 — LE « + » À CÔTÉ DU CHAMP LIEN : chaque clic ajoute un
            # champ de lien supplémentaire, pour joindre d'autres photos déjà
            # en ligne (imgbb…) à la même carte.
            _n_liens = int(st.session_state.get("gal_nb_liens", 0) or 0)
            _liens_sup = []
            for _k_l in range(1, _n_liens + 1):
                _liens_sup.append(st.text_input(
                    "LIEN de photo " + str(_k_l + 1),
                    placeholder="https://i.ibb.co/…",
                    key=f"gal_lien_sup_{_k_l}"))
            _bplus_gal, _bmoins_gal = st.columns(2)
            with _bplus_gal:
                _plus_gal = st.form_submit_button("➕ Ajouter un champ photo",
                                                  width="stretch")
            with _bmoins_gal:
                _moins_gal = (st.form_submit_button("➖ Un champ de moins",
                                                    width="stretch")
                              if _n_liens else False)
        # v7.9.18 — TÉLÉVERSEMENT DIRECT de plusieurs photos en un seul
        # envoi (demande : Souvenirs / Témoignages). v7.9.19 — PLUS D'ÉCHEC
        # QUI BLOQUE : si l'hébergement d'images (Cloudinary) n'est pas
        # configuré ou indisponible, chaque photo est rangée DANS
        # L'APPLICATION (static/galerie/…) et s'affiche exactement pareil ;
        # le champ lien ci-dessus reste accepté pour une photo déjà en ligne.
        _f_gal = st.file_uploader(
            "📷 Téléverser une ou plusieurs photos (facultatif — JPG/PNG/WebP)",
            accept_multiple_files=True, type=["jpg", "jpeg", "png", "webp"],
            key=f"gal_upload_multi_{_g_gen}")
        if _f_gal:
            st.caption("📷 " + str(len(_f_gal)) + " photo(s) prête(s) : "
                       + ", ".join(f.name for f in _f_gal[:6])
                       + (" …" if len(_f_gal) > 6 else ""))
        _x_gal = st.text_area("Texte" + (" *" if _rub_gal == "temoignages" else " (optionnel)"),
                              height=110, key=f"gal_x_{_g_gen}",
                              placeholder="Un mot qui raconte le moment…" if _rub_gal == "souvenirs"
                              else "Racontez la grâce reçue, avec sobriété et reconnaissance…")
        if _plus_gal:
            st.session_state["gal_nb_liens"] = min(_n_liens + 1, 9)
            st.rerun()
        if _moins_gal:
            st.session_state["gal_nb_liens"] = max(_n_liens - 1, 0)
            st.rerun()
        if st.form_submit_button("📢 Publier dans la Galerie +", type="primary", width="stretch"):
            if not _t_gal.strip() or (_rub_gal == "temoignages" and not _x_gal.strip()):
                st.error("Titre requis (et, pour un témoignage, le texte aussi).")
            elif _i_gal.strip() and not _i_gal.strip().startswith("http"):
                st.error("Le lien de la photo doit commencer par https://")
            else:
                # v7.9.18 — rassembler les photos : téléversées D'ABORD
                # (l'ordre de l'album suit l'ordre des fichiers choisis),
                # puis le(s) lien(s) collé(s) éventuel(s).
                _urls_gal = []
                if _f_gal:
                    for _f in _f_gal:
                        try:
                            _u_env = sauvegarder_illustration(_f)
                        except Exception:
                            _u_env = None
                        if not _u_env:
                            # v7.9.19 — l'hébergeur est absent ou injoignable :
                            # la photo est reçue quand même, rangée dans
                            # l'application (static/galerie/…).
                            try:
                                _u_env = sauvegarder_photo_locale(_f)
                            except Exception:
                                _u_env = None
                        if _u_env:
                            _urls_gal.append(_u_env)
                    if not _urls_gal:
                        st.error("Aucune photo n'a pu être enregistrée (ni hébergement "
                                 "d'images, ni rangement local). Vérifiez la connexion "
                                 "et les droits du dossier « static » ; sinon utilisez "
                                 "un lien imgbb dans le champ « LIEN de photo ».")
                        st.stop()
                    elif len(_urls_gal) < len(_f_gal):
                        st.warning(str(len(_f_gal) - len(_urls_gal))
                                   + " photo(s) n'ont pas pu être enregistrées ; "
                                     "les autres sont publiées.")
                if _i_gal.strip().startswith("http"):
                    _urls_gal.append(_i_gal.strip())
                for _ls in _liens_sup:
                    if _ls and str(_ls).strip().startswith("http"):
                        _urls_gal.append(str(_ls).strip())
                _stock_gal = " | ".join(_urls_gal) if _urls_gal else None
                c.execute("""INSERT INTO galerie_plus
                             (rubrique, titre, texte, image_url, date_event, lieu,
                              auteur_nom, date_publication)
                             VALUES (?,?,?,?,?,?,?,?)""",
                          (_rub_gal, _t_gal.strip(), _x_gal.strip() or None,
                           _stock_gal,
                           _d_gal.isoformat() if _d_gal else None,
                           _l_gal.strip() or None, _a_gal.strip() or None,
                           date.today().isoformat()))
                commit_and_sync()
                _n_photos = len(urls_galerie(_stock_gal or ""))
                st.session_state["flash_success"] = (
                    "✅ Publié dans « 🖼️ Galerie + → "
                    + ("🏞️ Souvenirs" if _rub_gal == "souvenirs" else "💬 Témoignages")
                    + " » (" + str(_n_photos) + " photo(s)) — visible immédiatement "
                      "dans l'Espace de Prière.")
                # les champs renaissent propres (génération suivante), y
                # compris les champs de lien ajoutés par le +
                st.session_state["gal_gen"] = _g_gen + 1
                st.session_state.pop("gal_nb_liens", None)
                st.rerun()

    _publies = c.execute("""SELECT id, titre, image_url, date_event, lieu, auteur_nom, date_publication
                            FROM galerie_plus WHERE rubrique=?
                            ORDER BY COALESCE(date_event, date_publication) DESC, id DESC""",
                         (_rub_gal,)).fetchall()
    st.markdown("---")
    _lbl_gal = "🏞️ Souvenirs publiés" if _rub_gal == "souvenirs" else "💬 Témoignages publiés"
    st.markdown(f"#### {_lbl_gal} ({len(_publies)})")
    if not _publies:
        st.info("Aucun élément publié pour l'instant dans cette sous-rubrique.")
    for (gid, gtitre, gimg, gdevt, glieu, gauteur, gdpub) in _publies:
        _c_txt, _c_btn = st.columns([10, 2])
        with _c_txt:
            _d_aff = gdevt or gdpub
            _n_gal = len(urls_galerie(gimg or ""))
            st.write(f"📌 **{gtitre}** — {_d_aff or 'sans date'}"
                     + (f" · 📍 {glieu}" if glieu else "")
                     + (f" · ✍️ {gauteur}" if gauteur else ""))
            if gimg:
                # v7.9.18 — une entrée peut porter plusieurs photos
                st.caption("🖼️ " + (str(_n_gal) + " photos"
                                    if _n_gal > 1 else str(gimg)))
        with _c_btn:
            if st.button("🗑️", key=f"gal_del_{gid}"):
                supprimer_photos_galerie(gimg)
                c.execute("DELETE FROM galerie_plus WHERE id=?", (gid,))
                commit_and_sync()
                st.session_state["flash_success"] = "Élément retiré de la Galerie +. 🗑️"
                st.rerun()


def show_diocese():
    d_info = c.execute("SELECT nom, responsable, bureau FROM diocese WHERE id=?", (1,)).fetchone()
    nom_dio = d_info[0] if d_info else "Diocèse"

    # Migrations douces (idempotentes, silencieuses) — v7.6.6 : via safe_migrate
    # (connexion jetable), même principe que database.py et le SAS.
    try:
        c.execute("SELECT whatsapp_responsable FROM paroisses LIMIT 1")
    except Exception:
        safe_migrate("ALTER TABLE paroisses ADD COLUMN whatsapp_responsable TEXT")
    try:
        c.execute("SELECT whatsapp_responsable FROM diocese LIMIT 1")
    except Exception:
        safe_migrate("ALTER TABLE diocese ADD COLUMN whatsapp_responsable TEXT")

    _rubriques_dio = [
        "🏛️ Voir diocèse", "🏘️ Créer paroisses", "📋 Gérer paroisses",
        "📅 Abonnements", "📌 Suivi", "🕊️ Espace spirituel", "💬 WhatsApp",
        "🔍 Rechercher matricule", "🔐 Gérer les accès", "📊 Statistiques", "📥 Export Excel",
        "📦 Archives", "🗑️ Réinitialiser"
    ]
    # Session neuve (F5) : restituer la rubrique mémorisée AVANT de dessiner
    # le menu — sinon il retombe sur la 1ʳᵉ entrée et efface la mémoire.
    if "nav_dio" in st.session_state and st.session_state["nav_dio"] not in _rubriques_dio:
        del st.session_state["nav_dio"]
    if "nav_dio" not in st.session_state:
        _rub = lire_menu_session()
        if _rub and _rub in _rubriques_dio:
            st.session_state["nav_dio"] = _rub
            st.session_state["_menu_sync"] = _rub
    menu = st.sidebar.radio("Navigation", _rubriques_dio, key="nav_dio")
    synchroniser_menu_session(menu)

    if menu == "🏛️ Voir diocèse":
        st.markdown(f'<h2 style="color:#1A237E; font-size: 1.4rem;">🏛️ {html.escape(nom_dio).upper()}</h2>', unsafe_allow_html=True)
        afficher_messages_flash()
        if d_info:
            _wa_dio_actuel = ""
            try:
                _row_dio = c.execute("SELECT whatsapp_responsable FROM diocese WHERE id=?", (1,)).fetchone()
                if _row_dio and _row_dio[0]:
                    _wa_dio_actuel = _row_dio[0]
            except Exception:
                pass
            st.markdown(f'<div class="custom-info-box"><b>Responsable diocésain :</b> {html.escape(d_info[1] or "")}<br><b>Bureau diocésain :</b> {html.escape(d_info[2] or "")}<br><b>📱 WhatsApp :</b> {_wa_dio_actuel or "Non renseigné"}</div>', unsafe_allow_html=True)
            with st.expander("✏️ Modifier les informations"):
                with st.form("form_edit_dio"):
                    c_ed1, c_ed2 = st.columns(2)
                    with c_ed1:
                        nr = st.text_input("Nouveau responsable", value=d_info[1] or "")
                        _wa_dio = st.text_input("📱 WhatsApp du responsable diocésain", value=_wa_dio_actuel)
                    with c_ed2:
                        nb = st.text_area("Nouveau bureau", value=d_info[2] or "")
                    if st.form_submit_button("💾 Enregistrer", width="stretch"):
                        c.execute("UPDATE diocese SET responsable=?, bureau=? WHERE id=?", (nr, nb, 1))
                        c.execute("UPDATE diocese SET whatsapp_responsable=? WHERE id=?", (_wa_dio.strip() or None, 1))
                        commit_and_sync()
                        st.session_state["flash_success"] = "Mis à jour ! ✅"
                        st.rerun()

    elif menu == "🏘️ Créer paroisses":
        st.markdown('<h2 style="color:#1A237E;">🏘️ Créer une paroisse</h2>', unsafe_allow_html=True)
        afficher_messages_flash()

        with st.form("creer_paroisse"):
            c1, c2 = st.columns(2)
            with c1:
                nom = st.text_input("Nom de la paroisse")
                commune = st.text_input("Commune")
                responsable = st.text_input("Responsable")
                wa_resp = st.text_input("📱 WhatsApp du responsable (ex. 0700000000)")
            with c2:
                ville = st.text_input("Ville")
                bureau = st.text_area("Bureau")
            if st.form_submit_button("🏘️ Créer", width="stretch"):
                if nom and commune and ville and responsable:
                    if c.execute("SELECT id FROM paroisses WHERE nom=? AND commune=? AND ville=?", (nom.strip(), commune.strip(), ville.strip())).fetchone():
                        st.error("❌ Cette paroisse existe déjà !")
                    else:
                        c.execute("INSERT INTO paroisses (nom, commune, ville, responsable, bureau, whatsapp_responsable, diocese_id) VALUES (?,?,?,?,?,?,?)",
                                  (nom.strip(), commune.strip(), ville.strip(), responsable.strip(), bureau, wa_resp.strip() or None, 1))
                        # re-SELECT plutôt que lastrowid (invalide si reconnexion Turso)
                        pid = c.execute("SELECT id FROM paroisses WHERE nom=? AND commune=? AND ville=?",
                                        (nom.strip(), commune.strip(), ville.strip())).fetchone()[0]
                        username = f"paroisse_{pid}"
                        mdp = generer_mot_de_passe()
                        c.execute("INSERT INTO utilisateurs (username, password, role, diocese_id, paroisse_id) VALUES (?,?,?,?,?)",
                                  (username, hash_password(mdp), "paroisse", 1, pid))
                        commit_and_sync()
                        st.success(f"✅ Paroisse '{nom}' créée")
                        st.markdown(f"<div style='background:#e8f5e9;padding:15px;border-radius:10px;border:1px solid #c8e6c9;'>🔑 Identifiant : <code style='color:#d84315;'>{username}</code><br>🔒 Mot de passe : <code style='color:#d84315;'>{mdp}</code></div>", unsafe_allow_html=True)
                        if wa_resp.strip():
                            _msg = ("🕊️ Bénédiction !\n\n"
                                    + "La paroisse " + nom + " est enregistrée sur le Gestionnaire des Équipes du Rosaire (Diocèse de Grand-Bassam).\n\n"
                                    + "🔐 Vos identifiants de connexion (portail gestionnaire) :\n"
                                    + "👤 Utilisateur : " + username + "\n"
                                    + "🔑 Mot de passe : " + mdp + "\n"
                                    + "🌐 Le portail : " + URL_ESPACE_SPIRITUEL + "\n\n"
                                    + "🔳 Lien signé de votre Espace communautaire (à mettre sur vos affiches — le QR correspondant se télécharge dans le gestionnaire, menu Gérer paroisses) :\n"
                                    + URL_ESPACE_SPIRITUEL + "/?espace=1&p=" + str(pid) + "\n\n"
                                    + "📿 Que le Rosaire unisse votre paroisse !")
                            _wa_link = lien_whatsapp(wa_resp, _msg)
                            st.markdown("#### 📨 Expédition des identifiants")
                            st.caption("Un clic ouvre WhatsApp avec le message prêt — envoyez-le au responsable.")
                            st.markdown(f'<a href="{_wa_link}" target="_blank" class="whatsapp-link">📱 Envoyer les identifiants au responsable</a>', unsafe_allow_html=True)
                else:
                    st.error("Tous les champs sont requis")

    elif menu == "📋 Gérer paroisses":
        _n_par = c.execute("SELECT COUNT(*) FROM paroisses").fetchone()[0]
        st.markdown('<h2 style="color:#1A237E;">📋 Consultation des paroisses — '
                    + str(_n_par) + ' paroisse(s)</h2>', unsafe_allow_html=True)
        afficher_messages_flash()

        for state in ['show_equipes', 'show_equipiers', 'show_membres_equipe']:
            if state not in st.session_state: st.session_state[state] = None

        paroisses = c.execute("SELECT id, nom, commune, ville, responsable, bureau, whatsapp_responsable FROM paroisses ORDER BY nom").fetchall()

        for p in paroisses:
            pid, nom, commune, ville, responsable, bureau, wa_resp_actuel = p
            nb_equipes = c.execute("SELECT COUNT(*) FROM equipes WHERE paroisse_id=?", (pid,)).fetchone()[0]
            nb_membres = c.execute("SELECT COUNT(*) FROM membres WHERE paroisse_id=? AND statut='actif'", (pid,)).fetchone()[0]

            with st.expander(f"🏛️ {nom} ({commune} / {ville}) - {nb_equipes} équipe(s) - {nb_membres} membre(s)"):
                st.write(f"**Responsable :** {responsable}")
                st.write(f"**Bureau :** {bureau}")

                # QR signé de CETTE paroisse (traçabilité missionnaire)
                with st.expander("🔳 QR paroissial de cette paroisse"):
                    _url_signee = f"{URL_ESPACE_SPIRITUEL}/?espace=1&p={pid}"
                    st.code(_url_signee)
                    _png = _qrcode_png_bytes(_url_signee)
                    st.image(_png, width=200)
                    st.download_button("📥 Télécharger le QR (PNG)", data=_png,
                                       file_name=f"qr_paroisse_{pid}.png",
                                       key=f"qr_dl_{pid}", width="stretch")
                    st.caption("Imprimez ce QR sur les affiches de la paroisse : chaque scan est compté à son origine (fidèle anonyme).")

                # 📱 WhatsApp du responsable (édition — le responsable peut changer)
                with st.expander("📱 WhatsApp du responsable paroissial"):
                    _wa_new = st.text_input("Numéro WhatsApp", value=wa_resp_actuel or "",
                                            key=f"wa_edit_{pid}")
                    if st.button("💾 Enregistrer le numéro", key=f"wa_save_{pid}"):
                        c.execute("UPDATE paroisses SET whatsapp_responsable=? WHERE id=?",
                                  (_wa_new.strip() or None, pid))
                        commit_and_sync()
                        st.success("Numéro WhatsApp enregistré ! ✅")

                col1, col2 = st.columns(2)
                with col1:
                    if st.button(f"👥 Voir les équipes", key=f"btn_equipes_{pid}"):
                        st.session_state['show_equipes'] = pid if st.session_state.get('show_equipes') != pid else None
                        st.session_state['show_equipiers'] = None
                        st.session_state['show_membres_equipe'] = None
                        st.rerun()
                with col2:
                    if st.button(f"👤 Voir tous les équipiers", key=f"btn_equipiers_{pid}"):
                        st.session_state['show_equipiers'] = pid if st.session_state.get('show_equipiers') != pid else None
                        st.session_state['show_equipes'] = None
                        st.session_state['show_membres_equipe'] = None
                        st.rerun()

                if st.session_state.get('show_equipes') == pid:
                    st.markdown("---")
                    equipes = c.execute("SELECT id, nom_equipe, responsable, bureau FROM equipes WHERE paroisse_id=? ORDER BY nom_equipe", (pid,)).fetchall()
                    st.markdown(f"#### 👥 Équipes de {nom} — {len(equipes)} équipe(s)")
                    if not equipes: st.info("Aucune équipe dans cette paroisse")
                    else:
                        for eq in equipes:
                            eq_id, eq_nom, eq_resp, eq_bureau = eq
                            nb_membres_eq = c.execute("SELECT COUNT(*) FROM membres WHERE equipe_id=? AND statut='actif'", (eq_id,)).fetchone()[0]
                            with st.expander(f"📌 {eq_nom} - Respo: {eq_resp} ({nb_membres_eq} membres)"):
                                st.write(f"**Bureau :** {eq_bureau}")
                                if st.button(f"📋 Voir les membres de {eq_nom}", key=f"btn_membres_eq_{eq_id}"):
                                    st.session_state['show_membres_equipe'] = eq_id if st.session_state.get('show_membres_equipe') != eq_id else None
                                    st.rerun()

                                if st.session_state.get('show_membres_equipe') == eq_id:
                                    membres_eq = c.execute("""SELECT matloc, matricule, nom, prenom, whatsapp, numero_meditation, date_adhesion
                                                            FROM membres WHERE equipe_id=? AND statut='actif' ORDER BY nom""", (eq_id,)).fetchall()
                                    if not membres_eq: st.info("Aucun membre")
                                    else:
                                        df = pd.DataFrame(membres_eq, columns=["MatLoc", "Matricule", "Nom", "Prénom", "WhatsApp", "N° méditation", "Date adhésion"])
                                        df.insert(0, "N°", range(1, len(df) + 1))
                                        st.dataframe(df, hide_index=True, width="stretch")
                                        out = io.BytesIO()
                                        with pd.ExcelWriter(out, engine='openpyxl') as w: df.to_excel(w, index=False)
                                        out.seek(0)
                                        st.download_button(f"📥 Exporter {eq_nom}", data=out, file_name=f"membres_{eq_nom}_{date.today()}.xlsx", key=f"export_eq_{eq_id}")

                if st.session_state.get('show_equipiers') == pid:
                    st.markdown("---")
                    st.markdown(f"#### 👤 Tous les équipiers de {nom}")
                    membres_paroisse = c.execute("""SELECT m.matloc, m.matricule, m.nom, m.prenom, m.whatsapp, m.numero_meditation, m.date_adhesion, e.nom_equipe
                                                    FROM membres m JOIN equipes e ON m.equipe_id = e.id
                                                    WHERE m.paroisse_id=? AND m.statut='actif' ORDER BY e.nom_equipe, m.nom""", (pid,)).fetchall()
                    if not membres_paroisse: st.info("Aucun membre actif")
                    else:
                        st.info(f"📊 Total : {len(membres_paroisse)} membre(s) actif(s)")
                        df = pd.DataFrame(membres_paroisse, columns=["MatLoc", "Matricule", "Nom", "Prénom", "WhatsApp", "N° méditation", "Date adhésion", "Équipe"])
                        df.insert(0, "N°", range(1, len(df) + 1))
                        st.dataframe(df, hide_index=True, width="stretch")
                        out = io.BytesIO()
                        with pd.ExcelWriter(out, engine='openpyxl') as w: df.to_excel(w, index=False)
                        out.seek(0)
                        st.download_button(f"📥 Exporter les équipiers de {nom}", data=out, file_name=f"equipiers_{nom}_{date.today()}.xlsx", key=f"export_par_{pid}")

    elif menu == "📅 Abonnements":
        st.markdown('<h2 style="color:#1A237E;">📅 Suivi des abonnements (Diocèse)</h2>', unsafe_allow_html=True)

        for state in ['show_paroisse_abos', 'show_equipe_abos', 'abos_view_type']:
            if state not in st.session_state: st.session_state[state] = None

        annee_pastorale_en_cours = get_periode_pastorale()[0]
        annee_debut = st.number_input("Année de début de la période", min_value=2020, max_value=annee_pastorale_en_cours, value=annee_pastorale_en_cours, step=1)
        st.write(f"**Période :** {periode_affichage(annee_debut)}")

        total_membres = c.execute("SELECT COUNT(*) FROM membres WHERE statut='actif'").fetchone()[0]
        payes = c.execute("SELECT COUNT(*) FROM abonnements WHERE annee_debut=? AND statut='paye'", (annee_debut,)).fetchone()[0]

        c1, c2 = st.columns(2)
        c1.metric("📊 Total membres actifs", total_membres)
        c2.metric("✅ Abonnements enregistrés", payes)

        taux = f"{payes/total_membres*100:.0f}%" if total_membres else "0%"
        st.caption(f"📊 **Taux de recouvrement global :** {taux}")
        st.markdown("---")

        for p in c.execute("SELECT id, nom FROM paroisses ORDER BY nom").fetchall():
            pid, nom_paroisse = p
            stats = c.execute("""SELECT COUNT(m.id) as total, SUM(CASE WHEN a.annee_debut=? AND a.statut='paye' THEN 1 ELSE 0 END) as payes
                                FROM membres m LEFT JOIN abonnements a ON m.id=a.membre_id AND a.annee_debut=?
                                WHERE m.paroisse_id=? AND m.statut='actif'""", (annee_debut, annee_debut, pid)).fetchone()
            total_par, payes_par = stats[0] or 0, stats[1] or 0
            pourcent = f"{(payes_par/total_par*100):.0f}%" if total_par > 0 else "0%"

            with st.expander(f"🏛️ {nom_paroisse} - {total_par} membre(s) - {payes_par} à jour ({pourcent})"):
                col1, col2 = st.columns(2)
                with col1:
                    if st.button(f"👥 Voir les équipes", key=f"abos_btn_equipes_{pid}"):
                        st.session_state['show_paroisse_abos'] = pid if not (st.session_state.get('show_paroisse_abos') == pid and st.session_state.get('abos_view_type') == 'equipes') else None
                        st.session_state['abos_view_type'] = 'equipes'; st.session_state['show_equipe_abos'] = None; st.rerun()
                with col2:
                    if st.button(f"👤 Voir tous les équipiers", key=f"abos_btn_membres_{pid}"):
                        st.session_state['show_paroisse_abos'] = pid if not (st.session_state.get('show_paroisse_abos') == pid and st.session_state.get('abos_view_type') == 'membres') else None
                        st.session_state['abos_view_type'] = 'membres'; st.session_state['show_equipe_abos'] = None; st.rerun()

                if st.session_state.get('show_paroisse_abos') == pid and st.session_state.get('abos_view_type') == 'equipes':
                    st.markdown("---"); st.markdown(f"#### 👥 Équipes de {nom_paroisse}")
                    for eq in c.execute("SELECT id, nom_equipe FROM equipes WHERE paroisse_id=? ORDER BY nom_equipe", (pid,)).fetchall():
                        eid, eq_nom = eq
                        stats_eq = c.execute("""SELECT COUNT(m.id) as total, SUM(CASE WHEN a.annee_debut=? AND a.statut='paye' THEN 1 ELSE 0 END) as payes
                                              FROM membres m LEFT JOIN abonnements a ON m.id=a.membre_id AND a.annee_debut=?
                                              WHERE m.equipe_id=? AND m.statut='actif'""", (annee_debut, annee_debut, eid)).fetchone()
                        total_eq, payes_eq = stats_eq[0] or 0, stats_eq[1] or 0
                        pourcent_eq = f"{(payes_eq/total_eq*100):.0f}%" if total_eq > 0 else "0%"
                        with st.expander(f"📌 {eq_nom} - {total_eq} membre(s) - {payes_eq} à jour ({pourcent_eq})"):
                            if st.button(f"📋 Voir les détails", key=f"abos_voir_eq_{eid}"):
                                st.session_state['show_equipe_abos'] = eid if st.session_state.get('show_equipe_abos') != eid else None; st.rerun()
                            if st.session_state.get('show_equipe_abos') == eid:
                                membres_eq = c.execute("""SELECT m.id, m.nom, m.prenom, m.matricule, a.type_abonnement, a.date_paiement, a.montant
                                                        FROM membres m LEFT JOIN abonnements a ON m.id=a.membre_id AND a.annee_debut=? AND a.statut='paye'
                                                        WHERE m.equipe_id=? AND m.statut='actif' ORDER BY m.nom""", (annee_debut, eid)).fetchall()
                                abonnes, reabonnes, non_inscrits = [], [], []
                                for m in membres_eq:
                                    if m[4] == 'abonnement': abonnes.append(m)
                                    elif m[4] == 'reabonnement': reabonnes.append(m)
                                    else: non_inscrits.append(m)

                                t1, t2, t3 = st.tabs(["📝 Abonnés", "🔄 Réabonnés", "❌ Non enregistrés"])
                                with t1:
                                    if abonnes:
                                        df = pd.DataFrame(abonnes, columns=["ID", "Nom", "Prénom", "Matricule", "Type", "Date", "Montant"])[["Nom", "Prénom", "Matricule", "Date", "Montant"]]
                                        df["Montant"] = df["Montant"].apply(lambda x: f"{x or 0} FCFA")
                                        st.dataframe(df, hide_index=True, width="stretch")
                                    else: st.info("Aucun abonnement enregistré")
                                with t2:
                                    if reabonnes:
                                        df = pd.DataFrame(reabonnes, columns=["ID", "Nom", "Prénom", "Matricule", "Type", "Date", "Montant"])[["Nom", "Prénom", "Matricule", "Date", "Montant"]]
                                        df["Montant"] = df["Montant"].apply(lambda x: f"{x or 0} FCFA")
                                        st.dataframe(df, hide_index=True, width="stretch")
                                    else: st.info("Aucun réabonnement enregistré")
                                with t3:
                                    if non_inscrits:
                                        for n in non_inscrits: st.write(f"- {n[1]} {n[2]} ({n[3] or '—'})")
                                    else: st.success("✅ Tous les membres sont à jour")

                if st.session_state.get('show_paroisse_abos') == pid and st.session_state.get('abos_view_type') == 'membres':
                    st.markdown("---"); st.markdown(f"#### 👤 Tous les équipiers de {nom_paroisse}")
                    membres_paroisse = c.execute("""SELECT m.id, m.nom, m.prenom, m.matricule, m.whatsapp, e.nom_equipe, a.type_abonnement, a.date_paiement, a.montant
                                                    FROM membres m JOIN equipes e ON m.equipe_id = e.id
                                                    LEFT JOIN abonnements a ON m.id=a.membre_id AND a.annee_debut=? AND a.statut='paye'
                                                    WHERE m.paroisse_id=? AND m.statut='actif' ORDER BY e.nom_equipe, m.nom""", (annee_debut, pid)).fetchall()
                    if not membres_paroisse: st.info("Aucun membre actif")
                    else:
                        abonnes_par, reabonnes_par, non_inscrits_par = [], [], []
                        for m in membres_paroisse:
                            if m[6] == 'abonnement': abonnes_par.append(m)
                            elif m[6] == 'reabonnement': reabonnes_par.append(m)
                            else: non_inscrits_par.append(m)
                        st.info(f"📊 Total : {len(membres_paroisse)} - ✅ {len(abonnes_par)} abonnés - 🔄 {len(reabonnes_par)} réabonnés - ❌ {len(non_inscrits_par)} non enregistrés")
                        t1, t2, t3 = st.tabs(["📝 Abonnés", "🔄 Réabonnés", "❌ Non enregistrés"])
                        with t1:
                            if abonnes_par:
                                df = pd.DataFrame(abonnes_par, columns=["ID", "Nom", "Prénom", "Matricule", "WhatsApp", "Équipe", "Type", "Date", "Montant"])[["Nom", "Prénom", "Matricule", "WhatsApp", "Équipe", "Date", "Montant"]]
                                df["Montant"] = df["Montant"].apply(lambda x: f"{x or 0} FCFA")
                                st.dataframe(df, hide_index=True, width="stretch")
                            else: st.info("Aucun abonnement")
                        with t2:
                            if reabonnes_par:
                                df = pd.DataFrame(reabonnes_par, columns=["ID", "Nom", "Prénom", "Matricule", "WhatsApp", "Équipe", "Type", "Date", "Montant"])[["Nom", "Prénom", "Matricule", "WhatsApp", "Équipe", "Date", "Montant"]]
                                df["Montant"] = df["Montant"].apply(lambda x: f"{x or 0} FCFA")
                                st.dataframe(df, hide_index=True, width="stretch")
                            else: st.info("Aucun réabonnement")
                        with t3:
                            if non_inscrits_par:
                                for n in non_inscrits_par: st.write(f"- {n[1]} {n[2]} ({n[3] or '—'}) - {n[5]}")
                            else: st.success("✅ Tous les membres sont à jour")

    elif menu == "📌 Suivi":
        st.markdown(f'<h2 style="color:#1A237E;">📌 Suivi et Agenda - {nom_dio}</h2>', unsafe_allow_html=True)

        # v7.8.14 — SÉLECTEUR PERSISTANT (remplace st.tabs, qui ne garde aucune
        # mémoire : chaque interaction ramenait à l'onglet primaire).
        _onglets_dio = ["📅 Agenda", "📝 Vie de prière des paroisses", "📊 Engagement spirituel"]
        _suivi_dio = st.radio("Section du suivi", _onglets_dio, key="dio_suivi_onglet",
                              horizontal=True, label_visibility="collapsed")
        st.markdown("---")
        if _suivi_dio == _onglets_dio[0]:
            ajouter_evenement_agenda(diocese_id=1, auteur_nom=st.session_state.get('username'))
            st.markdown("---")
            afficher_agenda_complet_universel(diocese_id=1)

        elif _suivi_dio == _onglets_dio[1]:
            paroisses = c.execute("SELECT id, nom, commune FROM paroisses").fetchall()
            if paroisses:
                par_dict = {f"{p[1]} ({p[2]})": p[0] for p in paroisses}
                choix_par = st.selectbox("Sélectionnez la paroisse", list(par_dict.keys()), key="suivi_hist_dio_par")
                pid_select = par_dict[choix_par]

                from services import TYPES_EVENEMENTS
                filtre_type = st.selectbox("Filtrer par type d'évènement", ["Tous"] + TYPES_EVENEMENTS, key="filtre_hist_dio")

                afficher_historique_paroisse(paroisse_id=pid_select, filtre_type=filtre_type)
            else:
                st.info("Aucune paroisse créée.")

        else:
            paroisses2 = c.execute("SELECT id, nom, commune FROM paroisses").fetchall()
            if paroisses2:
                par_dict2 = {f"{p[1]} ({p[2]})": p[0] for p in paroisses2}
                choix_par2 = st.selectbox("Sélectionnez la paroisse pour le bilan", list(par_dict2.keys()), key="etat_hist_dio_par")
                pid_select2 = par_dict2[choix_par2]

                afficher_etat_presences_paroisse(paroisse_id=pid_select2)
            else:
                st.info("Aucune paroisse créée.")

    elif menu == "🕊️ Espace spirituel":
        st.markdown('<h2 style="color:#1A237E;">🕊️ Gestion de l\'Espace Spirituel</h2>', unsafe_allow_html=True)
        st.caption("Le Service Communication prépare les contenus — VOUS seul publiez (onglet 📡). "
                   "Le thème pastoral et les bandes défilantes se gèrent ici. "
                   "Ce qui est validé rejoint l'Espace de Prière : évangélisation élargie, membres et visiteurs.")
        afficher_messages_flash()

        # v7.7 — navigation à MÉMOIRE : la sélection survit aux rechargements
        # (coches, suppressions). Les onglets simples repartaient au 1er.
        _vue_dio = st.radio("Section", ["📡 Communication", "📋 Contenu existant"],
                            key="dio_esprit_vue", horizontal=True, label_visibility="collapsed")

        if _vue_dio == "📡 Communication":
            st.caption("🕯️ Le SAS : la cellule Communication prépare et soumet — VOUS seul validez et publiez. "
                       "Chaque contenu validé rejoint sa zone dédiée de l'Espace de Prière. "
                       "v7.8.5 : le feuillet mensuel en Équipe est désormais géré par le "
                       "Service Communication (onglet 🕯️ Thème pastoral).")
            # v7.9.2 — la SAISIE de la Galerie + rejoint le Service
            # Communication (le menu autonome du diocèse disparaît) ;
            # l'archive après publication vit dans « 📋 Contenu existant ».
            _vue_comm = st.radio("Onglet", ["🕊️ Soumissions (SAS)", "🖼️ Galerie +"],
                                 key="dio_comm_vue", horizontal=True,
                                 label_visibility="collapsed")
            if _vue_comm == "🕊️ Soumissions (SAS)":
                from views.view_communication_validation import show_validation_communication
                show_validation_communication()
            else:
                _galerie_plus_saisie()

        else:
            # v7.7 — libellés déclarés UNE SEULE FOIS : le radio et les
            # comparaisons utilisent ces variables (aucun risque de décalage
            # icône/texte ou d'espace en trop).
            _LBL_BANDES = "📺 Bandes défilantes actives"
            _LBL_PM = "🙏 Prières / 📖 Méditations"
            _LBL_THEME = "🕯️ Thème"
            _LBL_GAL = "🖼️ Galerie +"
            _LBL_MU = "🎵 Musiques"
            _LBL_AUTRES = "📦 Autres contenus"
            
            # v7.9.2 — l'onglet « 🖼️ Galerie + » (archive après publication)
            # s'insère entre « 🙏 Prières / 📖 Méditations » et « 🎵 Musiques ».
            # v7.10.4 — l'onglet « 🕯️ Thème » (gestion APRÈS publication du
            # feuillet et de son questionnaire : réponses reçues…) se glisse
            # entre « 🙏 Prières / 📖 Méditations » et « 🖼️ Galerie + ».
            _vue_exist = st.radio("Catégorie",
                                  [_LBL_BANDES, _LBL_PM, _LBL_THEME, _LBL_GAL, _LBL_MU, _LBL_AUTRES],
                                  key="dio_exist_vue", horizontal=True, label_visibility="collapsed")

            if _vue_exist == _LBL_BANDES:
                st.caption("Maximum 3 bandes actives — seules les plus récentes s'affichent dans l'entête des espaces. "
                           "Les bandes sont soumises par le Service Communication puis validées au SAS (📡).")
                bandes_actives = c.execute("""SELECT id, contenu_texte, fichier_url, date_publication, paroisse_cible FROM espace_spirituel
                                              WHERE type_contenu='annonce_defilante'
                                              ORDER BY date_publication DESC, id DESC""").fetchall()
                if not bandes_actives:
                    st.info("Aucune bande défilante active.")
                else:
                    if len(bandes_actives) >= 3:
                        st.warning(f"⚠️ {len(bandes_actives)} bandes actives : seules les 3 plus récentes s'affichent dans l'entête. Supprimez les anciennes.")
                    _paroisses_map = {p[0]: p[1] for p in c.execute("SELECT id, nom FROM paroisses").fetchall()}
                    for b in bandes_actives:
                        etiquette = "🌐 Partout" if b[2] != 'membre' else "👤 Membres seuls"
                        _cible_lbl = f" • 🏘️ {_paroisses_map[b[4]]}" if b[4] and b[4] in _paroisses_map else ""
                        c_txt, c_infos, c_btn = st.columns([4, 2, 1])
                        with c_txt:
                            st.write(f"📺 {b[1]}")
                        with c_infos:
                            st.caption(f"{etiquette}{_cible_lbl} • {b[3]}")
                        with c_btn:
                            if st.button("🗑️", key=f"del_defil_{b[0]}"):
                                c.execute("DELETE FROM espace_spirituel WHERE id=?", (b[0],))
                                commit_and_sync()
                                st.rerun()

            elif _vue_exist == _LBL_PM:
                _gestionnaire_archives_espace(
                    "Gestion DÉDIÉE des Prières 🙏 et Méditations 📖 — exactement ce que voit "
                    "l'utilisateur dans sa rubrique 📖 Archives. Cochez puis supprimez en un "
                    "seul clic (avec confirmation).",
                    ("priere", "meditation"), "pm")

            elif _vue_exist == _LBL_MU:
                _gestionnaire_archives_espace(
                    "Gestion DÉDIÉE des Musiques 🎵 — fichiers audio ET vidéos YouTube "
                    "publiés dans la sous-rubrique 🎵 Musiques. Cochez puis supprimez en un "
                    "seul clic (avec confirmation).",
                    ("audio",), "mu")

            elif _vue_exist == _LBL_THEME:
                # v7.10.4 — gestion APRÈS publication du feuillet et de son
                # questionnaire : état du mois, questions parues, réponses reçues.
                _gestionnaire_theme_publie()

            elif _vue_exist == _LBL_GAL:
                # v7.9.2 — archive de la Galerie + après publication
                _gestionnaire_archives_galerie()

            else:
                # v7.6.6 — DEMANDE 5 & 6 : les archives (prières, méditations,
                # musiques, actualités) NE PASSENT PLUS ICI (onglet 📖 Archives).
                # Ce gestionnaire ne garde que les contenus divers, avec coches.
                st.caption("Contenus DIVERS : actualités 📰 et tout autre type futur "
                           "(hors prières 🙏, méditations 📖, musiques 🎵 et bandes défilantes).")
                contenus = c.execute("""SELECT id, type_contenu, titre, date_publication, image_url, fichier_url, paroisse_cible
                                        FROM espace_spirituel
                                        WHERE type_contenu NOT IN ('annonce_defilante','priere','meditation','audio')
                                        ORDER BY date_publication DESC, id DESC""").fetchall()
                if not contenus:
                    st.info("Aucun contenu divers. Les prières 🙏, méditations 📖 et musiques 🎵 "
                            "ont leurs onglets dédiés ci-dessus — les actualités 📰 apparaissent ici.")
                else:
                    _paroisses_map = {p[0]: p[1] for p in c.execute("SELECT id, nom FROM paroisses").fetchall()}
                    _coches_autres = []
                    for cont in contenus:
                        _cible_lbl = f" 🏘️ {_paroisses_map[cont[6]]}" if cont[6] and cont[6] in _paroisses_map else ""
                        c_chk, c_txt = st.columns([1, 12])
                        with c_chk:
                            _coche = st.checkbox("", key=f"chk_autre_{cont[0]}")
                        with c_txt:
                            st.write(f"📌 **{cont[2] or '(sans titre)'}** — *{cont[1]}* · {cont[3]}{_cible_lbl}")
                        if _coche:
                            _coches_autres.append(cont)
                    if not _coches_autres:
                        st.session_state.pop("confirm_sup_autres", None)
                    elif not st.session_state.get("confirm_sup_autres"):
                        st.warning(f"⚠️ {len(_coches_autres)} élément(s) sélectionné(s) pour suppression.")
                        if st.button("🗑️ Supprimer la sélection…", key="btn_sup_autres", type="primary"):
                            st.session_state["confirm_sup_autres"] = True
                            st.rerun()
                    else:
                        st.error("🔴 CONFIRMATION — les éléments cochés seront supprimés DÉFINITIVEMENT :")
                        for cont in _coches_autres:
                            st.write(f"• 📌 {cont[2] or '(sans titre)'} ({cont[1]})")
                        c_ok2, c_ann2, _r2 = st.columns([1.6, 1, 3])
                        with c_ok2:
                            if st.button("✅ Oui, supprimer définitivement", key="btn_sup_autres_ok", type="primary"):
                                for cont in _coches_autres:
                                    for url in (cont[4], cont[5]):
                                        if url and url.startswith("http"):
                                            supprimer_photo(url)
                                _ids2 = [x[0] for x in _coches_autres]
                                _ph2 = ",".join("?" * len(_ids2))
                                c.execute(f"DELETE FROM espace_spirituel WHERE id IN ({_ph2})", _ids2)
                                commit_and_sync()
                                for cont in _coches_autres:
                                    st.session_state.pop(f"chk_autre_{cont[0]}", None)
                                st.session_state.pop("confirm_sup_autres", None)
                                st.session_state["flash_success"] = f"{len(_ids2)} élément(s) supprimé(s). 🗑️"
                                st.rerun()
                        with c_ann2:
                            if st.button("❌ Annuler", key="btn_sup_autres_non"):
                                st.session_state.pop("confirm_sup_autres", None)
                                st.rerun()

    elif menu == "💬 WhatsApp":
        st.markdown(f'<h2 style="color:#1A237E;">💬 Messages WhatsApp - {nom_dio}</h2>', unsafe_allow_html=True)
        afficher_whatsapp_tabs(equipe_id=None, paroisse_id=None)

    elif menu == "🔍 Rechercher matricule":
        st.markdown('<h2 style="color:#1A237E;">🔍 Recherche par matricule</h2>', unsafe_allow_html=True)
        matricule = st.text_input("Matricule (MatLoc ou Matricule)")
        if matricule.strip():
            m = c.execute('''SELECT m.matloc, m.matricule, m.nom, m.prenom, m.whatsapp, p.nom, e.nom_equipe, m.photo_path
                             FROM membres m
                             LEFT JOIN paroisses p ON m.paroisse_id = p.id
                             LEFT JOIN equipes e ON m.equipe_id = e.id
                             WHERE (m.matloc = ? OR m.matricule = ?) AND m.statut = 'actif' ''',
                          (matricule.upper().strip(), matricule.upper().strip())).fetchone()
            if m:
                st.success("Membre trouvé")
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.write(f"**{m[2]} {m[3]}** - MatLoc: {m[0]} | Matricule: {m[1] or '—'}")
                    st.write(f"💬 WhatsApp: {m[4] or 'Non renseigné'}")
                    st.markdown(f"🏘️ **Paroisse :** {m[5] or 'Non assignée'}  \n👥 **Équipe :** {m[6] or 'Non assignée'}")
                with col2:
                    if m[7]:
                        try: st.image(m[7], width=100)
                        except Exception: pass
            else:
                st.error("Non trouvé ou membre archivé")

    elif menu == "🔐 Gérer les accès":
        st.markdown('<h2 style="color:#1A237E;">🔐 Gestion des accès</h2>', unsafe_allow_html=True)
        afficher_messages_flash()
        st.markdown("### 🏘️ Paroisses")
        for p in c.execute("SELECT id, nom, responsable FROM paroisses").fetchall():
            user = c.execute("SELECT id, username FROM utilisateurs WHERE paroisse_id=? AND role='paroisse'", (p[0],)).fetchone()
            if user:
                with st.expander(f"🏛️ {p[1]} - {p[2]}"):
                    st.write(f"**Identifiant :** `{user[1]}`")
                    if st.button(f"🔄 Réinitialiser le mot de passe", key=f"reset_par_{p[0]}"):
                        nouveau = generer_mot_de_passe()
                        c.execute("UPDATE utilisateurs SET password=? WHERE id=?", (hash_password(nouveau), user[0]))
                        commit_and_sync()
                        st.session_state['new_pwd_par'] = {'user': user[1], 'pwd': nouveau}

                    if st.session_state.get('new_pwd_par') and st.session_state['new_pwd_par']['user'] == user[1]:
                        st.markdown(f"<div style='background:#e8f5e9;padding:15px;border-radius:10px;border:1px solid #c8e6c9;'>🔑 Nouveau mot de passe pour <code>{st.session_state['new_pwd_par']['user']}</code> : <code style='color:#d84315;font-size:1.2rem;'>{st.session_state['new_pwd_par']['pwd']}</code></div>", unsafe_allow_html=True)
                        if st.button("OK, j'ai noté le mot de passe", key=f"ok_pwd_par_{p[0]}"):
                            del st.session_state['new_pwd_par']
                            st.rerun()

        # 📡 Compte du Service Communication — la cellule prépare les contenus
        # et les soumet au SAS. Sans ce compte, la page Communication est
        # inaccessible (aucun autre endroit ne crée ce rôle).
        st.markdown("### 📡 Service Communication")
        user_com = c.execute("SELECT id, username FROM utilisateurs WHERE role='communication'").fetchone()
        if user_com:
            with st.expander(f"📡 Compte existant — {user_com[1]}"):
                st.write(f"**Identifiant :** `{user_com[1]}`")
                if st.button("🔄 Réinitialiser le mot de passe", key="reset_com"):
                    nouveau_com = generer_mot_de_passe()
                    c.execute("UPDATE utilisateurs SET password=? WHERE id=?", (hash_password(nouveau_com), user_com[0]))
                    commit_and_sync()
                    st.session_state['new_pwd_com'] = {'user': user_com[1], 'pwd': nouveau_com}
                if st.session_state.get('new_pwd_com') and st.session_state['new_pwd_com']['user'] == user_com[1]:
                    st.markdown(f"<div style='background:#e8f5e9;padding:15px;border-radius:10px;border:1px solid #c8e6c9;'>🔑 Nouveau mot de passe pour <code>{st.session_state['new_pwd_com']['user']}</code> : <code style='color:#d84315;font-size:1.2rem;'>{st.session_state['new_pwd_com']['pwd']}</code></div>", unsafe_allow_html=True)
                    if st.button("OK, j'ai noté le mot de passe", key="ok_pwd_com"):
                        del st.session_state['new_pwd_com']
                        st.rerun()
        else:
            with st.expander("➕ Créer le compte de la cellule Communication"):
                st.caption("Ce compte donne accès au canal de soumission (prières, bandes défilantes, "
                           "actualités, thème, musiques). Rien n'est publié sans votre validation au SAS.")
                nom_com = st.text_input("Nom d'utilisateur", value="communication", key="com_user")
                mdp_com = st.text_input("Mot de passe (laisser vide → généré automatiquement)", type="password", key="com_pwd")
                if st.button("📡 Créer le compte Communication", key="btn_creer_com", type="primary"):
                    ident = (nom_com or "").strip() or "communication"
                    if c.execute("SELECT id FROM utilisateurs WHERE username=?", (ident,)).fetchone():
                        st.error("❌ Ce nom d'utilisateur existe déjà.")
                    else:
                        _mdp_final = (mdp_com or "").strip() or generer_mot_de_passe()
                        c.execute("INSERT INTO utilisateurs (username, password, role, diocese_id) VALUES (?,?,?,?)",
                                  (ident, hash_password(_mdp_final), "communication", 1))
                        commit_and_sync()
                        st.session_state['new_pwd_com'] = {'user': ident, 'pwd': _mdp_final}
                        st.rerun()

    elif menu == "📊 Statistiques":
        st.markdown('<h2 style="color:#1A237E;">📊 Statistiques générales</h2>', unsafe_allow_html=True)
        tab_gen, tab_freq = st.tabs(["📌 Général", "📈 Fréquentation"])
        with tab_gen:
            c1, c2, c3 = st.columns(3)
            c1.metric("🏘️ Paroisses", c.execute("SELECT COUNT(*) FROM paroisses").fetchone()[0])
            c2.metric("👥 Équipes", c.execute("SELECT COUNT(*) FROM equipes").fetchone()[0])
            c3.metric("👤 Membres actifs", c.execute("SELECT COUNT(*) FROM membres WHERE statut='actif'").fetchone()[0])
        with tab_freq:
            st.caption("Visites des 30 derniers jours (une visite = une ouverture de session).")
            from services import stats_visites_pivot
            pivot = stats_visites_pivot(30)
            if pivot.empty:
                st.info("Aucune visite enregistrée sur la période.")
            else:
                pivot = pivot.rename(columns={"communautaire": "🏘️ Communautaire", "membre": "👤 Membre"})
                st.bar_chart(pivot)
            totaux = c.execute("SELECT page, COUNT(*) FROM stats_visites GROUP BY page").fetchall()
            d1, d2 = st.columns(2)
            for nom_page, nb in totaux:
                if nom_page == "communautaire":
                    d1.metric("🌐 Total Espace communautaire", nb)
                elif nom_page == "membre":
                    d2.metric("👤 Total Espace Membre", nb)

    elif menu == "📥 Export Excel":
        st.markdown('<h2 style="color:#1A237E;">📥 Export des données</h2>', unsafe_allow_html=True)
        if c.execute("SELECT COUNT(*) FROM membres").fetchone()[0] == 0: st.warning("Aucune donnée à exporter.")
        else:
            excel_file = exporter_excel_diocese()
            st.download_button("📥 Télécharger l'export global", data=excel_file, file_name=f"export_diocese_{date.today()}.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch")

    elif menu == "📦 Archives":
        st.markdown('<h2 style="color:#1A237E; font-size: 1.4rem;">📦 Archives du diocèse</h2>', unsafe_allow_html=True)
        archives = c.execute('''SELECT m.matloc, m.matricule, m.nom, m.prenom, a.situation, a.date_debut, a.date_fin, a.commentaire, a.equipe_id, a.paroisse_id, a.auteur_nom
                                FROM archives a JOIN membres m ON a.membre_id = m.id ORDER BY a.date_fin DESC''').fetchall()
        if not archives: st.info("Aucune archive.")
        else:
            for a in archives:
                d1, d2 = safe_date(a[5]), safe_date(a[6])
                duree = (d2 - d1).days // 365 if d1 and d2 else 0
                eq_nom, par_nom = "N/A", "N/A"
                if a[8]:
                    eq_info = c.execute("SELECT e.nom_equipe, p.nom FROM equipes e JOIN paroisses p ON e.paroisse_id = p.id WHERE e.id=?", (a[8],)).fetchone()
                    if eq_info: eq_nom, par_nom = eq_info[0], eq_info[1]
                elif a[9]:
                    par_info = c.execute("SELECT nom FROM paroisses WHERE id=?", (a[9],)).fetchone()
                    if par_info: par_nom = par_info[0]

                header = f"📌 {a[2]} {a[3]} ({a[0]} / {a[1] or '—'}) – {afficher_situation(a[4])} – {duree} an(s)"
                with st.expander(header):
                    st.write(f"**Paroisse :** {par_nom} | {eq_nom}")
                    st.write(f"**Ajouté par :** {a[10] or 'Inconnu'}")
                    if a[7]: st.write(f"**Commentaire :** {a[7]}")

    elif menu == "🗑️ Réinitialiser":
        st.markdown('<h2 style="color:#1A237E;">🗑️ RÉINITIALISATION COMPLÈTE</h2>', unsafe_allow_html=True)
        st.error("⚠️ ACTION IRRÉVERSIBLE ! Tout sera détruit : paroisses, équipes, membres, présences, abonnements, archives, agenda ET contenu de l'Espace Spirituel.")
        with st.expander("🔴 Cliquez pour réinitialiser"):
            confirmation = st.text_input("Tapez 'SUPPRIMER' pour confirmer")
            if confirmation == "SUPPRIMER":
                # Fichiers Cloudinary supprimés AVANT la purge SQL
                for (photo,) in c.execute("SELECT photo_path FROM membres WHERE photo_path IS NOT NULL").fetchall():
                    supprimer_photo(photo)
                for (affiche,) in c.execute("SELECT affiche_url FROM evenements WHERE affiche_url IS NOT NULL").fetchall():
                    supprimer_photo(affiche)
                for img_url, fic_url in c.execute("SELECT image_url, fichier_url FROM espace_spirituel").fetchall():
                    if img_url: supprimer_photo(img_url)
                    if fic_url: supprimer_photo(fic_url)

                if os.path.exists("photos"): shutil.rmtree("photos")

                c.execute("DELETE FROM suivi_presences")
                c.execute("DELETE FROM evenement_equipes")
                c.execute("DELETE FROM evenements")
                c.execute("DELETE FROM agenda")
                c.execute("DELETE FROM periodes_cloturees")
                c.execute("DELETE FROM abonnements")
                c.execute("DELETE FROM archives")
                c.execute("DELETE FROM espace_spirituel")
                c.execute("DELETE FROM membres")
                c.execute("DELETE FROM equipes")
                c.execute("DELETE FROM paroisses")
                c.execute("DELETE FROM utilisateurs WHERE role != 'diocese'")
                commit_and_sync()
                st.session_state["flash_success"] = "Toutes les données ont été supprimées. 🗑️"
                st.rerun()
