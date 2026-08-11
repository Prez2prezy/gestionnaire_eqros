import streamlit as st
import pandas as pd
import io
from datetime import date, timedelta
from database import c, commit_and_sync
from services import (safe_date, envoyer_notification_telegram, lien_whatsapp,
                      verifier_abonnement, periode_affichage, get_periode_pastorale, 
                      est_cloture, cloturer_periode)

def widget_type_abonnement(prefix, m_id, annee):
    type_abo = st.radio("Type", ["📝 Abonnement", "🔄 Réabonnement"], key=f"type_{prefix}_{m_id}_{annee}", horizontal=True)
    montant = st.number_input("Montant (FCFA)", min_value=0, value=5000, step=500, key=f"mont_{prefix}_{m_id}_{annee}")
    return ("abonnement" if "Abonnement" in type_abo else "reabonnement"), montant

def ajouter_evenement_agenda(equipe_id=None, paroisse_id=None, diocese_id=None, auteur_nom="Système"):
    st.markdown(f'<h3 style="color:#1A237E;">📅 Vos évènements à venir</h3>', unsafe_allow_html=True)
    prefix = f"ag_{equipe_id}_{paroisse_id}_{diocese_id}"
    
    with st.expander("➕ Ajouter / Enregistrer un évènement à l'agenda"):
        with st.form(f"ajout_agenda_{prefix}"):
            c1, c2 = st.columns(2)
            with c1: 
                date_ag = st.date_input("📅 Date", value=date.today() + timedelta(days=7), key=f"d_ag_{prefix}")
            with c2: 
                type_ag = st.selectbox("⛪ Type", ["Prière mensuelle", "Prière commune", "Prière spéciale", "Pèlerinage", "Réunion", "Autre"], key=f"t_ag_{prefix}")
            
            lieu_ag = st.text_input("📍 Lieu", key=f"l_ag_{prefix}")
            desc_ag = st.text_area("📝 Description", key=f"desc_ag_{prefix}")
            
            # --- SÉLECTION DES ÉQUIPES INVITÉES ---
            equipes_invitees_ids = []
            
            # CORRECTION : Initialisation par défaut pour éviter le bug de variable non définie
            faire_suivre_check = False 
            
            if paroisse_id and not equipe_id and not diocese_id:
                st.markdown("**👥 Sélectionnez les équipes concernées :**")
                equipes_paroisse = c.execute("SELECT id, nom_equipe FROM equipes WHERE paroisse_id=?", (paroisse_id,)).fetchall()
                if equipes_paroisse:
                    options_equipes = ["🤝 Toutes les équipes"] + [e[1] for e in equipes_paroisse]
                    eq_dict = {"🤝 Toutes les équipes": "ALL", **{e[1]: e[0] for e in equipes_paroisse}}
                    
                    cle_selection = f"sel_eq_par_{prefix}"
                    if type_ag == "Prière commune":
                        if st.session_state.get(cle_selection) != ["🤝 Toutes les équipes"]:
                            st.session_state[cle_selection] = ["🤝 Toutes les équipes"]
                    
                    equipes_selectionnees = st.multiselect("Équipes", options_equipes, key=cle_selection)
                    
                    if "🤝 Toutes les équipes" in equipes_selectionnees:
                        equipes_invitees_ids = [e[0] for e in equipes_paroisse]
                    else:
                        equipes_invitees_ids = [eq_dict[nom] for nom in equipes_selectionnees]
                else:
                    st.warning("Aucune équipe créée dans cette paroisse.")
                    
            elif equipe_id and not paroisse_id and not diocese_id:
                eq_info = c.execute("SELECT nom_equipe, paroisse_id FROM equipes WHERE id=?", (equipe_id,)).fetchone()
                if eq_info:
                    autres_equipes = c.execute("SELECT id, nom_equipe FROM equipes WHERE paroisse_id=? AND id != ?", (eq_info[1], equipe_id)).fetchall()
                    if autres_equipes:
                        st.markdown("**🔗 Co-organiser avec une autre équipe ? (Optionnel)**")
                        eq_dict_autres = {f"{e[1]}": e[0] for e in autres_equipes}
                        eq_conjointe = st.multiselect("Autre équipe", list(eq_dict_autres.keys()), key=f"sel_eq_conj_{prefix}")
                        equipes_invitees_ids = [eq_dict_autres[nom] for nom in eq_conjointe]
                    
                    faire_suivre_check = st.checkbox("📤 Demander à la Paroisse de faire suivre au Diocèse", value=False, key=f"faire_suivre_{prefix}")
            
            if st.form_submit_button("📅 Enregistrer", width="stretch"):
                # 1. Création de l'événement principal
                c.execute('''INSERT INTO evenements (equipe_id, paroisse_id, diocese_id, date_evenement, type_evenement, lieu, auteur_nom) VALUES (?,?,?,?,?,?,?)''',
                          (equipe_id, paroisse_id, diocese_id, date_ag.isoformat(), type_ag, lieu_ag, auteur_nom))
                new_event_id = c.lastrowid
                
                # 2. Liaison dans la table de jointure
                if equipe_id:
                    c.execute("INSERT INTO evenement_equipes (evenement_id, equipe_id) VALUES (?, ?)", (new_event_id, equipe_id))
                
                for eid_inv in equipes_invitees_ids:
                    c.execute("INSERT INTO evenement_equipes (evenement_id, equipe_id) VALUES (?, ?)", (new_event_id, eid_inv))
                
                commit_and_sync()
                
                faire_suivre = 0
                if equipe_id and not paroisse_id:
                    faire_suivre = 1 if faire_suivre_check else 0
                c.execute('''INSERT INTO agenda (equipe_id, paroisse_id, diocese_id, date_event, type_event, lieu, description, auteur_nom, a_faire_suivre, evenement_id) VALUES (?,?,?,?,?,?,?,?,?,?)''',
                          (equipe_id, paroisse_id, diocese_id, date_ag.isoformat(), type_ag, lieu_ag, desc_ag, auteur_nom, faire_suivre, new_event_id))
                commit_and_sync()
                
                # CORRECTION : Sécurisation du nom de la source pour éviter un crash si la BDD est inconsistante
                source = "Diocèse"
                if equipe_id:
                    eq_res = c.execute("SELECT nom_equipe FROM equipes WHERE id=?", (equipe_id,)).fetchone()
                    source = eq_res[0] if eq_res and eq_res[0] else "Équipe"
                elif paroisse_id:
                    par_res = c.execute('SELECT nom FROM paroisses WHERE id=?', (paroisse_id,)).fetchone()
                    source = f"Paroisse {par_res[0]}" if par_res and par_res[0] else "Paroisse"
                    
                nb_invites = f" ({len(equipes_invitees_ids)} équipe(s) invitée(s))" if equipes_invitees_ids else ""
                envoyer_notification_telegram(f"📅 <b>Nouvel évènement !</b>\n🏢 {source}{nb_invites}\n⛪ {type_ag}\n🗓 {date_ag.strftime('%d/%m/%Y')}\n📍 {lieu_ag}\n👤 {auteur_nom}")
                st.success(f"Évènement enregistré ! {nb_invites} ✅")
                st.rerun()

def afficher_agenda_complet_universel(equipe_id=None, paroisse_id=None, diocese_id=None):
    st.markdown(f'<h3 style="color:#1A237E;">📋 Planification des agendas</h3>', unsafe_allow_html=True)
    query = '''SELECT id, date_event, type_event, lieu, description, auteur_nom, equipe_id, paroisse_id, diocese_id, a_faire_suivre, evenement_id FROM agenda WHERE date_event >= ? '''
    params, conditions = [date.today().isoformat()], []
    
    if equipe_id:
        conditions.extend([
            "equipe_id = ?", 
            "(paroisse_id = ? AND equipe_id IS NULL AND (a_faire_suivre IS NULL OR a_faire_suivre != 2))", 
            "(diocese_id = 1 AND paroisse_id IS NULL AND equipe_id IS NULL)"
        ])
        pid = c.execute("SELECT paroisse_id FROM equipes WHERE id=?", (equipe_id,)).fetchone()
        params.extend([equipe_id, pid[0] if pid and pid[0] else -1])
    elif paroisse_id:
        conditions.extend(["(paroisse_id = ? AND equipe_id IS NULL)", "equipe_id IN (SELECT id FROM equipes WHERE paroisse_id = ?)", "(diocese_id = 1 AND paroisse_id IS NULL AND equipe_id IS NULL)"])
        params.extend([paroisse_id, paroisse_id])
    elif diocese_id:
        conditions.extend([
            "(diocese_id = ? AND paroisse_id IS NULL AND equipe_id IS NULL)", 
            "paroisse_id IN (SELECT id FROM paroisses WHERE diocese_id = ?)"
        ])
        params.extend([diocese_id, diocese_id])
        
    if conditions: query += " AND (" + " OR ".join(conditions) + ")"
    query += " ORDER BY date_event ASC"
    
    items = c.execute(query, params).fetchall()
    if not items: return st.info("Aucun évènement à venir.")
    
    for item in items:
        i_date = safe_date(item[1])
        if not i_date: continue
        
        source_icon, source_nom = "🏛️", "Diocèse"
        if item[6]:
            eq_info = c.execute("SELECT nom_equipe FROM equipes WHERE id=?", (item[6],)).fetchone()
            if eq_info: source_nom, source_icon = f"{eq_info[0]}", "👥"
        elif item[7]:
            par_info = c.execute("SELECT nom FROM paroisses WHERE id=?", (item[7],)).fetchone()
            if par_info: source_nom, source_icon = f"Paroisse {par_info[0]}", "🏘️"

        delta = (i_date - date.today()).days
        delai = "🔴 Aujourd'hui !" if delta == 0 else "🟠 Demain" if delta == 1 else f"🟡 Dans {delta} jours" if delta <= 7 else f"🟢 Dans {delta} jours"
        icone = {"Prière mensuelle": "🧎", "Prière commune": "🙏", "Prière spéciale": "✨", "Pèlerinage": "🚶‍♂️", "Réunion": "🤝"}.get(item[2], "📅")
        
        titre = f"{icone} {i_date.strftime('%d/%m/%Y')} - {item[2]} - {source_icon} {source_nom} ({delai})"
        if item[9] == 1: titre = f"🚨 {titre}"
        elif item[9] == 2: titre = f"📬 {titre}"
            
        with st.expander(titre):
            if item[9] == 1:
                st.markdown('''<div style="background-color: #ffebee; margin: -10px -20px 20px -20px; padding: 15px 20px; border-left: 5px solid #d32f2f; border-radius: 0 8px 8px 0;"><span style="color: #b71c1c; font-weight: bold; font-size: 1.1rem;">🚩 Demande de transmission au Diocèse</span><br><span style="color: #c62828;">L\'équipe émettrice souhaite que cette information soit validée et transmise.</span></div>''', unsafe_allow_html=True)
            elif item[9] == 2:
                st.markdown('''<div style="background-color: #e8f5e9; margin: -10px -20px 20px -20px; padding: 15px 20px; border-left: 5px solid #2e7d32; border-radius: 0 8px 8px 0;"><span style="color: #1b5e20; font-weight: bold; font-size: 1.1rem;">📬 Information validée et transmise</span><br><span style="color: #2e7d32;">Cette annonce a été jugée pertinente et remontée par le niveau paroissial.</span></div>''', unsafe_allow_html=True)

            st.write(f"**🏢 Source :** {source_icon} {source_nom}")
            st.write(f"**👤 Ajouté par :** {item[5]}")
            if item[3]: st.write(f"**📍 Lieu :** {item[3]}")
            if item[4]: st.write(f"**📝 Détails :** {item[4]}")
            
            if st.button("🗑️ Supprimer de mon agenda", key=f"del_ag_{item[0]}"):
                c.execute("DELETE FROM agenda WHERE id=?", (item[0],))
                commit_and_sync()
                st.rerun()

            if item[10]: 
                import urllib.parse
                base_url = "https://gestion-rosaire-hw6wk9ckkfkqogcbm9ock6.streamlit.app/" 
                magic_link = f"{base_url}/?e={item[10]}"
                message = f"Équipier, confirme ta présence pour la {item[2]} du {i_date.strftime('%d/%m/%Y')}.\nMatLoc (Code de vérification):\n\nCliquez ici pour répondre :\n{magic_link}"
                wa_link = f"https://wa.me/?text={urllib.parse.quote(message, safe=':/?=')}"
                st.markdown("---")
                st.markdown(f'<a href="{wa_link}" target="_blank" class="whatsapp-link">📱 Envoyer le lien de réponse sur WhatsApp</a>', unsafe_allow_html=True)

            if st.session_state.get('role') == 'paroisse':
                if item[6] and not item[7] and item[9] == 1:
                    eq_nom_res = c.execute("SELECT nom_equipe FROM equipes WHERE id=?", (item[6],)).fetchone()
                    eq_nom = eq_nom_res[0] if eq_nom_res else "Équipe inconnue"
                    
                    c_val, c_ign = st.columns(2)
                    with c_val:
                        if st.button("⬆️ Valider et faire suivre", key=f"val_fwd_{item[0]}", type="primary"):
                            desc_dio = f"📢 **Transmis par la Paroisse**\nOrigine : {eq_nom}\n\n{item[4] or ''}"
                            c.execute('''INSERT INTO agenda (diocese_id, paroisse_id, date_event, type_event, lieu, description, auteur_nom, a_faire_suivre) VALUES (1, ?, ?, ?, ?, ?, ?, 2)''',
                                      (st.session_state.get('paroisse_id'), item[1], item[2], item[3], desc_dio, f"{st.session_state.get('username')} (Transmis)"))
                            
                            desc_accuse = f"✅ **Accusé de réception**\nVotre demande a été validée et transmise au Diocèse par la Paroisse."
                            c.execute('''INSERT INTO agenda (equipe_id, date_event, type_event, lieu, description, auteur_nom, a_faire_suivre) VALUES (?, ?, ?, ?, ?, ?, 2)''',
                                      (item[6], item[1], item[2], item[3], desc_accuse, f"{st.session_state.get('username')} (Accusé)"))
                            
                            c.execute("DELETE FROM agenda WHERE id=?", (item[0],))
                            commit_and_sync()
                            st.success("Validé ! L'équipe est notifiée et le Diocèse a reçu l'information.")
                            st.rerun()
                            
                    with c_ign:
                        st.write("") 
                        if st.button("❌ Ignorer la demande", key=f"ign_fwd_{item[0]}"):
                            c.execute("DELETE FROM agenda WHERE id=?", (item[0],))
                            commit_and_sync()
                            st.info("Demande ignorée.")
                            st.rerun()
                            
                elif item[8] and not item[6]:
                    st.markdown("---")
                    equipes_paroisse = c.execute("SELECT id, nom_equipe FROM equipes WHERE paroisse_id=?", (st.session_state.get('paroisse_id'),)).fetchall()
                    if equipes_paroisse:
                        eq_dict = {e[1]: e[0] for e in equipes_paroisse}
                        c_sel, c_btn = st.columns([2, 1])
                        with c_sel:
                            choix_eq = st.selectbox("Transmettre à l'équipe :", list(eq_dict.keys()), key=f"fwd_sel_eq_{item[0]}")
                        with c_btn:
                            st.write("")
                            if st.button("⬇️ Faire suivre", key=f"fwd_eq_{item[0]}"):
                                new_desc = f"📢 **Transmis par la Paroisse**\nOrigine : Diocèse\n\n{item[4] or ''}"
                                c.execute('''INSERT INTO agenda (equipe_id, date_event, type_event, lieu, description, auteur_nom, a_faire_suivre) VALUES (?,?,?,?,?,?,0)''',
                                          (eq_dict[choix_eq], item[1], item[2], item[3], new_desc, f"{st.session_state.get('username')} (Transmis)"))
                                commit_and_sync()
                                st.success(f"Transmis à {choix_eq} !")
                                st.rerun()

def afficher_historique_suivi(equipe_id, filtre_type="Tous"):
    query = '''SELECT e.id, e.date_evenement, e.type_evenement, e.lieu,
               SUM(CASE WHEN sp.statut='physique' THEN 1 ELSE 0 END),
               SUM(CASE WHEN sp.statut='spirituel' THEN 1 ELSE 0 END),
               SUM(CASE WHEN sp.statut='a_contacter' THEN 1 ELSE 0 END)
               FROM evenements e 
               JOIN evenement_equipes ee ON e.id = ee.evenement_id
               LEFT JOIN suivi_presences sp ON e.id = sp.evenement_id
               WHERE ee.equipe_id = ? AND e.date_evenement <= ? '''
    params = [equipe_id, date.today().isoformat()]
    if filtre_type != "Tous": 
        query += " AND e.type_evenement = ?"; 
        params.append(filtre_type)
    query += " GROUP BY e.id ORDER BY e.date_evenement DESC LIMIT 20"
    
    for ev in c.execute(query, params).fetchall():
        d_ev = safe_date(ev[1])
        if not d_ev: continue
        nb_p, nb_e, nb_a = ev[4] or 0, ev[5] or 0, ev[6] or 0
        taux = (nb_p / (nb_p+nb_e+nb_a) * 100) if (nb_p+nb_e+nb_a) > 0 else 0
        couleur = "green" if taux >= 75 else "orange" if taux >= 50 else "red"
        icone = {"Prière mensuelle": "🧎", "Prière commune": "🙏", "Prière spéciale": "✨", "Pèlerinage": "🚶‍♂️", "Réunion": "🤝", "Autre": "📌"}.get(ev[2], "📅")
        
        with st.expander(f"{icone} {d_ev.strftime('%d/%m/%Y')} - {ev[2]} | ✅ {nb_p} ⚠️ {nb_e} ❌ {nb_a}"):
            st.markdown(f"**Taux de présence :** :{couleur}[{taux:.0f}%]")
            for statut, label in [('physique', '✅ Présents physiques'), ('spirituel', '🟡 Présents spirituels'), ('a_contacter', '⚪ Sans nouvelles')]:
                rows = c.execute('''SELECT m.nom, m.prenom FROM membres m JOIN suivi_presences sp ON m.id=sp.membre_id WHERE sp.evenement_id=? AND sp.statut=?''', (ev[0], statut)).fetchall()
                if rows: 
                    st.write(f"{label} : " + ", ".join([f"{r[0]} {r[1]}" for r in rows]))

def afficher_whatsapp_tabs(equipe_id=None):
    t1, t2 = st.tabs(["🎂 Anniversaires", "📢 Rappels réabonnement"])
    with t1:
        ans = c.execute('''SELECT m.nom, m.prenom, m.whatsapp, e.nom_equipe, p.nom, m.date_naissance FROM membres m JOIN equipes e ON m.equipe_id=e.id JOIN paroisses p ON m.paroisse_id=p.id WHERE m.statut='actif' AND strftime('%m-%d', m.date_naissance) = ?''', (date.today().strftime('%m-%d'),)).fetchall()
        if ans:
            for a in ans:
                st.markdown(f"**🎂 {a[0]} {a[1]}** - 📍 {a[4]} / {a[3]}")
                if a[2]:
                    lien = lien_whatsapp(a[2], f"Joyeux anniversaire {a[0]} {a[1]} ! 🎉\\n\\nToute l'équipe du Rosaire vous souhaite une journée bénie.")
                    if lien: st.markdown(f'<a href="{lien}" target="_blank" class="whatsapp-link">📱 Souhaiter</a>', unsafe_allow_html=True)
                st.markdown("---")
        else: st.info("🎉 Aucun anniversaire aujourd'hui")
    with t2:
        annee = st.number_input("Année de début", 2020, date.today().year+1, date.today().year, key="rappel_whats")
        query = '''SELECT m.nom, m.prenom, m.whatsapp, e.nom_equipe, p.nom FROM membres m JOIN equipes e ON m.equipe_id=e.id JOIN paroisses p ON m.paroisse_id=p.id WHERE m.statut='actif' AND m.id NOT IN (SELECT a.membre_id FROM abonnements a WHERE a.annee_debut=? AND a.statut='paye')'''
        params = [annee]
        if equipe_id: query += " AND m.equipe_id = ?"; params.append(equipe_id)
        query += " ORDER BY p.nom, e.nom_equipe, m.nom"
        retard = c.execute(query, params).fetchall()
        if retard:
            for m in retard:
                st.markdown(f"**❌ {m[0]} {m[1]}** - 📍 {m[4]} / {m[3]}")
                if m[2]:
                    lien = lien_whatsapp(m[2], f"Bonjour {m[0]} {m[1]},\\n\\nVotre réabonnement pour la période {periode_affichage(annee)} n'a pas été enregistré. Merci de régulariser.")
                    if lien: st.markdown(f'<a href="{lien}" target="_blank" class="whatsapp-link">📱 Rappeler</a>', unsafe_allow_html=True)
                st.markdown("---")
        else: st.success(f"🎉 Tous à jour pour {periode_affichage(annee)} !")

def enregistrer_presence_equipe(equipe_id):
    annee_pasto, debut_pasto, fin_pasto = get_periode_pastorale()
    if est_cloture('equipe', equipe_id, annee_pasto):
        st.error(f"⛔ L'année pastorale {annee_pasto} - {annee_pasto+1} est clôturée. Impossible d'ajouter ou modifier des séances.")
        return    
    types_evenements = ["Prière mensuelle", "Prière commune", "Prière spéciale", "Pèlerinage", "Réunion", "Autre"]
    membres_actifs = c.execute("SELECT id, nom, prenom FROM membres WHERE equipe_id=? AND statut='actif' ORDER BY nom", (equipe_id,)).fetchall()
    
    if not membres_actifs:
        st.warning("Aucun membre actif dans l'équipe pour le moment.")
        return

    with st.expander("📝 Enregistrer / Modifier une séance", expanded=False):
        evenements_lies = c.execute('''SELECT e.id, e.date_evenement, e.type_evenement, e.lieu, e.auteur_nom FROM evenements e JOIN evenement_equipes ee ON e.id = ee.evenement_id WHERE ee.equipe_id = ? ORDER BY e.date_evenement DESC''', (equipe_id,)).fetchall()
        
        options_evts = {}
        for ev in evenements_lies:
            d_ev = safe_date(ev[1])
            if d_ev:
                label = f"{d_ev.strftime('%d/%m/%Y')} - {ev[2]} (Par {ev[4] or 'Mon équipe'})"
                options_evts[label] = ev[0]
                
        choix_evt = st.selectbox("📋 Sélectionner un évènement existant", ["-- Créer un nouvel évènement --"] + list(options_evts.keys()), key="sel_evt_exist")
        
        event_id = None
        lieu_event = ""
        date_event = date.today()
        type_event = types_evenements[0]
        
        if choix_evt != "-- Créer un nouvel évènement --":
            event_id = options_evts[choix_evt]
            ev_details = c.execute("SELECT date_evenement, type_evenement, lieu FROM evenements WHERE id=?", (event_id,)).fetchone()
            date_event = safe_date(ev_details[0])
            type_event = ev_details[1]
            lieu_event = ev_details[2]
            st.info(f"📅 Date : {date_event.strftime('%d/%m/%Y')} | ⛪ Type : {type_event} | 📍 Lieu : {lieu_event or 'Non défini'}")
        else:
            c1, c2, c3 = st.columns(3)
            with c1: date_event = st.date_input("📅 Date", value=date.today(), key="date_suivi_eq")
            with c2: type_event = st.selectbox("⛪ Type", types_evenements, key="type_suivi_eq")
            with c3: lieu_event = st.text_input("📍 Lieu", key="lieu_suivi_eq")

        dernier_event_en_memoire = st.session_state.get("dernier_event_vu")
        if event_id != dernier_event_en_memoire:
            cles_a_supprimer = [k for k in st.session_state.keys() if k.startswith("radio_membre_")]
            for k in cles_a_supprimer:
                del st.session_state[k]
            st.session_state["dernier_event_vu"] = event_id

        with st.form("form_suivi_presences"):
            st.markdown(f"**Participation de l'équipe pour le {date_event.strftime('%d/%m/%Y')} ({type_event}) :**")
            st.caption("💡 Cochez 'Présent spirituel' pour ceux qui participent à l'évènement depuis chez eux.")
            
            statuts = {}
            for m in membres_actifs:
                existing = None
                if event_id:
                    existing = c.execute('''SELECT statut FROM suivi_presences WHERE membre_id=? AND evenement_id=?''', (m[0], event_id)).fetchone()
                
                db_statut = existing[0] if existing and existing[0] in ["physique", "spirituel", "a_contacter"] else "a_contacter"
                widget_key = f"radio_membre_{m[0]}"
                
                if widget_key not in st.session_state:
                    st.session_state[widget_key] = db_statut
                
                statuts[m[0]] = st.radio(
                    f"{m[1]} {m[2]}", 
                    ["physique", "spirituel", "a_contacter"], 
                    format_func=lambda x: {"physique": "🟢 Présent physiquement", "spirituel": "🟡 Présent spirituellement (à distance)", "a_contacter": "⚪ Sans nouvelles"}[x],
                    key=widget_key,
                    horizontal=True
                )
            
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                submitted = st.form_submit_button("💾 Enregistrer la communion", width="stretch")
            with col_btn2:
                clear = st.form_submit_button("🗑️ Effacer cette séance", width="stretch")
            
            if submitted:
                if event_id:
                    if choix_evt == "-- Créer un nouvel évènement --":
                        c.execute("UPDATE evenements SET lieu=? WHERE id=?", (lieu_event, event_id))
                else:
                    c.execute("INSERT INTO evenements (equipe_id, type_evenement, date_evenement, lieu, auteur_nom) VALUES (?, ?, ?, ?, ?)", 
                              (equipe_id, type_event, date_event.isoformat(), lieu_event, st.session_state.get('username')))
                    event_id = c.lastrowid
                    c.execute("INSERT INTO evenement_equipes (evenement_id, equipe_id) VALUES (?, ?)", (event_id, equipe_id))
                
                c.execute("DELETE FROM suivi_presences WHERE evenement_id=?", (event_id,))
                for m_id, statut in statuts.items():
                    c.execute("INSERT INTO suivi_presences (membre_id, evenement_id, statut) VALUES (?, ?, ?)", (m_id, event_id, statut))
                commit_and_sync()
                st.success("Communion de l'équipe enregistrée avec succès ! ✅")
                st.rerun()

            if clear and event_id:
                c.execute("DELETE FROM suivi_presences WHERE evenement_id=?", (event_id,))
                c.execute("DELETE FROM evenement_equipes WHERE evenement_id=?", (event_id,))
                c.execute("DELETE FROM evenements WHERE id=?", (event_id,))
                commit_and_sync()
                st.warning("Séance effacée.")
                st.rerun()

    st.markdown("---")
    st.subheader("📊 Historique et Engagement")
    filtre_type = st.selectbox("Filtrer par type d'évènement", ["Tous"] + types_evenements, key="filtre_hist_eq")
    afficher_historique_suivi(equipe_id, filtre_type)

def afficher_etat_presences_globales(equipe_id):
    st.markdown(f'<h3 style="color:#1A237E;">📊 État de l\'engagement spirituel (Croisement par évènement)</h3>', unsafe_allow_html=True)
    
    annee_actuelle, _, _ = get_periode_pastorale()
    choix_annee = st.selectbox("Année pastorale", [annee_actuelle, annee_actuelle - 1, annee_actuelle - 2], 
                               format_func=lambda x: f"Sept {x} - Août {x+1}", key="sel_annee_eq_globale")
    
    debut_periode = date(choix_annee, 9, 1)
    fin_periode = date(choix_annee + 1, 8, 31)
    
    if est_cloture('equipe', equipe_id, choix_annee):
        st.success("✅ Cette année pastorale est clôturée et archivée.")
    elif choix_annee == annee_actuelle and date.today().month in [9, 10]:
        if st.button("🔒 Clôturer et archiver cette année", key="cloturer_eq"):
            cloturer_periode('equipe', equipe_id, choix_annee, st.session_state['username'])
            st.success("Année clôturée ! Les données sont figées.")
            st.rerun()
    
    types_evenements = ["Prière mensuelle", "Prière commune", "Prière spéciale", "Pèlerinage", "Réunion", "Autre"]
    membres = c.execute("SELECT nom, prenom FROM membres WHERE equipe_id=? AND statut='actif' ORDER BY nom", (equipe_id,)).fetchall()
    if not membres: 
        return st.info("Aucun membre actif dans l'équipe.")
        
    presences = c.execute('''
        SELECT m.nom, m.prenom, e.type_evenement, sp.statut 
        FROM suivi_presences sp 
        JOIN evenements e ON sp.evenement_id = e.id 
        JOIN membres m ON sp.membre_id = m.id
        JOIN evenement_equipes ee ON e.id = ee.evenement_id
        WHERE ee.equipe_id = ? AND e.date_evenement >= ? AND e.date_evenement <= ?
    ''', (equipe_id, debut_periode.isoformat(), fin_periode.isoformat())).fetchall()
    
    if not presences: 
        return st.info(f"Aucune présence enregistrée pour la période de Sept {choix_annee} à Août {choix_annee+1}.")
        
    df = pd.DataFrame(presences, columns=["Nom", "Prenom", "Type", "Statut"])
    df['Est_Engage'] = df['Statut'].isin(['physique', 'spirituel']).astype(int)
    
    stats = df.groupby(['Nom', 'Prenom', 'Type'])['Est_Engage'].agg(['sum', 'count']).reset_index()
    stats.columns = ['Nom', 'Prenom', 'Type', 'Engage', 'Total']
    stats['Taux'] = (stats['Engage'] / stats['Total'] * 100).round(1)
    
    pivot = stats.pivot_table(index=['Nom', 'Prenom'], columns='Type', values='Taux', aggfunc='first')
    for t in types_evenements:
        if t not in pivot.columns: pivot[t] = 0.0
    pivot = pivot[types_evenements].fillna(0)
    
    pivot['Taux global'] = df.groupby(['Nom', 'Prenom'])['Est_Engage'].mean() * 100
    pivot = pivot.reset_index()
    pivot['Membres'] = pivot['Nom'] + ' ' + pivot['Prenom']
    pivot = pivot.drop(columns=['Nom', 'Prenom'])
    
    colonnes_finales = ['Membres'] + types_evenements + ['Taux global']
    pivot = pivot[colonnes_finales].round(1)
    
    taux_equipe = {'Membres': '📊 Taux d\'engagement équipe'}
    for t in types_evenements: taux_equipe[t] = pivot[t].mean().round(1)
    taux_equipe['Taux global'] = pivot['Taux global'].mean().round(1)
    
    df_affichage = pivot.copy()
    for col in types_evenements + ['Taux global']: df_affichage[col] = df_affichage[col].apply(lambda x: f"{x:.1f}%")
        
    df_ligne_equipe = pd.DataFrame([taux_equipe])
    for col in types_evenements + ['Taux global']: df_ligne_equipe[col] = df_ligne_equipe[col].apply(lambda x: f"{x:.1f}%")
        
    # CORRECTION : Plus besoin du "démimage" lourd, ignore_index=True règle le problème PyArrow tout seul
    df_final = pd.concat([df_affichage, df_ligne_equipe], ignore_index=True)
    st.dataframe(df_final, width="stretch")
    
    # Le reste pour le téléchargement
    st.markdown("---")
    st.markdown("### 📥 Générer les rapports d'activité")
    df_excel_complet = pd.concat([pivot, pd.DataFrame([taux_equipe])], ignore_index=True)
    
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        st.markdown("**🏢 Rapport de l'équipe**")
        out_team = io.BytesIO()
        with pd.ExcelWriter(out_team, engine='openpyxl') as w: df_excel_complet.to_excel(w, index=False, sheet_name="Bilan Equipe")
        out_team.seek(0)
        st.download_button(label="📥 Télécharger le bilan de l'équipe", data=out_team, file_name=f"bilan_equipe_Sept{choix_annee}.xlsx", key="dl_team_report", width="stretch")
        
    with col_btn2:
        st.markdown("**👤 Rapport individuel**")
        noms_membres = ["-- Sélectionner --"] + [f"{m[0]} {m[1]}" for m in membres]
        choix_membre = st.selectbox("Choisir un membre", noms_membres, key="select_indiv_report")
        if choix_membre != noms_membres[0]:
            df_indiv = pivot[pivot['Membres'] == choix_membre].copy()
            out_indiv = io.BytesIO()
            with pd.ExcelWriter(out_indiv, engine='openpyxl') as w: df_indiv.to_excel(w, index=False, sheet_name=f"Bilan {choix_membre.split()[0]}")
            out_indiv.seek(0)
            st.download_button(label=f"📥 Télécharger le bilan de {choix_membre.split()[0]}", data=out_indiv, file_name=f"bilan_{choix_membre.replace(' ', '_')}_Sept{choix_annee}.xlsx", key="dl_indiv_report", width="stretch")


def afficher_etat_presences_paroisse(paroisse_id):
    st.markdown(f'<h3 style="color:#1A237E;">📊 État de l\'engagement spirituel (Vue Paroisse)</h3>', unsafe_allow_html=True)
    
    annee_actuelle, _, _ = get_periode_pastorale()
    choix_annee = st.selectbox("Année pastorale", [annee_actuelle, annee_actuelle - 1, annee_actuelle - 2], 
                               format_func=lambda x: f"Sept {x} - Août {x+1}", key="sel_annee_par_globale")
    
    debut_periode = date(choix_annee, 9, 1)
    fin_periode = date(choix_annee + 1, 8, 31)
    
    if est_cloture('paroisse', paroisse_id, choix_annee):
        st.success("✅ Cette année pastorale est clôturée et archivée pour la paroisse.")
    elif choix_annee == annee_actuelle and date.today().month in [9, 10]:
        if st.button("🔒 Clôturer et archiver cette année (Paroisse)", key="cloturer_par"):
            cloturer_periode('paroisse', paroisse_id, choix_annee, st.session_state['username'])
            st.success("Année clôturée !")
            st.rerun()
    
    types_evenements = ["Prière mensuelle", "Prière commune", "Prière spéciale", "Pèlerinage", "Réunion", "Autre"]
    
    # CORRECTION CRITIQUE : On lie evenement_equipes via l'équipe du membre pour éviter de multiplier les lignes
    presences = c.execute('''
        SELECT COALESCE(eq.nom_equipe, 'Événement Paroisse') as Equipe, e.type_evenement, sp.statut 
        FROM suivi_presences sp 
        JOIN membres m ON sp.membre_id = m.id
        JOIN evenements e ON sp.evenement_id = e.id 
        LEFT JOIN evenement_equipes ee ON e.id = ee.evenement_id AND ee.equipe_id = m.equipe_id
        LEFT JOIN equipes eq ON ee.equipe_id = eq.id
        WHERE (e.paroisse_id = ? OR eq.paroisse_id = ?) AND e.date_evenement >= ? AND e.date_evenement <= ?
    ''', (paroisse_id, paroisse_id, debut_periode.isoformat(), fin_periode.isoformat())).fetchall()
    
    if not presences: 
        return st.info(f"Aucune présence enregistrée pour la période de Sept {choix_annee} à Août {choix_annee+1}.")
        
    df = pd.DataFrame(presences, columns=["Equipe", "Type", "Statut"])
    df['Est_Engage'] = df['Statut'].isin(['physique', 'spirituel']).astype(int)
    
    stats = df.groupby(['Equipe', 'Type'])['Est_Engage'].agg(['sum', 'count']).reset_index()
    stats.columns = ['Equipe', 'Type', 'Engage', 'Total']
    stats['Taux'] = (stats['Engage'] / stats['Total'] * 100).round(1)
    
    pivot = stats.pivot_table(index='Equipe', columns='Type', values='Taux', aggfunc='first')
    for t in types_evenements:
        if t not in pivot.columns: pivot[t] = 0.0
    pivot = pivot[types_evenements].fillna(0)
    
    pivot['Taux global'] = df.groupby('Equipe')['Est_Engage'].mean().mul(100).round(1)
    pivot = pivot.reset_index()
    
    colonnes_finales = ['Equipe'] + types_evenements + ['Taux global']
    pivot = pivot[colonnes_finales].round(1)
    
    taux_paroisse = {'Equipe': '📊 Taux d\'engagement Paroisse'}
    for t in types_evenements: taux_paroisse[t] = pivot[t].mean().round(1)
    taux_paroisse['Taux global'] = pivot['Taux global'].mean().round(1)
    
    df_affichage = pivot.copy()
    for col in types_evenements + ['Taux global']: df_affichage[col] = df_affichage[col].apply(lambda x: f"{x:.1f}%")
        
    df_ligne_paroisse = pd.DataFrame([taux_paroisse])
    for col in types_evenements + ['Taux global']: df_ligne_paroisse[col] = df_ligne_paroisse[col].apply(lambda x: f"{x:.1f}%")
        
    # CORRECTION CRITIQUE : Plus de "démimage" nécessaire, et c'est bien 'Equipe' désormais
    df_final = pd.concat([df_affichage, df_ligne_paroisse], ignore_index=True)
    st.dataframe(df_final, width="stretch")
    
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine='openpyxl') as w:
        pd.concat([pivot, pd.DataFrame([taux_paroisse])], ignore_index=True).to_excel(w, index=False, sheet_name="Bilan Paroisse")
    out.seek(0)
    st.download_button("📥 Télécharger le bilan de la paroisse", data=out, file_name=f"bilan_paroisse_Sept{choix_annee}.xlsx", key="dl_par_report", width="stretch")

def afficher_historique_paroisse(paroisse_id, filtre_type="Tous"):
    # CORRECTION : Utilisation de COUNT(DISTINCT sp.membre_id) pour éviter de multiplier les présences
    # si un événement est lié à plusieurs équipes de la même paroisse
    query = '''SELECT e.id, e.date_evenement, e.type_evenement, e.lieu, GROUP_CONCAT(DISTINCT eq.nom_equipe) as noms_equipes,
               COUNT(DISTINCT CASE WHEN sp.statut='physique' THEN sp.membre_id END),
               COUNT(DISTINCT CASE WHEN sp.statut='spirituel' THEN sp.membre_id END),
               COUNT(DISTINCT CASE WHEN sp.statut='a_contacter' THEN sp.membre_id END)
               FROM evenements e 
               JOIN evenement_equipes ee ON e.id = ee.evenement_id
               JOIN equipes eq ON ee.equipe_id = eq.id
               LEFT JOIN suivi_presences sp ON e.id = sp.evenement_id
               WHERE eq.paroisse_id = ? AND e.date_evenement <= ? '''
    params = [paroisse_id, date.today().isoformat()]
    if filtre_type != "Tous":
        query += " AND e.type_evenement = ?"; 
        params.append(filtre_type)
    query += " GROUP BY e.id ORDER BY e.date_evenement DESC LIMIT 20"
    
    for ev in c.execute(query, params).fetchall():
        d_ev = safe_date(ev[1])
        if not d_ev: continue
        nb_p, nb_e, nb_a = ev[5] or 0, ev[6] or 0, ev[7] or 0
        total = nb_p + nb_e + nb_a
        taux = (nb_p / total * 100) if total > 0 else 0
        couleur = "green" if taux >= 75 else "orange" if taux >= 50 else "red"
        icone = {"Prière mensuelle": "🧎", "Prière commune": "🙏", "Prière spéciale": "✨", "Pèlerinage": "🚶‍♂️", "Réunion": "🤝", "Autre": "📌"}.get(ev[2], "📅")
        
        with st.expander(f"{icone} {d_ev.strftime('%d/%m/%Y')} - {ev[2]} ({ev[4]}) | ✅ {nb_p} ⚠️ {nb_e} ❌ {nb_a}"):
            st.markdown(f"**Taux de présence :** :{couleur}[{taux:.0f}%]")
            for statut, label in [('physique', '✅ Présents physiques'), ('spirituel', '🟡 Présents spirituels'), ('a_contacter', '⚪ Sans nouvelles')]:
                rows = c.execute('''SELECT m.nom, m.prenom, eq.nom_equipe FROM membres m 
                                    JOIN suivi_presences sp ON m.id=sp.membre_id 
                                    JOIN equipes eq ON m.equipe_id=eq.id
                                    WHERE sp.evenement_id=? AND sp.statut=?''', (ev[0], statut)).fetchall()
                if rows: 
                    st.write(f"{label} : " + ", ".join([f"{r[0]} {r[1]} ({r[2]})" for r in rows]))

def afficher_page_reponse_membre(event_id):
    st.caption("🔒 En saisissant votre identifiant, vous acceptez que vos données de présence soient enregistrées par les responsables de votre équipe.")
    st.markdown("<h2 style='text-align:center; color:#1A237E; font-size: 1.5rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;'>📿 Réponse de Communion</h2>", unsafe_allow_html=True)
    
    try:
        event_id = int(event_id)
    except:
        st.error("Lien invalide.")
        return

    evt = c.execute("SELECT type_evenement, date_evenement, lieu FROM evenements WHERE id=?", (event_id,)).fetchone()
    if not evt:
        st.error("Cet événement n'existe pas.")
        return
        
    date_evt = safe_date(evt[1])
    st.markdown(f"""
    <div style="background-color:#f3e5f5; padding:20px; border-radius:10px; text-align:center; margin-bottom:30px;">
        <h3 style="color:#4A148C; margin-bottom:10px;">{evt[0]}</h3>
        <p style="font-size:1.1rem; color:#1A237E; margin:5px 0;">📅 {date_evt.strftime('%d/%m/%Y') if date_evt else 'Date inconnue'}</p>
        <p style="font-size:1.1rem; color:#1A237E; margin:5px 0;">📍 {evt[2] or 'Lieu non défini'}</p>
    </div>
    """, unsafe_allow_html=True)

    # CORRECTION BUG : Réinitialisation de la mémoire si l'événement change dans l'URL
    if st.session_state.get('event_id_verifie') != event_id:
        st.session_state['membre_verifie'] = False
        st.session_state['membre_info'] = None
        st.session_state['membre_a_repondu'] = False
        st.session_state['event_id_verifie'] = event_id

    # --- ÉTAPE 1 : VÉRIFICATION ---
    if not st.session_state.get('membre_verifie', False):
        st.markdown("**Entrez votre numéro de membre (MatLoc) :**")
        col1, col2 = st.columns([2, 1])
        with col1:
            matloc_saisi = st.text_input("MatLoc", placeholder="Ex: GBA-A1B2C", label_visibility="collapsed").upper().strip()
        with col2:
            st.write("")
            bouton_verifier = st.button("Vérifier", width="stretch")

        if bouton_verifier and matloc_saisi:
            membre = c.execute("""
                SELECT m.id, m.nom, m.prenom 
                FROM membres m 
                JOIN evenement_equipes ee ON m.equipe_id = ee.equipe_id 
                WHERE m.matloc = ? AND ee.evenement_id = ? AND m.statut = 'actif'
            """, (matloc_saisi, event_id)).fetchone()

            if not membre:
                st.error("❌ MatLoc inconnu ou vous ne faites pas partie d'une équipe invitée à cet événement.")
            else:
                st.session_state['membre_verifie'] = True
                st.session_state['membre_info'] = membre
                st.rerun()

    # --- ÉTAPE 2 : LE CHOIX ---
    else:
        membre = st.session_state['membre_info']
        st.success(f"Bonjour **{membre[1]} {membre[2]}** ! Comment vous joignez-vous à nous ?")
        
        deja_repondu = c.execute("SELECT statut FROM suivi_presences WHERE membre_id=? AND evenement_id=?", (membre[0], event_id)).fetchone()
        index_defaut = 0
        if deja_repondu and deja_repondu[0] == 'spirituel': 
            index_defaut = 1

        choix = st.radio(
            "Votre engagement :", 
            ["physique", "spirituel"], 
            format_func=lambda x: {"physique": "🟢 Je serai présent physiquement", "spirituel": "🟡 Je prierai de chez moi (Spirituel)"}[x],
            index=index_defaut,
            horizontal=False
        )

        if st.button("✅ Confirmer ma réponse", width="stretch", type="primary"):
            if deja_repondu:
                c.execute("UPDATE suivi_presences SET statut=? WHERE membre_id=? AND evenement_id=?", (choix, membre[0], event_id))
            else:
                c.execute("INSERT INTO suivi_presences (membre_id, evenement_id, statut) VALUES (?, ?, ?)", (membre[0], event_id, choix))
            commit_and_sync()
            st.session_state['membre_a_repondu'] = True

        if st.session_state.get('membre_a_repondu'):
            if choix == "physique":
                st.balloons()
                st.success("À bientôt en communion physique ! 🙏")
            else: 
                st.snow()
                st.success("Merci pour votre communion spirituelle, nous nous unirons à vous ! 🙏")
