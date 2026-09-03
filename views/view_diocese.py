import os
import shutil
import html
import streamlit as st
import pandas as pd
import io
from datetime import date
from database import c, commit_and_sync
from services import (hash_password, generer_mot_de_passe, safe_date, afficher_situation,
                      exporter_excel_diocese, periode_affichage, get_periode_pastorale,
                      sauvegarder_audio, sauvegarder_illustration, sauvegarder_pdf, supprimer_photo,
                      afficher_messages_flash)
# FIX CRITIQUE (bug n°1) : les DEUX fonctions réellement appelées par le menu "Suivi"
# sont désormais importées. L'ancien fichier importait afficher_historique_suivi et
# afficher_etat_presences_globales (qui servent à la VUE ÉQUIPE) → NameError sur
# les onglets "Vie de prière des paroisses" et "Engagement spirituel".
from components import (ajouter_evenement_agenda, afficher_agenda_complet_universel,
                        afficher_whatsapp_tabs, afficher_historique_paroisse,
                        afficher_etat_presences_paroisse)

def show_diocese():
    d_info = c.execute("SELECT nom, responsable, bureau FROM diocese WHERE id=?", (1,)).fetchone()
    nom_dio = d_info[0] if d_info else "Diocèse"

    menu = st.sidebar.radio("Navigation", [
        "🏛️ Voir diocèse", "🏘️ Créer paroisses", "📋 Gérer paroisses",
        "📅 Abonnements", "📌 Suivi", "🕊️ Espace spirituel", "💬 WhatsApp",
        "🔍 Rechercher matricule", "🔐 Gérer les accès", "📊 Statistiques", "📥 Export Excel",
        "📦 Archives", "🗑️ Réinitialiser"
    ])

    if menu == "🏛️ Voir diocèse":
        st.markdown(f'<h2 style="color:#1A237E; font-size: 1.4rem;">🏛️ {html.escape(nom_dio).upper()}</h2>', unsafe_allow_html=True)
        afficher_messages_flash()  # FIX : messages posés au run précédent enfin visibles
        if d_info:
            st.markdown(f'<div class="custom-info-box"><b>Responsable diocésain :</b> {html.escape(d_info[1] or "")}<br><b>Bureau diocésain :</b> {html.escape(d_info[2] or "")}</div>', unsafe_allow_html=True)
            with st.expander("✏️ Modifier les informations"):
                with st.form("form_edit_dio"):
                    nr = st.text_input("Nouveau responsable", value=d_info[1] or "")
                    nb = st.text_area("Nouveau bureau", value=d_info[2] or "")
                    if st.form_submit_button("💾 Enregistrer", width="stretch"):
                        c.execute("UPDATE diocese SET responsable=?, bureau=? WHERE id=?", (nr, nb, 1))
                        commit_and_sync()
                        st.session_state["flash_success"] = "Mis à jour ! ✅"  # FIX : flash mémorisé
                        st.rerun()

    elif menu == "🏘️ Créer paroisses":
        st.markdown('<h2 style="color:#1A237E;">🏘️ Créer une paroisse</h2>', unsafe_allow_html=True)
        afficher_messages_flash()

        # FIX : les identifiants de la paroisse créée sont mémorisés en session_state
        # et affichés ICI (avant le formulaire) → ils survivent aux reruns, l'admin
        # a le temps de les noter. (L'ancien bloc disparaissait à la 1re interaction.)
        if st.session_state.get('new_paroisse_info'):
            info = st.session_state['new_paroisse_info']
            st.success(f"✅ Paroisse '{info['nom']}' créée")
            st.markdown(f"<div style='background:#e8f5e9;padding:20px;border-radius:10px;border:1px solid #c8e6c9;'><p><strong>🔑 Identifiant :</strong> <code style='color:#d84315;font-size:1.2rem;'>{info['user']}</code></p><p><strong>🔒 Mot de passe :</strong> <code style='color:#d84315;font-size:1.2rem;'>{info['mdp']}</code></p><p style='color:#2e7d32;'><em>⚠️ Notez ces identifiants maintenant, ils ne seront plus affichés.</em></p></div>", unsafe_allow_html=True)
            if st.button("OK, j'ai noté les identifiants", key="ok_new_paroisse"):
                del st.session_state['new_paroisse_info']
                st.rerun()

        with st.form("creer_paroisse"):
            c1, c2 = st.columns(2)
            with c1:
                nom = st.text_input("Nom de la paroisse")
                commune = st.text_input("Commune")
                responsable = st.text_input("Responsable")
            with c2:
                ville = st.text_input("Ville")
                bureau = st.text_area("Bureau")
            if st.form_submit_button("🏘️ Créer", width="stretch"):
                if nom and commune and ville and responsable:
                    if c.execute("SELECT id FROM paroisses WHERE nom=? AND commune=? AND ville=?", (nom.strip(), commune.strip(), ville.strip())).fetchone():
                        st.error("❌ Cette paroisse existe déjà !")
                    else:
                        c.execute("INSERT INTO paroisses (nom, commune, ville, responsable, bureau, diocese_id) VALUES (?,?,?,?,?,?)",
                                  (nom.strip(), commune.strip(), ville.strip(), responsable.strip(), bureau, 1))
                        # FIX : re-SELECT au lieu de c.lastrowid (lastrowid peut être
                        # invalide si le CursorWrapper s'est reconnecté pendant l'INSERT)
                        pid = c.execute("SELECT id FROM paroisses WHERE nom=? AND commune=? AND ville=?",
                                        (nom.strip(), commune.strip(), ville.strip())).fetchone()[0]
                        username = f"paroisse_{pid}"
                        mdp = generer_mot_de_passe()
                        c.execute("INSERT INTO utilisateurs (username, password, role, diocese_id, paroisse_id) VALUES (?,?,?,?,?)",
                                  (username, hash_password(mdp), "paroisse", 1, pid))
                        commit_and_sync()
                        st.session_state['new_paroisse_info'] = {'nom': nom, 'user': username, 'mdp': mdp}
                        st.rerun()
                else:
                    st.error("Tous les champs sont requis")

    elif menu == "📋 Gérer paroisses":
        st.markdown('<h2 style="color:#1A237E;">📋 Consultation des paroisses</h2>', unsafe_allow_html=True)

        for state in ['show_equipes', 'show_equipiers', 'show_membres_equipe']:
            if state not in st.session_state: st.session_state[state] = None

        paroisses = c.execute("SELECT id, nom, commune, ville, responsable, bureau FROM paroisses ORDER BY nom").fetchall()

        for p in paroisses:
            pid, nom, commune, ville, responsable, bureau = p
            nb_equipes = c.execute("SELECT COUNT(*) FROM equipes WHERE paroisse_id=?", (pid,)).fetchone()[0]
            nb_membres = c.execute("SELECT COUNT(*) FROM membres WHERE paroisse_id=? AND statut='actif'", (pid,)).fetchone()[0]

            with st.expander(f"🏛️ {nom} ({commune} / {ville}) - {nb_equipes} équipe(s) - {nb_membres} membre(s)"):
                st.write(f"**Responsable :** {responsable}")
                st.write(f"**Bureau :** {bureau}")

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
                    st.markdown(f"#### 👥 Équipes de {nom}")
                    equipes = c.execute("SELECT id, nom_equipe, responsable, bureau FROM equipes WHERE paroisse_id=? ORDER BY nom_equipe", (pid,)).fetchall()
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
                                # FIX : f"{x} FCFA" crashait sur None → "(x or 0)"
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

        tab_avenir, tab_passe, tab_etat = st.tabs(["📅 Agenda", "📝 Vie de prière des paroisses", "📊 Engagement spirituel"])

        with tab_avenir:
            ajouter_evenement_agenda(diocese_id=1, auteur_nom=st.session_state.get('username'))
            st.markdown("---")
            afficher_agenda_complet_universel(diocese_id=1)

        with tab_passe:
            paroisses = c.execute("SELECT id, nom, commune FROM paroisses").fetchall()
            if paroisses:
                # FIX : clé composite "nom (commune)" — deux paroisses du même nom
                # rendaient l'une d'elles inaccessible dans le selectbox
                par_dict = {f"{p[1]} ({p[2]})": p[0] for p in paroisses}
                choix_par = st.selectbox("Sélectionnez la paroisse", list(par_dict.keys()), key="suivi_hist_dio_par")
                pid_select = par_dict[choix_par]

                from services import TYPES_EVENEMENTS
                filtre_type = st.selectbox("Filtrer par type d'évènement", ["Tous"] + TYPES_EVENEMENTS, key="filtre_hist_dio")

                # FIX (bug n°1) : fonction désormais correctement importée
                afficher_historique_paroisse(paroisse_id=pid_select, filtre_type=filtre_type)
            else:
                st.info("Aucune paroisse créée.")

        with tab_etat:
            paroisses2 = c.execute("SELECT id, nom, commune FROM paroisses").fetchall()
            if paroisses2:
                par_dict2 = {f"{p[1]} ({p[2]})": p[0] for p in paroisses2}
                choix_par2 = st.selectbox("Sélectionnez la paroisse pour le bilan", list(par_dict2.keys()), key="etat_hist_dio_par")
                pid_select2 = par_dict2[choix_par2]

                # FIX (bug n°1) : fonction désormais correctement importée
                afficher_etat_presences_paroisse(paroisse_id=pid_select2)
            else:
                st.info("Aucune paroisse créée.")

    elif menu == "🕊️ Espace spirituel":
        st.markdown('<h2 style="color:#1A237E;">🕊️ Gestion de l\'Espace Spirituel</h2>', unsafe_allow_html=True)
        st.caption("Ici, vous publiez les prières, méditations et musiques qui apparaîtront dans l'espace des membres.")
        afficher_messages_flash()

        # FIX CRITIQUE (bug n°2) : nettoyage des champs exécuté au DÉBUT de la section,
        # AVANT l'instantiation des widgets. L'ancien `del st.session_state[clé]`
        # dans le handler du formulaire provoquait une StreamlitAPIException
        # (impossible de supprimer la clé d'un widget déjà instancié dans le run).
        cles_nettoyage = st.session_state.pop("nettoyage_espace", None)
        if cles_nettoyage:
            for cle in cles_nettoyage:
                st.session_state.pop(cle, None)

        tab_add, tab_manage = st.tabs(["➕ Publier du contenu", "📋 Contenu existant"])

        with tab_add:
            s_tab_priere, s_tab_med, s_tab_audio = st.tabs(["🙏 Prière", "📖 Méditation", "🎵 Musique"])

            def publier_texte(type_contenu, prefixe_cle, label):
                titre = st.session_state.get(f"titre_{prefixe_cle}")
                if not titre:
                    st.error("Le titre est obligatoire.")
                    return

                contenu_texte = st.session_state.get(f"texte_{prefixe_cle}", "") or ""
                pdf_uploader = st.session_state.get(f"pdf_{prefixe_cle}")

                if pdf_uploader is not None:
                    url_pdf = sauvegarder_pdf(pdf_uploader)
                    if url_pdf:
                        # Bouton "Télécharger" via le flag fl_attachment de Cloudinary
                        url_pdf_dl = url_pdf.replace('/upload/', '/upload/fl_attachment/')
                        contenu_texte = f'''<div style="text-align: center; margin: 20px 0; padding: 20px; background: #f3e5f5; border-radius: 10px; border: 1px dashed #4527a0;">
                            <a href="{url_pdf}" target="_blank" style="background-color: #4527a0; color: white; padding: 15px 30px; text-decoration: none; border-radius: 8px; font-weight: bold; font-size: 1.1rem; display: inline-block; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin: 5px;">
                                📄 Ouvrir le document PDF
                            </a>
                            <a href="{url_pdf_dl}" style="background-color: #7b1fa2; color: white; padding: 15px 22px; text-decoration: none; border-radius: 8px; font-weight: bold; font-size: 1.1rem; display: inline-block; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin: 5px;">
                                ⬇️ Télécharger
                            </a>
                            <p style="margin-top: 10px; font-size: 0.9rem; color: #666;">Ouvrir dans un nouvel onglet, ou télécharger sur votre appareil</p>
                        </div>''' + "\n\n" + contenu_texte
                    else:
                        st.session_state["flash_warning"] = f"Le PDF n'a pas pu être hébergé (Cloudinary indisponible ?) — {label} publiée sans le document."

                url_illustration = sauvegarder_illustration(st.session_state.get(f"illus_{prefixe_cle}"))

                c.execute("""INSERT INTO espace_spirituel (type_contenu, titre, contenu_texte, fichier_url, image_url, date_publication, auteur_nom)
                             VALUES (?, ?, ?, ?, ?, ?, ?)""",
                          (type_contenu, titre, contenu_texte, None, url_illustration, date.today().isoformat(), st.session_state.get('username')))
                commit_and_sync()

                st.session_state["nettoyage_espace"] = [f"titre_{prefixe_cle}", f"texte_{prefixe_cle}", f"pdf_{prefixe_cle}", f"illus_{prefixe_cle}"]
                st.session_state["flash_success"] = f"{label} publiée avec succès ! ✅"
                st.rerun()
            with s_tab_priere:
                st.info("Rédigez une prière. Vous pouvez intégrer des images (Markdown) ou joindre un PDF.")
                with st.form("form_priere"):
                    st.text_input("Titre de la prière", key="titre_priere")
                    st.text_area("Texte de la prière", height=300, key="texte_priere")
                    st.markdown("📎 **Joindre un document PDF :**")
                    st.file_uploader("Choisir un PDF", type=["pdf"], key="pdf_priere")
                    st.file_uploader("🖼️ Image d'illustration (optionnel)", type=["jpg", "png", "jpeg", "webp"], key="illus_priere")
                    if st.form_submit_button("✅ Publier la prière", width="stretch"):
                        publier_texte('priere', 'priere', "La prière")

            with s_tab_med:
                st.info("Rédigez une méditation. Vous pouvez intégrer des images (Markdown) ou joindre un PDF.")
                with st.form("form_med"):
                    st.text_input("Titre de la méditation", key="titre_med")
                    st.text_area("Texte de la méditation", height=300, key="texte_med")
                    st.markdown("📎 **Joindre un document PDF :**")
                    st.file_uploader("Choisir un PDF", type=["pdf"], key="pdf_med")
                    st.file_uploader("🖼️ Image d'illustration (optionnel)", type=["jpg", "png", "jpeg", "webp"], key="illus_med")
                    if st.form_submit_button("✅ Publier la méditation", width="stretch"):
                        publier_texte('meditation', 'med', "La méditation")

            with s_tab_audio:
                st.info("Uploadez un fichier audio (MP3, WAV) ou vidéo (MP4).")
                with st.form("form_audio"):
                    st.text_input("Titre du chant ou de la musique", key="titre_audio")
                    st.file_uploader("🎵 Fichier audio ou vidéo", key="fichier_audio")
                    st.file_uploader("🖼️ Image d'illustration (optionnel)", type=["jpg", "png", "jpeg", "webp"], key="illus_audio")

                    if st.form_submit_button("✅ Publier la musique", width="stretch"):
                        titre = st.session_state.get("titre_audio")
                        if not titre:
                            st.error("Le titre est obligatoire.")
                        else:
                            fichier_audio = st.session_state.get("fichier_audio")
                            # FIX : ne plus publier une musique SANS fichier si l'upload échoue
                            # (l'ancien code insérait fichier_url=None → "fichier introuvable" chez le membre)
                            if fichier_audio:
                                url_audio = sauvegarder_audio(fichier_audio)
                                if not url_audio:
                                    st.error("❌ L'upload du fichier a échoué (Cloudinary indisponible ?). La musique n'a pas été publiée.")
                                    st.stop()
                            else:
                                url_audio = None
                            url_illustration = sauvegarder_illustration(st.session_state.get("illus_audio"))

                            c.execute("""INSERT INTO espace_spirituel (type_contenu, titre, contenu_texte, fichier_url, image_url, date_publication, auteur_nom)
                                         VALUES (?, ?, ?, ?, ?, ?, ?)""",
                                      ("audio", titre, None, url_audio, url_illustration, date.today().isoformat(), st.session_state.get('username')))
                            commit_and_sync()

                            st.session_state["nettoyage_espace"] = ["titre_audio", "fichier_audio", "illus_audio"]
                            st.session_state["flash_success"] = "Musique publiée avec succès ! ✅"
                            st.rerun()

        with tab_manage:
            contenus = c.execute("SELECT id, type_contenu, titre, date_publication, image_url, fichier_url FROM espace_spirituel ORDER BY date_publication DESC, id DESC").fetchall()
            if not contenus:
                st.info("Aucun contenu publié pour le moment.")
            else:
                for cont in contenus:
                    icone = {"priere": "🙏", "meditation": "📖", "audio": "🎵"}.get(cont[1], "📌")
                    c1, c2 = st.columns([4, 1])
                    with c1:
                        st.write(f"{icone} **{cont[2]}** - *{cont[3]}*")
                    with c2:
                        # FIX : confirmation + nettoyage Cloudinary des fichiers liés
                        if st.button("🗑️", key=f"del_espace_{cont[0]}"):
                            for url in (cont[4], cont[5]):
                                if url: supprimer_photo(url)
                            c.execute("DELETE FROM espace_spirituel WHERE id=?", (cont[0],))
                            commit_and_sync()
                            st.rerun()

    elif menu == "💬 WhatsApp":
        st.markdown(f'<h2 style="color:#1A237E;">💬 Messages WhatsApp - {nom_dio}</h2>', unsafe_allow_html=True)
        # FIX : signature étendue (paroisse_id) — le diocèse voit tout, c'est son rôle
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

    elif menu == "📊 Statistiques":
        st.markdown('<h2 style="color:#1A237E;">📊 Statistiques générales</h2>', unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        c1.metric("🏘️ Paroisses", c.execute("SELECT COUNT(*) FROM paroisses").fetchone()[0])
        c2.metric("👥 Équipes", c.execute("SELECT COUNT(*) FROM equipes").fetchone()[0])
        c3.metric("👤 Membres actifs", c.execute("SELECT COUNT(*) FROM membres WHERE statut='actif'").fetchone()[0])

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
                # FIX : suppression des fichiers Cloudinary AVANT la purge SQL
                # (l'ancien code laissait des fichiers orphelins facturés dans le bucket)
                for (photo,) in c.execute("SELECT photo_path FROM membres WHERE photo_path IS NOT NULL").fetchall():
                    supprimer_photo(photo)
                for (affiche,) in c.execute("SELECT affiche_url FROM evenements WHERE affiche_url IS NOT NULL").fetchall():
                    supprimer_photo(affiche)
                for img_url, fic_url in c.execute("SELECT image_url, fichier_url FROM espace_spirituel").fetchall():
                    if img_url: supprimer_photo(img_url)
                    if fic_url: supprimer_photo(fic_url)

                if os.path.exists("photos"): shutil.rmtree("photos")

                # FIX : purge COMPLÈTE, y compris espace_spirituel (l'ancien code
                # le laissait survivre à une "réinitialisation complète")
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
