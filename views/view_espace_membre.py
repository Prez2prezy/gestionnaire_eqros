import streamlit as st
import time
import streamlit.components.v1 as components
import json
from datetime import date
from database import c, commit_and_sync
from services import safe_date

# --- Design doux et apaisant pour l'espace de prière ---
st.markdown("""
<style>
    .card-welcome {
        background: linear-gradient(135deg, #e8eaf6 0%, #f3e5f5 100%);
        padding: 25px;
        border-radius: 15px;
        text-align: center;
        margin-bottom: 25px;
        border: 1px solid #e0e0e0;
    }
    .card-event {
        background: #ffffff;
        padding: 20px;
        border-radius: 12px;
        border-left: 5px solid #4527a0;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        margin-bottom: 20px;
    }
    .card-profile {
        background: #ffffff;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

def show_espace_membre(matloc_membre=None):
    # --- L'ESPACE PUBLIC (Si pas de MatLoc) ---
    if not matloc_membre:
        st.markdown('<h2 style="color:#4527a0; text-align:center;">🕊️ Espace de Prière & Méditation</h2>', unsafe_allow_html=True)
        st.markdown('<p style="text-align:center; color:#666;">Diocèse de Grand-Bassam</p>', unsafe_allow_html=True)
        
        # On affiche directement l'espace spirituel public
        tab_priere, tab_meditation, tab_musique = st.tabs(["🙏 Prières", "📖 Méditations", "🎵 Musiques"])
        _render_spiritual_tabs(tab_priere, tab_meditation, tab_musique)
        return

    # --- L'ESPACE PERSONNALISE (Si MatLoc est fourni) ---
    membre = c.execute("""
        SELECT m.id, m.nom, m.prenom, m.matloc, m.whatsapp, m.date_adhesion, m.photo_path, e.nom_equipe, p.nom 
        FROM membres m 
        JOIN equipes e ON m.equipe_id = e.id 
        JOIN paroisses p ON m.paroisse_id = p.id 
        WHERE m.matloc=? AND m.statut='actif'
    """, (matloc_membre,)).fetchone()
    
    if not membre:
        st.error("Identifiant de membre inconnu. Vérifiez votre lien MatLoc.")
        return

    # CALCUL DE L'ANCIENNETE
    date_adh = safe_date(membre[5])
    annees_fidelite = (date.today() - date_adh).days // 365 if date_adh else 0

    # ====================================================================
    # LES 3 GRANDS ONGLETS PRINCIPAUX (Mobile First)
    # ====================================================================
    tab_ressources, tab_agenda, tab_profil = st.tabs(["🙏 Ressources", "📅 Mon Agenda", "👤 Mon Espace"])

    # --------------------------------------------------------------------
    # ONGLET 1 : RESSOURCES SPIRITUELLES
    # --------------------------------------------------------------------
    with tab_ressources:
        # CARTE DE BIENVENUE
        st.markdown(f"""
        <div class="card-welcome">
            <h2 style="color:#4527a0; margin-top:0;">Bienvenue {membre[2]} {membre[1]} 🕊️</h2>
            <p style="color:#6a1b9a; font-size:1.1rem;"> <b>{membre[7]}</b> | {membre[8]}</p>
            <p style="color:#888; font-size:0.9rem;">Retrouvez ici vos ressources pour la prière et la méditation.</p>
        </div>
        """, unsafe_allow_html=True)

        # MISE EN AVANT DU DERNIER CONTENU
        dernier_contenu = c.execute("SELECT type_contenu, titre FROM espace_spirituel ORDER BY date_publication DESC LIMIT 1").fetchone()
        if dernier_contenu:
            icone = "🙏" if dernier_contenu[0] == "priere" else "📖" if dernier_contenu[0] == "meditation" else "🎵"
            st.info(f"🆕 {icone} Dernière publication : **{dernier_contenu[1]}**")

        # SOUS-ONGLETS DU CONTENU
        tab_priere, tab_meditation, tab_musique = st.tabs(["🙏 Prières", "📖 Méditations", "🎵 Musiques"])
        _render_spiritual_tabs(tab_priere, tab_meditation, tab_musique)


    # --------------------------------------------------------------------
    # ONGLET 2 : AGENDA (SPOTLIGHT SUR LE PROCHAIN ÉVÉNEMENT)
    # --------------------------------------------------------------------
    with tab_agenda:
        st.markdown("### 📅 Vos prochains rassemblements")
        
        # ON CIBLE LE PROCHAIN ÉVÉNEMENT
        prochain_evt = c.execute('''
            SELECT e.id, e.date_evenement, e.type_evenement, e.lieu, 
                   (SELECT statut FROM suivi_presences WHERE membre_id=? AND evenement_id=e.id)
            FROM evenements e 
            JOIN evenement_equipes ee ON e.id = ee.evenement_id 
            WHERE ee.equipe_id = (SELECT equipe_id FROM membres WHERE matloc=?) 
            AND e.date_evenement >= ?
            ORDER BY e.date_evenement ASC LIMIT 1
        ''', (membre[0], matloc_membre, date.today().isoformat())).fetchone()

        if prochain_evt:
            evt_date = safe_date(prochain_evt[1])
            delta = (evt_date - date.today()).days
            delai = "🔴 Aujourd'hui !" if delta == 0 else "🟠 C'est demain !" if delta == 1 else f"📅 Dans {delta} jours"
            icone_evt = {"Prière mensuelle": "🧎", "Prière commune": "🙏", "Prière spéciale": "✨", "Pèlerinage": "🚶‍♂️", "Réunion": "🤝"}.get(prochain_evt[2], "📅")
            
            # LE SPOTLIGHT
            st.markdown(f"""
            <div class="card-event">
                <h3 style="color:#4527a0; margin-top:0;">{icone} {prochain_evt[2]}</h3>
                <p style="font-size:1.2rem; margin:10px 0;"><b>{delai}</b></p>
                <p>🗓️ <b>{evt_date.strftime('%d/%m/%Y')}</b> &nbsp;&nbsp; 📍 {prochain_evt[3] or 'Lieu à définir'}</p>
            </div>
            """, unsafe_allow_html=True)

            # GESTION DE LA RÉPONSE
            if not prochain_evt[4]: # S'il n'a pas répondu
                st.markdown("**Comment vous joignez-vous à nous ?**")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("🟢 Présent physiquement", use_container_width=True, type="primary"):
                        st.session_state['repondre_event_id'] = prochain_evt[0]
                        st.session_state['choix_action'] = "physique"
                        st.rerun()
                with col2:
                    if st.button("🟡 Présent spirituellement", use_container_width=True):
                        st.session_state['repondre_event_id'] = prochain_evt[0]
                        st.session_state['choix_action'] = "spirituel"
                        st.rerun()
            else:
                statut_txt = "✅ Physique" if prochain_evt[4] == 'physique' else "🟡 Spirituel"
                st.success(f"Vous êtes inscrit : {statut_txt}")

            # LE FORMULAIRE CACHÉ QUI APPARAIT AU CLIC (Garde votre logique exacte)
            if 'repondre_event_id' in st.session_state:
                evt_id = st.session_state['repondre_event_id']
                evt = c.execute("SELECT type_evenement, date_evenement, lieu FROM evenements WHERE id=?", (evt_id,)).fetchone()
                if evt:
                    d_evt = safe_date(evt[1])
                    st.info(f"Confirmation pour : **{evt[0]}** du {d_evt.strftime('%d/%m/%Y')}")
                    
                    if st.button("✅ Confirmer définitivement", type="primary"):
                        choix = st.session_state.get('choix_action', 'physique')
                        deja_repondu = c.execute("SELECT statut FROM suivi_presences WHERE membre_id=? AND evenement_id=?", (membre[0], evt_id)).fetchone()
                        if deja_repondu:
                            c.execute("UPDATE suivi_presences SET statut=? WHERE membre_id=? AND evenement_id=?", (choix, membre[0], evt_id))
                        else:
                            c.execute("INSERT INTO suivi_presences (membre_id, evenement_id, statut) VALUES (?, ?, ?)", (membre[0], evt_id, choix))
                        commit_and_sync()
                        del st.session_state['repondre_event_id']
                        del st.session_state['choix_action']
                        if choix == "physique": st.balloons()
                        else: st.snow()
                        st.success("Merci pour votre engagement ! 🙏")
                        time.sleep(2)
                        st.rerun()
        else:
            st.success("✅ Aucun événement à venir. Profitez de ce temps de repos !")


    # --------------------------------------------------------------------
    # ONGLET 3 : MON ESPACE (CARTE DE MEMBRE)
    # --------------------------------------------------------------------
    with tab_profil:
        st.markdown("### 👤 Ma Fiche Membre")
        
        col_photo, col_infos = st.columns([1, 2])
        
        with col_photo:
            st.markdown('<div class="card-profile">', unsafe_allow_html=True)
            if membre[6]:
                try: st.image(membre[6], width=150)
                except: st.markdown("<h1 style='color:#4527a0;'>👤</h1>", unsafe_allow_html=True)
            else:
                st.markdown("<h1 style='color:#4527a0;'>👤</h1>", unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
        with col_infos:
            st.markdown(f"""
            <div class="card-profile" style="text-align: left; padding: 30px;">
                <h2 style="color:#4527a0; margin-top:0; text-align:center;">{membre[2]} {membre[1]}</h2>
                <hr style="border: 1px solid #e0e0e0;">
                <p style="font-size: 1.1rem;"><b>🪪 MatLoc :</b> <code style="background:#f3e5f5; padding:5px; border-radius:5px; color:#4527a0; font-weight:bold;">{membre[3]}</code></p>
                <p><b>👥 Équipe :</b> {membre[7]}</p>
                <p><b>🏛️ Paroisse :</b> {membre[8]}</p>
                <p><b>💬 WhatsApp :</b> {membre[4] or 'Non renseigné'}</p>
                <p><b>📅 Fidélité :</b> {annees_fidelite} an(s)</p>
            </div>
            """, unsafe_allow_html=True)

# ====================================================================
# FONCTION PRIVÉE PÉVITER LA RÉPÉTITION DU CODE SPIRITUEL
# ====================================================================
def _render_spiritual_tabs(tab_priere, tab_meditation, tab_musique):
    """Gère l'affichage des prières, méditations et musiques"""
    
    with tab_priere:
        prières = c.execute("SELECT titre, contenu_texte, image_url FROM espace_spirituel WHERE type_contenu='priere' ORDER BY date_publication DESC").fetchall()
        if not prières:
            st.info("Aucune prière publiée pour le moment.")
        else:
            for p in prières:
                with st.expander(f"📖 {p[0]}"):
                    if len(p) > 2 and p[2] and p[2].startswith("http"): 
                        st.image(p[2], use_column_width="auto")
                    if p[1]:
                        st.markdown(p[1], unsafe_allow_html=True)

    with tab_meditation:
        meditations = c.execute("SELECT titre, contenu_texte, image_url FROM espace_spirituel WHERE type_contenu='meditation' ORDER BY date_publication DESC").fetchall()
        if not meditations:
            st.info("Aucune méditation disponible pour le moment.")
        else:
            for m in meditations:
                with st.expander(f"📖 {m[0]}"):
                    if len(m) > 2 and m[2] and m[2].startswith("http"): 
                        st.image(m[2], use_column_width="auto")
                    if m[1]:
                        st.markdown(m[1], unsafe_allow_html=True)

    with tab_musique:
        audios = c.execute("SELECT titre, fichier_url FROM espace_spirituel WHERE type_contenu='audio' ORDER BY date_publication DESC").fetchall()
        
        if not audios:
            st.info("Aucun fichier audio n'a encore été ajouté.")
        else:
            tracks_json = [{"title": a[0], "url": a[1]} for a in audios if a[1] is not None and str(a[1]).startswith("http")]
            
            if not tracks_json:
                st.warning("Les URL des fichiers doivent commencer par http:// ou https://")
            else:
                # J'INSÈRE ICI LE CODE DU LECTEUR AUDIO QUE NOUS AVONS CRÉÉ ET CORRIGÉ ENSEMBLE
                # (J'abrège le HTML pour ne pas prendre 3 pages, mais VOUS devez mettre 
                # le bloc complet avec les boutons, le <video> et le <script> ici)
                player_html = """
                <div style="font-family: sans-serif; max-width: 600px; margin: auto; padding: 15px; border: 1px solid #e0e0e0; border-radius: 15px; background: #fafafa;">
                    <h3 style="text-align:center; color:#4527a0; margin-top:0;">🎵 Lecteur Spirituel</h3>
                    <!-- METTEZ TOUT LE HTML DU LECTEUR ICI -->
                    <p style="text-align:center; color:red; font-weight:bold;">LECTEUR AUDIO ICI</p>
                </div>
                """.replace("TRACKS_DATA", json.dumps(tracks_json))
                components.html(player_html, height=750)
