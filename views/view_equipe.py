import streamlit as st
import pandas as pd
import io
import os
import json
import base64
import html
import logging
from datetime import date
from database import (c, commit_and_sync, verifier_reparer_intentions, jours_depuis,
                      prise_en_charge_automatique, stats_dizaines_jour, serie_dizaines,
                      tableau_pointages_equipe, tableau_pointages_visiteurs,
                      _assurer_table_reserve, reserve_compteur, reserve_lignes,
                      retirer_intention_reserve, publier_reserve_due,
                      OBJECTIF_RESERVE,
                      mission_creer, missions_equipe,
                      mission_rapport_enregistrer, mission_supprimer,
                      mission_prochaine_seance, derniere_chaine_seance)
from services import (sauvegarder_photo, supprimer_photo, archiver_membre, safe_date, 
                      afficher_situation, enregistrer_abonnement, verifier_abonnement, 
                      periode_affichage, generer_matricule_unique, get_periode_pastorale,
                      get_max_membres, synchroniser_menu_session, lire_menu_session,
                      afficher_messages_flash)
from components import (ajouter_evenement_agenda, afficher_agenda_complet_universel, 
                        afficher_historique_suivi, afficher_whatsapp_tabs, widget_type_abonnement, 
                        enregistrer_presence_equipe, afficher_etat_presences_globales,
                        bloc_chaine_seance)
from stcompat import comp_html


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
    """📚 RÉSERVE D'INTENTIONS (v7.9.19) — pour CHACUN des 20 N° de
    méditation, au moins UNE intention préparée à l'avance. « Que chacun
    ait sa dernière intention selon son N° méd. » Le responsable pose les
    intentions de SES membres en face de chaque membre, dans la ⛓️ Chaîne
    de la dernière séance (au-dessus) — c'est elle qui pourvoit la réserve.
    Un N° méd. peut porter plusieurs intentions : celui/celle qui médite ce
    N° voit ses intentions augmentées selon le surplus."""
    _assurer_table_reserve()
    publier_reserve_due()
    # le message de confirmation (chaîne enregistrée, intentions ajoutées)
    # s'affiche ici, en tête du bloc, APRÈS le rerun.
    afficher_messages_flash()
    st.markdown("---")
    st.markdown("### 📚 Réserve d'intentions")
    st.caption("Chaque N° méd. (1-20) porte AU MOINS une intention : c'est elle que le "
               "lecteur du jour reçoit selon SON N° méd. et médite pendant 20 jours — "
               "chacun a ainsi sa propre intention de prochain. Posez les intentions de "
               "vos membres dans la ⛓️ Chaîne de la dernière séance (au-dessus), en face "
               "de chaque membre. Compteurs toutes équipes confondues (la chaîne est "
               "universelle). 🤫 Comme toujours : être une tombe.")
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
    _lignes = reserve_lignes(equipe_id=eid)
    if not _lignes:
        st.info("La réserve de l'équipe est vide : ouvrez « ⛓️ Chaîne de la dernière "
                "séance » (au-dessus) et écrivez les intentions en face de chaque "
                "membre — elles rejoindront cette réserve.")
        return
    with st.expander(f"🗂️ Intentions en réserve de l'équipe ({len(_lignes)})"):
        _n_par_num = {}
        for (rid, num, texte, auteur, _eqi, daj) in _lignes:
            _n_par_num[int(num)] = _n_par_num.get(int(num), 0) + 1
        for (rid, num, texte, auteur, _eqi, daj) in _lignes:
            _multi = (" · surplus N° " + str(int(num)).zfill(2)
                      if _n_par_num.get(int(num), 0) > 1 else "")
            st.markdown(f"**N° méd. {int(num):02d}** — *{auteur or 'Membre'}*"
                        + (f" · ajoutée le {daj}" if daj else "") + _multi)
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
    # v7.9.19 — LA CHAÎNE D'ABORD : c'est elle qui pourvoit la réserve —
    # dans « ⛓️ Enregistrer la chaîne d'une séance », la liste des membres
    # s'affiche à la verticale avec, en face de chacun, la zone de saisie de
    # son intention (elle rejoint directement la 📚 réserve, sans passer par
    # la 🕯️ Zone du jour). Puis la réserve, qui montre ce que la chaîne a
    # pourvu ; la traduction est au modèle demandé : « X prie pour Y — N°
    # méd. Z. »
    bloc_chaine_seance([(eid, "")], "eq")
    _bloc_reserve_equipe(eid)


# ====================================================================
# v7.10.0 — L'ENVOI EN MISSION (les deux fiches du responsable d'équipe)
# La FICHE D'ENVOI EN MISSION porte la proposition : objectif, date,
# lieu et la liste des personnes envoyées. La FICHE DE RAPPORT DE
# MISSION recueille le retour : déroulement, grâces, difficultés,
# propositions. Chaque fiche s'imprime (ou s'enregistre en PDF) d'un
# clic — elle seule sort sur le papier, rien d'autre de la page.
# ====================================================================
_ID_FICHE = "fiche-imprimable-mission"


def _logo_mission_b64():
    """Le chapelet doré des Équipes du Rosaire, porté par la fiche."""
    _ici = os.path.dirname(os.path.abspath(__file__))
    for _chemin in (os.path.join(_ici, "..", "images", "logo.png"),
                    os.path.join("images", "logo.png"),
                    os.path.join(_ici, "..", "static",
                                 "logo_equipes_rosaire.png")):
        try:
            if os.path.exists(_chemin):
                return ("data:image/png;base64,"
                        + base64.b64encode(open(_chemin, "rb").read()).decode())
        except Exception:
            continue
    return None


def _grille_participants(participants):
    """La table des envoyés, ligne à ligne — membres et venus d'ailleurs."""
    if not participants:
        return ('<div class="fm-ligne-vide">Personne n\u2019est encore inscrit '
                'sur cette mission.</div>')
    _lignes = ""
    for _i, p in enumerate(participants, start=1):
        _nom = html.escape(str(p.get("nom") or "—"))
        _num = html.escape(str(p.get("numero_med") or "—"))
        _contact = html.escape(str(p.get("contact") or "—"))
        _hors = (' <span class="fm-hors">hors équipe</span>'
                 if p.get("externe") else "")
        _lignes += ('<tr><td class="fm-num">' + str(_i) + '</td>'
                    '<td>' + _nom + _hors + '</td>'
                    '<td>' + _num + '</td>'
                    '<td>' + _contact + '</td></tr>')
    return ('<table class="fm-table">'
            '<thead><tr><th>N°</th><th>Nom et prénoms</th>'
            '<th>N° méd.</th><th>Contact</th></tr></thead>'
            '<tbody>' + _lignes + '</tbody></table>')


_CSS_FICHE = """
  .fm-fiche { font-family: Georgia, 'Times New Roman', serif; color:#1a1a2e;
              background:#ffffff; border:2px solid #1A237E; border-radius:12px;
              padding:26px 30px; margin:10px 4px; line-height:1.5; }
  .fm-fiche * { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  .fm-tete { text-align:center; border-bottom:3px double #FFD700;
             padding-bottom:12px; margin-bottom:14px; }
  .fm-tete img { height:74px; margin-bottom:6px; }
  .fm-tete .fm-mouvement { font-size:0.98rem; font-weight:bold;
                           letter-spacing:2px; color:#1A237E;
                           text-transform:uppercase; }
  .fm-tete .fm-diocese { font-size:0.85rem; color:#4527a0; }
  .fm-titre { text-align:center; font-size:1.28rem; font-weight:bold;
              color:#1A237E; letter-spacing:1.5px; margin:14px 0 2px;
              text-transform:uppercase; }
  .fm-soustitre { text-align:center; font-size:0.88rem; font-style:italic;
                  color:#555; margin-bottom:14px; }
  .fm-bandeau { display:flex; flex-wrap:wrap; gap:6px 22px; font-size:0.92rem;
                background:#e8eaf6; border-radius:8px; padding:10px 14px;
                margin:10px 0 14px; }
  .fm-bandeau b { color:#1A237E; }
  .fm-bloc { margin:12px 0; }
  .fm-bloc .fm-etiquette { font-size:0.8rem; font-weight:bold;
                           text-transform:uppercase; letter-spacing:1px;
                           color:#1A237E; margin-bottom:4px; }
  .fm-bloc .fm-texte { border:1px solid #c5cae9; border-radius:8px;
                       padding:10px 12px; font-size:0.95rem;
                       background:#fafaff; white-space:pre-wrap; }
  .fm-table { width:100%; border-collapse:collapse; font-size:0.92rem;
              margin-top:6px; }
  .fm-table th { background:#1A237E; color:#ffffff; padding:7px 9px;
                 text-align:left; font-size:0.82rem; letter-spacing:0.5px; }
  .fm-table td { border:1px solid #c5cae9; padding:7px 9px; }
  .fm-table tr:nth-child(even) td { background:#f3f5fb; }
  .fm-num { width:34px; text-align:center; font-weight:bold; color:#1A237E; }
  .fm-hors { font-size:0.72rem; background:#fff3cd; border:1px solid #ffd54f;
             border-radius:8px; padding:1px 7px; margin-left:6px;
             font-style:italic; }
  .fm-ligne-vide { font-size:0.9rem; font-style:italic; color:#777;
                   padding:8px 0; }
  .fm-priere { text-align:center; font-style:italic; color:#4527a0;
               font-size:0.95rem; margin:18px 10px 6px; }
  .fm-signatures { display:flex; justify-content:space-between; gap:20px;
                   margin-top:26px; }
  .fm-signatures .fm-sig { flex:1; text-align:center; font-size:0.88rem; }
  .fm-signatures .fm-sig .fm-role { font-weight:bold; color:#1A237E;
                                    margin-bottom:52px; }
  .fm-signatures .fm-sig .fm-nom { border-top:1px solid #999;
                                   padding-top:5px; font-size:0.82rem;
                                   color:#444; }
  .fm-pied { text-align:center; font-size:0.72rem; color:#888;
             margin-top:16px; border-top:1px solid #e0e0e0; padding-top:8px; }
"""


def _entete_fiche_mission(titre_fiche, soustitre):
    """Tête commune des deux fiches (mouvement, diocèse, titre)."""
    _logo = _logo_mission_b64()
    return ('<div class="fm-tete">'
            + ('<img src="' + _logo + '" alt="">' if _logo else "")
            + '<div class="fm-mouvement">Équipes du Rosaire</div>'
            + '<div class="fm-diocese">Diocèse de Grand-Bassam — '
            + '« Équipier : l\u2019évangile avec Marie ! »</div></div>'
            + '<div class="fm-titre">' + titre_fiche + '</div>'
            + '<div class="fm-soustitre">' + soustitre + '</div>')


def _periode_mission_txt(mission, eid=None):
    """v7.11.1 — Le texte de la PÉRIODE d'une mission : « du 24/10/2026 au
    21/11/2026 », ou « du 24/10/2026 jusqu'à la prochaine séance » tant
    que la séance suivante n'a pas été enregistrée (dès qu'elle l'est, la
    période se referme toute seule sur sa date). Les missions anciennes
    (une seule date) affichent « du … » à la hauteur de leur date."""
    _deb = str(mission.get("date_debut") or mission.get("date_mission") or "").strip()
    _deb_txt = "—"
    try:
        if _deb:
            _deb_txt = safe_date(_deb).strftime("%d/%m/%Y")
    except Exception:
        _deb_txt = _deb or "—"
    _fin = str(mission.get("date_fin") or "").strip()
    if not _fin and eid and _deb:
        _fin = mission_prochaine_seance(eid, _deb) or ""
    if _fin:
        try:
            _fin_txt = safe_date(_fin).strftime("%d/%m/%Y")
        except Exception:
            _fin_txt = _fin
        return f"du {_deb_txt} au {_fin_txt}"
    return f"du {_deb_txt} jusqu'à la prochaine séance"


def _bandeau_mission(mission, nom_equipe, nom_paroisse, eid=None):
    """Ligne d'identité de la mission (équipe, paroisse, période, lieu).
    v7.11.1 — la DATE laisse place à la PÉRIODE (une mission se déroule du
    lendemain de la dernière séance de prière jusqu'à la prochaine séance)
    et le groupe envoyé s'affiche quand l'équipe se scinde."""
    _groupe = str(mission.get("groupe") or "").strip().upper()
    _grp_txt = (" — groupe " + _groupe) if _groupe else ""
    return ('<div class="fm-bandeau">'
            '<span>✈️ <b>Équipe :</b> ' + html.escape(nom_equipe) + _grp_txt
            + '</span>'
            '<span>🏘️ <b>Paroisse :</b> ' + html.escape(nom_paroisse or "—")
            + '</span>'
            '<span>🗓️ <b>Période :</b> '
            + html.escape(_periode_mission_txt(mission, eid)) + '</span>'
            '<span>📍 <b>Lieu :</b> ' + html.escape(mission.get("lieu") or "—")
            + '</span></div>')


def _fiche_envoi_html(mission, nom_equipe, nom_paroisse, resp_equipe,
                      resp_paroisse):
    """La FICHE D'ENVOI EN MISSION — la proposition remise au responsable :
    objectif de la mission et liste des personnes envoyées."""
    _participants = mission.get("participants") or []
    _corps = (
        _entete_fiche_mission(
            "Fiche d\u2019envoi en mission",
            "Proposition préparée par le responsable d\u2019équipe — "
            "à présenter pour bénédiction et accord")
        + _bandeau_mission(mission, nom_equipe, nom_paroisse)
        + '<div class="fm-bloc"><div class="fm-etiquette">🎯 Objectif de la mission</div>'
        + '<div class="fm-texte">' + html.escape(mission.get("objectif") or "—")
        + '</div></div>'
        + '<div class="fm-bloc"><div class="fm-etiquette">👥 Personnes envoyées en mission ('
        + str(len(_participants)) + ')</div>'
        + _grille_participants(_participants) + '</div>'
        + '<div class="fm-priere">« Allez partout dans le monde, et proclamez '
        'la Bonne Nouvelle à toute la création. » — Marc 16, 15<br>'
        'Que La Vierge Marie, Étoile de la nouvelle évangélisation, '
        'accompagne chaque envoyé.</div>'
        + '<div class="fm-signatures">'
        + '<div class="fm-sig"><div class="fm-role">Le Responsable de l\u2019équipe</div>'
        + '<div class="fm-nom">' + html.escape(resp_equipe or "") + '</div></div>'
        + '<div class="fm-sig"><div class="fm-role">Le Responsable paroissial</div>'
        + '<div class="fm-nom">' + html.escape(resp_paroisse or "") + '</div></div>'
        + '</div>'
        + '<div class="fm-pied">Fiche d\u2019envoi en mission — préparée le '
        + html.escape(str(mission.get("date_envoi") or ""))
        + ' par ' + html.escape(str(mission.get("auteur_nom") or "—"))
        + '</div>')
    return '<div class="fm-fiche" id="' + _ID_FICHE + '">' + _corps + '</div>'


def _fiche_rapport_html(mission, nom_equipe, nom_paroisse, resp_equipe):
    """La FICHE DE RAPPORT DE MISSION — le retour du responsable :
    déroulement, grâces reçues, difficultés, propositions."""
    _r = mission.get("rapport") or {}
    _eff = _r.get("participants_effectifs") or []
    _corps = (
        _entete_fiche_mission(
            "Fiche de rapport de mission",
            "Retour de la mission confiée — remis par le responsable "
            "d\u2019équipe après la mission")
        + _bandeau_mission(mission, nom_equipe, nom_paroisse)
        + '<div class="fm-bloc"><div class="fm-etiquette">🎯 Rappel de l\u2019objectif</div>'
        + '<div class="fm-texte">' + html.escape(mission.get("objectif") or "—")
        + '</div></div>'
        + '<div class="fm-bloc"><div class="fm-etiquette">👥 Personnes ayant porté la mission</div>'
        + '<div class="fm-texte">'
        + (html.escape(" · ".join(_eff)) if _eff
           else html.escape(" · ".join(str(p.get("nom") or "")
                                       for p in (mission.get("participants")
                                                 or [])) or "—"))
        + '</div></div>'
        + '<div class="fm-bloc"><div class="fm-etiquette">📖 Déroulement de la mission</div>'
        + '<div class="fm-texte">' + html.escape(_r.get("deroulement") or "—")
        + '</div></div>'
        + '<div class="fm-bloc"><div class="fm-etiquette">✨ Grâces reçues et moments forts</div>'
        + '<div class="fm-texte">' + html.escape(_r.get("graces") or "—")
        + '</div></div>'
        + '<div class="fm-bloc"><div class="fm-etiquette">🌫️ Difficultés rencontrées</div>'
        + '<div class="fm-texte">' + html.escape(_r.get("difficultes") or "—")
        + '</div></div>'
        + '<div class="fm-bloc"><div class="fm-etiquette">🌱 Propositions et suites à donner</div>'
        + '<div class="fm-texte">' + html.escape(_r.get("propositions") or "—")
        + '</div></div>'
        + '<div class="fm-priere">« Racontez-leur ce que le Seigneur a fait '
        'pour vous. » — Que la joie de cette mission porte du fruit.</div>'
        + '<div class="fm-signatures">'
        + '<div class="fm-sig"><div class="fm-role">Le Responsable de l\u2019équipe</div>'
        + '<div class="fm-nom">' + html.escape(resp_equipe or "") + '</div></div>'
        + '<div class="fm-sig"><div class="fm-role">Le Responsable paroissial / diocésain</div>'
        + '<div class="fm-nom"></div></div>'
        + '</div>'
        + '<div class="fm-pied">Fiche de rapport de mission — mission « '
        + html.escape(str(mission.get("titre") or "")) + ' » · rapport noté le '
        + html.escape(str(mission.get("date_rapport") or ""))
        + '</div>')
    return '<div class="fm-fiche" id="' + _ID_FICHE + '">' + _corps + '</div>'


_CSS_IMPRESSION_FICHE = """
@media print {
    body, body * { visibility: hidden !important; }
    #""" + _ID_FICHE + """, #""" + _ID_FICHE + """ * {
        visibility: visible !important; }
    #""" + _ID_FICHE + """ { position: absolute; left: 0; top: 0;
        width: 100%; border-radius: 0; margin: 0; box-shadow: none; }
    @page { margin: 12mm; }
}
"""


def _rendre_fiche_imprimable(fiche_html, nom_fichier):
    """Montre la fiche, pose l'impression (elle seule sort sur le papier)
    et offre le fichier autonome à télécharger (imprimable d'où que ce soit)."""
    st.markdown("<style>" + _CSS_IMPRESSION_FICHE + _CSS_FICHE + "</style>",
                unsafe_allow_html=True)
    st.markdown(fiche_html, unsafe_allow_html=True)
    _c1, _c2 = st.columns(2)
    with _c1:
        comp_html(
            '<div style="font-family:sans-serif; text-align:center; '
            'margin-top:2px;"><button onclick="window.parent.print()" '
            'style="background:#1A237E; color:#fff; border:none; '
            'border-radius:24px; padding:9px 22px; font-size:0.92rem; '
            'font-weight:bold; cursor:pointer;">🖨️ Imprimer la fiche '
            '(ou l\u2019enregistrer en PDF)</button></div>', height=52)
    with _c2:
        _autonome = (
            '<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, '
            'initial-scale=1"><title>' + html.escape(nom_fichier)
            + '</title><style>' + _CSS_FICHE + '''
                body { background:#f0f0f5; margin:0; padding:14px; }
                .barre { text-align:center; margin:10px 0 16px; }
                .barre button { background:#1A237E; color:#fff; border:none;
                    border-radius:24px; padding:10px 24px; font-size:0.95rem;
                    font-weight:bold; cursor:pointer; }
                @media print {
                    body { background:#fff; padding:0; }
                    .barre { display:none; }
                    .fm-fiche { border:none; margin:0; }
                    @page { margin: 12mm; }
                }
            </style></head><body>'
            '<div class="barre"><button onclick="window.print()">🖨️ Imprimer '
            'cette fiche</button></div>'
            + fiche_html + '</body></html>''')
        st.download_button("📥 Télécharger la fiche (page à imprimer)",
                           data=_autonome.encode("utf-8"),
                           file_name=nom_fichier,
                           mime="text/html", width="stretch",
                           key="dl_" + nom_fichier)


_STATUTS_MISSION = {"envoi": "🟡 Proposition prête (fiche d'envoi)",
                    "rapportee": "✅ Rapport de mission reçu"}


def _onglet_missions(eid, pid, nom_equipe):
    """✈️ ENVOI EN MISSION — le responsable prépare l'envoi (fiche
    imprimable : personnes + objectif) puis range le retour (fiche de
    rapport imprimable). Les fiches se gardent dans l'équipe, prêtes à
    être re-imprimées.
    v7.11.1 — LA MISSION SE DÉROULE SUR UNE PÉRIODE : du lendemain de la
    dernière séance de prière mensuelle jusqu'à la prochaine séance (la
    fin se referme toute seule dès que la séance suivante est
    enregistrée). ET L'ÉQUIPE PEUT SE SCINDER : chaque mission porte son
    groupe (A…Z) et l'onglet se range en « ✈️ Les missions de l'équipe :
    groupe A / groupe B / … »."""
    _info_eq = c.execute("SELECT responsable FROM equipes WHERE id=?",
                         (eid,)).fetchone()
    _resp_eq = (_info_eq[0] if _info_eq and _info_eq[0] else
                st.session_state.get('username', ""))
    _resp_par = None
    if pid:
        _r = c.execute("SELECT responsable FROM paroisses WHERE id=?",
                       (pid,)).fetchone()
        _resp_par = _r[0] if _r else None

    # v7.11.1 — le début PROPOSÉ : le lendemain de la dernière séance de
    # prière mensuelle enregistrée (chaîne de séance) ; sans séance connue,
    # aujourd'hui. La fin, elle, reste ouverte : « jusqu'à la prochaine
    # séance » tant que le responsable ne la fixe pas lui-même.
    _deb_defaut, _note_deb = date.today(), "aucune séance enregistrée pour "\
        "l'instant — le début est proposé à aujourd'hui"
    try:
        _derniere = derniere_chaine_seance(eid)
        if _derniere and _derniere[1]:
            _ds = safe_date(_derniere[1])
            if _ds:
                _deb_defaut = date.fromordinal(_ds.toordinal() + 1)
                _note_deb = ("le lendemain de la dernière séance ("
                             + _ds.strftime("%d/%m/%Y") + ")")
    except Exception:
        pass

    with st.expander("➕ Préparer une mission (fiche d'envoi en mission)"):
        with st.form("form_mission", clear_on_submit=True):
            _titre = st.text_input("Nom de la mission",
                                   placeholder="Ex. : Visite et prière avec "
                                               "les familles de Moossou")
            _objectif = st.text_area(
                "Objectif de la mission (ce que la mission vient chercher)",
                height=90,
                placeholder="Ex. : porter la prière du Rosaire aux familles "
                            "éloignées, retrouver les membres absents, "
                            "inviter de nouveaux équipiers…")
            _c1, _c2, _c3 = st.columns(3)
            with _c1:
                _date_deb = st.date_input(
                    "🗓️ Début de la mission", value=_deb_defaut,
                    help="Proposé d'office : " + _note_deb + ".")
            with _c2:
                _date_fin = st.date_input(
                    "Fin de la mission (facultatif)", value=None,
                    help="Laisse vide : la mission court jusqu'à la "
                         "prochaine séance de prière — dès qu'elle est "
                         "enregistrée, la période se referme sur sa date.")
            with _c3:
                _groupe = st.selectbox(
                    "✈️ Groupe envoyé en mission",
                    list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"), index=0,
                    help="L'équipe peut se scinder en plusieurs groupes : "
                         "chaque groupe porte ses propres missions.")
            with _c1:
                _lieu = st.text_input("Lieu / quartier / familles visitées")
            with _c2:
                st.markdown(
                    '<div style="font-size:0.82rem; opacity:0.75; '
                    'margin-top:0.6rem;">🛐 Une mission se déroule du '
                    'lendemain de la dernière séance de prière mensuelle '
                    'jusqu\u2019à la prochaine.</div>',
                    unsafe_allow_html=True)
            _membres = c.execute(
                """SELECT id, matloc, nom, prenom, numero_meditation,
                          whatsapp FROM membres
                   WHERE equipe_id=? AND statut='actif'
                   ORDER BY nom, prenom""", (eid,)).fetchall()
            _opts = {f"{m[2]} {m[3]} — N° méd. {m[4] or '?'}": m
                     for m in _membres}
            _choisis = st.multiselect(
                "👥 Personnes de l'équipe envoyées en mission",
                list(_opts.keys()))
            _hors = st.text_area(
                "➕ Personnes venues d'ailleurs (une par ligne — "
                "facultatif)", height=70,
                placeholder="Ex. : Frère Jean-Baptiste\nSœur Marie-Claire")
            if st.form_submit_button("✈️ Ouvrir la mission et préparer la fiche",
                                     type="primary", width="stretch"):
                if not _titre.strip():
                    st.error("Donne d'abord un nom à la mission.")
                elif not _objectif.strip():
                    st.error("L'objectif de la mission est le cœur de la "
                             "fiche — écris-le.")
                elif not _choisis and not _hors.strip():
                    st.error("Liste au moins une personne envoyée en mission.")
                elif (_date_deb and _date_fin and _date_fin < _date_deb):
                    st.error("La fin de la mission ne peut pas précéder son "
                             "début.")
                else:
                    _participants = []
                    for _lbl in _choisis:
                        _m = _opts[_lbl]
                        _participants.append({
                            "nom": f"{_m[2]} {_m[3]}".strip(),
                            "matloc": _m[1],
                            "numero_med": _m[4],
                            "contact": _m[5] or "",
                            "externe": 0})
                    for _l in _hors.split("\n"):
                        _l = _l.strip()
                        if _l:
                            _participants.append({"nom": _l, "matloc": None,
                                                  "numero_med": None,
                                                  "contact": "", "externe": 1})
                    _mid = mission_creer(
                        eid, pid, _titre.strip(), _objectif.strip(),
                        date_mission=(_date_deb.isoformat() if _date_deb
                                      else None),
                        lieu=(_lieu.strip() or None),
                        participants=_participants,
                        auteur_nom=st.session_state.get('username'),
                        date_debut=(_date_deb.isoformat() if _date_deb
                                    else None),
                        date_fin=(_date_fin.isoformat() if _date_fin
                                  else None),
                        groupe=_groupe)
                    if _mid:
                        st.session_state["flash_success"] = (
                            "✈️ Mission ouverte pour le groupe " + _groupe
                            + " ! Ta fiche d'envoi est prête juste en "
                              "dessous — imprime-la.")
                        st.rerun()
                    else:
                        st.error("La mission n'a pas pu être ouverte — "
                                 "réessaie.")

    _missions = missions_equipe(eid)
    if not _missions:
        st.info("Aucune mission pour le moment — ouvre la première : la fiche "
                "d'envoi en mission naîtra de ta préparation.")
        return
    # v7.11.1 — L'ÉQUIPE SE SCINDE : les missions se rangent par groupe
    # (A, B, … Z), chacune sous son « ✈️ Les missions de l'équipe : groupe
    # X ». Une mission ancienne sans groupe connu rejoint le groupe A —
    # rien ne se perd, rien ne se déplace hors de son groupe.
    _par_groupe = {}
    for _m in _missions:
        _g = str(_m[13] if len(_m) > 13 else "").strip().upper() or "A"
        if not ("A" <= _g <= "Z"):
            _g = "A"
        _par_groupe.setdefault(_g, []).append(_m)
    for _g in sorted(_par_groupe):
        _liste_g = _par_groupe[_g]
        st.markdown("#### ✈️ Les missions de l'équipe : groupe " + _g
                    + " (" + str(len(_liste_g)) + ")")
        for (_mid, _titre, _objectif, _date_m, _lieu, _part_json, _statut,
             _date_envoi, _auteur, _rapport_json, _date_rapport,
             _date_debut, _date_fin, _groupe_m) in _liste_g:
            try:
                _participants = json.loads(_part_json or "[]")
            except Exception:
                _participants = []
            try:
                _rapport = json.loads(_rapport_json or "{}")
            except Exception:
                _rapport = {}
            _mission = {"id": _mid, "titre": _titre, "objectif": _objectif,
                        "date_mission": _date_m, "lieu": _lieu,
                        "participants": _participants, "statut": _statut,
                        "date_envoi": _date_envoi, "auteur_nom": _auteur,
                        "rapport": _rapport, "date_rapport": _date_rapport,
                        "date_debut": _date_debut, "date_fin": _date_fin,
                        "groupe": _groupe_m}
            _periode = _periode_mission_txt(_mission, eid)
            _badge = _STATUTS_MISSION.get(_statut, _statut)
            with st.expander("✈️ " + _titre + " — " + _periode
                             + "   ·   " + _badge):
                _c1, _c2, _c3 = st.columns(3)
                with _c1:
                    if st.button("🖨️ Fiche d'envoi", key=f"mi_env_{_mid}",
                                 width="stretch", type="primary"):
                        st.session_state["mission_fiche"] = ("envoi", _mid)
                with _c2:
                    if st.button("📝 Rapport de mission", key=f"mi_rap_{_mid}",
                                 width="stretch"):
                        st.session_state["mission_fiche"] = ("rapport", _mid)
                with _c3:
                    if st.button("🗑️ Supprimer", key=f"mi_del_{_mid}",
                                 width="stretch",
                                 help="Retire définitivement cette mission "
                                      "(essai erroné)."):
                        st.session_state["mission_suppr"] = _mid
                if st.session_state.get("mission_suppr") == _mid:
                    st.warning("Retirer définitivement « " + _titre + " » et "
                               "son rapport ?")
                    _c1, _c2 = st.columns(2)
                    with _c1:
                        if st.button("✅ Oui, retirer", key=f"mi_del_ok_{_mid}",
                                     width="stretch"):
                            mission_supprimer(_mid)
                            st.session_state.pop("mission_suppr", None)
                            st.session_state["flash_success"] = (
                                "🗑️ Mission retirée.")
                            st.rerun()
                    with _c2:
                        if st.button("↩️ Non, la garder",
                                     key=f"mi_del_no_{_mid}",
                                     width="stretch"):
                            st.session_state.pop("mission_suppr", None)
                            st.rerun()

                st.markdown("🎯 **Objectif :** " + (_objectif or "—"))
                st.markdown("🗓️ **Période :** " + _periode
                            + "  ·  📍 **Lieu :** " + (_lieu or "—"))
                if _participants:
                    st.caption("👥 " + " · ".join(
                        str(p.get("nom") or "?")
                        + (" (hors équipe)" if p.get("externe") else "")
                        for p in _participants))
                if _rapport:
                    _r = _rapport
                    st.markdown("📝 **Rapport reçu le "
                                + str(_date_rapport or "?") + "** — "
                                "déroulement, grâces, difficultés et "
                                "propositions sont gardés dans la fiche de "
                                "rapport.")

                # ── la fiche demandée ────────────────────────────────
                _demande = st.session_state.get("mission_fiche")
                if _demande and _demande[1] == _mid:
                    _genre = _demande[0]
                    if _genre == "envoi":
                        st.markdown("### 🖨️ La fiche d'envoi en mission")
                        _rendre_fiche_imprimable(
                            _fiche_envoi_html(_mission, nom_equipe,
                                              _nom_par(pid), _resp_eq,
                                              _resp_par),
                            f"fiche_envoi_mission_{_mid}.html")
                    else:
                        if not _rapport:
                            st.info("Le rapport n'est pas encore rempli — "
                                    "remplis-le ci-dessous, la fiche naîtra "
                                    "de tes mots.")
                        else:
                            st.markdown(
                                "### 🖨️ La fiche de rapport de mission")
                            _rendre_fiche_imprimable(
                                _fiche_rapport_html(_mission, nom_equipe,
                                                    _nom_par(pid), _resp_eq),
                                f"fiche_rapport_mission_{_mid}.html")

                # ── le rapport : remplir / corriger ──────────────────
                with st.expander("📝 " + ("Corriger le rapport de mission"
                                          if _rapport else
                                          "Remplir le rapport de mission "
                                          "(après la mission)")):
                    with st.form(f"form_rapport_{_mid}"):
                        _r0 = _rapport or {}
                        _der = st.text_area("📖 Déroulement de la mission "
                                            "(ce qui s'est passé)",
                                            value=_r0.get("deroulement", ""),
                                            height=90)
                        _gra = st.text_area("✨ Grâces reçues et moments forts",
                                            value=_r0.get("graces", ""),
                                            height=80)
                        _dif = st.text_area("🌫️ Difficultés rencontrées",
                                            value=_r0.get("difficultes", ""),
                                            height=70)
                        _pro = st.text_area(
                            "🌱 Propositions et suites à donner",
                            value=_r0.get("propositions", ""), height=70)
                        _noms = [str(p.get("nom") or "")
                                 for p in _participants]
                        _eff0 = [n for n in (_r0.get("participants_effectifs")
                                             or []) if n in _noms]
                        _eff = st.multiselect(
                            "👥 Personnes ayant effectivement porté la "
                            "mission", _noms, default=_eff0)
                        if st.form_submit_button(
                                "💾 Enregistrer le rapport de mission",
                                type="primary", width="stretch"):
                            if not _der.strip():
                                st.error("Raconte au moins le déroulement — "
                                         "c'est le cœur du rapport.")
                            else:
                                mission_rapport_enregistrer(_mid, {
                                    "deroulement": _der.strip(),
                                    "graces": _gra.strip(),
                                    "difficultes": _dif.strip(),
                                    "propositions": _pro.strip(),
                                    "participants_effectifs": _eff})
                                st.session_state["flash_success"] = (
                                    "✅ Rapport de mission enregistré — la "
                                    "fiche de rapport est prête à être "
                                    "imprimée.")
                                st.rerun()


def _nom_par(pid):
    """Le nom de la paroisse de l'équipe (pour les fiches)."""
    if not pid:
        return None
    try:
        _r = c.execute("SELECT nom FROM paroisses WHERE id=?", (pid,)).fetchone()
        return _r[0] if _r else None
    except Exception:
        return None


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
        # v7.10.0 — 5ᵉ onglet « ✈️ Envoi en mission » : la fiche d'envoi
        # (personnes + objectif) et la fiche de rapport, imprimables.
        _onglets_suivi = ["📅 Agenda", "🙏 Vos intentions à une équipe",
                          "✈️ Envoi en mission", "📝 Vie de prière de l'équipe",
                          "📊 Engagement spirituel"]
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
            _onglet_missions(eid, pid, nom_equipe)
        elif _suivi_actif == _onglets_suivi[3]:
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
