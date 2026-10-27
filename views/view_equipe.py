import streamlit as st
import pandas as pd
import io
import logging
from datetime import date
from database import (c, commit_and_sync, verifier_reparer_intentions, jours_depuis,
                      prise_en_charge_automatique, stats_dizaines_jour, serie_dizaines,
                      tableau_pointages_equipe, tableau_pointages_visiteurs,
                      _assurer_table_reserve, reserve_compteur, reserve_lignes,
                      ajouter_intention_reserve, retirer_intention_reserve,
                      OBJECTIF_RESERVE)
from services import (sauvegarder_photo, supprimer_photo, archiver_membre, safe_date, 
                      afficher_situation, enregistrer_abonnement, verifier_abonnement, 
                      periode_affichage, generer_matricule_unique, get_periode_pastorale,
                      get_max_membres, synchroniser_menu_session, lire_menu_session,
                      afficher_messages_flash)
from components import (ajouter_evenement_agenda, afficher_agenda_complet_universel, 
                        afficher_historique_suivi, afficher_whatsapp_tabs, widget_type_abonnement, 
                        enregistrer_presence_equipe, afficher_etat_presences_globales,
                        bloc_chaine_seance)


def _bloc_dizaines_equipe(eid):
    """📿 LA CHAÎNE EN DIRECT (v7.9.2) — bloc en tête de l'onglet
    « 📊 Engagement spirituel » : le responsable voit QUI a égrené sa
    dizaine aujourd'hui (pointage volontaire en fin de livre) et la
    mémoire des jours passés. Les visiteurs (passages anonymes) restent
    globaux.
    v7.9.11 — LE TABLEAU DE LA CHAÎNE, à la demande du fondateur : les
    deux listes du jour (« ✅ Ont pointé » / « ⏳ Pas encore pointé »)
    laissent place à une grille jour par jour — les membres en colonnes,
    « ✅ » dans la case de qui a fait sa méditation, vide sinon. La ligne
    du jour vit en tête ; à 00h00 elle s'archive toute seule et demeure
    consultable à souhait, la ligne du nouveau jour s'affiche. Le même
    tableau sert aux visiteurs (passages anonymes, comptés jour par
    jour, sans jamais les nommer)."""
    st.markdown("#### 📿 Chaîne des dizaines — aujourd'hui")
    st.caption("Le pointage est volontaire : chaque équipier le fait en fin de « 🕯️ Un jour, "
               "une dizaine » (bouton « ✅ Merci Sainte Mère pour ton aide de ce jour! », ou "
               "« ✕ Terminer » en fin de mystère — v7.9.3). Il atteste d'une dizaine égrenée "
               "dans l'application — le contenu de la prière, lui, reste personnel.")
    _mbr, _vis, _liste = stats_dizaines_jour(equipe_id=eid)
    _total_eq = c.execute("SELECT COUNT(*) FROM membres WHERE equipe_id=? AND statut='actif'",
                          (eid,)).fetchone()[0]
    r_d = st.columns(4)
    r_d[0].metric("📿 Dizaines pointées aujourd'hui", f"{_mbr}/{_total_eq}")
    r_d[1].metric("🔥 Passages visiteurs", _vis,
                  delta="communauté (toutes paroisses)" if _vis else None,
                  delta_color="off")
    _pct = str(round(_mbr / _total_eq * 100)) + "%" if _total_eq else "0%"
    r_d[2].metric("📈 Participation de l'équipe", _pct)
    _ser = serie_dizaines(7, equipe_id=eid)
    _somme7 = sum(x[1] for x in _ser)
    r_d[3].metric("🗓️ Sur 7 jours", _somme7,
                  delta="dizaines membres cumulées", delta_color="off")

    # ---- v7.9.11 — LE TABLEAU DE LA CHAÎNE, jour par jour -----------------
    _periode = st.selectbox("Mémoire du tableau", [7, 14, 30], index=1,
                            format_func=lambda n: f"{n} derniers jours",
                            key="chaine_periode_jours")
    _jours, _membres, _grille, _totaux = tableau_pointages_equipe(
        _periode, equipe_id=eid)
    if not _membres:
        st.info("Aucun membre actif : le tableau attendra la première "
                "équipe. 🕊️")
    else:
        _auj = date.today().isoformat()
        _jours_fr = ["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."]
        _lignes = []
        for _j in _jours:
            _d = date.fromisoformat(_j)
            _ligne = {"Jour": ("✨ " if _j == _auj else "")
                      + _d.strftime("%d/%m") + " (" + _jours_fr[_d.weekday()] + ")"}
            for (_mat, _lib) in _membres:
                _ligne[_lib] = "✅" if (_j, _mat) in _grille else ""
            _lignes.append(_ligne)
        # la ligne des totaux : les ✅ de la période, membre par membre
        # (en chaîne — le tableau mêle ✅ et nombres sans broncher)
        _total_l = {"Jour": "📿 Total"}
        for (_mat, _lib) in _membres:
            _total_l[_lib] = str(_totaux.get(_mat, 0))
        _lignes.append(_total_l)
        st.dataframe(pd.DataFrame(_lignes), width="stretch", hide_index=True)
        st.caption("La ligne du jour vit en tête (✨) ; à minuit elle "
                   "s'archive toute seule — les lignes passées demeurent "
                   "consultables à souhait.")
    # ---- v7.9.11 — LES VISITEURS, jour par jour (le même tableau) ---------
    with st.expander("🔥 Les visiteurs, jour par jour"):
        _visiteurs = tableau_pointages_visiteurs(_periode)
        st.dataframe(pd.DataFrame(
            [{"Jour": date.fromisoformat(_j).strftime("%d/%m"),
              "🔥 Visiteurs": ("✅ ×" + str(_n) if _n > 1 else ("✅" if _n else ""))}
             for (_j, _n) in _visiteurs]),
            width="stretch", hide_index=True)
        st.caption("Les visiteurs prient en passants anonymes : le tableau "
                   "note leurs passages, jour après jour, sans jamais les nommer.")

def _assurer_table_intentions_eq():
    """v7.8.14 — création douce de la table des intentions confiées aux équipes
    (statut : 'recue' → 'en_priere' → 'archivee').
    v7.8.15 — colonne auteur_contact (WhatsApp / adresse mail du fidèle).
    v7.8.17 — pont vers la RÉPARATION CENTRALISÉE (database.verifier_reparer_
    intentions) : sonde de lecture + ALTER doux de CHAQUE colonne attendue +
    reconnexion si le cache de statements est périmé — les bases distantes
    créées par un brouillon antérieur peuvent manquer de n'importe quelle
    colonne (correctif de « Impossible de lire les intentions »)."""
    verifier_reparer_intentions()


def _bloc_reserve_equipe(eid):
    """📚 RÉSERVE D'INTENTIONS PAR N° MÉD. (v7.9.3) — pour CHACUN des 20 N°
    de méditation, UNE intention préparée à l'avance (v7.9.4). « Que chacun
    ait sa dernière intention selon son N° méd. » Le responsable ajoute ici
    les intentions de SES membres — le N° méd. du membre désigne
    l'emplacement ; le visiteur du jour reçoit, selon SON N° méd.,
    l'intention de cet emplacement et la médite sur 20 jours."""
    _assurer_table_reserve()
    # v7.9.3 — la confirmation d'un ajout (flash posé par le formulaire)
    # s'affiche ici, en tête du bloc, APRÈS le rerun.
    afficher_messages_flash()
    st.markdown("---")
    st.markdown("### 📚 Réserve d'intentions — 1 intention par N° méd.")
    st.caption("Chaque N° méd. (1-20) porte UNE intention : c'est elle que le visiteur "
               "du jour reçoit selon SON N° méd. et médite pendant 20 jours — chacun "
               "a ainsi sa propre intention de prochain. Ajoutez ici les intentions "
               "de vos membres, une par N° méd. Compteurs toutes équipes confondues "
               "(la chaîne est universelle). 🤫 Comme toujours : être une tombe.")
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
    membres = c.execute("""SELECT id, nom, prenom, numero_meditation FROM membres
                           WHERE equipe_id=? AND statut='actif' ORDER BY nom""",
                        (eid,)).fetchall()
    with st.expander("➕ Ajouter une intention à la réserve"):
        if not membres:
            st.info("Ajoutez d'abord vos membres (« 👤 Mes membres ») : chaque intention "
                    "de la réserve est portée par un membre, selon son N° méd.")
        else:
            with st.form("form_reserve_eq", clear_on_submit=True):
                _sel = st.selectbox(
                    "Membre (son N° méd. désigne l'emplacement de la réserve)",
                    list(range(len(membres))),
                    format_func=lambda i: (
                        f"{membres[i][1]} {membres[i][2]}"
                        + (f" — N° méd. {membres[i][3]}" if membres[i][3]
                           else " — ⚠️ sans N° méd. (renseignez-le dans 👤 Mes membres)")))
                _txt = st.text_area("Intention de prière *", height=90, max_chars=500,
                                    placeholder="Pour la santé de…, pour ma famille…, "
                                                "pour les vocations…")
                if st.form_submit_button("➕ Ajouter à la réserve", type="primary"):
                    _m = membres[_sel]
                    try:
                        _num = int(str(_m[3]).strip()) if _m[3] else None
                    except (TypeError, ValueError):
                        _num = None
                    if _num is None or not (1 <= _num <= 20):
                        st.warning("⚠️ " + str(_m[1]) + " " + str(_m[2])
                                   + " n'a pas de N° méditation valide (1-20). "
                                     "Renseignez-le d'abord dans « 👤 Mes membres ».")
                    else:
                        _ok, _msg = ajouter_intention_reserve(
                            _num, _txt,
                            auteur_nom=(str(_m[1]) + " " + str(_m[2])).strip(),
                            equipe_id=eid)
                        if _ok:
                            st.session_state["flash_success"] = _msg
                            st.rerun()
                        # v7.9.4 — refus (emplacement déjà pourvu) : la lectrice
                        # doit le VOIR — flash en tête de bloc, expander fermé ou pas.
                        st.session_state["flash_warning"] = _msg
                        st.rerun()
    _lignes = reserve_lignes(equipe_id=eid)
    if _lignes:
        with st.expander(f"🗂️ Intentions en réserve de l'équipe ({len(_lignes)})"):
            for (rid, num, texte, auteur, _eqi, daj) in _lignes:
                st.markdown(f"**N° méd. {int(num):02d}** — *{auteur or 'Membre'}*"
                            + (f" · ajoutée le {daj}" if daj else ""))
                st.write(texte)
                if st.button("🗑️ Retirer de la réserve", key=f"res_del_{rid}"):
                    retirer_intention_reserve(rid, equipe_id=eid)
                    st.rerun()
                st.markdown("---")


def _onglet_intentions_equipe(eid):
    """🙏 VOS INTENTIONS À UNE ÉQUIPE (v7.8.14) — onglet de « 📌 Suivi et
    Agenda » : la boîte de réception du responsable. Compteur, 🕊️ Prise en
    prière, 🗄️ Archiver, principe « être une tombe » rappelé."""
    _assurer_table_intentions_eq()
    # v7.9.1 — RÈGLE DU LENDEMAIN : le balayage tourne à chaque ouverture de
    # l'onglet — une intention reçue hier (ou avant) passe automatiquement
    # « en prière » pour 20 jours, sans action du responsable (qui garde le
    # bouton pour une prise en charge IMMÉDIATE le jour même).
    prise_en_charge_automatique()
    st.caption("🙏 Les intentions confiées à votre équipe depuis l’**Espace "
               "communautaire** (« 🙏 Vos intentions à une équipe », juste avant "
               "📰 Actualités de la Paroisse) arrivent ICI, directement à vous. "
               "🤫 **Principe « être une tombe »** : elles ne se racontent pas, "
               "ne se commentent pas et ne sortent jamais de l’équipe — elles se "
               "portent en prière, puis s’archivent. "
               "⏱️ *v7.9.1 : chaque intention reçue passe automatiquement « en "
               "prière » le lendemain de sa réception, pour 20 jours (20 mystères) — "
               "le bouton 🕊️ sert aux prises en charge immédiates du jour même.*")
    try:
        n_rec = c.execute("SELECT COUNT(*) FROM intentions_equipes "
                          "WHERE equipe_id=? AND statut='recue'", (eid,)).fetchone()[0]
        n_pri = c.execute("SELECT COUNT(*) FROM intentions_equipes "
                          "WHERE equipe_id=? AND statut='en_priere'", (eid,)).fetchone()[0]
        n_arc = c.execute("SELECT COUNT(*) FROM intentions_equipes "
                          "WHERE equipe_id=? AND statut='archivee'", (eid,)).fetchone()[0]
        en_attente = c.execute("""SELECT id, texte, auteur_nom, auteur_contact, anonyme,
                                         statut, date_soumission, date_statut
                                  FROM intentions_equipes
                                  WHERE equipe_id=? AND statut != 'archivee'
                                  ORDER BY date_soumission DESC, id DESC""",
                               (eid,)).fetchall()
        archivees = c.execute("""SELECT id, texte, auteur_nom, auteur_contact, anonyme,
                                        date_soumission, date_statut
                                 FROM intentions_equipes
                                 WHERE equipe_id=? AND statut='archivee'
                                 ORDER BY date_statut DESC, id DESC""",
                              (eid,)).fetchall()
    except Exception as _e:
        # v7.8.17 — JOURNALISE l'erreur réelle (le except muet rendait le
        # diagnostic impossible) puis message doux côté responsable.
        logging.getLogger(__name__).warning(
            f"Onglet intentions (équipe {eid}) : lecture impossible — {_e!r}")
        st.error("Impossible de lire les intentions pour le moment. "
                 "Si le problème persiste après un rafraîchissement, notez "
                 "l'heure : l'erreur réelle est inscrite dans les journaux "
                 "de l'application.")
        return
    m1, m2, m3 = st.columns(3)
    m1.metric("🆕 Reçues", n_rec)
    m2.metric("🕊️ En prière", n_pri)
    m3.metric("🗄️ Archivées", n_arc)
    st.markdown("---")
    if not en_attente:
        st.info("Aucune intention en attente : la boîte de réception est vide. "
                "Les fidèles les confient depuis « 🙏 Vos intentions à une "
                "équipe » de l'Espace communautaire.")
    for (iid, texte, auteur, contact, anon, statut, dsoum, dstat) in en_attente:
        badge = "🆕" if statut == 'recue' else "🕊️"
        qui = "Anonyme" if anon else (auteur or "Membre")
        with st.expander(f"{badge} {dsoum} — {qui}"):
            st.write(texte)
            if not anon and (contact or "").strip():
                st.caption("📞 Contact : " + str(contact).strip())
            if statut == 'en_priere':
                # v7.9.0 — règle des 20 mystères rappelée au responsable.
                _j = jours_depuis(dstat or dsoum)
                st.caption("🕊️ En prière depuis le " + str(dstat or dsoum) + " — J+"
                           + str(_j) + "/20 (minimum 20 jours — 20 mystères — sinon "
                           "jusqu’à la prochaine prière mensuelle)"
                           + (" ✅ à archiver à la prochaine prière mensuelle" if _j >= 20 else ""))
            else:
                st.caption("🆕 Reçue le " + str(dsoum))
            b1, b2 = st.columns(2)
            with b1:
                if statut == 'recue':
                    if st.button("🕊️ Prise en prière", key=f"int_pri_{iid}",
                                 width="stretch", type="primary"):
                        c.execute("UPDATE intentions_equipes SET statut='en_priere', "
                                  "date_statut=? WHERE id=?",
                                  (date.today().isoformat(), iid))
                        commit_and_sync()
                        st.rerun()
                else:
                    st.button("🕊️ En prière", key=f"int_pri_ok_{iid}",
                              width="stretch", disabled=True)
            with b2:
                if st.button("🗄️ Archiver", key=f"int_arc_{iid}", width="stretch"):
                    c.execute("UPDATE intentions_equipes SET statut='archivee', "
                              "date_statut=? WHERE id=?",
                              (date.today().isoformat(), iid))
                    commit_and_sync()
                    st.rerun()
    if archivees:
        st.markdown("---")
        with st.expander(f"🗄️ Archives des intentions ({len(archivees)})"):
            for (iid, texte, auteur, contact, anon, dsoum, dstat) in archivees:
                qui = "Anonyme" if anon else (auteur or "Membre")
                st.markdown("**" + str(dsoum) + " — " + qui + "**")
                if not anon and (contact or "").strip():
                    st.caption("📞 Contact : " + str(contact).strip())
                st.write(texte)
                if st.button("🗑️ Supprimer définitivement", key=f"int_del_{iid}"):
                    c.execute("DELETE FROM intentions_equipes WHERE id=?", (iid,))
                    commit_and_sync()
                    st.rerun()
                st.markdown("---")
    # v7.9.3 — la RÉSERVE : 20 intentions par N° méd., préparées d'avance
    # par le responsable (les intentions de ses membres).
    _bloc_reserve_equipe(eid)
    # v7.9.18 — LA CHAÎNE DE LA DERNIÈRE SÉANCE : après chaque prière
    # mensuelle, le responsable note l'ordre des membres présents
    # physiquement ; l'application en tire la traduction (« X aura pour
    # prochain Y — N° méd. Z, méditera et priera son intention jusqu'à la
    # prochaine séance ») et rappelle l'intention à porter pour chaque
    # maillon (prise dans la réserve ci-dessus).
    bloc_chaine_seance([(eid, "")], "eq")


def show_equipe():
    eid = st.session_state['equipe_id']
    equipe_info = c.execute("SELECT nom_equipe, responsable, bureau FROM equipes WHERE id=?", (eid,)).fetchone()
    nom_equipe = equipe_info[0] if equipe_info else "Mon équipe"
    
    pid_result = c.execute("SELECT paroisse_id FROM equipes WHERE id=?", (eid,)).fetchone()
    if not pid_result:
        st.error("Équipe introuvable temporairement. Veuillez actualiser la page (F5).")
        return
    pid = pid_result[0]
    max_membres = get_max_membres(eid)

    _rubriques_eq = ["👥 Mon équipe", "👤 Mes membres", "📅 Abonnements", "📌 Suivi", "💬 WhatsApp", "📦 Archives"]
    if "nav_eq" in st.session_state and st.session_state["nav_eq"] not in _rubriques_eq:
        del st.session_state["nav_eq"]
    if "nav_eq" not in st.session_state:
        _rub = lire_menu_session()
        if _rub and _rub in _rubriques_eq:
            st.session_state["nav_eq"] = _rub
            st.session_state["_menu_sync"] = _rub
    menu = st.sidebar.radio("Navigation", _rubriques_eq, key="nav_eq")
    synchroniser_menu_session(menu)

    # CORRECTION MÉMOIRE : Ajout de 'modif_abo_id' au nettoyage pour éviter les formulaires fantômes
    if st.session_state.get('last_menu') != menu:
        for key in ['open_form_eq', 'delete_membre_id', 'modif_abo_id']:
            if key in st.session_state: del st.session_state[key]
        st.session_state['last_menu'] = menu

    if menu == "👥 Mon équipe":
        st.markdown(f'<h2 style="color:#1A237E; font-size: 1.4rem;">👥 {nom_equipe}</h2>', unsafe_allow_html=True)
        eq = c.execute("SELECT responsable, bureau FROM equipes WHERE id=?", (eid,)).fetchone()
        if eq:
            nb = c.execute("SELECT COUNT(*) FROM membres WHERE equipe_id=? AND statut='actif'", (eid,)).fetchone()[0]
            st.markdown(f'<div class="custom-info-box"><b>Responsable :</b> {eq[0]}<br><b>Bureau :</b> {eq[1]}<br><b>Effectif :</b> {nb}/{max_membres} membres</div>', unsafe_allow_html=True)
            with st.expander("✏️ Modifier les informations"):
                nouveau_resp = st.text_input("Nouveau responsable", value=eq[0] or "")
                nouveau_bureau = st.text_area("Nouveau bureau", value=eq[1] or "")
                if st.button("💾 Enregistrer les modifications", key="update_equipe"):
                    if nouveau_resp:
                        c.execute("UPDATE equipes SET responsable=?, bureau=? WHERE id=?", (nouveau_resp, nouveau_bureau, eid))
                        commit_and_sync(); st.success("Informations mises à jour ! ✅"); st.rerun()
                    else: st.error("Le nom du responsable est obligatoire.")

    elif menu == "👤 Mes membres":
        st.markdown(f'<h2 style="color:#1A237E;">👤 Membres - {nom_equipe}</h2>', unsafe_allow_html=True)
        if 'open_form_eq' not in st.session_state: st.session_state['open_form_eq'] = None
        _par_row = c.execute("SELECT p.nom FROM paroisses p JOIN equipes e ON p.id = e.paroisse_id WHERE e.id=?", (eid,)).fetchone()
        paroisse_nom = _par_row[0] if _par_row and _par_row[0] else "(paroisse non définie)"
        nb = c.execute("SELECT COUNT(*) FROM membres WHERE equipe_id=? AND statut=?", (eid, 'actif')).fetchone()[0]
        st.info(f"{nb}/{max_membres} membres")
        
        if nb < max_membres:
            if st.button("➕ Ajouter un membre", key="btn_ajout_eq"):
                st.session_state['open_form_eq'] = "ajout" if st.session_state['open_form_eq'] != "ajout" else None
                st.rerun()
            
            if st.session_state.get('open_form_eq') == "ajout":
                with st.container():
                    st.markdown("---\n#### ➕ Nouveau membre")
                    with st.form("form_ajout_eq"):
                        c1, c2 = st.columns(2)
                        with c1: nom, prenom = st.text_input("Nom"), st.text_input("Prénom")
                        naissance = st.date_input("Date de naissance", min_value=date(1950,1,1), max_value=date.today())
                        with c2: whatsapp, numero_meditation = st.text_input("WhatsApp"), st.text_input("N° méditation", max_chars=2)
                        photo = st.file_uploader("Photo", type=['jpg','png','jpeg','webp'])
                        # COHABITATION : lien imgbb prioritaire, sinon fichier
                        photo_lien = st.text_input("…ou lien de photo (https://... — ex. imgbb : i.ibb.co/…)")
                        col_date, col_mle = st.columns(2)
                        with col_date: date_adhesion = st.date_input("Date d'adhésion", min_value=date(1950,1,1), max_value=date.today(), value=date.today())
                        with col_mle: matricule_nat = st.text_input("Matricule")
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.form_submit_button("❌ Annuler"): st.session_state['open_form_eq'] = None; st.rerun()
                        with col2:
                            if st.form_submit_button("✅ Ajouter"):
                                if not (nom and prenom):
                                    st.error("Le nom et le prénom sont requis.")
                                elif c.execute("SELECT id FROM membres WHERE nom=? AND prenom=? AND date_naissance=? AND statut=?", (nom, prenom, naissance.isoformat(), 'actif')).fetchone():
                                    st.error("Membre déjà actif")
                                elif photo_lien.strip() and not photo_lien.strip().startswith("http"):
                                    st.error("Le lien de photo doit commencer par https://")
                                else:
                                    matloc = generer_matricule_unique()
                                    c.execute("""INSERT INTO membres (matloc, nom, prenom, date_naissance, whatsapp, date_adhesion, paroisse_id, equipe_id, statut, numero_meditation, matricule) VALUES (?,?,?,?,?,?,?,?,?,?,?)""", (matloc, nom, prenom, naissance.isoformat(), whatsapp, date_adhesion.isoformat(), pid, eid, 'actif', numero_meditation, matricule_nat))
                                    mid = c.lastrowid
                                    # COHABITATION : lien imgbb prioritaire, sinon upload Cloudinary/local
                                    photo_finale = photo_lien.strip() if photo_lien.strip() else (sauvegarder_photo(photo, matloc) if photo else None)
                                    if photo_finale:
                                        c.execute("UPDATE membres SET photo_path=? WHERE id=?", (photo_finale, mid))
                                    commit_and_sync(); st.session_state['open_form_eq'] = None; st.success(f"Ajouté ! MatLoc: {matloc}"); st.rerun()
        
        st.markdown("---")
        membres = c.execute("""SELECT id, matloc, nom, prenom, whatsapp, photo_path, date_adhesion, numero_meditation, matricule FROM membres WHERE equipe_id=? AND statut=? ORDER BY nom""", (eid, 'actif')).fetchall()
        
        for m in membres:
            id_m, matloc, nom, prenom, whatsapp, photo_path, date_adhesion, num_med, matricule_nat = m
            with st.expander(f"{nom} {prenom} - {matloc}" + (f" - N° {num_med}" if num_med else "") + (f" - Mat: {matricule_nat}" if matricule_nat else "")):
                col1, col2 = st.columns([3,1])
                col1.write(f"🏘️ **Paroisse :** {paroisse_nom}\n💬 WhatsApp: {whatsapp}\n📅 Adhésion: {date_adhesion}")
                if photo_path: col1.image(photo_path, width=80)
                with col2:
                    if st.button("✏️ Modifier", key=f"eq_btn_mod_{id_m}"): st.session_state['open_form_eq'] = f"mod_{id_m}"; st.rerun()
                    if st.button("📦 Archiver", key=f"eq_btn_arch_{id_m}"): st.session_state['open_form_eq'] = f"arch_{id_m}"; st.rerun()
                    if st.button("🗑️ Supprimer", key=f"eq_btn_del_{id_m}"): st.session_state['delete_membre_id'] = id_m; st.rerun()
                
                if st.session_state.get('open_form_eq') == f"mod_{id_m}":
                    st.markdown("---\n#### ✏️ Modification")
                    # 1. ON AJOUTE date_naissance ET date_adhesion DANS LA REQUÊTE
                    m_data = c.execute("SELECT nom, prenom, date_naissance, whatsapp, photo_path, numero_meditation, date_adhesion, matricule FROM membres WHERE id=?", (id_m,)).fetchone()
                    if m_data:
                        with st.form(f"form_mod_eq_{id_m}"):
                            st.text_input("MatLoc", value=matloc, disabled=True)
                            new_nom, new_prenom = st.text_input("Nom", value=m_data[0]), st.text_input("Prénom", value=m_data[1])
                            
                            # 2. ON PRÉPARE LES DATES POUR LES AFFICHER CORRECTEMENT
                            dn_initiale = safe_date(m_data[2]) if m_data[2] else date.today()
                            da_initiale = safe_date(m_data[6]) if m_data[6] else date.today()
                            
                            new_whatsapp, new_num_med = st.text_input("WhatsApp", value=m_data[3]), st.text_input("N° méditation", value=m_data[5] or "", max_chars=2)
                            
                            # 3. ON AJOUTE LES CASES DATES COMME DANS LE FORMULAIRE D'AJOUT
                            col_date, col_mle = st.columns(2)
                            with col_date: 
                                new_date_naissance = st.date_input("Date de naissance", value=dn_initiale)
                                new_date_adhesion = st.date_input("Date d'adhésion", value=da_initiale)
                            with col_mle: 
                                new_matricule = st.text_input("Matricule", value=m_data[7] or "")
                            
                            new_photo = st.file_uploader("Nouvelle photo", type=['jpg','png','jpeg','webp'])
                            # COHABITATION : lien imgbb prioritaire, sinon fichier
                            new_photo_lien = st.text_input("…ou lien de photo (https://... — ex. imgbb : i.ibb.co/…)",
                                                           placeholder="Laisser vide pour garder la photo actuelle")
                            col1, col2 = st.columns(2)
                            with col1:
                                if st.form_submit_button("❌ Annuler"): st.session_state['open_form_eq'] = None; st.rerun()
                            with col2:
                                if st.form_submit_button("💾 Enregistrer"):
                                    _lien_ok = True
                                    if new_photo_lien.strip() and not new_photo_lien.strip().startswith("http"):
                                        st.error("Le lien de photo doit commencer par https:// — la photo n'a pas été modifiée.")
                                        _lien_ok = False
                                    # 4. ON MET À JOUR LA BASE DE DONNÉES AVEC LES DATES
                                    c.execute("UPDATE membres SET nom=?, prenom=?, date_naissance=?, whatsapp=?, numero_meditation=?, date_adhesion=?, matricule=? WHERE id=?", 
                                              (new_nom, new_prenom, new_date_naissance.isoformat(), new_whatsapp, new_num_med, new_date_adhesion.isoformat(), new_matricule, id_m))
                                    # COHABITATION : lien imgbb prioritaire, sinon fichier
                                    photo_finale = None
                                    if new_photo_lien.strip() and _lien_ok:
                                        photo_finale = new_photo_lien.strip()
                                    elif new_photo:
                                        photo_finale = sauvegarder_photo(new_photo, matloc)
                                    if photo_finale:
                                        supprimer_photo(m_data[4])
                                        c.execute("UPDATE membres SET photo_path=? WHERE id=?", (photo_finale, id_m))
                                    commit_and_sync(); st.session_state['open_form_eq'] = None; st.success("Membre modifié"); st.rerun()
                
                elif st.session_state.get('open_form_eq') == f"arch_{id_m}":
                    st.markdown("---\n#### 📦 Archivage")
                    with st.form(f"form_arch_eq_{id_m}"):
                        situation = st.radio("Situation", ["Transféré", "Déplacé", "Radié", "Défunt"])
                        c1, c2 = st.columns(2)
                        with c1: annee_debut_arch = st.number_input("Année début (Sept)", min_value=2000, max_value=date.today().year+5, value=date.today().year, step=1)
                        with c2: annee_fin_arch = st.number_input("Année fin (Sept)", min_value=2000, max_value=date.today().year+10, value=date.today().year+1, step=1)
                        commentaire = st.text_area("Commentaire")
                        equipe_destination = None
                        if situation == "Transféré":
                            equipes_dispo = c.execute("SELECT id, nom_equipe FROM equipes WHERE paroisse_id=? AND id != ?", (pid, eid)).fetchall()
                            if equipes_dispo:
                                dest_dict = {e[1]: e[0] for e in equipes_dispo}
                                dest_nom = st.selectbox("Équipe d'accueil", list(dest_dict.keys()))
                                equipe_destination = dest_dict[dest_nom]
                                if c.execute("SELECT COUNT(*) FROM membres WHERE equipe_id=? AND statut='actif'", (equipe_destination,)).fetchone()[0] >= get_max_membres(equipe_destination): st.error("Équipe pleine.")
                            else: st.warning("Aucune autre équipe.")
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.form_submit_button("❌ Annuler"): st.session_state['open_form_eq'] = None; st.rerun()
                        with col2:
                            if st.form_submit_button("✅ Archiver"):
                                if annee_fin_arch <= annee_debut_arch: st.error("Année invalide.")
                                elif situation == "Transféré" and not equipe_destination: st.error("Choisissez une équipe.")
                                elif situation == "Transféré":
                                    if c.execute("SELECT COUNT(*) FROM membres WHERE equipe_id=? AND statut='actif'", (equipe_destination,)).fetchone()[0] >= get_max_membres(equipe_destination):
                                        st.error("Impossible : l'équipe d'accueil est pleine.")
                                    else:
                                        c.execute("UPDATE membres SET statut='archive' WHERE id=?", (id_m,))
                                        c.execute('''INSERT INTO archives (membre_id, situation, date_debut, date_fin, commentaire, auteur_id, auteur_nom, auteur_role, paroisse_id, equipe_id) VALUES (?, 'Transféré', ?, ?, ?, ?, ?, ?, ?, ?)''', (id_m, date(annee_debut_arch, 9, 1).isoformat(), date(annee_fin_arch, 9, 1).isoformat(), f"Transféré vers {dest_nom}", st.session_state['user_id'], st.session_state['username'], 'equipe', pid, eid))
                                        c.execute("UPDATE membres SET equipe_id=?, statut='actif' WHERE id=?", (equipe_destination, id_m))
                                        commit_and_sync(); st.session_state['open_form_eq'] = None; st.success(f"Transféré vers {dest_nom} !"); st.rerun()
                                else:
                                    archiver_membre(id_m, situation, annee_debut_arch, annee_fin_arch, commentaire, st.session_state['user_id'], st.session_state['username'], 'equipe', pid, eid)
                                    st.session_state['open_form_eq'] = None; st.success("Membre archivé"); st.rerun()
        
        if 'delete_membre_id' in st.session_state:
            del_id = st.session_state['delete_membre_id']
            m_del = c.execute("SELECT nom, prenom, photo_path FROM membres WHERE id=?", (del_id,)).fetchone()
            if m_del:
                st.warning(f"⚠️ Supprimer définitivement {m_del[0]} {m_del[1]} ?")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ Oui, supprimer"):
                        if m_del[2]: supprimer_photo(m_del[2])
                        c.execute("DELETE FROM membres WHERE id=?", (del_id,))
                        c.execute("DELETE FROM abonnements WHERE membre_id=?", (del_id,))
                        # CORRECTION CRITIQUE : On supprime aussi ses présences pour ne pas fausser les statistiques !
                        c.execute("DELETE FROM suivi_presences WHERE membre_id=?", (del_id,))
                        commit_and_sync()
                        del st.session_state['delete_membre_id']; st.success("Membre supprimé"); st.rerun()
                with col2:
                    if st.button("❌ Annuler"): del st.session_state['delete_membre_id']; st.rerun()
        
        if membres:
            st.markdown("---\n### 📥 Export des données")
            df_export = pd.DataFrame([(m[1], m[8] or "-", m[2], m[3], m[7], m[4], m[6]) for m in membres], columns=["MatLoc", "Matricule", "Nom", "Prénom", "N° méditation", "WhatsApp", "Date adhésion"])
            output = io.BytesIO()
            try:
                with pd.ExcelWriter(output, engine='openpyxl') as writer: df_export.to_excel(writer, sheet_name=f"Membres_{nom_equipe}", index=False)
                output.seek(0)
                st.download_button("📥 Exporter les membres (Excel)", data=output, file_name=f"membres_{nom_equipe}_{paroisse_nom}_{date.today()}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"export_membres_eq_{eid}_{date.today()}")
            except Exception as e: st.error(f"Erreur export: {e}")

    elif menu == "📅 Abonnements":
        st.markdown(f'<h2 style="color:#1A237E;">💰 Gestion des abonnements - {nom_equipe}</h2>', unsafe_allow_html=True)
        
        # CORRECTION LOGIQUE : Année pastorale par défaut
        annee_pastorale_en_cours = get_periode_pastorale()[0]
        annee = st.number_input("Année de début", 2020, annee_pastorale_en_cours, annee_pastorale_en_cours)
        st.write(f"**Période :** {periode_affichage(annee)}")
        
        for m in c.execute("SELECT id, nom, prenom, matricule FROM membres WHERE equipe_id=? AND statut='actif'", (eid,)).fetchall():
            deja = verifier_abonnement(m[0], annee)
            if deja:
                abo_info = c.execute("SELECT type_abonnement, montant FROM abonnements WHERE membre_id=? AND annee_debut=?", (m[0], annee)).fetchone()
                type_affiche = "Abonnement" if abo_info[0] == "abonnement" else "Réabonnement"
                col_info, col_btn = st.columns([4, 1])
                with col_info: st.info(f"{m[1]} {m[2]} ({m[3]}) – ✅ {type_affiche} ({abo_info[1]} FCFA)")
                with col_btn:
                    if st.button("✏️", key=f"mod_abo_{m[0]}_{annee}"): st.session_state['modif_abo_id'] = m[0]; st.rerun()
            else:
                with st.expander(f"{m[1]} {m[2]} ({m[3]}) – ❌ Non enregistré"):
                    type_abo, montant = widget_type_abonnement("eq", m[0], annee)
                    if st.button("Enregistrer", key=f"btn_eq_{m[0]}_{annee}"): enregistrer_abonnement(m[0], annee, montant, type_abo); st.success("Enregistré !"); st.rerun()

        if 'modif_abo_id' in st.session_state:
            mod_id = st.session_state['modif_abo_id']
            m_info = c.execute("SELECT nom, prenom, matricule FROM membres WHERE id=?", (mod_id,)).fetchone()
            abo_info = c.execute("SELECT type_abonnement, montant FROM abonnements WHERE membre_id=? AND annee_debut=?", (mod_id, annee)).fetchone()
            if m_info and abo_info:
                st.markdown(f"### ✏️ Modifier l'abonnement de {m_info[1]} {m_info[0]}")
                with st.form(f"modif_abo_form_{mod_id}"):
                    index_type = 0 if abo_info[0] == "abonnement" else 1
                    new_type = st.radio("Type", ["📝 Abonnement", "🔄 Réabonnement"], index=index_type, horizontal=True, key=f"mod_type_{mod_id}")
                    montant_actuel = int(abo_info[1]) if abo_info[1] is not None else 0
                    new_montant = st.number_input("Montant (FCFA)", min_value=0, value=montant_actuel, step=500, key=f"mod_mont_{mod_id}")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.form_submit_button("💾 Mettre à jour", width="stretch"):
                            type_str = "abonnement" if "Abonnement" in new_type else "reabonnement"
                            enregistrer_abonnement(mod_id, annee, new_montant, type_str); del st.session_state['modif_abo_id']; st.success("Modifié ✅"); st.rerun()
                    with col2:
                        if st.form_submit_button("🗑️ Supprimer", width="stretch"):
                            c.execute("DELETE FROM abonnements WHERE membre_id=? AND annee_debut=?", (mod_id, annee)); commit_and_sync(); del st.session_state['modif_abo_id']; st.warning("Supprimé."); st.rerun()
                    with col3:
                        if st.form_submit_button("❌ Annuler", width="stretch"): del st.session_state['modif_abo_id']; st.rerun()

        st.markdown("---")
        tab_liste = st.tabs(["📝 Abonnés", "🔄 Réabonnés", "❌ Non enregistrés"])
        with tab_liste[0]:
            abonnes = c.execute('''SELECT m.matricule, m.nom, m.prenom, a.date_paiement, a.montant FROM membres m JOIN abonnements a ON m.id=a.membre_id WHERE m.equipe_id=? AND a.annee_debut=? AND a.type_abonnement='abonnement' AND a.statut='paye' ORDER BY m.nom''', (eid, annee)).fetchall()
            if abonnes:
                # CORRECTION AFFICHAGE : Suppression du champ "N°" en double dans le dictionnaire
                data = [{"Matricule": a[0], "Nom": a[1], "Prénom": a[2], "Date paiement": a[3], "Montant": f"{a[4]} FCFA"} for a in abonnes]
                df = pd.DataFrame(data); df.index = df.index + 1; st.dataframe(df, width="stretch")
            else: st.info("Aucun abonné.")
        with tab_liste[1]:
            reabonnes = c.execute('''SELECT m.matricule, m.nom, m.prenom, a.date_paiement, a.montant FROM membres m JOIN abonnements a ON m.id=a.membre_id WHERE m.equipe_id=? AND a.annee_debut=? AND a.type_abonnement='reabonnement' AND a.statut='paye' ORDER BY m.nom''', (eid, annee)).fetchall()
            if reabonnes:
                # CORRECTION AFFICHAGE : Suppression du champ "N°" en double
                data = [{"Matricule": r[0], "Nom": r[1], "Prénom": r[2], "Date paiement": r[3], "Montant": f"{r[4]} FCFA"} for r in reabonnes]
                df = pd.DataFrame(data); df.index = df.index + 1; st.dataframe(df, width="stretch")
            else: st.info("Aucun réabonné.")
        with tab_liste[2]:
            non_inscrits = c.execute('''SELECT m.matricule, m.nom, m.prenom FROM membres m WHERE m.equipe_id=? AND m.statut='actif' AND m.id NOT IN (SELECT a.membre_id FROM abonnements a WHERE a.annee_debut=? AND a.statut='paye') ORDER BY m.nom''', (eid, annee)).fetchall()
            if non_inscrits:
                # CORRECTION AFFICHAGE : Suppression du champ "N°" en double
                data = [{"Matricule": n[0], "Nom": n[1], "Prénom": n[2]} for n in non_inscrits]
                df = pd.DataFrame(data); df.index = df.index + 1; st.dataframe(df, width="stretch")
            else: st.success("🎉 Tous les membres sont à jour !")

    elif menu == "📌 Suivi":
        st.markdown(f'<h2 style="color:#1A237E;">📌 Suivi et Agenda - {nom_equipe}</h2>', unsafe_allow_html=True)
        # v7.8.14 — SÉLECTEUR PERSISTANT (remplace st.tabs, qui ne garde AUCUNE
        # mémoire entre rafraîchissements : chaque coche ou bouton ramenait à
        # l'onglet primaire) + 4ᵉ onglet « 🙏 Vos intentions à une équipe ».
        _onglets_suivi = ["📅 Agenda", "🙏 Vos intentions à une équipe",
                          "📝 Vie de prière de l'équipe", "📊 Engagement spirituel"]
        _suivi_actif = st.radio("Section du suivi", _onglets_suivi,
                                key="eq_suivi_onglet", horizontal=True,
                                label_visibility="collapsed")
        st.markdown("---")
        if _suivi_actif == _onglets_suivi[0]:
            ajouter_evenement_agenda(equipe_id=eid, auteur_nom=st.session_state['username'])
            st.markdown("---")
            afficher_agenda_complet_universel(equipe_id=eid)
        elif _suivi_actif == _onglets_suivi[1]:
            _onglet_intentions_equipe(eid)
        elif _suivi_actif == _onglets_suivi[2]:
            enregistrer_presence_equipe(equipe_id=eid)
        else:
            # v7.9.2 — le bloc « 📿 Chaîne des dizaines » ouvre l'onglet
            # 📊 Engagement spirituel, avant le détail des présences.
            _bloc_dizaines_equipe(eid)
            st.markdown("---")
            afficher_etat_presences_globales(equipe_id=eid)

    elif menu == "💬 WhatsApp":
        st.markdown(f'<h2 style="color:#1A237E;">💬 Messages WhatsApp - {nom_equipe}</h2>', unsafe_allow_html=True)
        afficher_whatsapp_tabs(equipe_id=eid)
    
    elif menu == "📦 Archives":
        st.markdown(f'<h2 style="color:#1A237E; font-size: 1.4rem;">📦 Archives - {nom_equipe}</h2>', unsafe_allow_html=True)
        membres_actifs = c.execute("SELECT id, nom, prenom, matloc FROM membres WHERE equipe_id=? AND statut='actif' ORDER BY nom", (eid,)).fetchall()
        archives_equipe = c.execute('''SELECT a.id, m.nom, m.prenom, m.matloc, a.situation, a.date_debut, a.date_fin, a.commentaire, m.id as membre_id FROM archives a JOIN membres m ON a.membre_id = m.id WHERE a.equipe_id = ? ORDER BY a.date_fin DESC''', (eid,)).fetchall()
        
        with st.expander("➕ Archiver un membre de l'équipe"):
            if not membres_actifs: st.warning("Aucun membre actif.")
            else:
                with st.form("archive_membre"):
                    membre_choisi = st.selectbox("Membre à archiver", membres_actifs, format_func=lambda x: f"{x[1]} {x[2]} ({x[3]})")
                    situation = st.radio("Situation", ["Transféré", "Déplacé", "Radié", "Défunt"])
                    c1, c2 = st.columns(2)
                    with c1: annee_debut_arch = st.number_input("Année début (Sept)", min_value=2000, max_value=date.today().year+5, value=date.today().year, step=1)
                    with c2: annee_fin_arch = st.number_input("Année fin (Sept)", min_value=2000, max_value=date.today().year+10, value=date.today().year+1, step=1)
                    commentaire = st.text_area("Commentaire (optionnel)")
                    equipe_destination = None
                    if situation == "Transféré":
                        equipes_dispo = c.execute("SELECT id, nom_equipe FROM equipes WHERE paroisse_id=? AND id != ?", (pid, eid)).fetchall()
                        if equipes_dispo:
                            dest_dict = {e[1]: e[0] for e in equipes_dispo}
                            dest_nom = st.selectbox("Équipe d'accueil", list(dest_dict.keys()))
                            equipe_destination = dest_dict[dest_nom]
                            if c.execute("SELECT COUNT(*) FROM membres WHERE equipe_id=? AND statut='actif'", (equipe_destination,)).fetchone()[0] >= get_max_membres(equipe_destination): st.error("Impossible : équipe pleine.")
                        else: st.warning("Aucune autre équipe.")
                    if st.form_submit_button("Archiver"):
                        if annee_fin_arch <= annee_debut_arch: st.error("Année invalide.")
                        elif situation == "Transféré" and not equipe_destination: st.error("Choisissez une équipe.")
                        elif situation == "Transféré":
                            if c.execute("SELECT COUNT(*) FROM membres WHERE equipe_id=? AND statut='actif'", (equipe_destination,)).fetchone()[0] >= get_max_membres(equipe_destination):
                                st.error("Impossible : l'équipe d'accueil est pleine.")
                            else:
                                c.execute("UPDATE membres SET statut='archive' WHERE id=?", (membre_choisi[0],))
                                c.execute('''INSERT INTO archives (membre_id, situation, date_debut, date_fin, commentaire, auteur_id, auteur_nom, auteur_role, paroisse_id, equipe_id) VALUES (?, 'Transféré', ?, ?, ?, ?, ?, ?, ?, ?)''', (membre_choisi[0], date(annee_debut_arch, 9, 1).isoformat(), date(annee_fin_arch, 9, 1).isoformat(), f"Transféré vers {dest_nom}", st.session_state['user_id'], st.session_state['username'], 'equipe', pid, eid))
                                c.execute("UPDATE membres SET equipe_id=?, statut='actif' WHERE id=?", (equipe_destination, membre_choisi[0]))
                                commit_and_sync(); st.success(f"Transféré vers {dest_nom} !"); st.rerun()
                        else:
                            archiver_membre(membre_choisi[0], situation, annee_debut_arch, annee_fin_arch, commentaire, st.session_state['user_id'], st.session_state['username'], 'equipe', pid, eid)
                            st.success(f"✅ {membre_choisi[1]} {membre_choisi[2]} archivé."); st.rerun()
        
        st.markdown(f'<h3 style="color:#1A237E;">✏️ Gérer les archives de votre équipe</h3>', unsafe_allow_html=True)
        if archives_equipe:
            for arch in archives_equipe:
                arch_id, nom, prenom, matloc, situation, date_debut_raw, date_fin_raw, commentaire, membre_id = arch
                d1, d2 = safe_date(date_debut_raw), safe_date(date_fin_raw)
                duree = (d2 - d1).days // 365 if d1 and d2 else 0
                with st.expander(f"{nom} {prenom} ({matloc}) – {afficher_situation(situation)} – {duree} an(s) - Sept {d1.year if d1 else '?'} – Sept {d2.year if d2 else '?'}"):
                    with st.form(f"edit_arch_{arch_id}"):
                        liste_situations = ["Transféré", "Déplacé", "Radié", "Défunt"]
                        index_sit = liste_situations.index(situation) if situation in liste_situations else 0
                        new_situation = st.selectbox("Situation", liste_situations, index=index_sit)
                        c1, c2 = st.columns(2)
                        with c1: new_ad = st.number_input("Année début (Sept)", min_value=2000, max_value=date.today().year+5, value=d1.year if d1 else date.today().year, step=1)
                        with c2: new_af = st.number_input("Année fin (Sept)", min_value=2000, max_value=date.today().year+10, value=d2.year if d2 else date.today().year+1, step=1)
                        new_com = st.text_area("Commentaire", value=commentaire or "")
                        
                        btn1, btn2 = st.columns(2)
                        with btn1:
                            if st.form_submit_button("💾 Mettre à jour"):
                                if new_af <= new_ad: st.error("Année invalide.")
                                else:
                                    c.execute("UPDATE archives SET situation=?, date_debut=?, date_fin=?, commentaire=? WHERE id=?", (new_situation, date(new_ad, 9, 1).isoformat(), date(new_af, 9, 1).isoformat(), new_com, arch_id))
                                    commit_and_sync(); st.success("Archive modifiée"); st.rerun()
                        with btn2:
                            if situation in ("Déplacé", "Radié"):
                                if st.form_submit_button("🔄 Réintégrer"):
                                    c.execute("UPDATE membres SET statut='actif' WHERE id=?", (membre_id,)); c.execute("DELETE FROM archives WHERE id=?", (arch_id,))
                                    commit_and_sync(); st.success(f"{nom} {prenom} réintégré(e)."); st.rerun()
                            else: st.info("Un transféré ou un défunt ne peut pas être réintégré.")
        else: 
            st.info("Aucune archive.")

