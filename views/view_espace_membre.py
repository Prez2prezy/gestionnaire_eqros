import streamlit as st
import time
import streamlit.components.v1 as components
import json
from datetime import date
from database import c, commit_and_sync
from services import safe_date

# --- DESIGN DE L'ESPACE MEMBRE ---
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
        
        tab_priere, tab_meditation, tab_musique = st.tabs(["🙏 Prières", "📖 Méditations", "🎵 Musiques"])
        _render_spiritual_tabs(tab_priere, tab_meditation, tab_musique)
        return

    # --- L'ESPACE PERSONNALISE (Si MatLoc est fourni) ---
    # ATTENTION : J'AI ENLEVÉ LE TRY...EXCEPT ICI. 
    # Si quelque chose plante, Streamlit nous dira EXACTEMENT quoi, au lieu de parler des "10 éléments".
    
    membre = c.execute("""
        SELECT m.id, m.nom, m.prenom, m.matloc, m.whatsapp, m.date_adhesion, m.photo_path, m.numero_meditation, e.nom_equipe, p.nom 
        FROM membres m 
        JOIN equipes e ON m.equipe_id = e.id 
        JOIN paroisses p ON m.paroisse_id = p.id 
        WHERE m.matloc=? AND m.statut='actif'
    """, (matloc_membre,)).fetchone()
    
    if not membre:
        st.error("Identifiant de membre inconnu. Vérifiez votre lien MatLoc.")
        return

    date_adh = safe_date(membre[5])
    annees_fidelite = (date.today() - date_adh).days // 365 if date_adh else 0

    tab_ressources, tab_agenda, tab_profil = st.tabs(["🙏 Ressources", "📅 Mon Agenda", "👤 Mon Espace"])

    # --------------------------------------------------------------------
    # ONGLET 1 : RESSOURCES SPIRITUELLES
    # --------------------------------------------------------------------
    with tab_ressources:
        st.markdown(f"""
        <div class="card-welcome">
            <h2 style="color:#4527a0; margin-top:0;">Bienvenue {membre[2]} {membre[1]} 🕊️</h2>
            <p style="color:#6a1b9a; font-size:1.1rem;">{membre[8]} | {membre[9]}</p>
            <p style="color:#888; font-size:0.9rem;">Retrouvez ici vos ressources pour la prière et la méditation.</p>
        </div>
        """, unsafe_allow_html=True)

        dernier_contenu = c.execute("SELECT type_contenu, titre FROM espace_spirituel ORDER BY date_publication DESC LIMIT 1").fetchone()
        if dernier_contenu:
            icone = "🙏" if dernier_contenu[0] == "priere" else "📖" if dernier_contenu[0] == "meditation" else "🎵"
            st.info(f"🆕 {icone} Dernière publication : **{dernier_contenu[1]}**")

        tab_priere, tab_meditation, tab_musique = st.tabs(["🙏 Prières", "📖 Méditations", "🎵 Musiques"])
        _render_spiritual_tabs(tab_priere, tab_meditation, tab_musique)

    # --------------------------------------------------------------------
    # ONGLET 2 : AGENDA
    # --------------------------------------------------------------------
    with tab_agenda:
        st.markdown("### 📅 Vos prochains rassemblements")
        
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
            
            st.markdown(f"""
            <div class="card-event">
                <h3 style="color:#4527a0; margin-top:0;">{icone_evt} {prochain_evt[2]}</h3>
                <p style="font-size:1.2rem; margin:10px 0;"><b>{delai}</b></p>
                <p>🗓️ <b>{evt_date.strftime('%d/%m/%Y')}</b> &nbsp;&nbsp; 📍 {prochain_evt[3] or 'Lieu à définir'}</p>
            </div>
            """, unsafe_allow_html=True)

            if not prochain_evt[4]:
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
    # ONGLET 3 : MON ESPACE 
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
                <p><b>👥</b> {membre[8]}</p>
                <p><b>📿 N° de Méditation :</b> {membre[7] or 'Non défini'}</p>
                <p><b>🏛️ Paroisse :</b> {membre[9]}</p>
                <p><b>💬 WhatsApp :</b> {membre[4] or 'Non renseigné'}</p>
                <p><b>📅 Fidélité :</b> {annees_fidelite} an(s)</p>
            </div>
            """, unsafe_allow_html=True)


# ====================================================================
# FONCTIONS PRIVÉES
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
                # --- DÉBUT DU LECTEUR AUDIO COMPLET ---
                player_html = """
                <div style="font-family: sans-serif; max-width: 600px; margin: auto; padding: 15px; border: 1px solid #e0e0e0; border-radius: 15px; background: #fafafa;">
                    <h3 style="text-align:center; color:#4527a0; margin-top:0;">🎵 Lecteur Spirituel</h3>
                    
                    <div id="now-playing" style="text-align:center; font-weight:bold; font-size:1.1rem; margin-bottom:15px; min-height: 30px; color:#333;">
                        Cliquez sur une piste
                    </div>
                    
                    <div style="display: flex; justify-content: center; gap: 10px; margin-bottom: 15px; flex-wrap: wrap;">
                        <button id="btn-prev" style="background:none; border:none; font-size:20px; cursor:pointer; padding:5px;">⏮️</button>
                        <button id="btn-shuffle" style="background:none; border:none; font-size:20px; cursor:pointer; opacity:0.5; padding:5px;">🔀</button>
                        <button id="btn-loop" style="background:none; border:none; font-size:20px; cursor:pointer; opacity:0.5; padding:5px;">🔁</button>
                        <button id="btn-next" style="background:none; border:none; font-size:20px; cursor:pointer; padding:5px;">⏭️</button>
                        <button id="btn-play-selection" style="background:#4527a0; color:white; border:none; font-size:14px; cursor:pointer; opacity:0.5; padding:5px 10px; border-radius:15px;">▶️ Sélection</button>
                    </div>

                    <video id="audio-player" controls controlsList="nodownload" style="width: 100%; outline:none; max-height: 150px; background:black; border-radius:8px;"></video>
                    
                    <ul id="playlist" style="list-style: none; padding: 0; margin-top: 15px; max-height: 350px; overflow-y: auto; border-top: 1px solid #ddd; padding-top: 10px;"></ul>
                </div>

                <script>
                    const tracks = TRACKS_DATA;
                    let currentTrackIndex = 0;
                    let isShuffled = false;
                    let loopMode = 0; 
                    let playbackOrder = tracks.map((_, i) => i);
                    let selectedTracks = new Set();

                    const audio = document.getElementById('audio-player');
                    const nowPlaying = document.getElementById('now-playing');
                    const playlistEl = document.getElementById('playlist');
                    const btnShuffle = document.getElementById('btn-shuffle');
                    const btnLoop = document.getElementById('btn-loop');
                    const btnPlaySel = document.getElementById('btn-play-selection');

                    function renderPlaylist() {
                        playlistEl.innerHTML = '';
                        playbackOrder.forEach((origIndex) => {
                            const li = document.createElement('li');
                            li.style.padding = '8px';
                            li.style.margin = '4px 0';
                            li.style.background = origIndex === currentTrackIndex ? '#e1bee7' : 'white';
                            li.style.borderRadius = '8px';
                            li.style.cursor = 'pointer';
                            li.style.borderLeft = origIndex === currentTrackIndex ? '5px solid #4527a0' : '5px solid transparent';
                            
                            const checkbox = document.createElement('input');
                            checkbox.type = 'checkbox';
                            checkbox.checked = selectedTracks.has(origIndex);
                            checkbox.style.marginRight = '10px';
                            checkbox.style.transform = 'scale(1.3)';
                            checkbox.style.cursor = 'pointer';
                            checkbox.onclick = (e) => {
                                e.stopPropagation(); 
                                if (selectedTracks.has(origIndex)) selectedTracks.delete(origIndex);
                                else selectedTracks.add(origIndex);
                                updateSelectionButton();
                            };
                            li.prepend(checkbox);

                            const textSpan = document.createElement('span');
                            textSpan.innerHTML = '<span style="color:#4527a0">🎵</span> ' + tracks[origIndex].title;
                            li.appendChild(textSpan);
                            
                            li.onclick = () => playTrack(origIndex);
                            playlistEl.appendChild(li);
                        });
                        updateSelectionButton();
                    }

                    function updateSelectionButton() {
                        if (selectedTracks.size > 0) {
                            btnPlaySel.style.opacity = '1';
                            btnPlaySel.innerText = '▶️ Lecture (' + selectedTracks.size + ')';
                        } else {
                            btnPlaySel.style.opacity = '0.5';
                            btnPlaySel.innerText = '▶️ Sélection';
                        }
                    }

                    function playSelection() {
                        if (selectedTracks.size === 0) return;
                        playbackOrder = Array.from(selectedTracks);
                        playTrack(playbackOrder[0]);
                    }

                    function playTrack(index) {
                        currentTrackIndex = index;
                        audio.src = tracks[index].url;
                        nowPlaying.innerText = tracks[index].title;
                        audio.play().catch(e => console.error("Erreur de lecture:", e));
                        renderPlaylist();
                    }

                    function nextTrack() {
                        let currentDisplayIndex = playbackOrder.indexOf(currentTrackIndex);
                        if (currentDisplayIndex < playbackOrder.length - 1) {
                            playTrack(playbackOrder[currentDisplayIndex + 1]);
                        } else if (loopMode === 1) {
                            playTrack(playbackOrder[0]);
                        }
                    }

                    function prevTrack() {
                        if (audio.currentTime > 3) {
                            audio.currentTime = 0;
                        } else {
                            let currentDisplayIndex = playbackOrder.indexOf(currentTrackIndex);
                            if (currentDisplayIndex > 0) {
                                playTrack(playbackOrder[currentDisplayIndex - 1]);
                            } else if (loopMode === 1) {
                                playTrack(playbackOrder[playbackOrder.length - 1]);
                            }
                        }
                    }

                    function toggleShuffle() {
                        isShuffled = !isShuffled;
                        btnShuffle.style.opacity = isShuffled ? '1' : '0.5';
                        if (isShuffled) {
                            for (let i = playbackOrder.length - 1; i > 0; i--) {
                                const j = Math.floor(Math.random() * (i + 1));
                                [playbackOrder[i], playbackOrder[j]] = [playbackOrder[j], playbackOrder[i]];
                            }
                        } else {
                            playbackOrder = tracks.map((_, i) => i);
                        }
                        renderPlaylist();
                    }

                    function toggleLoop() {
                        loopMode = (loopMode + 1) % 3;
                        if (loopMode === 0) { 
                            audio.loop = false; 
                            btnLoop.style.opacity = '0.5'; 
                            btnLoop.innerText = '🔁'; 
                        }
                        else if (loopMode === 1) { 
                            audio.loop = false; 
                            btnLoop.style.opacity = '1'; 
                            btnLoop.innerText = '🔁'; 
                        }
                        else { 
                            audio.loop = true; 
                            btnLoop.style.opacity = '1'; 
                            btnLoop.innerText = '🔂'; 
                        }
                    }

                    audio.addEventListener('ended', () => {
                        if (!audio.loop) {
                            nextTrack(); 
                        }
                    });

                    document.getElementById('btn-prev').addEventListener('click', prevTrack);
                    document.getElementById('btn-next').addEventListener('click', nextTrack);
                    document.getElementById('btn-shuffle').addEventListener('click', toggleShuffle);
                    document.getElementById('btn-loop').addEventListener('click', toggleLoop);
                    document.getElementById('btn-play-selection').addEventListener('click', playSelection);

                    renderPlaylist();
                </script>
                """.replace("TRACKS_DATA", json.dumps(tracks_json))

                components.html(player_html, height=750)
                # --- FIN DU LECTEUR AUDIO COMPLET ---
