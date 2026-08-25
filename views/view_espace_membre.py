import streamlit as st
import time
import streamlit.components.v1 as components
import json
from datetime import date
from database import c, commit_and_sync
from services import safe_date

# --- Un design plus doux et apaisant pour l'espace de prière ---
st.markdown("""
<style>
    .espace-header {
        text-align: center;
        padding: 30px;
        background: linear-gradient(135deg, #e8eaf6 0%, #f3e5f5 100%);
        border-radius: 15px;
        margin-bottom: 30px;
    }
    .espace-title {
        color: #4527a0 !important;
        font-size: 2rem !important;
        margin-bottom: 10px !important;
    }
    .espace-subtitle {
        color: #6a1b9a !important;
        font-size: 1.1rem !important;
    }
</style>
""", unsafe_allow_html=True)

def show_espace_membre(matloc_membre=None):
    # --- 1. EN-TÊTE PERSONNALISÉ OU PUBLIC ---
    if matloc_membre:
        membre = c.execute("SELECT nom, prenom, nom_equipe FROM membres m JOIN equipes e ON m.equipe_id = e.id WHERE m.matloc=? AND m.statut='actif'", (matloc_membre,)).fetchone()
        if membre:
            st.markdown(f"""
            <div class="espace-header">
                <h3 class="espace-title">🙏 Bienvenue {membre[1]} {membre[0]}</h3>
                <p class="espace-subtitle">{membre[2]}</p>
                <p class="espace-subtitle" style="font-size: 0.9rem; opacity: 0.8;">Voici votre espace de ressourcement spirituel</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="espace-header">
                <h3 class="espace-title">📿 Espace de Prière</h3>
                <p class="espace-subtitle">Bienvenue dans cet espace de paix</p>
            </div>
            """, unsafe_allow_html=True)
            st.warning("Identifiant de membre inconnu. Vous voyez l'espace public.")
    else:
        st.markdown("""
        <div class="espace-header">
            <h3 class="espace-title">📿 Espace de Prière & Méditation</h3>
            <p class="espace-subtitle">Diocèse de Grand-Bassam</p>
        </div>
        """, unsafe_allow_html=True)

    # --- 2. LES ONGLETS DE CONTENU ---
    tab_priere, tab_meditation, tab_musique, tab_evenements = st.tabs([
        "🙏 Prières & Oraisons", 
        "📖 Méditations", 
        "🎵 Musique & Chants", 
        "📅 Mes prochains événements"
    ])

    with tab_priere:
        st.markdown("### 🙏 Textes de prières")
        prières = c.execute("SELECT titre, contenu_texte, image_url FROM espace_spirituel WHERE type_contenu='priere' ORDER BY date_publication DESC").fetchall()
        if not prières:
            st.info("Aucune prière publiée pour le moment.")
        else:
            for p in prières:
                with st.expander(f"📖 {p[0]}"):
                    # L'image d'illustration (celle uploadée séparément) reste en en-tête
                    # On vérifie d'abord que m contient bien au moins 3 éléments avant de lire m[2]
                    if len(p) > 2 and p[2] and p[2].startswith("http"): 
                        st.image(p[2], width="stretch")
                    
                    # MODIFICATION ICI : st.write devient st.markdown avec unsafe_allow_html=True
                    # Cela permet d'interpréter les ![](url) et les <iframe> tapés dans le texte
                    if p[1]:
                        st.markdown(p[1], unsafe_allow_html=True)

    with tab_meditation:
        st.markdown("### 📖 Textes de méditation")
        meditations = c.execute("SELECT titre, contenu_texte, image_url FROM espace_spirituel WHERE type_contenu='meditation' ORDER BY date_publication DESC").fetchall()
        if not meditations:
            st.info("Aucune méditation disponible pour le moment.")
        else:
            for m in meditations:
                with st.expander(f"📖 {m[0]}"):
                    # L'image d'illustration (celle uploadée séparément) reste en en-tête
                    if m[2] and m[2].startswith("http"): 
                        st.image(m[2], width="stretch")
                    
                    # MODIFICATION ICI : st.write devient st.markdown avec unsafe_allow_html=True
                    if m[1]:
                        st.markdown(m[1], unsafe_allow_html=True)

    with tab_musique:
        st.markdown("### 🎵 Lecteur de chants")
        audios = c.execute("SELECT titre, fichier_url FROM espace_spirituel WHERE type_contenu='audio' ORDER BY date_publication DESC").fetchall()
        
        if not audios:
            st.info("Aucun fichier audio n'a encore été ajouté.")
        else:
            tracks_json = [{"title": a[0], "url": a[1]} for a in audios if a[1] is not None and str(a[1]).startswith("http")]
            
            if not tracks_json:
                st.warning("Les URL des fichiers doivent commencer par http:// ou https://")
            else:
                player_html = """
                <div style="font-family: sans-serif; max-width: 600px; margin: auto; padding: 15px; border: 1px solid #e0e0e0; border-radius: 15px; background: #fafafa;">
                    <h3 style="text-align:center; color:#4527a0; margin-top:0;">🎵 Lecteur Spirituel</h3>
                    
                    <div id="now-playing" style="text-align:center; font-weight:bold; font-size:1.1rem; margin-bottom:10px; min-height: 30px; color:#333;">
                        Cliquez sur une piste
                    </div>
                    
                    <div style="display: flex; justify-content: center; gap: 10px; margin-bottom: 10px; flex-wrap: wrap;">
                        <button id="btn-prev" style="background:none; border:none; font-size:20px; cursor:pointer; padding:5px;">⏮️</button>
                        <button id="btn-shuffle" style="background:none; border:none; font-size:20px; cursor:pointer; opacity:0.5; padding:5px;">🔀</button>
                        <button id="btn-loop" style="background:none; border:none; font-size:20px; cursor:pointer; opacity:0.5; padding:5px;">🔁</button>
                        <button id="btn-next" style="background:none; border:none; font-size:20px; cursor:pointer; padding:5px;">⏭️</button>
                        <button id="btn-play-selection" style="background:#4527a0; color:white; border:none; font-size:14px; cursor:pointer; opacity:0.5; padding:5px 10px; border-radius:15px;">▶️ Sélection</button>
                    </div>

                    <!-- HAUTEUR RÉDUITE à 150px pour laisser de la place à la liste -->
                    <video id="audio-player" controls controlsList="nodownload" style="width: 100%; outline:none; max-height: 150px; background:black; border-radius:8px;"></video>
                    
                    <!-- LISTE : max-height augmenté à 350px pour pouvoir défiler -->
                    <ul id="playlist" style="list-style: none; padding: 0; margin-top: 15px; max-height: 350px; overflow-y: auto; border-top: 1px solid #ddd; padding-top: 10px;"></ul>
                </div>

                <script>
                    const tracks = TRACKS_DATA;
                    let currentTrackIndex = 0;
                    let isShuffled = false;
                    let loopMode = 0; // 0: Aucune, 1: Toute la playlist, 2: Piste actuelle
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
                            audio.loop = false; // Désactive la boucle native HTML
                            btnLoop.style.opacity = '0.5'; 
                            btnLoop.innerText = '🔁'; 
                        }
                        else if (loopMode === 1) { 
                            audio.loop = false; // Désactive la boucle native (on utilise nextTrack)
                            btnLoop.style.opacity = '1'; 
                            btnLoop.innerText = '🔁'; 
                        }
                        else { 
                            audio.loop = true; // LA MAGIE : Active la boucle native du lecteur HTML !
                            btnLoop.style.opacity = '1'; 
                            btnLoop.innerText = '🔂'; 
                        }
                    }

                    // Gestion de la fin de la piste (uniquement si on n'est pas en boucle native)
                    audio.addEventListener('ended', () => {
                        if (!audio.loop) {
                            nextTrack(); 
                        }
                    });

                    // Liaison des boutons
                    document.getElementById('btn-prev').addEventListener('click', prevTrack);
                    document.getElementById('btn-next').addEventListener('click', nextTrack);
                    document.getElementById('btn-shuffle').addEventListener('click', toggleShuffle);
                    document.getElementById('btn-loop').addEventListener('click', toggleLoop);
                    document.getElementById('btn-play-selection').addEventListener('click', playSelection);

                    renderPlaylist();
                </script>
                """.replace("TRACKS_DATA", json.dumps(tracks_json))

                # HAUTEUR AUGMENTÉE À 750 pour tout voir et pouvoir défiler !
                components.html(player_html, height=750)


    with tab_evenements:
        st.markdown("### 📅 Événements à venir")
        if matloc_membre:
            membre = c.execute("SELECT id, nom, prenom FROM membres WHERE matloc=? AND statut='actif'", (matloc_membre,)).fetchone()
            
            if not membre:
                st.warning("Identifiant de membre introuvable.")
            else:
                # --- 1. LE FORMULAIRE DE RÉPONSE ---
                if 'repondre_event_id' in st.session_state:
                    evt_id = st.session_state['repondre_event_id']
                    evt = c.execute("SELECT type_evenement, date_evenement, lieu FROM evenements WHERE id=?", (evt_id,)).fetchone()
                    
                    if evt:
                        date_evt = safe_date(evt[1])
                        st.info(f"Vous répondez pour : **{evt[0]}** du {date_evt.strftime('%d/%m/%Y') if date_evt else '?'}")
                        
                        deja_repondu = c.execute("SELECT statut FROM suivi_presences WHERE membre_id=? AND evenement_id=?", (membre[0], evt_id)).fetchone()
                        index_defaut = 0
                        if deja_repondu and deja_repondu[0] == 'spirituel': 
                            index_defaut = 1

                        choix = st.radio(
                            "Votre engagement :", 
                            ["physique", "spirituel"], 
                            format_func=lambda x: {"physique": "🟢 Je serai présent physiquement", "spirituel": "🟡 Je prierai de chez moi (Spirituel)"}[x],
                            index=index_defaut,
                            horizontal=True
                        )

                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("✅ Confirmer ma réponse", type="primary", width="stretch"):
                                if deja_repondu:
                                    c.execute("UPDATE suivi_presences SET statut=? WHERE membre_id=? AND evenement_id=?", (choix, membre[0], evt_id))
                                else:
                                    c.execute("INSERT INTO suivi_presences (membre_id, evenement_id, statut) VALUES (?, ?, ?)", (membre[0], evt_id, choix))
                                commit_and_sync()
                                del st.session_state['repondre_event_id']
                                if choix == "physique": st.balloons()
                                else: st.snow()
                                st.success("Merci pour votre réponse ! 🙏")
                                                                
                                time.sleep(3.5) # <-- MAGIE ICI : On laisse le temps à l'animation
                                st.rerun()
                        with col2:
                            if st.button("❌ Annuler", width="stretch"):
                                del st.session_state['repondre_event_id']
                                st.rerun()
                                
                        st.markdown("---")

                # --- 2. LA LISTE DES ÉVÉNEMENTS ---
                evenements = c.execute('''
                    SELECT e.id, e.date_evenement, e.type_evenement, e.lieu 
                    FROM evenements e 
                    JOIN evenement_equipes ee ON e.id = ee.evenement_id 
                    JOIN membres m ON ee.equipe_id = m.equipe_id 
                    WHERE m.matloc = ? AND e.date_evenement >= ?
                    ORDER BY e.date_evenement ASC LIMIT 5
                ''', (matloc_membre, date.today().isoformat())).fetchall()
                
                if not evenements:
                    st.success("✅ Aucun événement à venir. Profitez de ce temps de repos !")
                else:
                    for ev in evenements:
                        ev_date = safe_date(ev[1])
                        if not ev_date: continue
                        
                        delta = (ev_date - date.today()).days
                        if delta == 0: delai = "🔴 Aujourd'hui !"
                        elif delta == 1: delai = "🟠 Demain"
                        elif delta <= 7: delai = f"🟡 Dans {delta} jours"
                        else: delai = f"🟢 Dans {delta} jours"
                        
                        icone = {"Prière mensuelle": "🧎", "Prière commune": "🙏", "Prière spéciale": "✨", "Pèlerinage": "🚶‍♂️", "Réunion": "🤝"}.get(ev[2], "📅")
                        
                        st.markdown(f"""
                        <div style="background: white; padding: 15px; border-radius: 10px; border-left: 5px solid #4527a0; margin-bottom: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.05);">
                            <b>{icone} {ev[2]}</b><br>
                            📅 {ev_date.strftime('%d/%m/%Y')} ({delai})<br>
                            📍 {ev[3] or 'Lieu à définir'}
                        </div>
                        """, unsafe_allow_html=True)
                        
                        if st.button("✍️ Confirmer ma présence pour cet événement", key=f"rep_{ev[0]}"):
                            st.session_state['repondre_event_id'] = ev[0]
                            st.rerun()
                            
        else:
            st.info("Connectez-vous avec votre lien personnel (contenant votre numéro MatLoc) pour voir vos prochains événements ici.")
