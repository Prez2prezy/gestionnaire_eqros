import re
import html
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
                      reserve_compteur, reserve_lignes, publier_reserve_due,
                      OBJECTIF_RESERVE,
                      # v7.9.10 — LE SAS DES INTENTIONS (la zone du jour
                      # déménage du diocèse vers la paroisse)
                      intentions_du_jour_attente, intentions_du_jour_compte,
                      envoyer_intention_du_jour_en_reserve, ecarter_intention_du_jour,
                      # v7.14.4 — la relance (lecture seule, rien n'écrit)
                      cotis_parametres_lire, cotis_relances_lignes,
                      # v7.16.7 — le suivi de près de la caisse (lecture pure)
                      cotis_div_declarations_maison, cotis_declarations_attente,
                      # v7.17.0 — LES CONTRÔLES DU RESPONSABLE (lecture pure) :
                      # le livre des reports de ses équipes, les arriérés
                      cotis_reports_abo_livre, cotis_arrieres_annee,
                      # v7.18.0 — L'AUTORISATION EN GESTE BLOQUANT : les
                      # déclarations de SES membres adressées à la trésorerie
                      # du diocèse attendent SON accord (le responsable
                      # paroissial est le responsable direct du passage)
                      cotis_div_autorisations_attente,
                      cotis_div_autorisation_accorder,
                      cotis_div_autorisation_refuser,
                      cotis_declaration_autorisations_attente,
                      cotis_declaration_autorisation_accorder,
                      cotis_declaration_autorisation_refuser,
                      cotis_div_type_label)
from services import (hash_password, generer_mot_de_passe, sauvegarder_photo, supprimer_photo,
                      archiver_membre, safe_date, afficher_situation, sans_accents, 
                      enregistrer_abonnement, verifier_abonnement, periode_affichage, 
                      generer_matricule_unique, get_periode_pastorale, lien_whatsapp, URL_ESPACE_SPIRITUEL,
                      synchroniser_menu_session, lire_menu_session, afficher_messages_flash)
# v7.13.0 — lignes d'intercession sans redondance
from components import ligne_intercession
from components import (ajouter_evenement_agenda, afficher_agenda_complet_universel, afficher_historique_suivi, 
                        afficher_whatsapp_tabs, widget_type_abonnement, afficher_etat_presences_globales,
                        # v7.14.4 — le message de relance prêt à copier
                        cotis_reglages_aff, cotis_relance_message_collectif,
                        # v7.18.2 — la gestion du panneau bleu de maintenance
                        gestion_maintenance_site)

def _zone_du_jour_paroisse(pid, equipes):
    """🕯️ ZONE DU JOUR — LE SAS DES INTENTIONS (v7.9.10, déménagée du
    diocèse vers la paroisse) : « Les intentions c'est une affaire des
    paroisses et de ses équipes. » Toutes les intentions reçues y
    transitent ; AUCUNE ne peut être publiée sans y passer : relue ici,
    harmonisée (orthographe, dignité, clarté), envoyée en réserve
    IMMÉDIATEMENT — et publiée à 00h00 le jour suivant, heure à laquelle
    la chaîne de prière la montre au fidèle. Portée : les intentions
    confiées aux équipes de LA paroisse (et celles notées à son nom)."""
    st.markdown("### 🕯️ Zone du jour — le sas des intentions confiées")
    afficher_messages_flash()
    st.caption("Toute intention confiée dans la journée arrive ICI d'abord : c'est le "
               "sas, aucune ne peut être publiée sans y passer. Relisez-la, harmonisez "
               "son texte — orthographe, dignité, clarté — puis envoyez-la en réserve : "
               "elle sera publiée à 00h00 le jour suivant, et c'est ce texte soigné que "
               "la chaîne de prière portera au lecteur.")
    _ids_eq = [e[0] for e in equipes]
    _attente, _envoyees_auj, _ecartees = intentions_du_jour_compte(
        equipe_ids=_ids_eq, paroisse_id=pid)
    _m1, _m2, _m3 = st.columns(3)
    _m1.metric("⏳ En attente", _attente)
    _m2.metric("🕊️ Envoyées en réserve (aujourd'hui)", _envoyees_auj)
    _m3.metric("🌙 Écartées", _ecartees)
    st.markdown("---")
    _lignes = intentions_du_jour_attente(equipe_ids=_ids_eq, paroisse_id=pid)
    _noms_eq = {e[0]: e[1] for e in equipes}
    if not _lignes:
        st.info("Aucune intention en attente : le sas est vide — "
                "la chaîne de prière est alimentée. 🕊️")
        return
    for (_zid, _txt, _nom, _anon, _jn, _eqi, _pri, _dt) in _lignes:
        _qui = "🕊️ Anonyme" if _anon else (str(_nom).strip() or "Notre prochain")
        _eq = _noms_eq.get(_eqi)
        _titre = f"🕯️ {_qui} — reçu le {_dt}" + (f" · équipe {_eq}" if _eq else "")
        with st.expander(_titre):
            st.markdown('<div style="background:#f8f5fd; border-left:4px solid #4A148C; '
                        'padding:10px 14px; border-radius:8px; font-style:italic;">'
                        + html.escape(_txt or "") + '</div>', unsafe_allow_html=True)
            _nouveau = st.text_area("Texte harmonisé (tel qu'il sera publié demain à 00h00)",
                                    value=_txt, key=f"zjp_txt_{_zid}", height=100)
            _b1, _b2 = st.columns(2)
            if _b1.button("🕊️ Traiter & envoyer en réserve", key=f"zjp_env_{_zid}",
                          type="primary"):
                _ok, _msg = envoyer_intention_du_jour_en_reserve(_zid, _nouveau)
                if _ok:
                    st.session_state["flash_success"] = _msg
                    st.rerun()
                else:
                    st.error(_msg)
            if _b2.button("🌙 Écarter de la chaîne", key=f"zjp_ec_{_zid}"):
                if ecarter_intention_du_jour(_zid):
                    st.session_state["flash_success"] = ("Intention écartée — elle ne "
                                                         "rejoindra pas la réserve. 🌙")
                    st.rerun()
                else:
                    st.error("Écart impossible (intention déjà traitée).")
    st.caption("🤫 Le principe « être une tombe » demeure : ce qui est lu ici se porte "
               "en prière, ne se raconte pas.")


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

    # ---------- 0. 🕯️ ZONE DU JOUR — LE SAS (v7.9.10, déménagée du diocèse)
    # « Les intentions c'est une affaire des paroisses et de ses équipes. »
    # Aucune intention ne peut être publiée sans y passer : elle y est
    # traitée puis envoyée vers la réserve immédiatement ; la publication
    # se fait à 00h00 du jour suivant.
    _zone_du_jour_paroisse(pid, equipes)
    st.markdown("---")

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
    # v7.13.0 — aperçu SANS REDONDANCE : quand l'intention nomme déjà sa
    # bénéficiaire, la ligne ne répète pas son nom deux fois.
    _ligne_apercu = ligne_intercession(_qui_prochain, _txt_prochain)
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

    # ---------- E. RÉSERVE D'INTENTIONS (v7.9.19) ----------
    # v7.9.19 — la chaîne de la dernière séance a quitté le niveau paroisse :
    # c'est au niveau de chaque équipe qu'elle se note, et c'est elle qui
    # pourvoit la réserve (les intentions des membres y sont posées en face
    # de chaque membre). La réserve ci-dessous RÉUNIT toutes les intentions
    # des réserves d'équipes — membres comme visiteurs.
    _bloc_reserve_paroisse(pid, equipes)


def _bloc_reserve_paroisse(pid, equipes):
    """📚 RÉSERVE D'INTENTIONS (v7.9.19 — titre simplifié, vue d'ensemble ;
    v7.10.3 — LA RÉSERVE REDEVIENT L'AFFAIRE DE LA PAROISSE : « les
    intentions, c'est une affaire de paroisse, de ses membres et visiteurs —
    le diocèse n'a rien à voir dedans. » La rubrique « 📚 Réserve » quitte le
    menu du diocèse, et la liste ne nomme plus les paroisses : retour à la
    vue d'ensemble des réserves d'équipes) :
    la vue PAROISSIALE RÉUNIT toutes les intentions en provenance des
    réserves des équipes — celles des MEMBRES (posées par les responsables
    d'équipe, directement en face de chaque membre dans la chaîne de séance)
    comme celles des VISITEURS (passées par le sas, la 🕯️ Zone du jour).
    « Si un N° méd. contient plus d'une intention, le membre comme le
    visiteur qui médite ce N° méd. verra ses intentions augmentées selon le
    surplus. » Lecture seule ici : l'ajout et le retrait se font dans chaque
    équipe. Compteurs GLOBAUX : la chaîne est universelle."""
    _assurer_table_reserve()
    publier_reserve_due()
    afficher_messages_flash()
    st.markdown("---")
    st.markdown("### 📚 Réserve d'intentions")
    st.caption("La réserve de la paroisse RÉUNIT toutes les intentions des réserves "
               "d'équipes : celles des MEMBRES (posées en face de chaque membre, dans "
               "la ⛓️ Chaîne de la dernière séance de chaque équipe) et celles des "
               "VISITEURS (passées par la 🕯️ Zone du jour). Chaque N° méd. porte AU "
               "MOINS une intention : c'est elle que le lecteur du jour reçoit selon "
               "SON N° méd. — et s'il en porte plusieurs, ses intentions augmentent "
               "selon le surplus. Compteurs et liste toutes équipes confondues (la "
               "chaîne est universelle). 🤫 Comme toujours : être une tombe.")
    _cpt = reserve_compteur()
    _total = sum(_cpt.values())
    _grille = ""
    for n in range(1, 21):
        _nb = _cpt[n]
        _lib = (str(min(_nb, OBJECTIF_RESERVE)) + "/" + str(OBJECTIF_RESERVE)
                + (" +" + str(_nb - OBJECTIF_RESERVE) if _nb > OBJECTIF_RESERVE else ""))
        _grille += (
            '<div style="min-width:62px; flex:1 0 62px; background:'
            + ("#1b2a5e" if _nb else "#121a45")
            + '; border:1px solid '
            + ("#FFD700" if _nb >= OBJECTIF_RESERVE else ("#3a4585" if _nb else "#27306b"))
            + '; border-radius:9px; padding:6px 4px; text-align:center;">'
            + '<div style="color:' + ("#FFD000" if _nb else "#5a6398")
            + '; font-weight:bold; font-size:0.95rem;">' + str(n).zfill(2) + '</div>'
            + '<div style="color:' + ("#e8eaf6" if _nb else "#5a6398")
            + '; font-size:0.72rem;">' + _lib + '</div></div>')
    st.markdown('<div style="display:flex; flex-wrap:wrap; gap:6px; margin:8px 0 4px 0;">'
                + _grille + '</div>', unsafe_allow_html=True)
    if _total >= 20 * OBJECTIF_RESERVE:
        st.success("🎯 Objectif atteint : les 20 N° méd. sont pourvus ("
                   + str(_total) + " intentions en réserve) — la chaîne ne tombera pas à sec.")
    else:
        st.caption("🎯 Objectif : 1 intention par N° méd. (20 au total) — réserve actuelle : "
                   + str(_total) + ".")
    _lignes = reserve_lignes()
    _noms_eq = {e[0]: e[1] for e in equipes}
    if not _lignes:
        st.info("La réserve est vide : les intentions arrivent ici dès que les "
                "équipes les posent (en face de chaque membre, dans la ⛓️ Chaîne de "
                "la dernière séance) et que la 🕯️ Zone du jour en envoie.")
        return
    with st.expander(f"🗂️ Intentions en réserve — toutes les équipes ({len(_lignes)})"):
        _n_par_num = {}
        for (rid, num, texte, auteur, eqi, daj) in _lignes:
            _n_par_num[int(num)] = _n_par_num.get(int(num), 0) + 1
        for (rid, num, texte, auteur, eqi, daj) in _lignes:
            _multi = (" · surplus N° " + str(int(num)).zfill(2)
                      if _n_par_num.get(int(num), 0) > 1 else "")
            st.markdown(f"**N° méd. {int(num):02d}** — *{auteur or 'Membre'}*"
                        + (f" · équipe « {_noms_eq.get(eqi, '?')} »" if eqi else "")
                        + (f" · ajoutée le {daj}" if daj else "") + _multi)
            st.write(texte)
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
                       "« ✅ Merci Sainte Mère de Dieu pour ton aide de ce jour ! ». Le membre est "
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
                      "💼 Ressources", "📌 Suivi", "💬 WhatsApp", "📥 Export Excel", "📦 Archives"]
    # v7.16.7 — LES CAISSES HORS DES ENTITÉS + RESSOURCES : la rubrique
    # « 💼 Caisse de la paroisse » QUITTE le menu (les trésoreries
    # existent en-dehors des entités, à la manière de la cellule de
    # communication) ; « 📅 Abonnements » se mue « 💼 Ressources » — la
    # maison où le responsable fait ses contrôles et les tâches qui lui
    # sont dévolues concernant les finances. La mémoire des sessions
    # suit : l'ancien nom porte le nouveau, l'ancienne caisse ramène à
    # l'accueil de la paroisse.
    _nouveaux_noms_par = {"📅 Abonnements": "💼 Ressources",
                          "💼 Caisse de la paroisse": "🏘️ Ma paroisse"}
    if st.session_state.get("nav_par") in _nouveaux_noms_par:
        st.session_state["nav_par"] = _nouveaux_noms_par[st.session_state["nav_par"]]
    if "nav_par" in st.session_state and st.session_state["nav_par"] not in _rubriques_par:
        del st.session_state["nav_par"]
    if "nav_par" not in st.session_state:
        _rub = lire_menu_session()
        if _rub in _nouveaux_noms_par:
            _rub = _nouveaux_noms_par[_rub]
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

        # v7.16.7 — LA CAISSE HORS DES ENTITÉS (le mot de la maison :
        # « pas en nouvelle rubrique ou en nouvelle section — les
        # trésoreries doivent exister en-dehors des entités comme la
        # cellule de communication pour le diocèse »). La trésorerie de
        # la paroisse tient SA maison avec son propre compte — la caisse,
        # rien d'autre. Le trésorier gère ; le responsable suit de près
        # (les lignes ci-dessous ne font que RELIRE la base) et accorde
        # l'autorisation : le compte se désigne, se renouvelle et se
        # retire ici.
        _tres_ca = c.execute("SELECT id, username FROM utilisateurs "
                             "WHERE paroisse_id=? AND role='tresorier_paroisse'",
                             (pid,)).fetchone()
        _annee_caisse = get_periode_pastorale()[0]
        with st.expander("💼 Caisse de la paroisse (hors des rubriques)"):
            if _tres_ca:
                st.info(f"💼 Caisse tenue par **{_tres_ca[1]}** — la maison s'ouvre avec son propre "
                        "accès (la caisse, rien d'autre) ; le registre ne dit réglé que par elle.")
            else:
                st.info("La caisse de la paroisse vit hors des rubriques, à la manière du compte "
                        "de la cellule communication : le trésorier la tient avec son propre accès — "
                        "la caisse, rien d'autre. La demande d'autorisation se fait ici.")
            # LE SUIVI DE PRÈS (lecture pure — la base n'est jamais écrite ici)
            _att_lignes = cotis_div_declarations_maison("paroisse", paroisse_id=pid,
                                                        annee_debut=_annee_caisse)
            _att_cibles = cotis_declarations_attente(dest="paroisse", paroisse_id=pid,
                                                     annee_debut=_annee_caisse)
            _n_att = len(_att_lignes) + len(_att_cibles)
            _n_recus = c.execute("""SELECT
                    (SELECT COUNT(*) FROM cotisations_diverses d
                     JOIN membres m ON d.membre_id=m.id
                     WHERE m.statut='actif' AND d.destination='paroisse'
                           AND d.regle_le >= datetime('now','-3 days')
                           AND m.paroisse_id=?)
                  + (SELECT COUNT(*) FROM abonnements a
                     JOIN membres m ON a.membre_id=m.id
                     WHERE m.statut='actif' AND a.destination='paroisse'
                           AND a.statut='paye'
                           AND COALESCE(a.cree_le, a.date_paiement) >= date('now','-3 days')
                           AND m.paroisse_id=?)""",
                (pid, pid)).fetchone()[0]
            st.caption(f"👀 Suivi de près — ⏳ {_n_att} déclaration(s) attendent sa "
                       f"confirmation · ✅ {_n_recus} versement(s) réglé(s) ici "
                       "ces dernières 72 heures.")
            if _tres_ca:
                if st.session_state.get(f'pwd_tresca_{pid}'):
                    st.markdown(f"<div style='background:#e8f5e9;padding:15px;border-radius:10px;border:1px solid #c8e6c9;'>🔑 Nouveau mot de passe du trésorier : <code style='color:#d84315;font-size:1.2rem;'>{st.session_state[f'pwd_tresca_{pid}']}</code></div>", unsafe_allow_html=True)
                    if st.button("OK, j'ai noté le mot de passe", key=f"ok_pwd_tresca_{pid}"):
                        del st.session_state[f'pwd_tresca_{pid}']; st.rerun()
                if st.button("🔄 Réinitialiser le mot de passe du trésorier", key=f"reset_tresca_{pid}"):
                    _np_ca = generer_mot_de_passe()
                    c.execute("UPDATE utilisateurs SET password=? WHERE id=?", (hash_password(_np_ca), _tres_ca[0]))
                    commit_and_sync()
                    st.session_state[f'pwd_tresca_{pid}'] = _np_ca
                    st.rerun()
                if st.session_state.get(f'confirm_tresca_{pid}'):
                    st.caption("⚠️ Le titulaire de cet accès perdra l'entrée à la caisse. "
                               "L'autorisation se redonne en un geste, si tu le souhaites.")
                    _ct1ca, _ct2ca = st.columns(2)
                    if _ct1ca.button("🗑️ Oui, retirer l'accès", key=f"del_tresca_go_{pid}", type="primary"):
                        c.execute("DELETE FROM utilisateurs WHERE id=?", (_tres_ca[0],))
                        commit_and_sync()
                        st.session_state[f'confirm_tresca_{pid}'] = False
                        st.success(f"Accès caisse retiré ({_tres_ca[1]}).")
                        st.rerun()
                    if _ct2ca.button("✖ Ne rien retirer", key=f"del_tresca_no_{pid}"):
                        st.session_state[f'confirm_tresca_{pid}'] = False
                        st.rerun()
                elif st.button("🗑️ Retirer l'accès à la caisse", key=f"del_tresca_{pid}"):
                    st.session_state[f'confirm_tresca_{pid}'] = True
                    st.rerun()
            elif st.session_state.get(f'form_tresca_{pid}'):
                _user_par_ca = c.execute("SELECT username FROM utilisateurs WHERE paroisse_id=? AND role='paroisse'",
                                         (pid,)).fetchone()
                # (le form porte un ID différent de son drapeau — l'état de
                # session et les clefs de widgets ne partagent pas leur nom)
                with st.form(f"form_tresorier_ca_{pid}"):
                    _nom_ca = st.text_input("Identifiant du trésorier",
                                            value=f"{(_user_par_ca[0] if _user_par_ca else 'paroisse')}-tres",
                                            key=f"tresca_user_{pid}")
                    _mdp_ca = st.text_input("Mot de passe (laisser vide → généré automatiquement)",
                                            type="password", key=f"tresca_pwd_{pid}")
                    _fc1, _fc2 = st.columns(2)
                    if _fc1.form_submit_button("💼 Donner l'accès à la caisse", use_container_width=True,
                                               key=f"tresca_go_{pid}"):
                        _ident_ca = (_nom_ca or "").strip()
                        if not _ident_ca:
                            st.error("❌ L'identifiant du trésorier est obligatoire.")
                        elif c.execute("SELECT id FROM utilisateurs WHERE username=?", (_ident_ca,)).fetchone():
                            st.error("❌ Cet identifiant existe déjà.")
                        else:
                            _mdp_final_ca = (_mdp_ca or "").strip() or generer_mot_de_passe()
                            c.execute("INSERT INTO utilisateurs (username, password, role, paroisse_id) VALUES (?,?,?,?)",
                                      (_ident_ca, hash_password(_mdp_final_ca), "tresorier_paroisse", pid))
                            commit_and_sync()
                            st.session_state[f'pwd_tresca_{pid}'] = _mdp_final_ca
                            st.session_state[f'form_tresca_{pid}'] = False
                            st.rerun()
                    if _fc2.form_submit_button("✖ Renoncer", use_container_width=True,
                                               key=f"tresca_no_{pid}"):
                        st.session_state[f'form_tresca_{pid}'] = False
                        st.rerun()
            else:
                if st.button("💼 Donner l'accès à la caisse", key=f"add_tresca_{pid}",
                             help="Ouvre la maison de la trésorerie de la paroisse : la caisse seule, "
                                  "hors des rubriques — à la manière du compte de la cellule communication."):
                    st.session_state[f'form_tresca_{pid}'] = True
                    st.rerun()

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

        # v7.18.2 — LE PANNEAU BLEU DE MAINTENANCE (la gestion, en bas du
        # panneau de bord de la paroisse) : la maison pose son mot une fois,
        # tous le voient — visiteurs comme membres — et le geste « 🧹 »
        # éteint le panneau quand la maintenance est rentrée.
        gestion_maintenance_site()

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

                    # v7.16.3 — LE 💼 TRÉSORIER DE LA CAISSE (dossier c, le GO) :
                    # un second accès pour l'équipe, qui n'ouvre QUE la
                    # trésorerie — la caisse sans le reste du Gestionnaire,
                    # à la manière du compte de la cellule communication. La
                    # paroisse désigne, réinitialise ou retire ; l'équipe voit
                    # qui tient sa caisse ; le fidèle ne change de rien.
                    _tres_par = c.execute("SELECT id, username FROM utilisateurs WHERE equipe_id=? AND role='tresorier'", (eq_id,)).fetchone()
                    if _tres_par:
                        st.code(f"💼 Trésorerie : {_tres_par[1]}")
                        if st.session_state.get(f'confirm_tres_{eq_id}'):
                            st.caption("⚠️ Le titulaire de cet accès perdra l'entrée à la trésorerie. "
                                       "Le compte se rouvre en un geste, si la paroisse le souhaite.")
                            _ct1, _ct2 = st.columns(2)
                            if _ct1.button("🗑️ Oui, retirer l'accès", key=f"del_tres_go_{eq_id}", type="primary"):
                                c.execute("DELETE FROM utilisateurs WHERE id=?", (_tres_par[0],))
                                commit_and_sync()
                                st.session_state[f'confirm_tres_{eq_id}'] = False
                                st.success(f"Accès trésorerie retiré ({_tres_par[1]}).")
                                st.rerun()
                            if _ct2.button("✖ Ne rien retirer", key=f"del_tres_no_{eq_id}"):
                                st.session_state[f'confirm_tres_{eq_id}'] = False
                                st.rerun()
                        elif st.button("🗑️ Retirer le compte Trésorier", key=f"del_tres_{eq_id}"):
                            st.session_state[f'confirm_tres_{eq_id}'] = True
                            st.rerun()
                        if st.session_state.get(f'pwd_tres_{eq_id}'):
                            st.markdown(f"<div style='background:#e8f5e9;padding:15px;border-radius:10px;border:1px solid #c8e6c9;'>🔑 Nouveau mot de passe du trésorier : <code style='color:#d84315;font-size:1.2rem;'>{st.session_state[f'pwd_tres_{eq_id}']}</code></div>", unsafe_allow_html=True)
                            if st.button("OK, j'ai noté le mot de passe", key=f"ok_pwd_tres_{eq_id}"):
                                del st.session_state[f'pwd_tres_{eq_id}']; st.rerun()
                        if st.button("🔄 Réinitialiser le mot de passe du trésorier", key=f"reset_tres_{eq_id}"):
                            _np = generer_mot_de_passe()
                            c.execute("UPDATE utilisateurs SET password=? WHERE id=?", (hash_password(_np), _tres_par[0]))
                            commit_and_sync()
                            st.session_state[f'pwd_tres_{eq_id}'] = _np
                            st.rerun()
                    elif st.session_state.get(f'form_tres_{eq_id}'):
                        _user_eq = user_info[0] if user_info else f"tresorier_{eq_id}"
                        with st.form(f"form_tresorier_{eq_id}"):
                            _nom_tres = st.text_input("Identifiant du trésorier", value=f"{_user_eq}-tres", key=f"tres_user_{eq_id}")
                            _mdp_tres = st.text_input("Mot de passe (laisser vide → généré automatiquement)", type="password", key=f"tres_pwd_{eq_id}")
                            _ft1, _ft2 = st.columns(2)
                            if _ft1.form_submit_button("💼 Créer le compte Trésorier", use_container_width=True,
                                                       key=f"tres_go_{eq_id}"):
                                _ident_t = (_nom_tres or "").strip()
                                if not _ident_t:
                                    st.error("❌ L'identifiant du trésorier est obligatoire.")
                                elif c.execute("SELECT id FROM utilisateurs WHERE username=?", (_ident_t,)).fetchone():
                                    st.error("❌ Cet identifiant existe déjà.")
                                else:
                                    _mdp_final_t = (_mdp_tres or "").strip() or generer_mot_de_passe()
                                    c.execute("INSERT INTO utilisateurs (username, password, role, paroisse_id, equipe_id) VALUES (?,?,?,?,?)",
                                              (_ident_t, hash_password(_mdp_final_t), "tresorier", pid, eq_id))
                                    commit_and_sync()
                                    st.session_state[f'pwd_tres_{eq_id}'] = _mdp_final_t
                                    st.session_state[f'form_tres_{eq_id}'] = False
                                    st.rerun()
                            if _ft2.form_submit_button("✖ Renoncer", use_container_width=True,
                                                       key=f"tres_no_{eq_id}"):
                                st.session_state[f'form_tres_{eq_id}'] = False
                                st.rerun()
                    else:
                        if st.button("💼 Désigner un trésorier", key=f"add_tres_{eq_id}",
                                     help="Ouvre un second accès pour l'équipe : la trésorerie seulement, sans le reste du Gestionnaire."):
                            st.session_state[f'form_tres_{eq_id}'] = True
                            st.rerun()
                
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
                    # v7.14.2 — le champ « Statut » aussi ici : la paroisse
                    # enregistre des nouveaux à part, puis les intègre — la
                    # mention « Nouveau » porte une année pastorale.
                    st_m = st.selectbox("Statut", ["Ancien", "Nouveau"],
                                        help="« Nouveau » : première année pastorale dans la base — "
                                             "il s'abonne (abonnement). La mention porte une année, "
                                             "puis retombe d'elle-même.")

                    if st.form_submit_button("✅ Ajouter"):
                        if not (n and p):
                            st.error("Le nom et le prénom sont requis.")
                        elif ph_lien.strip() and not ph_lien.strip().startswith("http"):
                            st.error("Le lien de photo doit commencer par https://")
                        else:
                            mat = generer_matricule_unique()
                            c.execute("""INSERT INTO membres (matloc, nom, prenom, date_naissance, whatsapp, date_adhesion, paroisse_id, equipe_id, statut, numero_meditation, matricule, mention_nouveau, mention_annee) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", (mat, n, p, dn.isoformat(), w, da.isoformat(), pid, eid, 'actif', nm, mat, ('Nouveau' if st_m == "Nouveau" else None), (get_periode_pastorale()[0] if st_m == "Nouveau" else None)))
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

    elif menu == "💼 Ressources":
        # v7.16.7 — LA MUE DU RÔLE (le mot de la maison) : « le rôle
        # "Abonnement - Réabonnement" au niveau des entités se mue
        # "Ressources". Le responsable pourra y faire ses contrôles et
        # autres tâches qui lui sont dévolues concernant les finances. »
        # La maison du responsable paroissial : l'état des abonnements,
        # le recouvrement équipe par équipe, les relances prêtes à copier
        # — les contrôles, sans jamais écrire à la place des caisses.
        st.markdown(f'<h2 style="color:#1A237E;">💼 Ressources - {nom_p}</h2>', unsafe_allow_html=True)
        
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
        
        for eq in c.execute("SELECT id, nom_equipe, responsable FROM equipes WHERE paroisse_id=? ORDER BY nom_equipe", (pid,)).fetchall():
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
                            # v7.14.4 — un matricule qui dort ne fait plus
                            # tomber la ligne (None concaténé — attrapé au banc)
                            st.write("- " + (np[0] or "") + " " + (np[1] or "") + " (`" + (np[2] or "—") + "`)")
                    else: 
                        st.success("✅ Tous à jour !")
                    # v7.14.4 — LA RELANCE DE L'ÉQUIPE (lecture seule) : le
                    # message prêt à copier pour WhatsApp — la paroisse le
                    # porte au responsable d'équipe, qui le transmet à ses
                    # équipiers. On ne fait que relire la base.
                    _rel_eq = cotis_relances_lignes(equipe_id=eq[0], annee_debut=annee)
                    if _rel_eq:
                        with st.expander("📣 Message de relance (WhatsApp)"):
                            st.caption("Prêt à copier (bouton en haut à droite) — "
                                       "à porter au responsable de l'équipe.")
                            st.code(cotis_relance_message_collectif(
                                eq[1], annee,
                                _rel_eq, cotis_reglages_aff(cotis_parametres_lire()),
                                responsable_nom=str(eq[2] or "").strip()),
                                language=None)

        # v7.17.0 — LES CONTRÔLES DU RESPONSABLE PAROISSIAL (le même
        # regard que chez l'équipe, étendu aux équipes de sa paroisse) :
        # le livre des reports accordés par les caisses de ses équipes,
        # les équipiers hors course et les arriérés de l'année passée —
        # lecture PURE, la base n'est jamais écrite ici ; les gestes
        # restent dans les caisses (celles des équipes, et la caisse de
        # la paroisse hors des rubriques).
        st.markdown("---")
        st.markdown("### 🧭 Les contrôles du responsable")
        st.caption("🔎 Lecture pure — les gestes restent dans les caisses "
                   "(celles des équipes et la caisse de la paroisse).")
        _livre_par = cotis_reports_abo_livre(annee, paroisse_id=pid)
        _rel_par = cotis_relances_lignes(paroisse_id=pid, annee_debut=annee)
        _hors_par = [l for l in _rel_par
                     if l.get("jours") is not None and l["jours"] < 0]
        _vivants_par = [l for l in _livre_par if l["vivant"]]
        _arr_par = cotis_arrieres_annee(annee - 1, paroisse_id=pid)
        _kp1, _kp2, _kp3 = st.columns(3)
        _kp1.metric("⏳ Reports en course", len(_vivants_par),
                    help="Les reports d'échéance accordés par les caisses "
                         "de tes équipes et toujours vivants.")
        _kp2.metric("⛔ Hors course", len(_hors_par),
                    help="Les équipiers de ta paroisse dont l'échéance "
                         "effective est passée sans règlement.")
        _kp3.metric(f"⏪ Arriérés {annee - 1} - {annee}", len(_arr_par),
                    help="Les impayés de l'année passée portés par tes "
                         "équipiers — le règlement vit dans l'année "
                         "d'origine (sélecteur d'année des caisses).")
        with st.expander(f"📋 Le livre des reports d'échéance — {len(_livre_par)} accord(s) posé(s)"):
            st.caption("Chaque accord posé par une caisse de tes équipes : "
                       "l'échéance d'origine → la reportée, la signature, "
                       "le mot — et l'état du membre aujourd'hui.")
            if _livre_par:
                _df_repp = pd.DataFrame([{
                    "Membre": f"{l['nom']} {l['prenom']}",
                    "Équipe": l["equipe"],
                    "D'origine": l["echeance_origine"],
                    "Reportée au": l["echeance_reportee"],
                    "Accordée par": (l["accordee_par_nom"] or "—")
                                    + (f" ({l['accordee_par_role']})"
                                       if l["accordee_par_role"] else ""),
                    "Le mot": l["motif"] or "—",
                    "État": l["etat"],
                } for l in _livre_par])
                _df_repp.index = _df_repp.index + 1
                st.dataframe(_df_repp, width="stretch")
            else:
                st.info("Aucun report posé par les caisses de tes équipes "
                        "pour cette année.")
        with st.expander(f"⛔ Hors course — {len(_hors_par)} équipier(s) hors délai"):
            if _hors_par:
                _df_hcp = pd.DataFrame([{
                    "Membre": f"{l['nom']} {l['prenom']}",
                    "Équipe": l["equipe"],
                    "MatLoc": l["matloc"] or "—",
                    "Échéance effective": l["echeance_aff"],
                    "Dépassée de": f"{-l['jours']} jour(s)",
                } for l in _hors_par])
                _df_hcp.index = _df_hcp.index + 1
                st.dataframe(_df_hcp, width="stretch")
            else:
                st.success("✅ Personne hors délai dans ta paroisse.")
        with st.expander(f"⏪ Les arriérés de l'année passée ({annee - 1} - {annee}) — "
                         f"{len(_arr_par)} équipier(s)"):
            if _arr_par:
                _df_avp = pd.DataFrame([{
                    "Membre": f"{a[1]} {a[2]}", "Équipe": a[4],
                    "MatLoc": a[3] or "—",
                } for a in _arr_par])
                _df_avp.index = _df_avp.index + 1
                st.dataframe(_df_avp, width="stretch")
            else:
                st.success("✅ Aucun arriéré de l'année passée dans ta "
                           "paroisse.")

        # v7.18.0 — LES AUTORISATIONS À ACCORDER (l'autorisation en geste
        # bloquant — le GESTE du responsable paroissial, au milieu de ses
        # contrôles) : un membre de ta paroisse qui déclare un versement à
        # la trésorerie du DIOCÈSE attend ton accord — tant qu'il n'est pas
        # posé, la caisse du diocèse ne voit RIEN (le blocage est réel, pas
        # une affiche). Les lignes du registre d'abord, puis la mensuelle
        # et l'abonnement déclarés. L'accord se donne en deux temps ; le
        # refus rend le dû au « ⏳ à régler » du membre.
        _authp_lignes = cotis_div_autorisations_attente(
            "paroisse", paroisse_id=pid, annee_debut=annee)
        _authp_decls = cotis_declaration_autorisations_attente(
            "paroisse", paroisse_id=pid, annee_debut=annee)
        _mois_lbls_ap = {1: "Janv.", 2: "Févr.", 3: "Mars", 4: "Avr.",
                         5: "Mai", 6: "Juin", 7: "Juil.", 8: "Août",
                         9: "Sept.", 10: "Oct.", 11: "Nov.", 12: "Déc."}

        def _lbl_mois_ap(_lst):
            return ", ".join(_mois_lbls_ap.get(int(_m), str(_m))
                             for _m in (_lst or []))

        def _fr_ap(_n):
            return f"{int(_n or 0):,}".replace(",", " ")

        st.markdown("---")
        st.markdown("### ✋ Autorisations à accorder")
        if _authp_lignes or _authp_decls:
            st.caption("Un membre de ta paroisse déclare un versement à la "
                       "trésorerie du diocèse : tant que ton autorisation "
                       "n'est pas posée, la caisse du diocèse ne le voit "
                       "pas. L'accord se donne en deux temps ; le refus "
                       "rend le dû au « ⏳ à régler ».")
            # le refus en deux temps (ligne du registre)
            if st.session_state.get('cotis_authp_refus_id'):
                _lp_r = next((_x for _x in _authp_lignes
                              if _x[0] == st.session_state['cotis_authp_refus_id']),
                             None)
                if _lp_r:
                    st.warning(f"🕊️ Refuser l'autorisation pour {_lp_r[6]} "
                               f"{_lp_r[7]} ({_lp_r[8] or '—'}) — "
                               f"{cotis_div_type_label(_lp_r[2]) or _lp_r[2]}"
                               + (f" — {_lp_r[4]}" if _lp_r[4] else "")
                               + f" · {_fr_ap(_lp_r[1])} FCFA déclarés à la "
                                 "trésorerie du diocèse ? La déclaration "
                                 "s'efface et le dû reprend son « ⏳ à "
                                 "régler ».")
                    _rp1, _rp2 = st.columns(2)
                    with _rp1:
                        if st.button("✔️ Oui, refuser l'autorisation",
                                     key="cotis_authp_refus_ok"):
                            cotis_div_autorisation_refuser(
                                st.session_state['cotis_authp_refus_id'])
                            del st.session_state['cotis_authp_refus_id']
                            st.rerun()
                    with _rp2:
                        if st.button("✖ Annuler",
                                     key="cotis_authp_refus_non"):
                            del st.session_state['cotis_authp_refus_id']
                            st.rerun()
                else:
                    del st.session_state['cotis_authp_refus_id']
            # l'accord en deux temps (ligne du registre)
            if st.session_state.get('cotis_authp_id'):
                _lp_a = next((_x for _x in _authp_lignes
                              if _x[0] == st.session_state['cotis_authp_id']),
                             None)
                if _lp_a:
                    st.warning(f"🕊️ Accorder l'autorisation pour {_lp_a[6]} "
                               f"{_lp_a[7]} ({_lp_a[8] or '—'}) — "
                               f"{cotis_div_type_label(_lp_a[2]) or _lp_a[2]}"
                               + (f" — {_lp_a[4]}" if _lp_a[4] else "")
                               + f" · {_fr_ap(_lp_a[1])} FCFA déclarés à la "
                                 "trésorerie du diocèse ? La déclaration "
                                 "parvient aussitôt à la caisse du diocèse, "
                                 "qui confirmera à son geste.")
                    _ap1, _ap2 = st.columns(2)
                    with _ap1:
                        if st.button("✔️ Oui, autoriser ce versement",
                                     key="cotis_authp_ok"):
                            cotis_div_autorisation_accorder(
                                st.session_state['cotis_authp_id'],
                                accorde_par=st.session_state.get('username'))
                            del st.session_state['cotis_authp_id']
                            st.rerun()
                    with _ap2:
                        if st.button("✖ Annuler", key="cotis_authp_non"):
                            del st.session_state['cotis_authp_id']
                            st.rerun()
                else:
                    del st.session_state['cotis_authp_id']
            for _xp in _authp_lignes:
                _dxp = safe_date(_xp[3])
                _dxp_txt = _dxp.strftime("%d/%m/%Y") if _dxp else (_xp[3] or "—")
                _dclp = safe_date(str(_xp[9])[:10] if _xp[9] else None)
                _dclp_txt = (_dclp.strftime("%d/%m à %H:%M") if _dclp
                             else str(_xp[9] or "—")[:16])
                _eqp_nom = _xp[13] or "—"
                _q1p, _q2p, _q3p = st.columns([5, 1, 1])
                with _q1p:
                    st.info(f"🕊️ {_xp[6]} {_xp[7]} ({_xp[8] or '—'}) de "
                            f"l'équipe **{_eqp_nom}** déclare avoir versé à "
                            "la trésorerie du diocèse — "
                            f"{cotis_div_type_label(_xp[2]) or _xp[2]}"
                            + (f" — {_xp[4]}" if _xp[4] else "")
                            + f" · {_fr_ap(_xp[1])} FCFA du {_dxp_txt} · "
                              f"déclaré le {_dclp_txt} — ⏳ ton autorisation "
                              "attend.")
                with _q2p:
                    if st.button("✋", key=f"cotis_authp_{_xp[0]}",
                                 help="Accorder l'autorisation (avec "
                                      "confirmation) — la déclaration "
                                      "part à la caisse du diocèse."):
                        st.session_state['cotis_authp_id'] = _xp[0]
                        st.rerun()
                with _q3p:
                    if st.button("✖", key=f"cotis_authp_ref_{_xp[0]}",
                                 help="Refuser l'autorisation (avec "
                                      "confirmation) — la déclaration "
                                      "s'efface et le dû reprend son "
                                      "« ⏳ à régler »."):
                        st.session_state['cotis_authp_refus_id'] = _xp[0]
                        st.rerun()
            # le refus / l'accord en deux temps (mensuelle / abonnement)
            if st.session_state.get('cotis_authpd_refus_id'):
                _cdp_r = next((_d for _d in _authp_decls
                               if _d[0] == st.session_state['cotis_authpd_refus_id']),
                              None)
                if _cdp_r:
                    _cote_cdp = ("🧮 Mensuelle (" + _lbl_mois_ap(_cdp_r[5]) + ")"
                                 if _cdp_r[3] == "mensuelle"
                                 else "📅 " + ("Abonnement"
                                               if _cdp_r[3] == "abonnement"
                                               else _cdp_r[3]))
                    st.warning(f"🕊️ Refuser l'autorisation pour {_cdp_r[9]} "
                               f"{_cdp_r[10]} ({_cdp_r[12] or '—'}) — "
                               f"{_cote_cdp} · {_fr_ap(_cdp_r[4])} FCFA "
                               "déclarés à la trésorerie du diocèse ? La "
                               "déclaration s'efface et le dû reprend son "
                               "« ⏳ à régler ».")
                    _rp3, _rp4 = st.columns(2)
                    with _rp3:
                        if st.button("✔️ Oui, refuser l'autorisation",
                                     key="cotis_authpd_refus_ok"):
                            cotis_declaration_autorisation_refuser(
                                st.session_state['cotis_authpd_refus_id'])
                            del st.session_state['cotis_authpd_refus_id']
                            st.rerun()
                    with _rp4:
                        if st.button("✖ Annuler",
                                     key="cotis_authpd_refus_non"):
                            del st.session_state['cotis_authpd_refus_id']
                            st.rerun()
                else:
                    del st.session_state['cotis_authpd_refus_id']
            if st.session_state.get('cotis_authpd_id'):
                _cdp_a = next((_d for _d in _authp_decls
                               if _d[0] == st.session_state['cotis_authpd_id']),
                              None)
                if _cdp_a:
                    _cote_cdpa = ("🧮 Mensuelle (" + _lbl_mois_ap(_cdp_a[5]) + ")"
                                  if _cdp_a[3] == "mensuelle"
                                  else "📅 " + ("Abonnement"
                                                if _cdp_a[3] == "abonnement"
                                                else _cdp_a[3]))
                    st.warning(f"🕊️ Accorder l'autorisation pour {_cdp_a[9]} "
                               f"{_cdp_a[10]} ({_cdp_a[12] or '—'}) — "
                               f"{_cote_cdpa} · {_fr_ap(_cdp_a[4])} FCFA "
                               "déclarés à la trésorerie du diocèse ? La "
                               "déclaration parvient aussitôt à la caisse "
                               "du diocèse.")
                    _ap3, _ap4 = st.columns(2)
                    with _ap3:
                        if st.button("✔️ Oui, autoriser ce versement",
                                     key="cotis_authpd_ok"):
                            cotis_declaration_autorisation_accorder(
                                st.session_state['cotis_authpd_id'],
                                accorde_par=st.session_state.get('username'))
                            del st.session_state['cotis_authpd_id']
                            st.rerun()
                    with _ap4:
                        if st.button("✖ Annuler", key="cotis_authpd_non"):
                            del st.session_state['cotis_authpd_id']
                            st.rerun()
                else:
                    del st.session_state['cotis_authpd_id']
            for _dp_au in _authp_decls:
                _cote_dpa = ("🧮 Mensuelle (" + _lbl_mois_ap(_dp_au[5]) + ")"
                             if _dp_au[3] == "mensuelle"
                             else "📅 " + ("Abonnement"
                                           if _dp_au[3] == "abonnement"
                                           else _dp_au[3]))
                _dclp_au = safe_date(str(_dp_au[6])[:10] if _dp_au[6] else None)
                _dclp_au_txt = (_dclp_au.strftime("%d/%m à %H:%M") if _dclp_au
                                else str(_dp_au[6] or "—")[:16])
                _q1d, _q2d, _q3d = st.columns([5, 1, 1])
                with _q1d:
                    st.info(f"🕊️ {_dp_au[9]} {_dp_au[10]} ({_dp_au[12] or '—'}) "
                            f"déclare avoir versé — {_cote_dpa} · "
                            f"{_fr_ap(_dp_au[4])} FCFA · déclaré le "
                            f"{_dclp_au_txt} — ⏳ ton autorisation attend.")
                with _q2d:
                    if st.button("✋", key=f"cotis_authpd_{_dp_au[0]}",
                                 help="Accorder l'autorisation (avec "
                                      "confirmation) — la déclaration "
                                      "part à la caisse du diocèse."):
                        st.session_state['cotis_authpd_id'] = _dp_au[0]
                        st.rerun()
                with _q3d:
                    if st.button("✖", key=f"cotis_authpd_ref_{_dp_au[0]}",
                                 help="Refuser l'autorisation (avec "
                                      "confirmation) — la déclaration "
                                      "s'efface et le dû reprend son "
                                      "« ⏳ à régler »."):
                        st.session_state['cotis_authpd_refus_id'] = _dp_au[0]
                        st.rerun()
        else:
            st.success("✅ Aucune autorisation en attente — les versements "
                       "déclarés à la trésorerie du diocèse par les membres "
                       "de ta paroisse sont tous autorisés, ou il n'y en a "
                       "aucun ce mois.")

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
        # v7.15.1 — « 💬 Messages WhatsApp - {paroisse} » RÉTABLI : l'onglet
        # « 📣 Relances » (déplacé de la caisse) y reste à sa place, groupé
        # par équipe ; les autres sections gardent leur place.
        st.markdown(f'<h2 style="color:#1A237E;">💬 Messages WhatsApp - {nom_p}</h2>', unsafe_allow_html=True)
        # v7.13.1 — LA SECTION RESPIRE SA PAROISSE : la paroisse courante
        # est passée aux quatre onglets (Anniversaires, Relances, Dizaines
        # du jour, Espace de prière) — les membres d'une autre paroisse
        # n'y apparaissent plus jamais.
        afficher_whatsapp_tabs(equipe_id=None, paroisse_id=pid)

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
