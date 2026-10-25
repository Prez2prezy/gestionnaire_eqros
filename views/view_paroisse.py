import re
import streamlit as st
import pandas as pd
import io
from datetime import date
from database import (c, commit_and_sync, verifier_reparer_intentions,
                      intention_du_prochain, intention_du_prochain_detail,
                      get_parametre, set_parametre,
                      INTENTIONS_UNIVERSELLES, jours_depuis,
                      prise_en_charge_automatique, stats_dizaines_jour,
                      _assurer_dizaines_journal, _assurer_table_reserve,
                      reserve_compteur, reserve_lignes,
                      ajouter_intention_reserve, retirer_intention_reserve,
                      OBJECTIF_RESERVE)
from services import (hash_password, generer_mot_de_passe, sauvegarder_photo, supprimer_photo,
                      archiver_membre, safe_date, afficher_situation, sans_accents, 
                      enregistrer_abonnement, verifier_abonnement, periode_affichage, 
                      generer_matricule_unique, get_periode_pastorale, lien_whatsapp, URL_ESPACE_SPIRITUEL,
                      synchroniser_menu_session, lire_menu_session, afficher_messages_flash)
from components import (ajouter_evenement_agenda, afficher_agenda_complet_universel, afficher_historique_suivi, 
                        afficher_whatsapp_tabs, widget_type_abonnement, afficher_etat_presences_globales)

def _onglet_coins_intentions(pid, equipes):
    """🙏 COINS DES INTENTIONS (v7.9.0) — 4e onglet de « 📌 Suivi et Agenda »
    côté paroisse : le BILAN de toutes les intentions confiées aux équipes
    (reçues / prises en charge / archivées) et le RÉGLAGE de la chaîne de
    prière universelle (1er choix : reçues · 2e : prises en charge · 3e :
    intentions universelles). C'est ce réglage qui nourrit la dernière
    intention (« Intention du prochain ») du livret « 🕯️ Un jour, une
    dizaine ».
    NB rappelé : une intention prise en charge dure au minimum 20 jours
    (20 mystères), sinon jusqu'à la prochaine prière mensuelle.
    v7.9.1 — RÈGLE DU LENDEMAIN : le balayage `prise_en_charge_automatique`
    tourne ici — toute intention reçue passe « en prière » le lendemain de
    sa réception (date_statut = réception + 1), pour 20 jours. Un même
    numéro ne porte jamais 2 intentions prises en charge."""
    verifier_reparer_intentions()
    prise_en_charge_automatique()
    ids_eq = [e[0] for e in equipes]
    _ph = ",".join("?" * len(ids_eq)) if ids_eq else "NULL"
    _prm = list(ids_eq)
    try:
        n_rec = c.execute(f"SELECT COUNT(*) FROM intentions_equipes "
                          f"WHERE equipe_id IN ({_ph}) AND statut='recue'", _prm).fetchone()[0]
        n_pri = c.execute(f"SELECT COUNT(*) FROM intentions_equipes "
                          f"WHERE equipe_id IN ({_ph}) AND statut='en_priere'", _prm).fetchone()[0]
        n_arc = c.execute(f"SELECT COUNT(*) FROM intentions_equipes "
                          f"WHERE equipe_id IN ({_ph}) AND statut='archivee'", _prm).fetchone()[0]
    except Exception:
        st.error("Impossible de lire les intentions pour le moment — la base "
                 "distante se réparera automatiquement au prochain "
                 "rafraîchissement (l'erreur réelle est journalisée).")
        return

    # ---------- A. BILAN GÉNÉRAL ----------
    st.markdown("### 🧾 Bilan des intentions confiées aux équipes")
    m1, m2, m3 = st.columns(3)
    m1.metric("🆕 Reçues", n_rec)
    m2.metric("🕊️ Prises en charge", n_pri)
    m3.metric("🗄️ Archivées", n_arc)
    st.caption("🕊️ Principe « être une tombe » : les intentions se portent en prière, "
               "elles ne se racontent pas et ne sortent jamais de l’équipe. Cette page "
               "en fait le bilan sans jamais les commenter. "
               "**NB : une intention prise en charge dure au minimum 20 jours "
               "(20 mystères), sinon jusqu’à la prochaine prière mensuelle.**")
    # v7.9.1 — la règle du lendemain, expliquée au gestionnaire paroissial.
    st.info("⏱️ **v7.9.1 — Règle du lendemain :** chaque intention reçue passe "
            "automatiquement « 🕊️ Prise en charge » **le lendemain de sa réception**, "
            "pour 20 jours (20 mystères) — sans aucune action manuelle. Un même "
            "numéro de téléphone ne peut porter qu’**une seule** intention prise en "
            "charge à la fois : les intentions suivantes du même numéro attendent "
            "l’archivage de la première.")

    # ---------- B. BILAN PAR ÉQUIPE ----------
    if not ids_eq:
        st.info("Aucune équipe dans cette paroisse : les fidèles ne peuvent "
                "confier d'intention nulle part pour l'instant.")
    else:
        lignes = c.execute(f"""SELECT id, equipe_id, texte, auteur_nom, anonyme,
                                       statut, date_soumission, date_statut
                                FROM intentions_equipes
                                WHERE equipe_id IN ({_ph})
                                ORDER BY date_soumission DESC, id DESC""", _prm).fetchall()
        noms_eq = {e[0]: e[1] for e in equipes}
        for eid in ids_eq:
            _les = [l for l in lignes if l[1] == eid]
            _rec = sum(1 for l in _les if l[5] == 'recue')
            _pri = sum(1 for l in _les if l[5] == 'en_priere')
            _arc = sum(1 for l in _les if l[5] == 'archivee')
            with st.expander(f"👥 {noms_eq.get(eid, '?')} — 🆕 {_rec} · 🕊️ {_pri} · 🗄️ {_arc}"):
                if not _les:
                    st.caption("Aucune intention confiée à cette équipe pour l'instant.")
                for (iid, _eqi, texte, auteur, anon, statut, dsoum, dstat) in _les:
                    qui = "Anonyme" if anon else (auteur or "Fidèle")
                    if statut == 'recue':
                        _j = jours_depuis(dsoum)
                        badge = f"🆕 Reçue le {dsoum} (J+{_j})"
                    elif statut == 'en_priere':
                        _j = jours_depuis(dstat or dsoum)
                        badge = (f"🕊️ En prière depuis le {dstat or dsoum} — J+{_j}/20"
                                 + (" ✅ 20 mystères accomplis : à archiver à la "
                                    "prochaine prière mensuelle" if _j >= 20
                                    else " (min. 20 jours / 20 mystères)"))
                    else:
                        badge = f"🗄️ Archivée (prise en charge {dstat or dsoum})"
                    st.markdown(f"**{badge}** — *{qui}* (équipe « {noms_eq.get(eid, '?')} »)")
                    st.write(texte)
                    st.markdown("---")

    # ---------- C. LA CHAÎNE DE PRIÈRE UNIVERSELLE ----------
    st.markdown("### 📿 La chaîne de prière universelle")
    st.caption("Dans le livret « 🕯️ Un jour, une dizaine », la dernière intention de chaque "
               "mystère (« Intention du prochain dans la chaine de prière ») est DEVENUE "
               "DYNAMIQUE : elle porte une vraie intention confiée par un fidèle. Choisissez "
               "ici ce que les visiteurs et membres priéront demain. La chaîne est "
               "UNIVERSELLE : elle puise dans les intentions confiées à toutes les équipes. "
               "🤫 Règle d’or : un visiteur ne peut jamais prier SA propre intention — "
               "son jour de naissance l’en empêche discrètement.")
    _mode = get_parametre("chaine_mode", "recues")
    _choix_txt = {"recues": "1️⃣ Les intentions RECUES (la plus ancienne d’abord : chaque "
                           "intention attend son tour dans la chaîne)",
                  "en_priere": "2️⃣ Les intentions PRISES EN CHARGE (celles que les équipes "
                               "portent déjà en prière)",
                  "universelle": "3️⃣ Les intentions universelles de l’Église (choix fixes ou "
                                 "rotation quotidienne)"}
    _mode_nouveau = st.radio("Quelle source nourrit l’intention du prochain ?",
                             list(_choix_txt.keys()), index=list(_choix_txt.keys()).index(_mode)
                             if _mode in _choix_txt else 0,
                             format_func=lambda k: _choix_txt[k],
                             key="chaine_mode_choix")
    _univ_nouveau = None
    if _mode_nouveau == "universelle":
        _opts = list(INTENTIONS_UNIVERSELLES) + \
                ["🔄 Rotation quotidienne des trois intentions"]
        _val = get_parametre("chaine_universelle", INTENTIONS_UNIVERSELLES[0])
        if _val == "rotation":
            _idx_u = len(_opts) - 1
        elif _val in INTENTIONS_UNIVERSELLES:
            _idx_u = list(INTENTIONS_UNIVERSELLES).index(_val)
        else:
            _idx_u = 0
        _univ_nouveau = st.selectbox("Quelle intention universelle ?", _opts, index=_idx_u,
                                     key="chaine_univ_choix")
    if st.button("💾 Enregistrer le choix de la chaîne", type="primary",
                 key="chaine_save"):
        set_parametre("chaine_mode", _mode_nouveau)
        if _mode_nouveau == "universelle":
            set_parametre("chaine_universelle",
                          "rotation" if (_univ_nouveau or "").startswith("🔄")
                          else _univ_nouveau)
        # Pas de st.rerun() ici : le message reste visible ET l'aperçu
        # ci-dessous (rendu après) reflète immédiatement le nouveau choix.
        st.success("✅ Choix enregistré : le livret « 🕯️ Un jour, une dizaine » porte "
                   "désormais cette intention (l'aperçu ci-dessous est à jour).")

    # ---------- D. APERÇU (ce que verra le visiteur) ----------
    # v7.9.1 — aperçu au NOUVEAU MODÈLE demandé : « intercède pour {Prénom
    # Nom} : … », « intercède pour cet anonyme : … », « intercède : … »
    # (universelle). Le texte est échappé (aucun HTML ne passe).
    _txt_prochain, _qui_prochain = intention_du_prochain_detail(jour_visiteur=None)
    _ligne_apercu = (("🕯️ Vierge Marie, mère de Dieu, intercède pour " + _qui_prochain
                      + " : " + _txt_prochain) if _qui_prochain
                     else ("🕯️ Vierge Marie, mère de Dieu, intercède : " + _txt_prochain))
    st.markdown(
        '<div style="background:linear-gradient(135deg,#1A237E 0%,#283593 100%);'
        ' border:1px solid #FFD700; border-radius:12px; padding:14px 16px; margin:8px 0;">'
        '<div style="color:#FFD000; font-size:0.85rem; font-weight:600;">👁️ Aperçu — ce que le '
        'visiteur lira dans « 🕯️ Un jour, une dizaine »</div>'
        '<div style="color:#ffffff; font-size:1rem; margin-top:6px; line-height:1.7;">'
        + _ligne_apercu.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        + '</div></div>',
        unsafe_allow_html=True)
    st.caption("🧭 Chaque visiteur reçoit l’intention de SON prochain selon son N° méd. "
               "(jour de naissance) et la médite sur sa fenêtre de 20 jours ; "
               "personne ne prie jamais sa propre intention. "
               "📚 La réserve ci-dessous garantit une intention d’avance pour "
               "chacun des N° méd.")

    # ---------- E. RÉSERVE D'INTENTIONS PAR N° MÉD. (v7.9.3) ----------
    _bloc_reserve_paroisse(pid, equipes)


def _bloc_reserve_paroisse(pid, equipes):
    """📚 RÉSERVE D'INTENTIONS PAR N° MÉD. (v7.9.3) — volet PAROISSIAL :
    « il est capital d'avoir au préalable une intention pour chacun des
    N° méd. Ça sera l'affaire des responsables d'équipe et paroissial. »
    (v7.9.4 — UNE intention par N° méd.) Le responsable paroissial ajoute
    ici les intentions des membres de ses équipes (il choisit l'équipe puis
    le membre — le N° méd. du membre désigne l'emplacement), en complément
    du travail des responsables d'équipe. Les compteurs sont GLOBAUX : la
    chaîne est universelle."""
    _assurer_table_reserve()
    # v7.9.3 — la confirmation d'un ajout (flash posé par le formulaire)
    # s'affiche ici, en tête du bloc, APRÈS le rerun.
    afficher_messages_flash()
    st.markdown("---")
    st.markdown("### 📚 Réserve d'intentions — 1 intention par N° méd.")
    st.caption("Chaque N° méd. (1-20) porte UNE intention : c'est elle que le visiteur "
               "du jour reçoit selon SON N° méd. et médite pendant 20 jours — chacun "
               "a ainsi sa propre intention de prochain. Ajoutez ici les intentions "
               "des membres de vos équipes, une par N° méd. Compteurs toutes équipes "
               "confondues (la chaîne est universelle). 🤫 Comme toujours : être une "
               "tombe.")
    _cpt = reserve_compteur()
    _total = sum(_cpt.values())
    _grille = "".join(
        '<div style="min-width:62px; flex:1 0 62px; background:'
        + ("#1b2a5e" if _cpt[n] else "#121a45")
        + '; border:1px solid '
        + ("#FFD700" if _cpt[n] >= OBJECTIF_RESERVE else ("#3a4585" if _cpt[n] else "#27306b"))
        + '; border-radius:9px; padding:6px 4px; text-align:center;">'
        + '<div style="color:' + ("#FFD000" if _cpt[n] else "#5a6398")
        + '; font-weight:bold; font-size:0.95rem;">' + str(n).zfill(2) + '</div>'
        + '<div style="color:' + ("#e8eaf6" if _cpt[n] else "#5a6398")
        + '; font-size:0.72rem;">' + str(_cpt[n]) + "/" + str(OBJECTIF_RESERVE) + '</div></div>'
        for n in range(1, 21))
    st.markdown('<div style="display:flex; flex-wrap:wrap; gap:6px; margin:8px 0 4px 0;">'
                + _grille + '</div>', unsafe_allow_html=True)
    if _total >= 20 * OBJECTIF_RESERVE:
        st.success("🎯 Objectif atteint : les 20 N° méd. sont pourvus ("
                   + str(_total) + " intentions en réserve) — la chaîne ne tombera pas à sec.")
    else:
        st.caption("🎯 Objectif : 1 intention par N° méd. (20 au total) — réserve actuelle : "
                   + str(_total) + ".")
    if not equipes:
        st.info("Aucune équipe dans cette paroisse : la réserve se remplit depuis "
                "les équipes (responsables d'équipe) ou dès qu'une équipe existera.")
        return
    with st.expander("➕ Ajouter une intention à la réserve"):
        _eq_sel = st.selectbox("Équipe du membre", list(range(len(equipes))),
                               format_func=lambda i: equipes[i][1],
                               key="res_par_eq")
        _eq_id = equipes[_eq_sel][0]
        _membres = c.execute("""SELECT id, nom, prenom, numero_meditation FROM membres
                                WHERE equipe_id=? AND statut='actif' ORDER BY nom""",
                             (_eq_id,)).fetchall()
        if not _membres:
            st.info("Cette équipe n'a pas encore de membre actif.")
        else:
            with st.form("form_reserve_par", clear_on_submit=True):
                _sel = st.selectbox(
                    "Membre (son N° méd. désigne l'emplacement de la réserve)",
                    list(range(len(_membres))),
                    format_func=lambda i: (
                        f"{_membres[i][1]} {_membres[i][2]}"
                        + (f" — N° méd. {_membres[i][3]}" if _membres[i][3]
                           else " — ⚠️ sans N° méd. (à renseigner par le responsable d'équipe)")))
                _txt = st.text_area("Intention de prière *", height=90, max_chars=500,
                                    placeholder="Pour la santé de…, pour ma famille…, "
                                                "pour les vocations…")
                if st.form_submit_button("➕ Ajouter à la réserve", type="primary"):
                    _m = _membres[_sel]
                    try:
                        _num = int(str(_m[3]).strip()) if _m[3] else None
                    except (TypeError, ValueError):
                        _num = None
                    if _num is None or not (1 <= _num <= 20):
                        st.warning("⚠️ " + str(_m[1]) + " " + str(_m[2])
                                   + " n'a pas de N° méditation valide (1-20). "
                                     "Le responsable d'équipe doit d'abord le renseigner.")
                    else:
                        _ok, _msg = ajouter_intention_reserve(
                            _num, _txt,
                            auteur_nom=(str(_m[1]) + " " + str(_m[2])).strip(),
                            equipe_id=_eq_id, paroisse_id=pid)
                        if _ok:
                            st.session_state["flash_success"] = _msg
                            st.rerun()
                        # v7.9.4 — refus (emplacement déjà pourvu) : flash en
                        # tête de bloc, visible même l'expander refermé.
                        st.session_state["flash_warning"] = _msg
                        st.rerun()
    _lignes = reserve_lignes(paroisse_id=pid)
    if _lignes:
        _noms_eq = {e[0]: e[1] for e in equipes}
        with st.expander(f"🗂️ Intentions en réserve de la paroisse ({len(_lignes)})"):
            for (rid, num, texte, auteur, eqi, daj) in _lignes:
                st.markdown(f"**N° méd. {int(num):02d}** — *{auteur or 'Membre'}*"
                            + (f" · équipe « {_noms_eq.get(eqi, '?')} »" if eqi else "")
                            + (f" · ajoutée le {daj}" if daj else ""))
                st.write(texte)
                if st.button("🗑️ Retirer de la réserve", key=f"res_del_par_{rid}"):
                    retirer_intention_reserve(rid)
                    st.rerun()
                st.markdown("---")


def _tableau_de_bord_paroisse(pid, nom_p):
    """🚦 TABLEAU DE BORD (v7.9.1) — 2e onglet de « 📊 Statistiques - {paroisse} » :
    la vue d'ensemble en un coup d'œil — effectifs, abonnements de l'année
    pastorale en cours, intentions (règle du lendemain + 20 mystères),
    prochaine prière, fréquentation de l'Espace communautaire et santé de
    chaque équipe. Lecture seule : rien ne se modifie ici."""
    annee_cours = get_periode_pastorale()[0]

    # ---- Intentions (balayage « lendemain » au passage, sans jamais casser)
    verifier_reparer_intentions()
    prise_en_charge_automatique()
    ids_eq = [e[0] for e in c.execute("SELECT id FROM equipes WHERE paroisse_id=?", (pid,)).fetchall()]
    _ph = ",".join("?" * len(ids_eq)) if ids_eq else "NULL"
    _prm = list(ids_eq)
    try:
        n_rec = c.execute(f"SELECT COUNT(*) FROM intentions_equipes WHERE equipe_id IN ({_ph}) AND statut='recue'", _prm).fetchone()[0]
        n_pri = c.execute(f"SELECT COUNT(*) FROM intentions_equipes WHERE equipe_id IN ({_ph}) AND statut='en_priere'", _prm).fetchone()[0]
        n_arc = c.execute(f"SELECT COUNT(*) FROM intentions_equipes WHERE equipe_id IN ({_ph}) AND statut='archivee'", _prm).fetchone()[0]
        _dstat = c.execute(f"SELECT date_statut FROM intentions_equipes WHERE equipe_id IN ({_ph}) AND statut='en_priere'", _prm).fetchall()
    except Exception:
        n_rec = n_pri = n_arc = 0
        _dstat = []
    n_fin = sum(1 for (ds,) in _dstat if (jours_depuis(ds) >= 20))

    # ---- Effectifs & abonnements
    nb_eq = len(ids_eq)
    nb_mbr = c.execute("SELECT COUNT(*) FROM membres WHERE paroisse_id=? AND statut='actif'", (pid,)).fetchone()[0]
    stats_abo = c.execute("""SELECT COUNT(m.id), SUM(CASE WHEN a.annee_debut=? AND a.statut='paye' THEN 1 ELSE 0 END)
                             FROM membres m LEFT JOIN abonnements a ON m.id = a.membre_id AND a.annee_debut=?
                             WHERE m.paroisse_id=? AND m.statut='actif'""", (annee_cours, annee_cours, pid)).fetchone()
    total_abo = int(stats_abo[0]) if stats_abo and stats_abo[0] else 0
    payes_abo = int(stats_abo[1]) if stats_abo and stats_abo[1] else 0
    taux = str(round(payes_abo / total_abo * 100)) + "%" if total_abo else "0%"

    # ---- Prochaine prière (agenda des équipes de la paroisse)
    try:
        _evt = c.execute(f"""SELECT e.date_evenement, e.type_evenement, e.lieu
                             FROM evenements e JOIN evenement_equipes ee ON e.id = ee.evenement_id
                             WHERE ee.equipe_id IN ({_ph}) AND e.date_evenement >= ?
                             ORDER BY e.date_evenement ASC LIMIT 1""",
                         (*ids_eq, date.today().isoformat())).fetchone() if ids_eq else None
    except Exception:
        _evt = None

    # ---- Fréquentation : scans du QR paroissial (30 derniers jours)
    _il_y_a_30 = (date.today().toordinal() - 30)
    try:
        n_vis = c.execute("SELECT COUNT(*) FROM visites_paroisse WHERE paroisse_id=?", (pid,)).fetchone()[0]
        n_vis_30 = 0
        for (_dv,) in c.execute("SELECT date_visite FROM visites_paroisse WHERE paroisse_id=?", (pid,)).fetchall():
            _d = safe_date(_dv)
            if _d and _d.toordinal() >= _il_y_a_30:
                n_vis_30 += 1
    except Exception:
        n_vis = n_vis_30 = 0

    st.markdown("### 🚦 Tableau de bord — " + str(nom_p))
    st.caption("Tout ce qui compte, en un coup d'œil · année pastorale " + str(annee_cours)
               + " (" + periode_affichage(annee_cours) + ")")
    r1 = st.columns(4)
    r1[0].metric("👥 Équipes", nb_eq)
    r1[1].metric("👤 Membres actifs", nb_mbr)
    r1[2].metric("💰 Abonnements payés", f"{payes_abo}/{total_abo}")
    r1[3].metric("📈 Recouvrement", taux)
    r2 = st.columns(4)
    r2[0].metric("🆕 Intentions reçues", n_rec)
    r2[1].metric("🕊️ En prière", n_pri)
    r2[2].metric("🗄️ Archivées", n_arc)
    r2[3].metric("⏰ 20 mystères accomplis", n_fin,
                 delta="à archiver à la prière mensuelle" if n_fin else None,
                 delta_color="off")
    if n_fin:
        st.warning("🕊️ **" + str(n_fin) + "** intention(s) en prière ont dépassé les "
                   "20 mystères : à archiver à la prochaine prière mensuelle "
                   "(onglet « 🙏 Coins des Intentions » du 📌 Suivi).")
    if n_rec:
        st.info("🆕 **" + str(n_rec) + "** intention(s) reçue(s) aujourd'hui : elles passeront "
                "automatiquement « 🕊️ Prises en charge » demain (règle du lendemain, 20 jours).")

    # ---- v7.9.2 : LA CHAÎNE DES DIZAINES (pointage volontaire en fin de livre)
    try:
        _assurer_dizaines_journal()
        _dz_m = c.execute(f"""SELECT COUNT(*) FROM dizaines_journal
                              WHERE type='membre' AND jour=?
                                AND equipe_id IN ({_ph})""",
                          (date.today().isoformat(), *ids_eq)).fetchone()[0] if ids_eq else 0
    except Exception:
        _dz_m = 0
    try:
        _dz_v = stats_dizaines_jour()[1]   # visiteurs (communauté, toutes paroisses)
    except Exception:
        _dz_v = 0
    r3 = st.columns(4)
    r3[0].metric("📿 Dizaines pointées aujourd'hui", _dz_m,
                 delta="membres des équipes · pointage volontaire", delta_color="off")
    r3[1].metric("🔥 Passages visiteurs (chaîne)", _dz_v,
                 delta="communauté, toutes paroisses", delta_color="off")
    with r3[2]:
        with st.expander("ℹ️ Comment lire les dizaines ?"):
            st.caption("Chaque équipier (ou visiteur) qui termine « 🕯️ Un jour, "
                       "une dizaine » dans l'Espace de Prière peut appuyer sur "
                       "« ✅ Merci Sainte Mère pour ton aide de ce jour! ». Le membre est "
                       "pointé 1 fois/jour (son équipe le voit), le visiteur compte "
                       "un passage anonyme.")

    _c_evt, _c_vis = st.columns(2)
    with _c_evt:
        st.markdown("#### 📅 Prochaine prière")
        if _evt:
            _d = safe_date(_evt[0])
            _j = (_d - date.today()).days if _d else None
            _delai = ("🔴 aujourd'hui" if _j == 0 else "🟠 demain"
                      if _j == 1 else f"📅 dans {_j} jours") if _j is not None else ""
            st.success(f"✨ **{_evt[1] or 'Prière'}** — {_d.strftime('%d/%m/%Y') if _d else _evt[0]} {_delai}\n\n📍 {_evt[2] or 'lieu à définir'}")
        else:
            st.info("Aucun évènement à venir dans l'agenda des équipes.")
    with _c_vis:
        st.markdown("#### 🌐 Espace communautaire")
        st.metric("🔳 Arrivées via le QR paroissial (30 jours)", n_vis_30)
        st.caption(f"Depuis l'origine : {n_vis} arrivée(s) comptée(s) à votre paroisse.")

    # ---- Santé par équipe
    st.markdown("#### 🧭 Santé des équipes")
    _lignes = []
    for (eid, enom) in c.execute("SELECT id, nom_equipe FROM equipes WHERE paroisse_id=? ORDER BY nom_equipe", (pid,)).fetchall():
        _m = c.execute("SELECT COUNT(*) FROM membres WHERE equipe_id=? AND statut='actif'", (eid,)).fetchone()[0]
        _p = c.execute("""SELECT COUNT(*) FROM membres m LEFT JOIN abonnements a
                          ON m.id = a.membre_id AND a.annee_debut=?
                          WHERE m.equipe_id=? AND m.statut='actif' AND a.statut='paye'""",
                       (annee_cours, eid)).fetchone()[0]
        try:
            _i = c.execute("SELECT COUNT(*) FROM intentions_equipes WHERE equipe_id=? AND statut='en_priere'", (eid,)).fetchone()[0]
        except Exception:
            _i = 0
        try:
            _dz_eq = stats_dizaines_jour(equipe_id=eid)[0]
        except Exception:
            _dz_eq = 0
        _lignes.append({"Équipe": enom, "Membres actifs": _m,
                        f"Abonnés {annee_cours}": _p, "🕊️ Intentions en prière": _i,
                        "📿 Dizaines aujourd'hui": _dz_eq})
    if _lignes:
        st.dataframe(pd.DataFrame(_lignes), width="stretch", hide_index=True)
    else:
        st.info("Aucune équipe : créez la première depuis « 👥 Mes équipes ».")


def generer_identifiant_equipe(nom_paroisse, nom_commune, nom_equipe, paroisse_id):
    nom_propre = nom_paroisse.lower()
    motifs_exclus = [r"notre[\s\-]*dame", r"sainte?", r"st\.?", r"notre", r"dame", r"du\b", r"d'", r"l'", r"de\b"]
    for motif in motifs_exclus:
        nom_propre = re.sub(motif, "", nom_propre, flags=re.IGNORECASE)
    nom_propre = re.sub(r"[\s'\-]", "", nom_propre)
    prefixe_par = sans_accents(nom_propre[:3]) if nom_propre else "par"
    prefixe_com = sans_accents(nom_commune[:3])
    est_jeune = "jeune" in nom_equipe.lower()
    suffixe = "j" if est_jeune else "eq"
    base = f"{prefixe_par}{prefixe_com}{suffixe}"
    # Numérotation naturelle : (nombre d'équipes actuelles du même type) + 1
    if est_jeune:
        nb = c.execute("SELECT COUNT(*) FROM equipes WHERE paroisse_id=? AND LOWER(nom_equipe) LIKE '%jeune%'", (paroisse_id,)).fetchone()[0]
    else:
        nb = c.execute("SELECT COUNT(*) FROM equipes WHERE paroisse_id=? AND LOWER(nom_equipe) NOT LIKE '%jeune%'", (paroisse_id,)).fetchone()[0]
    n = nb + 1
    # Sécurité anti-crash : si ce numéro est déjà porté par un compte existant
    # (cas rare), on passe au suivant au lieu de provoquer une erreur SQL.
    while c.execute("SELECT 1 FROM utilisateurs WHERE username=?", (f"{base}{n}",)).fetchone():
        n += 1
    return f"{base}{n}".lower()

def get_max_membres(equipe_id):
    paroisse_info = c.execute("""
        SELECT p.nom, p.commune 
        FROM equipes e 
        JOIN paroisses p ON e.paroisse_id = p.id 
        WHERE e.id=?
    """, (equipe_id,)).fetchone()
    
    if paroisse_info:
        nom_paroisse = str(paroisse_info[0]).lower() 
        commune = str(paroisse_info[1]).lower()
        if "notre dame" in nom_paroisse and "assomption" in nom_paroisse and "koumassi" in commune:
            return 20
            
    return 12

def show_paroisse():
    pid = st.session_state['paroisse_id']
    # Migration douce : WhatsApp responsable PAROISSE + DIOCÈSE (idempotent,
    # silencieux — couvre aussi une base où le diocèse ne s'est pas encore
    # connecté depuis l'ajout de la colonne)
    for _tbl in ("paroisses", "diocese"):
        try:
            c.execute(f"SELECT whatsapp_responsable FROM {_tbl} LIMIT 1")
        except Exception:
            try:
                c.execute(f"ALTER TABLE {_tbl} ADD COLUMN whatsapp_responsable TEXT")
                commit_and_sync()
            except Exception:
                pass
    p_info = c.execute("SELECT nom, commune, ville, responsable, bureau, whatsapp_responsable FROM paroisses WHERE id=?", (pid,)).fetchone()
    if not p_info:
        st.error("Paroisse introuvable temporairement. Veuillez actualiser la page (F5).")
        return
    nom_p = p_info[0]
    
    _rubriques_par = ["🏘️ Ma paroisse", "👥 Mes équipes", "👤 Membres", "📊 Statistiques",
                      "📅 Abonnements", "📌 Suivi", "💬 WhatsApp", "📥 Export Excel", "📦 Archives"]
    if "nav_par" in st.session_state and st.session_state["nav_par"] not in _rubriques_par:
        del st.session_state["nav_par"]
    if "nav_par" not in st.session_state:
        _rub = lire_menu_session()
        if _rub and _rub in _rubriques_par:
            st.session_state["nav_par"] = _rub
            st.session_state["_menu_sync"] = _rub
    menu = st.sidebar.radio("Navigation", _rubriques_par, key="nav_par")
    synchroniser_menu_session(menu)

    if menu == "🏘️ Ma paroisse":
        st.markdown(f'<h2 style="color:#1A237E;">🏘️ {nom_p}</h2>', unsafe_allow_html=True)
        _affiche_wa = p_info[5] or "Non renseigné"
        st.markdown(f'<div class="custom-info-box">Commune : {p_info[1]}<br>Ville : {p_info[2]}<br><b>Responsable :</b> {p_info[3]}<br><b>Bureau :</b> {p_info[4]}<br><b>📱 WhatsApp du responsable :</b> {_affiche_wa}</div>', unsafe_allow_html=True)

        # Lien public de la paroisse (QR signé — le même que celui expédié au responsable)
        with st.expander("🔳 Mon lien & QR paroissial (pour les affiches)"):
            _url_signee = f"{URL_ESPACE_SPIRITUEL}/?espace=1&p={pid}"
            st.code(_url_signee)
            st.caption("Partagez ce lien (ou le QR téléchargeable côté diocèse, menu Gérer paroisses) sur vos affiches : chaque scan est compté à l'origine de la paroisse.")

        with st.expander("✏️ Modifier les informations"):
            c_edit1, c_edit2 = st.columns(2)
            with c_edit1:
                nr = st.text_input("Nouveau responsable", value=p_info[3])
                nwa = st.text_input("📱 WhatsApp du responsable (ex. 0700000000)", value=p_info[5] or "")
            with c_edit2:
                nb = st.text_area("Nouveau bureau", value=p_info[4])
            if st.button("💾 Enregistrer"):
                c.execute("UPDATE paroisses SET responsable=?, bureau=?, whatsapp_responsable=? WHERE id=?",
                          (nr, nb, nwa.strip() or None, pid))
                commit_and_sync(); st.success("Mis à jour !"); st.rerun()

        # NOUVEAU : Zone de réinitialisation de la paroisse
        with st.expander("⚠️ ZONE DANGEREUSE : Réinitialisation de la paroisse"):
            st.error("Cette action supprimera **définitivement** toutes les équipes, les membres et les accès de cette paroisse. Cette action est irréversible.")
            confirm_text = st.text_input("Pour confirmer, tapez le mot : SUPPRIMER")
            if st.button("🗑️ Réinitialiser la paroisse", type="secondary") and confirm_text == "SUPPRIMER":
                c.execute("DELETE FROM membres WHERE paroisse_id=?", (pid,))
                c.execute("DELETE FROM equipes WHERE paroisse_id=?", (pid,))
                c.execute("DELETE FROM utilisateurs WHERE paroisse_id=? AND role='equipe'", (pid,))
                commit_and_sync()
                st.success("Paroisse entièrement réinitialisée. Vous pouvez recréer vos équipes.")
                st.rerun()

    elif menu == "👥 Mes équipes":
        # v7.9.9 — le titre ne compte que les équipes (à la demande) :
        # « 👥 Équipes de {paroisse} — N équipe(s) » (les membres se lisent
        # paroisse par paroisse, équipe par équipe, dans les listes).
        _n_eq = c.execute("SELECT COUNT(*) FROM equipes WHERE paroisse_id=?", (pid,)).fetchone()[0]
        st.markdown(f'<h2 style="color:#1A237E;">👥 Équipes de {nom_p} — {_n_eq} équipe(s)</h2>',
                    unsafe_allow_html=True)
        if st.button("➕ Créer une équipe"): st.session_state['show_eq_form'] = True
        if st.session_state.get('show_eq_form'):
            with st.form("f_eq"):
                nom_eq, resp, bur = st.text_input("Nom de l'équipe"), st.text_input("Responsable"), st.text_area("Bureau")
                c1, c2 = st.columns(2)
                if c1.form_submit_button("❌ Annuler"): del st.session_state['show_eq_form']; st.rerun()
                if c2.form_submit_button("✅ Créer") and nom_eq and resp:
                    doublon_resp = c.execute('SELECT e.nom_equipe, p.nom FROM equipes e JOIN paroisses p ON e.paroisse_id = p.id WHERE e.responsable = ?', (resp,)).fetchone()
                    if doublon_resp: st.error(f"❌ Responsable déjà assigné à '{doublon_resp[0]}' ({doublon_resp[1]}).")
                    elif c.execute("SELECT id FROM equipes WHERE nom_equipe=? AND paroisse_id=?", (nom_eq, pid)).fetchone(): st.error(f"❌ Équipe '{nom_eq}' existe déjà !")
                    else:
                        identifiant = generer_identifiant_equipe(p_info[0], p_info[1], nom_eq, pid)
                        mdp = generer_mot_de_passe()
                        c.execute("INSERT INTO equipes (nom_equipe, responsable, bureau, paroisse_id) VALUES (?,?,?,?)", (nom_eq, resp, bur, pid))
                        eid = c.lastrowid
                        c.execute("INSERT INTO utilisateurs (username, password, role, paroisse_id, equipe_id) VALUES (?,?,?,?,?)", (identifiant, hash_password(mdp), "equipe", pid, eid))
                        commit_and_sync(); del st.session_state['show_eq_form']
                        st.session_state['new_equipe_info'] = {'nom': nom_eq, 'user': identifiant, 'mdp': mdp}; st.rerun()
        
        if st.session_state.get('new_equipe_info'):
            info = st.session_state['new_equipe_info']
            st.success(f"✅ '{info['nom']}' créée !")
            st.markdown(f"<div style='background:#e8f5e9;padding:20px;border-radius:10px;border:1px solid #c8e6c9;'><p><strong>🔑 Identifiant :</strong> <code style='color:#d84315;font-size:1.2rem;'>{info['user']}</code></p><p><strong>🔒 Mot de passe :</strong> <code style='color:#d84315;font-size:1.2rem;'>{info['mdp']}</code></p></div>", unsafe_allow_html=True)
            if st.button("OK"): del st.session_state['new_equipe_info']; st.rerun()

        st.markdown("---")
        for eq in c.execute("SELECT id, nom_equipe, responsable, bureau FROM equipes WHERE paroisse_id=? ORDER BY nom_equipe", (pid,)).fetchall():
            eq_id, eq_nom, eq_resp, eq_bur = eq
            nb_m = c.execute("SELECT COUNT(*) FROM membres WHERE equipe_id=? AND statut='actif'", (eq_id,)).fetchone()[0]
            
            with st.expander(f"📌 {eq_nom} - {eq_resp} ({nb_m}/{get_max_membres(eq_id)} membres)"):
                if not st.session_state.get(f'edit_eq_par_{eq_id}'):
                    if st.button("✏️ Modifier l'équipe", key=f"btn_edit_eq_par_{eq_id}"):
                        st.session_state[f'edit_eq_par_{eq_id}'] = True
                        st.rerun()
                
                if st.session_state.get(f'edit_eq_par_{eq_id}'):
                    if st.button("🔑 Réinitialiser le mot de passe de connexion", key=f"reset_pwd_eq_par_{eq_id}"):
                        new_mdp = generer_mot_de_passe()
                        c.execute("UPDATE utilisateurs SET password=? WHERE equipe_id=? AND role='equipe'", (hash_password(new_mdp), eq_id))
                        commit_and_sync()
                        st.session_state[f'new_pwd_eq_par_{eq_id}'] = new_mdp
                    
                    if st.session_state.get(f'new_pwd_eq_par_{eq_id}'):
                        st.markdown(f"<div style='background:#fff3e0;padding:15px;border-radius:10px;border:1px solid #ffe0b2;'>🔑 Nouveau mot de passe de l'équipe : <code style='color:#d84315;font-size:1.2rem;'>{st.session_state[f'new_pwd_eq_par_{eq_id}']}</code></div>", unsafe_allow_html=True)
                        
                    with st.form(f"form_edit_eq_par_{eq_id}"):
                        new_nom = st.text_input("Nom de l'équipe", value=eq_nom, key=f"edit_nom_{eq_id}")
                        new_resp = st.text_input("Responsable", value=eq_resp, key=f"edit_resp_{eq_id}")
                        new_bur = st.text_area("Bureau", value=eq_bur, key=f"edit_bur_{eq_id}")
                        
                        c1, c2 = st.columns(2)
                        with c1:
                            if st.form_submit_button("💾 Enregistrer"):
                                c.execute("UPDATE equipes SET nom_equipe=?, responsable=?, bureau=? WHERE id=?", (new_nom, new_resp, new_bur, eq_id))
                                commit_and_sync()
                                if f'new_pwd_eq_par_{eq_id}' in st.session_state: del st.session_state[f'new_pwd_eq_par_{eq_id}']
                                del st.session_state[f'edit_eq_par_{eq_id}']
                                st.success("Équipe et accès mis à jour !")
                                st.rerun()
                        with c2:
                            if st.form_submit_button("❌ Annuler"):
                                if f'new_pwd_eq_par_{eq_id}' in st.session_state: del st.session_state[f'new_pwd_eq_par_{eq_id}']
                                del st.session_state[f'edit_eq_par_{eq_id}']
                                st.rerun()
                else:
                    st.write(f"**Bureau :** {eq_bur}")
                    user_info = c.execute("SELECT username FROM utilisateurs WHERE equipe_id=? AND role='equipe'", (eq_id,)).fetchone()
                    if user_info: st.code(f"🔑 Connexion : {user_info[0]}")
                
                # NOUVEAU : Bouton de suppression d'équipe
                st.markdown("---")
                if nb_m == 0:
                    if st.button(f"🗑️ Supprimer définitivement l'équipe {eq_nom}", key=f"del_eq_{eq_id}", type="secondary"):
                        c.execute("DELETE FROM utilisateurs WHERE equipe_id=?", (eq_id,))
                        c.execute("DELETE FROM equipes WHERE id=?", (eq_id,))
                        commit_and_sync()
                        st.success(f"Équipe {eq_nom} supprimée.")
                        st.rerun()
                else:
                    st.info("💡 Pour supprimer cette équipe, vous devez d'abord archiver ou transférer ses membres.")
                
                if st.button(f"📋 Voir les membres de {eq_nom}", key=f"btn_membres_eq_{eq_id}"):
                    st.session_state['show_membres_equipe'] = eq_id if st.session_state.get('show_membres_equipe') != eq_id else None
                    st.rerun()
                                
                if st.session_state.get('show_membres_equipe') == eq_id:
                    mbrs = c.execute("SELECT matloc, matricule, nom, prenom, whatsapp, numero_meditation, date_adhesion FROM membres WHERE equipe_id=? AND statut='actif' ORDER BY nom", (eq_id,)).fetchall()
                    if mbrs:
                        df = pd.DataFrame(mbrs, columns=["MatLoc", "Matricule", "Nom", "Prénom", "WhatsApp", "N° méditation", "Date adhésion"]); df.index=df.index+1
                        st.dataframe(df, width="stretch")

    elif menu == "👤 Membres":
        st.markdown(f'<h2 style="color:#1A237E;">👤 Membres - {nom_p}</h2>', unsafe_allow_html=True)        
        equipes = c.execute("SELECT id, nom_equipe FROM equipes WHERE paroisse_id=?", (pid,)).fetchall()
        if not equipes: st.warning("Créez d'abord une équipe.")
        else:
            eq_dict = {e[1]: e[0] for e in equipes}
            choix = st.selectbox("Équipe", list(eq_dict.keys()))
            eid = eq_dict[choix]
            max_m = get_max_membres(eid)
            nb = c.execute("SELECT COUNT(*) FROM membres WHERE equipe_id=? AND statut='actif'", (eid,)).fetchone()[0]
            st.info(f"{nb}/{max_m} membres")
            
            if nb < max_m and st.button("➕ Ajouter un membre"): st.session_state['form_mbr_par'] = "ajout"
            if st.session_state.get('form_mbr_par') == "ajout":
                with st.form("aj_mbr"):
                    c1, c2 = st.columns(2)
                    with c1: n, p = st.text_input("Nom"), st.text_input("Prénom")
                    dn = st.date_input("Naissance", min_value=date(1950, 1, 1), max_value=date.today())
                    with c2: w, nm = st.text_input("WhatsApp"), st.text_input("N° méd.", max_chars=2)
                    ph = st.file_uploader("Photo", ['jpg','png','webp'])
                    # COHABITATION : lien imgbb prioritaire, sinon fichier
                    ph_lien = st.text_input("…ou lien de photo (https://... — ex. imgbb : i.ibb.co/…)")
                    da = st.date_input("Date d'adhésion", min_value=date(1950, 1, 1), max_value=date.today(), value=date.today())

                    if st.form_submit_button("✅ Ajouter"):
                        if not (n and p):
                            st.error("Le nom et le prénom sont requis.")
                        elif ph_lien.strip() and not ph_lien.strip().startswith("http"):
                            st.error("Le lien de photo doit commencer par https://")
                        else:
                            mat = generer_matricule_unique()
                            c.execute("""INSERT INTO membres (matloc, nom, prenom, date_naissance, whatsapp, date_adhesion, paroisse_id, equipe_id, statut, numero_meditation, matricule) VALUES (?,?,?,?,?,?,?,?,?,?,?)""", (mat, n, p, dn.isoformat(), w, da.isoformat(), pid, eid, 'actif', nm, mat))
                            mid = c.lastrowid
                            # COHABITATION : lien imgbb prioritaire, sinon upload Cloudinary/local
                            photo_finale = ph_lien.strip() if ph_lien.strip() else (sauvegarder_photo(ph, mat) if ph else None)
                            if photo_finale:
                                c.execute("UPDATE membres SET photo_path=? WHERE id=?", (photo_finale, mid))
                            commit_and_sync(); del st.session_state['form_mbr_par']; st.success(f"Ajouté ! {mat}"); st.rerun()
            for m in c.execute("SELECT id, matloc, nom, prenom, whatsapp, photo_path, date_adhesion, numero_meditation, matricule FROM membres WHERE equipe_id=? AND statut='actif'", (eid,)).fetchall():
                with st.expander(f"{m[2]} {m[3]} - {m[1]}"):
                    c1, c2 = st.columns([3,1])
                    c1.write(f"👥 **Équipe :** {choix}\n💬 {m[4]} | 📅 {m[6]} | Matricule: {m[8] or '-'}")
                    if m[5]: c1.image(m[5], width=80)
                    with c2:
                        if st.button("📦 Archiver", key=f"btn_arch_p_{m[0]}"): st.session_state[f'form_arch_p_{m[0]}'] = True
                    
                    if st.session_state.get(f'form_arch_p_{m[0]}'):
                        with st.form(f"fa_arch_{m[0]}"):
                            sit = st.radio("Situation", ["Transféré", "Déplacé", "Radié", "Défunt"])
                            ac1, ac2 = st.columns(2)
                            with ac1: ad = st.number_input("Année début", 2000, date.today().year, date.today().year)
                            with ac2: af = st.number_input("Année fin", 2000, date.today().year+5, date.today().year+1)
                            com = st.text_area("Commentaire")
                            
                            equipe_destination = None
                            if sit == "Transféré":
                                equipes_dispo = c.execute("SELECT id, nom_equipe FROM equipes WHERE paroisse_id=? AND id != ?", (pid, eid)).fetchall()
                                if equipes_dispo:
                                    dest_dict = {e[1]: e[0] for e in equipes_dispo}
                                    dest_nom = st.selectbox("Équipe d'accueil", list(dest_dict.keys()))
                                    equipe_destination = dest_dict[dest_nom]
                                    nb_dest = c.execute("SELECT COUNT(*) FROM membres WHERE equipe_id=? AND statut='actif'", (equipe_destination,)).fetchone()[0]
                                    if nb_dest >= get_max_membres(equipe_destination): st.error(f"Impossible : l'équipe {dest_nom} est pleine.")
                                else: st.warning("Aucune autre équipe.")

                            col1, col2 = st.columns(2)
                            with col1:
                                if st.form_submit_button("❌ Annuler"): del st.session_state[f'form_arch_p_{m[0]}']; st.rerun()
                            with col2:
                                if st.form_submit_button("✅ Confirmer"):
                                    if af <= ad: st.error("Année invalide.")
                                    elif sit == "Transféré" and not equipe_destination: st.error("Sélectionnez une équipe.")
                                    elif sit == "Transféré":
                                        if c.execute("SELECT COUNT(*) FROM membres WHERE equipe_id=? AND statut='actif'", (equipe_destination,)).fetchone()[0] >= get_max_membres(equipe_destination):
                                            st.error("Impossible : l'équipe d'accueil est pleine.")
                                        else:
                                            c.execute("UPDATE membres SET statut='archive' WHERE id=?", (m[0],))
                                            c.execute('''INSERT INTO archives (membre_id, situation, date_debut, date_fin, commentaire, auteur_id, auteur_nom, auteur_role, paroisse_id, equipe_id) VALUES (?, 'Transféré', ?, ?, ?, ?, ?, ?, ?, ?)''', (m[0], date(ad, 9, 1).isoformat(), date(af, 9, 1).isoformat(), f"Transféré vers {dest_nom}", st.session_state['user_id'], st.session_state['username'], 'paroisse', pid, eid))
                                            c.execute("UPDATE membres SET equipe_id=?, statut='actif' WHERE id=?", (equipe_destination, m[0]))
                                            commit_and_sync()
                                            del st.session_state[f'form_arch_p_{m[0]}']
                                            st.success(f"Membre transféré vers {dest_nom} !")
                                            st.rerun()
                                    else:
                                        archiver_membre(m[0], sit, ad, af, com, st.session_state['user_id'], st.session_state['username'], 'paroisse', pid, eid)
                                        del st.session_state[f'form_arch_p_{m[0]}']; st.success("Archivé !"); st.rerun()

    elif menu == "📊 Statistiques":
        st.markdown(f'<h2 style="color:#1A237E;">📊 Statistiques - {nom_p}</h2>', unsafe_allow_html=True)
        # v7.9.1 — 2ᵉ onglet « 🚦 Tableau de bord » : la vue d'ensemble
        # (effectifs, abonnements, intentions, prochaine prière, fréquentation).
        _t_stats, _t_bord = st.tabs(["📈 Vue d'ensemble", "🚦 Tableau de bord"])
        with _t_stats:
            c1, c2 = st.columns(2)
            c1.metric("Équipes", c.execute("SELECT COUNT(*) FROM equipes WHERE paroisse_id=?", (pid,)).fetchone()[0])
            c2.metric("Membres actifs", c.execute("SELECT COUNT(*) FROM membres WHERE paroisse_id=? AND statut='actif'", (pid,)).fetchone()[0])
        with _t_bord:
            _tableau_de_bord_paroisse(pid, nom_p)

    elif menu == "📅 Abonnements":
        st.markdown(f'<h2 style="color:#1A237E;">💰 État des abonnements - {nom_p}</h2>', unsafe_allow_html=True)
        
        annee_pastorale_en_cours = get_periode_pastorale()[0]
        annee = st.number_input("Année de début de période", min_value=2020, max_value=annee_pastorale_en_cours, value=annee_pastorale_en_cours, step=1)
        st.write(f"**Période observée :** {periode_affichage(annee)}")
        
        stats_p = c.execute('''SELECT COUNT(m.id), SUM(CASE WHEN a.annee_debut=? AND a.statut='paye' THEN 1 ELSE 0 END) FROM membres m LEFT JOIN abonnements a ON m.id = a.membre_id AND a.annee_debut=? WHERE m.paroisse_id=? AND m.statut='actif' ''', (annee, annee, pid)).fetchone()
        # v-pb1 — blindage : Turso peut renvoyer les agrégats en TEXTE
        total_p = int(stats_p[0]) if stats_p and stats_p[0] else 0
        payes_p = int(stats_p[1]) if stats_p and stats_p[1] else 0
        
        if total_p > 0:
            pourcent_str = str(round(payes_p / total_p * 100)) + "%"
        else:
            pourcent_str = "0%"
        
        c1, c2 = st.columns(2)
        c1.metric("Total membres (Paroisse)", total_p)
        c2.metric("Abonnements enregistrés", payes_p)
        st.caption(f"📊 **Taux de recouvrement :** {pourcent_str}")
        
        st.markdown("---")
        
        for eq in c.execute("SELECT id, nom_equipe FROM equipes WHERE paroisse_id=? ORDER BY nom_equipe", (pid,)).fetchall():
            stats_eq = c.execute('''SELECT COUNT(m.id) as total, SUM(CASE WHEN a.annee_debut=? AND a.statut='paye' THEN 1 ELSE 0 END) as payes FROM membres m LEFT JOIN abonnements a ON m.id = a.membre_id AND a.annee_debut=? WHERE m.equipe_id=? AND m.statut='actif' GROUP BY m.equipe_id''', (annee, annee, eq[0])).fetchone()
            
            if stats_eq:
                # v-pb1 — blindage identique
                total_eq = int(stats_eq[0]) if stats_eq[0] else 0
                payes_eq = int(stats_eq[1]) if stats_eq[1] else 0
                
                if total_eq > 0:
                    pourcent_eq_str = str(round(payes_eq / total_eq * 100)) + "%"
                else:
                    pourcent_eq_str = "0%"
                
                with st.expander(f"📌 {eq[1]} - {payes_eq}/{total_eq} à jour ({pourcent_eq_str})"):
                    non_payes = c.execute('''SELECT m.nom, m.prenom, m.matricule FROM membres m WHERE m.equipe_id=? AND m.statut='actif' AND m.id NOT IN (SELECT membre_id FROM abonnements WHERE annee_debut=? AND statut='paye') ORDER BY m.nom''', (eq[0], annee)).fetchall()
                    
                    if non_payes:
                        st.write("❌ **En attente :**")
                        for np in non_payes:
                            st.write("- " + np[0] + " " + np[1] + " (`" + np[2] + "`)")
                    else: 
                        st.success("✅ Tous à jour !")

    elif menu == "📌 Suivi":
        st.markdown(f'<h2 style="color:#1A237E;">📌 Suivi et Agenda - {nom_p}</h2>', unsafe_allow_html=True)
        equipes = c.execute("SELECT id, nom_equipe FROM equipes WHERE paroisse_id=?", (pid,)).fetchall()
        
        if not equipes:
            st.warning("Aucune équipe créée dans cette paroisse. Vous ne pouvez pas gérer le suivi.")
        else:
            # v7.8.14 — SÉLECTEUR PERSISTANT (remplace st.tabs, qui ne garde
            # aucune mémoire : chaque interaction ramenait à l'onglet primaire).
            # v7.9.0 — 4e onglet : « 🙏 Coins des Intentions » (bilan des
            # intentions confiées aux équipes + réglage de la chaîne de
            # prière universelle).
            _onglets_par = ["📅 Agenda", "📝 Vie de prière des équipes",
                            "📊 Engagement spirituel", "🙏 Coins des Intentions"]
            _suivi_par = st.radio("Section du suivi", _onglets_par, key="par_suivi_onglet",
                                  horizontal=True, label_visibility="collapsed")
            st.markdown("---")
            if _suivi_par == _onglets_par[0]:
                ajouter_evenement_agenda(paroisse_id=pid, auteur_nom=st.session_state['username'])
                st.markdown("---")
                afficher_agenda_complet_universel(paroisse_id=pid)

            elif _suivi_par == _onglets_par[1]:
                st.markdown("### 📋 Faire le point des équipes")
                eq_dict = {eq[1]: eq[0] for eq in equipes}
                choix_eq = st.selectbox("Sélectionnez l'équipe à consulter", list(eq_dict.keys()), key="suivi_paroisse_eq")
                eid = eq_dict[choix_eq]
                
                types_evenements = ["Tous", "Prière mensuelle", "Prière commune", "Prière spéciale", "Pèlerinage", "Réunion", "Autre"]
                filtre_type = st.selectbox("Filtrer par type d'évènement", types_evenements, key="filtre_hist_par")
                
                afficher_historique_suivi(equipe_id=eid, filtre_type=filtre_type)

            elif _suivi_par == _onglets_par[3]:
                # v7.9.0 — 🙏 Coins des Intentions : bilan des intentions
                # confiées aux équipes + réglage de la chaîne de prière.
                _onglet_coins_intentions(pid, equipes)

            else:
                eq_dict2 = {eq[1]: eq[0] for eq in equipes}
                choix_eq2 = st.selectbox("Sélectionnez l'équipe pour voir le bilan", list(eq_dict2.keys()), key="etat_paroisse_eq")
                eid2 = eq_dict2[choix_eq2]
                afficher_etat_presences_globales(equipe_id=eid2)
    elif menu == "💬 WhatsApp":
        st.markdown(f'<h2 style="color:#1A237E;">💬 Messages WhatsApp - {nom_p}</h2>', unsafe_allow_html=True)
        afficher_whatsapp_tabs(equipe_id=None)

    elif menu == "📥 Export Excel":
        st.markdown(f'<h2 style="color:#1A237E;">📥 Export des membres - {nom_p}</h2>', unsafe_allow_html=True)
        mbrs = c.execute('''SELECT m.matloc, m.nom, m.prenom, m.date_naissance, m.whatsapp, m.date_adhesion, e.nom_equipe FROM membres m JOIN equipes e ON m.equipe_id=e.id WHERE m.paroisse_id=? AND m.statut='actif' ''', (pid,)).fetchall()
        if mbrs:
            df = pd.DataFrame(mbrs, columns=["MatLoc", "Nom", "Prénom", "Naissance", "WhatsApp", "Adhésion", "Équipe"])
            out = io.BytesIO()
            with pd.ExcelWriter(out, engine='openpyxl') as w: df.to_excel(w, index=False)
            out.seek(0); st.download_button("📥 Télécharger", out, f"membres_{nom_p}.xlsx")
    
    elif menu == "📦 Archives":
        st.markdown(f'<h2 style="color:#1A237E; font-size: 1.4rem;">📦 Archives - {nom_p}</h2>', unsafe_allow_html=True)
        archives = c.execute('''SELECT m.matloc, m.nom, m.prenom, a.situation, a.date_debut, a.date_fin, a.commentaire, a.equipe_id, a.auteur_nom FROM archives a JOIN membres m ON a.membre_id = m.id WHERE a.paroisse_id = ? ORDER BY a.date_fin DESC''', (pid,)).fetchall()
        if not archives: st.info("Aucune archive.")
        else:
            for a in archives:
                d1, d2 = safe_date(a[4]), safe_date(a[5])
                duree = (d2 - d1).days // 365 if d1 and d2 else 0
                eq_nom = c.execute("SELECT nom_equipe FROM equipes WHERE id=?", (a[7],)).fetchone()[0] if a[7] else "N/A"
                with st.expander(f"{a[1]} {a[2]} ({a[0]}) – {afficher_situation(a[3])} – {duree} an(s) ({eq_nom})"):
                    st.write(f"Ajouté par : {a[8] or 'Inconnu'}")
                    if a[6]: st.write(f"Commentaire : {a[6]}")
