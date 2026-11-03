# 📿 Gestionnaire des Équipes du Rosaire — Diocèse de Grand-Bassam

Application **Streamlit** de gestion administrative, spirituelle et missionnaire
des Équipes du Rosaire : paroisses, équipes, membres, abonnements, présences,
agenda, espace spirituel (prières, méditations, musiques, thème pastoral,
rosaire quotidien) et canal de communication avec validation diocésaine.

---

## 🗂️ Structure du projet

```
app.py                              # Point d'entrée : connexion, sessions, routage des rôles
database.py                         # Connexion (Turso ou SQLite locale), schéma, migrations
services.py                         # Sécurité, médias, Telegram, sessions, export Excel, stats
components.py                       # Composants partagés : agenda, WhatsApp, QR, thème pastoral…
mysteres.py                         # Les 20 mystères du Rosaire + calcul de la dizaine du jour
views/
    __init__.py
    view_diocese.py                 # Administration diocèse (12 rubriques)
    view_paroisse.py                # Administration paroisse (équipes, membres, abonnements)
    view_equipe.py                  # Espace responsable d'équipe
    view_communication.py           # Cellule Communication : préparation & soumission
    view_communication_validation.py # SAS diocèse : validation & publication
    view_espace_membre.py           # Espace communautaire public + espace membre (QR matloc)
    livret_thematique.py            # Données du livret de méditation du mois du Rosaire
images/                             # logo.png (livré — chapelet doré, remplaçable par le logo officiel, même nom)
photos/                             # Photos locales (si pas de Cloudinary)
```

## 🚀 Lancer en local

```bash
pip install -r requirements.txt
streamlit run app.py
```

Première connexion : utilisateur **diocese**, mot de passe **admin123**
(changez-le immédiatement via l'écran de connexion si `RESET_TOKEN` est
configuré, ou directement en base).

## 🔑 Configuration (facultative)

Copiez `.streamlit/secrets.toml.example` vers `.streamlit/secrets.toml` et
renseignez ce dont vous disposez :

| Clé | Utilité | Sans cette clé |
|-----|---------|----------------|
| `TURSO_URL` + `TURSO_AUTH_TOKEN` | Base Turso (multi-utilisateurs temps réel) | SQLite locale `gestion_religieuse.db` |
| `RESET_TOKEN` | Encart « mot de passe oublié » sur l'écran de connexion | Encart masqué |
| `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` | Notifications (soumissions, publications, évènements) | Notifications ignorées |
| `CLOUDINARY_*` | Hébergement des photos / PDF / audio / vidéo | Champs « lien imgbb » à utiliser |

## ☁️ Déployer sur Streamlit Cloud

1. Poussez ce dossier dans un dépôt GitHub.
2. Sur https://share.streamlit.io → **New app** → sélectionnez le dépôt,
   fichier principal : `app.py`.
3. Menu de l'app → **Settings → Secrets** → collez le contenu de votre
   `secrets.toml` (au minimum les clés Turso en production).
4. Le fichier `requirements.txt` installe automatiquement les dépendances.

## 👥 Rôles et comptes

| Rôle | Créé | Accède à |
|------|------|----------|
| `diocese` | Automatique au premier lancement | Administration complète (12 rubriques) |
| `paroisse` | À la création d'une paroisse (rubrique « 🏘️ Créer paroisses ») | Équipes, membres, abonnements, agenda de sa paroisse |
| `equipe` | À la création d'une équipe par la paroisse | Son équipe : membres, présences, agenda, WhatsApp |
| `communication` | Rubrique « 🔐 Gérer les accès » du diocèse (section 📡 Service Communication) | Canal de soumission — tout passe par le SAS diocèse |

Les identifiants `paroisse_*` sont affichés à la création et expédiables
par WhatsApp en un clic ; les mots de passe peuvent être réinitialisés dans
« 🔐 Gérer les accès ».

## 🕊️ Espace communautaire (public)

URL : `https://VOTRE-APP.streamlit.app/?espace=1`

- Quatre rubriques publiques : Actualités, Rosaire, Thème, Archives.
- **Dizaine du jour** : le visiteur saisit son jour de naissance → l'app
  calcule le(s) mystère(s) du jour (portage fidèle de la règle Android).
- **QR paroissiaux signés** : `?espace=1&p=ID_PAROISSE` — compte les visites
  par paroisse d'origine (rubrique « 📋 Gérer paroisses » → QR de la paroisse).
- **Espace membre** : `?espace=1&matloc=MATLOC` — le MatLoc du membre
  (imprimé sur ses fiches/QR) débloque « Mes évènements », Réponses de
  Communion, le feuillet mensuel en équipe et la dizaine personnalisée.
- **📰 Actualités de la Paroisse (v7.8.6)** : dans le fil d'actualité, un
  visiteur arrivé via le QR d'une paroisse (ou un membre de cette paroisse)
  voit les prochains évènements créés par les équipes de SA paroisse (et par
  la paroisse elle-même). Périmètre strict : jamais au-delà — un évènement
  d'équipe n'apparaît ni pour les autres paroisses, ni pour le visiteur sans
  contexte paroissial. La Réponse de Communion reste dans « 📅 Mes
  évènements » côté membre ; le Coin Affiche applique le même filtre.

## 📖 Le feuillet mensuel de prière (v7.8)

La zone « 📅 Sous-thème du mois » de la page 🕯️ Thème → Vue d'ensemble est
remplacée par le **feuillet mensuel de prière** :

- **Vitrine** : badge « 📖 LE FEUILLET MENSUEL DE PRIÈRE N° X » (N° = rang du
  mois pastoral : septembre = N°1 … août = N°12), « Mois de … », Sommaire du
  feuillet, bouton **« 📖 Ouvrir le livret »**.
- **Livret en autonomie** : comme la dizaine du jour, le livret s'ouvre en
  plein écran — entête réduite au logo + carte de l'espace (Membre /
  Communautaire), sans bandes défilantes ni thème de l'année. Le titre de la
  page reste toujours visible en haut (barre fixe), la pagination seule
  (« Page X / N ») clôt chaque page sous un trait fin.
- **Soumission (v7.8.6)** : après la saisie des sections (Service
  Communication → 🕯️ Thème pastoral → 2️⃣ bis), le bouton **« 📨 Soumettre le
  feuillet au diocèse »** envoie le feuillet au SAS (« 🕊️ Soumissions du
  Service Communication » → « 🟡 En attente de validation »). Le Service
  Communication ne publie JAMAIS d'elle-même ; la resoumission reste
  possible (mise à jour de l'alerte).
- **Saisie unique (v7.8.7)** : les rubriques invariables d'un mois à
  l'autre (Salve Regina, Prière à l'Esprit-Saint, Invocation à Marie…)
  ne se saisissent qu'UNE fois. Pour un nouveau mois, la section vide
  affiche **« ♻️ Reprendre le texte du mois précédent »** : un clic recopie
  la dernière saisie connue de cette rubrique (mois précédents, années
  antérieures). Le texte est ensuite ajustable avant enregistrement.
- **Publication (diocèse seul)** : au SAS, le diocèse relit l'aperçu
  (mois pastoral + sections saisies) puis **« ✅ Publier »** déclenche
  l'alerte « 📖 Nouveau feuillet » en tête du fil d'actualité (visible
  45 jours, masquable via « 📌 Marquer comme lue »). Le clic sur l'alerte
  ouvre directement le livret du feuillet annoncé.
- **Publication programmée (v7.8.8 — tous types de soumission)** : dans
  chaque soumission en attente, le diocèse peut choisir **« 🗓️ Programmer
  la publication »** (date + heure) au lieu de « ✅ Publier ». Le contenu
  reste invisible jusqu'à l'échéance, puis est publié automatiquement :
  chaque chargement de page sert de réveil (lazy cron, Abidjan = UTC).
  Zone « 🗓️ Programmées » au SAS (avec ▶️ Publier maintenant / ↩️ Revenir
  en attente) ; le Journal et le bloc feuillet affichent l'échéance.
- **Retour en haut de page (v7.8.2)** : à chaque tour de page (Suivant,
  Précédent, choix dans le Sommaire), la lecture reprend automatiquement en
  haut — le titre est visible sans scroller.
- **Archives (v7.8.2)** : les feuillets précédents sont archivés dans
  🕯️ Thème → 🔭 Vue d'ensemble, sous forme d'**expanders** (« 📚 Les
  feuillets précédents ») ; le lien « 📖 Relire ce feuillet » de chaque
  expander rouvre le livret en autonomie via `?flt=1&fa=ANNÉE&fm=MOIS`.

## 🎧 Lecteur compagnon — la musique suit la prière (v7.8.9)

Avant v7.8.9, le bouton « 🎧 Ouvrir l'onglet d'écoute dédié » ouvrait un
deuxième onglet : pratique sur PC, presque inutilisable sur téléphone (on ne
revient pas aisément à l'appli). Le lecteur compagnon corrige cela :

- **Téléphone (≤ 820 px)** : le bouton devient **« 🎧 Écouter en priant »** et
  navigue dans le MÊME onglet. La page d'écoute porte une barre dorée
  **« ◀️ Revenir à l'appli »** : un tap ramène à l'Espace de Prière.
- **Mini-barre compagnon** : dès qu'une musique a été lancée, une barre
  flottante (▶️/⏸️, titre, ⏭️) apparaît en bas de TOUTES les pages de
  l'espace — accueil, 📿 Rosaire chez les Équipiers, livret, archives — et
  **reprend automatiquement la musique là où elle s'était arrêtée**
  (mémoire `sessionStorage` de l'onglet ; oubli automatique après 2 h).
  La playlist continue même en passant d'une page à l'autre.
- **PC** : le bouton dédié ouvre une **fenêtre/onglet compagnon nommé**
  « rosaire_ecoute », réutilisé à chaque clic (jamais dupliqué) ; la page
  d'écoute y affiche l'astuce « réduisez la fenêtre » à la place du bouton
  Revenir.
- **Contrôles système** : la piste en cours est déclarée à l'API Media
  Session — titre + ⏮️ ⏯️ ⏭️ sur l'écran verrouillé et dans les
  notifications (Android/iPhone), sans rouvrir l'appli.
- **📺 Vignette flottante** (Picture-in-Picture) sur les lecteurs, quand le
  navigateur le permet : la vignette reste au-dessus des autres onglets.
- **Correctif sanitizeur** : Streamlit 1.66 injecte `target="_blank"` +
  `rel="noopener"` dans toutes les ancres de `st.markdown` ; le fixer
  `_fixer_liens_ecoute` rétablit `_self`/le nom de fenêtre en JS après
  rendu (motif éprouvé `_liens_meme_onglet` v7.8.1) — sans lui, chaque clic
  ouvrait un nouvel onglet et la mémoire de lecture se perdait.

## 🎨 Couverture du livret & corrections facilitées (v7.8.10)

- **Couverture du livret** : le feuillet mensuel a désormais une vraie
  couverture, du même style que la couverture de la dizaine (bleu nuit +
  or). Elle accompagne **① l'alerte « 📖 Nouveau feuillet »** du fil
  d'actualité (mention « 🔔 Nouveau · publié le … » intégrée) et **② le
  livret lui-même** : le sommaire s'ouvre sous la couverture, comme un
  livret papier (couverture → sommaire → pages). La couverture affiche le
  N° du feuillet, le mois pastoral, et le thème de l'année pastorale.
- **Couverture personnalisée (facultatif)** : Service Communication →
  🕯️ Thème pastoral → 2️⃣ bis → expander **« 🎨 Couverture du livret »** :
  collez le lien imgbb de la couverture scannée du feuillet ; elle est
  montrée au-dessus de la carte (alerte + sommaire). Sans image, la
  couverture générée automatiquement suffit. Table `feuillets_couvertures`
  (une image par mois pastoral, écrasable à volonté).
- **Corrections facilitées** : chaque triplet (année, mois, section) a ses
  propres clés de widget. Sélectionner une rubrique au vert ✅ (ex.
  « 5. Prière à l'Esprit-Saint ») affiche IMMÉDIATEMENT son titre ET son
  texte enregistré — fini les champs vides qui obligeaient à reprendre
  toute la procédure. Le bouton ♻️ purge les clés contextuelles : le texte
  repris s'affiche après le rerun.
- **Republication d'une version corrigée** : après publication, le bloc
  soumission ne disparaît plus (les `elif` court-circuités retiraient le
  bouton) : un bouton **« 📨 Soumettre une version corrigée au diocèse »**
  apparaît. La validation du diocèse met à jour `date_publication` —
  l'alerte du fil se rafraîchit (nouvelle date) et la communauté lit le
  livret corrigé. Idem après un refus : le bouton de soumission revient.
- **Ouvrir le livret à la couverture** : depuis la vitrine (Vue
  d'ensemble), le bouton « 📖 Ouvrir le livret » atterrit sur la couverture.
  Depuis l'alerte, le clic ouvre toujours directement la lecture (la
  couverture vient d'être vue dans l'alerte).

## ✒️ Mise en page du livret, photos placées, alerte fiabilisée (v7.8.11)

- **Typographie du feuillet (comme le livret papier)** — les pages du livret
  sont mises en page automatiquement (`_mise_en_page_feuillet`) :
  ① les marqueurs **R. / T. / 1. / 2. / 3+T.** (suivis de `.`, `:` ou `—`)
  sont en gras ; ② le texte des réponses **T. / 3+T.** est entièrement en
  gras (y compris les vers qui suivent, jusqu'à la ligne vide) ; ③ la
  section **« 7. À l'écoute de la Parole de Dieu »** est tout en gras
  SAUF le titre du passage (Évangile…, Au Livre des Psaumes…, Lecture… —
  rendu en italique centré) ; ④ la section **« 11. Salve Regina »** est
  tout en gras ; ⑤ un **interligne** plus généreux sépare deux marqueurs ;
  ⑥ dans **« 4. Célébrons en équipe »**, la légende des rôles
  (R — Responsable… / 1 — 1er lecteur · 2 — 2e lecteur · 3 — Chantre ·
  T — Tous ensemble) est en gras et la ligne **« Accueil »** devient une
  puce soulignée de taille sous-titre ; ⑦ les **titres de rubrique** sont
  écrits en police manuscrite (Caveat via Google Fonts ; repli local
  Segoe Print / Comic Sans MS si hors-ligne) ; ⑧ la barre fixe du livret
  suit le même style.
- **Cadre photo sous chaque titre de section** : chaque page porte un cadre
  façon photo papier (image encadrée, bordure or) ou, à défaut d'image, un
  emplacement pointillé « 📷 Photo de la rubrique » — comme un livret à
  illustrer.
- **Position de la photo (demande n°3)** : dans la saisie d'une section
  (2️⃣ bis), un menu **« 🖼️ Position de la photo dans le livret »** propose
  ⬆️ au-dessus du texte (centrée, défaut), ▶️ à droite ou ◀️ à gauche — la
  photo flotte alors dans la page et le texte l'habille (empilement
  automatique sur mobile). Colonne `feuillet_sections.pos_image`
  (migration idempotente). Le bouton ♻️ reprend aussi la position.
- **Photos du fil du jour** : à la soumission d'une Prière/Méditation, un
  menu « Position de la photo » permet droite/gauche — le préfixe
  `[droite]`/`[gauche]` du lien est interprété à l'affichage : l'image
  flotte DANS la carte « Prière/Méditation du jour ». Sans préfixe,
  l'image reste centrée au-dessus (comportement initial). Dans les
  expanders (Actualités, etc.), le préfixe est simplement nettoyé.
- **Alerte fiabilisée (demande n°2)** : l'alerte « 🔔 Nouveau feuillet »
  annonce désormais le **dernier mois pastoral publié récemment** (et non
  la dernière publication en date) : republier le feuillet de septembre
  après celui d'octobre ne renvoie plus l'alerte sur septembre — la
  couverture personnalisée d'octobre s'affiche bien dans l'alerte. Une
  publication à date illisible est annoncée sans mention de date
  (auto-réparation) ; hors délai de 45 jours, pas d'alerte.
- **Publications de feuillets blindées** : la publication (et la
  republication d'une version corrigée) passe par UPDATE puis INSERT —
  robuste même si la base ancienne n'a pas la contrainte UNIQUE ; une
  migration dédoublonne `feuillets_publications` et pose l'index unique
  `(annee_debut, mois)` (fini les lignes jumelles qui embrouillaient
  l'alerte).

## 🟡 État de publication affiché — fin du mystère « alerte bloquée » (v7.8.12)

- **Le constat** : la couverture d'octobre apparaissait au sommaire du
  livret mais l'alerte 🔔 restait sur septembre. Cause établie (base en
  main) : **octobre n'avait jamais traversé le circuit SAS** — aucune
  soumission « 📨 » pour ce mois, donc pas de ligne dans
  `feuillets_publications`. Le test « de bout en bout » du 18/10 portait
  sur la version corrigée de SEPTEMBRE (les seules soumissions de
  feuillet de l'historique). Et la couverture personnalisée enregistrée
  l'avait été pour septembre aussi (mois resté dans le sélecteur).
  L'alerte était donc **conforme au principe SAS** : elle annonce le
  dernier mois PUBLIÉ par le diocèse.
- **Le malentendu** : l'URL de test `?flt=1&fa=2026&fm=2` (lien profond)
  ouvre le livret d'octobre même non publié — la vitrine aussi dès qu'une
  section est saisie. On croyait donc le mois « publié » sans l'être.
- **Correctifs (transparence d'état)** :
  ① la **vitrine** du feuillet affiche un bandeau « 🟡 Livret en
  préparation » quand le mois affiché n'a pas de publication diocèse
  (avec rappel du dernier mois réellement publié) ;
  ② l'expander **« 🎨 Couverture du livret »** (2️⃣ bis) affiche
  désormais le **mois ciblé** (« 🖼️ Mois ciblé : N° 2 · Octobre 2026 »)
  et un avertissement si ce mois n'est pas encore publié — la couverture
  accompagnera l'alerte après validation diocèse.
- **Pour faire basculer l'alerte sur octobre** : 2️⃣ bis → sélectionner
  Octobre 2026 → enregistrer la couverture (mois ciblé affiché) →
  « 📨 Soumettre le feuillet au diocèse » → côté diocèse « ✅ Valider » →
  l'alerte 🔔 passe automatiquement à octobre avec sa couverture.

## 📿🔑 2 icônes PWA · intentions aux équipes · photos nouvelle mise en page (v7.8.14)

### 1. Deux icônes d'application — l'icône Streamlit a disparu des deux côtés
- **📿 « Rosaire — Espaces de prière »** : ouverte via `?espace=…` (Membre,
  Communautaire) ou la page Réponse de Communion (`?e=…`).
- **🔑 « Rosaire — Administration »** : connexion + rôles diocèse / paroisse /
  équipe / communication.
- L'échange est **automatique selon la partie ouverte** : le favicon de
  l'onglet, l'icône « Ajouter à l'écran d'accueil » (manifeste PWA) et
  l'apple-touch-icon sont injectés à chaque chargement
  (`components.injecter_icone_pwa`), le manifeste pointant l'icône
  correspondante. Les icônes (chapelet doré / clé dorée, fond bleu nuit
  liseré or) vivent dans **`static/`** (4 tailles chacune + 2 manifestes).
- **Indispensable** : `.streamlit/config.toml` contient désormais
  `server.enableStaticServing = true` (sinon `/app/static/…` renvoie du HTML).

### 2. « 🙏 Vos intentions à une équipe » — le circuit complet
- **Espace de Prière** (public ET membre) : la rubrique se présente dans le
  langage du dépliant (bannière bleu-or « Un jour, une dizaine ») **juste
  avant « 📰 Actualités de la Paroisse »** : choix de l'équipe (pré-sélection
  de l'équipe du membre), texte (600 car. max), anonymat possible → la
  table `intentions_equipes` reçoit l'intention, le flash confirme.
- **Gestionnaire → « 📌 Suivi et Agenda - Équipe X »** : le 4ᵉ onglet
  « 🙏 Vos intentions à une équipe » est la boîte de réception du
  responsable — compteur (🆕 Reçues / 🕊️ En prière / 🗄️ Archivées),
  🕊️ **Prise en prière**, 🗄️ **Archiver** (archivés consultables, supprimables),
  et principe **« être une tombe »** rappelé en tête.

### 3. Photos du livret — la nouvelle mise en page (remplace le centrage)
- **a. Bande du titre** : la page ouvre sur une bande — titre manuscrit sur
  les **¾ à gauche**, photo sur le **quart à l'extrême droite** ; sans photo,
  emplacement pointillé 📷.
- **b. Photos du corps** : **2 maximum**, chacune en 🡕 haut droite /
  🡖 haut gauche / 🡘 bas droite / 🡗 bas gauche (~¼ de page, texte habillé,
  **proportions d'origine** — aucun rognage). Schéma : `image_titre`,
  `image_url2`, `pos_image2` (migration douce automatique).
- **Couverture non rognée** : l'image de couverture s'affiche telle quelle
  (proportions d'origine, bornée à 420 px de haut).

### 4. A− / A+ en haut du livret
Deux mini-boutons très petits règlent la taille du texte de **90 % à 150 %**
(pas de 10), mémorisés pour la session (légende « 🔍 Taille du texte : N % »).

### 5. Fin de la défaillance « retour à l'onglet primaire »
Les onglets Streamlit n'ont **aucune mémoire** : chaque coche ou bouton
(« 💾 Enregistrer la couverture », « 📨 Soumettre », année des rappels…)
ramenait au 1er onglet. Tous les blocs à interaction sont remplacés par des
**sélecteurs persistants** (st.radio avec clé de session) : 📡 Service
Communication, 📌 Suivi et Agenda (équipe, paroisse, diocèse), 💬 WhatsApp.

### 6. Correction au passage
Le rappel ♻️ « Reprendre le texte du mois précédent » affichait la valeur de
`pos_image` à la place de l'année (indice 4 au lieu de 5) — corrigé.

## 🙏 Intentions : Espace communautaire + cadre doré (v7.8.15)

### 1. « 🙏 Vos intentions à une équipe » réservée à l'Espace communautaire
Le bloc n'apparaît **plus côté Membre** (vue `matloc`) : il est présenté
UNIQUEMENT dans l'Espace communautaire de la paroisse (`?p=…` / QR paroissial),
juste avant « 📰 Actualités de la Paroisse ». Côté code, `_render_fil_actualites`
gagne un paramètre `intentions=True` — l'appel de la vue Membre passe
`intentions=False`.

### 2. Le bloc « comme le dépliant » — un seul cadre doré
- **Cadre or** (bordure 2 px #FFD700, fond bleu nuit #121a45, coins arrondis,
  ombre) englobant **tout** : bannière, badge, expanseur, champs, cases, bouton.
- **Bannière** (dégradé #1A237E→#4527a0, titre Georgia doré) :
  « 🙏 Vos intentions à une équipe » + **« Confie à Notre Dame du Rosaire ton
  intention de prière par le canal d'une équipe »** + badge 🤫 « être une tombe ».
- **👥 Choix de l'équipe** : expanseur au liseré or ; après clic, son titre
  affiche le choix (« … — Équipe Espérance ») et le choix est mémorisé.
- **Champs à liséré doré** (#C9A227 sur fond #0d1338) : **Nom et Prénom\***,
  **Contact WhatsApp / Adresse mail\***, **Intention de prière\*** (600 car.),
  précédés de « * » indique les champs obligatoires.
- **☑ Case obligatoire** : « En envoyant cette intention, j'accepte que
  certaines données techniques soient utilisées à des fins de sécurité et de
  lutte contre les envois automatisés (spam) » + expanseur **🔒 Politique de
  confidentialité**.
- Soumission validée champ par champ (message « Il manque : … »), champs vidés
  après succès **sans perdre la saisie** en cas de refus (clés par génération).

### 3. Côté responsable — le contact arrive avec l'intention
- La table `intentions_equipes` gagne la colonne `auteur_contact`
  (migration douce automatique).
- Dans « 📌 Suivi et Agenda » → onglet « 🙏 Vos intentions à une équipe » :
  chaque carte affiche **📞 Contact : …** sauf si 🕊️ anonyme (le nom devient
  « Anonyme » et le contact est masqué). Compteurs, Prise en prière, Archiver
  et principe « être une tombe » inchangés.

### 4. Techniquement
Le cadre doré est posé par un mini-script (même mécanisme que
`injecter_icone_pwa`) qui ajoute la classe `.int-cadre-or` au container bordé
`st.container(border=True)` — le CSS par classe ne touche donc que ce bloc,
quel que soit le thème ou la version de Streamlit.

### 5. PWA — guide pas à pas
La réalisation des 2 icônes (📿 Espaces / 🔑 Administration) est documentée
pas à pas dans **`GUIDE_PWA_v7.8.15.md`** : ce qui est déjà dans le ZIP, la
vérification sur ordinateur (F12 → Application → Manifest), l'installation
Android/iPhone, le dépannage (cache, HTTPS, réinstallation) et le remplacement
des icônes par vos dessins.

## ☁️ Hotfix fiabilité Streamlit Cloud / Turso (v7.8.16)

Correctif des trois incidents observés dans les journaux Cloud, **après un
déploiement réussi, tout se répare tout seul au premier démarrage** :

### 1. La base distante se répare automatiquement
Sur la base Turso créée par une version antérieure, la table
`intentions_equipes` existait **sans** les colonnes récentes
(`anonyme`, `auteur_contact`) → la soumission plantait
(« table intentions_equipes has no column named anonyme »). Désormais :
- `database.py` crée la table à l'init et y applique 2 `safe_migrate`
  idempotents (ils s'exécutent à chaque démarrage sans risque) ;
- `_assurer_table_intentions` (vue membre) et
  `_assurer_table_intentions_eq` (vue équipe) ajoutent elles aussi les
  colonnes manquantes par `ALTER TABLE` doux — **sans toucher aux données**.

### 2. Les micro-coupures Turso ne font plus planter les pages
L'erreur Hrana « connection closed before message completed » (et les
erreurs http / timeout transitoires) est désormais **rattrapée** : 3
tentatives espacées d'une seconde avec reconnexion, puis seulement
l'erreur remonte. La mini-barre musicale (mini-lecteur), purement
décorative, s'escamote si la base ne répond pas — la page de l'Espace de
Prière s'affiche quand même.

### 3. Fin des avertissements « Please replace st.components.v1.html with st.iframe »
Nouveau module **`stcompat.py`** (à la racine de `app/`) : TOUT le rendu
HTML/JS (injection PWA, scripts de mesure, lecteurs, cadre doré) passe par
`comp_html()` — `st.iframe` sur Streamlit récent (hauteur bornée à 1 px
pour les scripts invisibles), repli automatique `components.v1.html` sur
les anciennes versions. Les journaux Cloud redeviennent silencieux.

### 4. La soumission d'intention est blindée
Si l'envoi échoue malgré les tentatives (réseau), un **message doux** invite
à réessayer et la saisie est **conservée** — plus jamais de traceback à
l'écran du fidèle.

### 5. v7.8.17 — la boîte de réception du responsable devient infaillible
Symptôme : « Impossible de lire les intentions pour le moment. » dans
l'onglet **🙏** de « 📌 Suivi et Agenda », sans aucune trace dans les
journaux (un `except` muet). Cause : la base Cloud, créée par un brouillon
antérieur, peut manquer de **n'importe quelle** colonne de
`intentions_equipes` — la réparation v7.8.16 ne couvrait que deux d'entre
elles (très probablement `date_statut` manquait aussi). Correctif :
- **`database.verifier_reparer_intentions()`** — appelée par les 2 vues
  avant toute lecture/écriture : sonde de lecture complète ; en cas d'échec,
  ALTER doux de **chaque** colonne attendue puis re-sonde ; si ça échoue
  encore, **reconnexion** de la base (cache de statements périmé) et
  nouvelle sonde ; chaque incident est **journalisé** ;
- l'onglet équipe journalise l'erreur réelle et explique quoi faire.

### 6. v7.9.0 — LA CHAÎNE DE PRIÈRE UNIVERSELLE 🔗
L'idée : **faire dire une dizaine au visiteur qui dépose une intention** —
celui qui confie devient « le prochain » de celui qui prie.

- **Formulaire d'intention** (Espace communautaire) :
  - nouveau champ obligatoire **« Jour de naissance (1 - 31) »** : clé
    discrète de la chaîne — il garantit que le fidèle ne priera **jamais
    SA propre intention** (le livret écarte automatiquement les intentions
    portant le même jour de naissance que le lecteur) ;
  - la case « 🕊️ Rester anonyme » est **retirée** ; placeholders adaptés
    (« Ex : N'guess KONÉ » / « …ou nguekon@exemple.com ») ; badge
    « 🤫 Tu es le prochain de l'équipe qui prie pour toi… » ;
  - après l'envoi : bandeau **« 📿 Prier ma dizaine maintenant »** qui
    ouvre directement le livret — le fidèle participe aussitôt à la chaîne.
- **Le livret « 🕯️ Un jour, une dizaine »** : la dernière intention de
  chaque mystère (« Intention du prochain dans la chaine de prière ») est
  désormais **DYNAMIQUE** — elle porte une vraie intention confiée par un
  fidèle (idem dans le Rosaire complet de l'Espace). La chaîne ne se casse
  jamais : sans intention disponible, elle retombe sur « La Paix dans le
  monde ».
- **Nouvel onglet « 🙏 Coins des Intentions »** (4ᵉ onglet de
  « 📌 Suivi et Agenda » côté paroisse) :
  - **bilan** de toutes les intentions confiées aux équipes
    (🆕 reçues / 🕊️ prises en charge / 🗄️ archivées), détail par équipe
    avec ancienneté ;
  - règle rappelée partout : **une intention prise en charge dure au
    minimum 20 jours (20 mystères), sinon jusqu'à la prochaine prière
    mensuelle** (badge J+X/20, alerte « ✅ à archiver » à l'échéance) ;
  - **réglage de la chaîne** : 1ᵉʳ choix = les intentions **reçues** (la
    plus ancienne d'abord), 2ᵉ = les **prises en charge**, 3ᵉ = les
    **intentions universelles** (« La Paix dans le monde », « Le Sacrement
    de la réconciliation », « La gestion juste et durable de la ressource
    vitale : l'eau » — choix fixe ou rotation quotidienne) ; aperçu en
    direct de ce que lira le visiteur.
- **SAS diocèse (v7.9.0 au passage)** : les soumissions déjà publiées qui
  traînaient encore dans « 🟡 En attente de validation » sont désormais
  **détectées** (titre/type déjà présent dans la table cible) et rangées
  sans republication — section « 🧹 Déjà publiés — à ranger » ; le compteur
  d'attente redevient exact ; si le rangement d'une publication échoue
  (micro-coupure Turso), l'erreur est affichée au lieu d'un succès
  mensonger.
- Technique : colonne `jour_naissance` (migration idempotente + réparation
  v7.8.17 étendue), table `parametres` (clé/valeur) pour les réglages de
  la chaîne, fonction `intention_du_prochain()` dans `database.py`.

### 7. v7.9.1 — La chaîne prend vie : lendemain, anonyme, Galerie + 🚦
Retours de validation de la v7.9.0, tous intégrés :

- **Le modèle d'intercession** — la ligne dynamique du livret devient :
  « 🕯️ Vierge Marie, mère de Dieu, **intercède pour {Prénom - Nom du
  visiteur} : {son intention}** » ; pour une intention anonyme :
  « intercède pour **cet anonyme** : … » ; pour une intention universelle
  (3ᵉ choix) : « intercède : … » (identique dans le Rosaire complet, le
  livre page-à-page et l'aperçu paroisse).
- **La case « 🕊️ Rester anonyme » est de retour** : le responsable voit
  « Anonyme » et le contact reste masqué ; le nom devient facultatif
  (au moins l'un des deux : nom OU anonyme). Le contact est toujours
  enregistré — il porte la règle d'unicité.
- **Règle du lendemain (automatique)** : chaque intention reçue passe
  « 🕊️ Prise en charge » **au lendemain de sa réception, pour 20 jours**
  (20 mystères) — `date_statut` est datée réception + 1, le décompte
  J+X/20 ne dépend pas du moment du balayage. Le bouton 🕊️ du
  responsable garde un sens : prise en charge **immédiate** le jour même.
- **Unicité par numéro** : **un même numéro de téléphone ne peut pas
  porter 2 intentions prises en charge** — vérifié à la soumission
  (message doux, saisie conservée) ET au balayage automatique ; les
  numéros sont comparés après normalisation (espaces, tirets, indicatif
  +225 / 00 225).
- **Tirage « selon le N° méd. »** : chaque visiteur reçoit l'intention
  placée à SON rang dans la file (sa clé = jour de naissance), au sein
  d'une fenêtre de 20 jours — il retrouve la même intention à chaque
  dizaine de la période, et deux N° méd. différents portent des
  intentions différentes dès que la file le permet. La règle d'or
  (personne ne prie sa propre intention) est conservée.
- **Rectifications de textes** : « Votre intention a été confiée à
  l'Équipe … » (sans guillemets) ; CTA « 📿 À vous maintenant : égrenez
  une dizaine et porter en prière votre prochain ».
- **🖼️ Galerie +** — nouvelle rubrique des Espaces de Prière (public ET
  membre), placée après « 🕯️ Thème », avec 2 sous-rubriques :
  **🏞️ Souvenirs** (photos des évènements) et **💬 Témoignages**
  (grâces reçues). Le diocèse publie et retire depuis son nouveau menu
  « 🖼️ Galerie + » (titre, photo par lien https, date, lieu, signature) ;
  la communauté lit des cartes style dépliant.
- **🚦 Tableau de bord** — 2ᵉ onglet de « 📊 Statistiques - {paroisse} » :
  effectifs, abonnements de l'année pastorale (recouvrement), intentions
  (reçues / en prière / archivées / **20 mystères accomplis à archiver**),
  prochaine prière de l'agenda, arrivées QR paroissial (30 jours) et
  santé de chaque équipe.
- Technique : table `galerie_plus` (créée à l'init + doucement pour les
  bases distantes), `prise_en_charge_automatique()`, `contact_en_priere()`,
  `intention_du_prochain_detail()` (texte + intercédé), rubrique placée
  pour préserver les liens `?r=1` / `?r=2` existants.

### 8. v7.9.2 — La chaîne en direct : dizaines pointées, Galerie + réorganisée, programmation traçable 📿
Observations et suggestions des utilisateurs, toutes intégrées :

- **« Y a-t-il une possibilité de savoir si un membre / un visiteur fait
  sa dizaine ? » — OUI, désormais :**
  - le **pointage volontaire** « ✅ J'ai égrené ma dizaine aujourd'hui »
    apparaît sur la DERNIÈRE page du livre « 🕯️ Un jour, une dizaine » —
    il atteste d'une dizaine égrenée DANS l'application (jamais du contenu
    de la prière, qui reste personnel) ;
  - **membre** : identifié par son MatLoc — 1 pointage par jour
    (contrainte UNIQUE), avec flamme 🔥 (jours consécutifs) et total du
    mois ; **visiteur** : compté comme un « passage » anonyme (1 par
    session et par jour, sans identité exigée) ;
  - le responsable d'équipe voit dans **« 📊 Engagement spirituel »** le
    nouveau bloc **« 📿 Chaîne des dizaines — aujourd'hui »** : qui a
    pointé, qui n'a pas encore pointé, la participation de l'équipe, la
    série des 7 derniers jours ;
  - le **🚦 Tableau de bord paroisse** affiche 2 nouveaux KPI
    (« 📿 Dizaines pointées aujourd'hui » pour ses équipes + « 🔥
    Passages visiteurs ») et la santé par équipe gagne la colonne
    « 📿 Dizaines aujourd'hui » ;
  - technique : table `dizaines_journal` (créée à l'init + doucement,
    zéro action manuelle sur Cloud) et fonctions `pointer_dizaine()`,
    `stats_dizaines_jour()`, `serie_dizaines()`, `compteur_dizaines_mois()`.
- **🖼️ Galerie + réorganisée** :
  - le menu autonome du diocèse **disparaît** ;
  - la **SAISIE** rejoint un onglet « 🖼️ Galerie + » de la section
    « 📡 Communication » (à côté du SAS « 🕊️ Soumissions ») ;
  - l'**ARCHIVE après publication** devient un onglet « 🖼️ Galerie + » de
    « 📋 Contenu existant », entre « 🙏 Prières / 📖 Méditations » et
    « 🎵 Musiques » — même mécanique à coches avec confirmation, photo
    distante supprimée avec l'entrée ;
  - la rubrique communauté change de place dans l'**Espace Membre** :
    « 🖼️ Galerie + » se situe maintenant **entre « 📅 Mes évènements » et
    « 📖 Archives »** (l'Espace communautaire garde son ordre ; les liens
    `?r=1` (Thème) restent valables).
- **Publications programmées — fiabilisées et TRANSPARENTES** (signalement
  « des publications programmées publiées avant l'échéance ») :
  - le réveil automatique est **testé sain** (une soumission programmée
    dans 5 jours n'est PAS publiée) ; il est en plus **blindé** :
    double protection temporelle (filtre SQL + re-parsing Python — un
    format de date inattendu n'est JAMAIS publié), **réclamation
    anti-course** (deux sessions ouvertes en même temps ne publient
    chacune leur copie), **auto-réparation** après 10 min d'une
    réclamation bloquée par un crash, et plus aucune exception ne peut
    casser une page ;
  - **traçabilité totale** : chaque publication enregistre
    `date_decision` + `auteur_decision` ; « 📔 Historique des décisions »
    affiche désormais « publiée le {date} · 👤 diocèse — clic « ✅
    Publier » » ou « · ⏰ publication automatique — programmation
    respectée » — impossible de confondre un clic et une échéance ;
  - **UX anti-erreur** : résumé LIVE avant de programmer (« → Résumé :
    publication le 27/10/2026 à 23:59 (dans 5 jour(s)) »), mention
    explicite que « ✅ Publier » reste une publication immédiate, flash
    enrichi, compte à rebours « ⏳ dans 5 j 14 h » sur chaque élément de
    « 🗓️ Programmées ».

### 9. v7.9.3 — Accueil harmonisé, pied de page, pointage « Terminer », réserve des N° méd. 🔒
Retours de validation v7.9.2, tous intégrés :

- **Accueil harmonisé (le fil d'actualité allégé)** :
  - « 🙏 Vos intentions à une équipe » **remonte** : elle quitte le fil
    d'actualité et se place juste après le dépliant, **AVANT « 🕯️ Un
    jour, une dizaine »**, dont elle reprend EXACTEMENT le langage
    visuel (dégradé #1A237E→#283593, liseré or 2 px, titre Georgia) —
    un Accueil homogène : dépliant → intentions → dizaine ;
  - le fil d'actualité est **allégé à UNE section**, celle qui correspond
    à nos attentes : la **prière/méditation du jour** (couronnée de
    l'alerte feuillet). Le 📣 Coin Affiche, « 📰 Actualités de la
    Paroisse » et « 📰 Actualités du diocèse » quittent l'Accueil (code
    conservé : repassez `FIL_ALLEGEE = False` dans
    `views/view_espace_membre.py` pour réafficher l'ancien fil) ;
  - le texte du dépliant suit le nouvel ordre (« Juste en dessous :
    confiez votre intention… puis entrez dans la dizaine »).
- **Pied de page du site + « 🔒 Politique de confidentialité »** :
  - un **pied de page** apparaît sur TOUTES les pages des Espaces de
    Prière (communautaire, membre, livre ouvert) : signature du
    Mouvement + la politique de confidentialité complète en encart
    repliable (données recueillies / usage / vos droits) ;
  - l'expander RGPD du formulaire des intentions reste en place (le
    consentement doit être informé sur place).
- **« ✕ Terminer » pointe la dizaine — cause incognito** :
  - chaque mystère a sa fin (page GLORIA PATRI) : un bouton « ✕
    Terminer » y figure désormais À CÔTÉ de « Suivant ▶ » ; **en
    cliquant dessus, il est pointé** — sans demander qui prie (membre :
    1 pointage/jour par MatLoc ; visiteur : un passage anonyme) — puis
    le livre se referme ;
  - le pointage explicite « ✅ J'ai égrené ma dizaine aujourd'hui »
    s'affiche maintenant sur la VRAIE dernière page, chaque jour (le
    livre du jour ne contient qu'UN mystère : la fin est la page
    Gloria, l'outro « Salve Regina » n'existe que le jour du mystère
    N° 20) ;
  - les responsables le voient : la légende du bloc « 📿 Chaîne des
    dizaines » mentionne les deux boutons.
- **📚 La réserve d'intentions — 20 intentions par N° méd.** :
  - « Les visiteurs du jour reçoivent les intentions de leurs prochains
    selon leurs N° méd. et méditent sur 20 jours : il est capital d'avoir
    AU PRÉALABLE 20 intentions pour chacun des N° méd. Ça sera l'affaire
    des responsables d'équipe et paroissial. » — c'est fait ;
  - nouvelle table **`intentions_reserve`** (N° méd. 1-20, texte,
    auteur, équipe, paroisse, date) créée à l'init ET doucement — zéro
    action manuelle sur Cloud ;
  - **côté responsable d'équipe** (onglet « 🙏 Vos intentions à une
    équipe ») et **côté responsable paroissial** (onglet « 🙏 Coins des
    Intentions ») : une **grille des 20 emplacements** (X/20, or quand
    l'objectif est atteint), le formulaire **« ➕ Ajouter une intention à
    la réserve »** (membre choisi → son N° méd. désigne l'emplacement et
    son nom signe l'intention), la liste des lignes posées avec retrait
    🗑️, et la confirmation flash ;
  - **la chaîne puise d'abord dans la réserve** : un visiteur dont le
    N° méd. correspond à un emplacement nourri reçoit une intention de
    CETTE réserve (rotation à chaque fenêtre de 20 jours) ; réserve
    vide → la file des soumissions (comportement v7.9.1) ; mode
    « universelle » choisi par la paroisse → prioritaire comme avant ;
    la règle d'or reste garantie (la réserve n'a pas de jour de
    naissance : elle n'entre jamais en conflit avec la clé du lecteur).
- **Pages remontées à l'ouverture (comme les feuillets)** :
  - à l'ouverture d'une page (changement de rubrique/sous-rubrique), la
    lecture repart DU HAUT de l'écran — même mécanique « nonce » que le
    retournement des pages du livret (`_scroll_top_si_nouvelle_page`) ;
  - l'entête est un peu plus compacte (logo 190→170 px, 150→136 et
    138→126 sur petits écrans) : la hauteur mesurée suit
    automatiquement, le contenu commence un peu plus haut ;
  - les interactions DANS une page (expander, bouton) ne repositionnent
    pas l'écran — seul un changement de page le fait.

## 🕊️ 10. v7.9.4 — La réserve affine son modèle (1 intention par N° méd., zone du jour, attachement 20 jours)

- **Compteurs de dénombrement** (harmonisation « Équipe 5 → 1/12 membres ») :
  - Paroisse « 👥 Mes équipes » : le titre devient **« 👥 Équipes de {paroisse} — N équipe(s) · M membre(s) »** ;
  - Diocèse « 📋 Gérer paroisses » : **« 📋 Consultation des paroisses — N paroisse(s) »**,
    et le détail interne **« 👥 Équipes de {paroisse} — N équipe(s) »** ;
- **📚 Réserve d'intentions — 1 intention par N° méd.** (le modèle v7.9.3
  s'affine) :
  - **UNE seule intention par N° méd.** : chaque emplacement (1-20) porte
    une intention — « Que chacun ait sa dernière intention selon son N°
    méd. » ; un second ajout au même emplacement est refusé avec un
    message doux (flash visible même l'encart refermé) ;
  - **la ZONE DU JOUR** (`intentions_du_jour`) : toute intention confiée
    dans « 🙏 Vos intentions à une équipe » y est recueillie en plus de
    la boîte du responsable (dont le travail ne change pas) ;
  - **LE LENDEMAIN**, chaque intention recueillie entre dans la réserve
    en remplaçant AU HASARD l'une des intentions en place
    (`traiter_intentions_du_jour`, idempotent, silencieux) ; l'ancienne
    passe en historique (`active=0`) — et si les demandes abondent, le
    stock tournant du N° méd. s'élargit d'autant (quota augmenté, la
    rotation par cycle de 20 jours s'en charge) ;
  - **L'ATTACHEMENT** (`attributions_prochain`) : l'intention du prochain
    reçue S'ATTACHE à son lecteur — **période désignée du membre (clé
    M:matloc) / 20 jours du visiteur (clé J:n° méd.)** — même si la
    réserve se renouvelle entre-temps ; échue, le tirage reprend dans la
    réserve renouvelée ;
  - **la règle d'or vaut aussi dans la réserve** : le jour de naissance
    du lecteur écarte l'intention qu'il a lui-même confiée ;
  - les responsables d'équipe et paroissial gardent le même bloc
    (grille 1/N°, or quand l'emplacement est pourvu, objectif « 20 au
    total ») ;
- **Message d'unicité repensé** (fidèle qui revient) : « 📿 Tu es déjà
  porté(e) en prière depuis le {date}. Ne brise pas la CHAÎNE DE PRIÈRE.
  Continue de méditer ta dizaine à CAUSE DE TON PROCHAIN. » suivie de
  **Matthieu 7.12** — plus aucune formulation de contrôle ;
- **« 🔒 Politique de confidentialité » retirée du formulaire** des
  intentions : elle vit désormais UNIQUEMENT en pied de page (la case de
  consentement renvoie « en pied de page ») ;
- **Pointage au ton complice** (fin de méditation) :
  - « 📿 La chaîne compte sur **Toi** — Marque ta présence du jour et ta
    gratitude envers La Vierge Marie pour l'écoute » ;
  - bouton **« ✅ Merci Sainte Mère pour ton aide de ce jour! »** ;
  - remerciement **« 📿 Ta dizaine est capitale pour la chaîne — Merci
    pour ta fidélité! — X dizaine(s) ce mois — À demain! 🕊️ »** (le
    compteur du mois est montré au membre) ;
  - les mentions de mécanisme disparaissent (« Le pointage enregistre… »,
    « Pointée ! … est enregistrée », « Dizaine d'aujourd'hui pointée »,
    info-bulle du « ✕ Terminer ») — jamais l'impression d'une
    surveillance ;
- **« J'ai honoré mon engagement de ce jour »** : au retour de la
  méditation, le bouton s'affiche juste après « 📿 Égrener la dizaine »
  (membre comme visiteur, quand la dizaine du jour est faite) — un clic,
  et il s'efface jusqu'à demain, comme « 📌 Marquer comme lue » ;
- tables nouvelles créées automatiquement (init + création douce,
  zéro action Cloud) : `intentions_du_jour`, `attributions_prochain` ;
  colonnes `active` / `qui` / `jour_naissance` ajoutées en ALTER doux à
  `intentions_reserve`.

### 11. v7.9.5 — « Chaîne des dizaines — aujourd'hui » : le même nom ne figure plus des deux côtés 📿

- **Correctif** (onglet « 📊 Engagement spirituel » de l'équipe) :
  « ⏳ Pas encore pointé aujourd'hui » listait **chaque** équipier actif,
  y compris ceux qui viennent de pointer — le même nom s'affichait dans
  « ✅ Ont pointé » ET dans « ⏳ Pas encore » (le rapprochement comparait
  des noms à un ensemble de MatLoc ; il se lit désormais par **MatLoc**,
  la clé unique qui a pointé) ;
- la liste « ⏳ Pas encore » ne contient plus que ceux qui n'ont pas
  encore marqué leur dizaine du jour, et « toute l'équipe est à jour
  🎉 » revient dès que le dernier a pointé ; la métrique
  « 📿 Dizaines pointées aujourd'hui » est inchangée ;
- aucun changement de base, aucune donnée à retoucher : le pointage
  existant était juste, seul l'affichage des listes est corrigé.

### 12. v7.9.6 — Fin de dizaine : deux rôles bien distincts, une carte qui se referme 📿

- **« ✕ Terminer » retrouve sa discrétion** : sa confirmation devient la
  ligne courte **« 📿 À demain! 🕊️ »** — il ne répète plus le
  remerciement complet avec le compteur du mois ; **le remerciement
  complet (« 📿 Ta dizaine est capitale pour la chaîne — Merci pour ta
  fidélité! — X dizaine(s) ce mois — À demain! 🕊️ ») reste la voix du
  seul bouton « ✅ Merci Sainte Mère pour ton aide de ce jour! »** de la
  dernière page — deux gestes, deux tonalités, plus de doublon ;
- **« J'ai honoré mon engagement de ce jour » referme désormais LA CARTE
  ENTIÈRE**, exactement comme « 📌 Marquer comme lue » referme la
  sienne : la bannière « 📿 Ta dizaine du jour », le bouton
  « 📿 Égrener la dizaine » et le bouton lui-même s'effacent jusqu'à
  demain (membre comme visiteur) ; le livre déjà ouvert, lui, reste
  prioritaire — on ne ferme pas une lecture en cours ;
- aucun changement de base ni de migration : deux ajustements d'écran.

### 13. v7.9.7 — Le raccourci de l'application : une vraie app, qui se souvient du fidèle 📿

- **Plein écran, comme une vraie app** : les métas « capable »
  (Android + iPhone) et la barre d'état sont posées à chaque chargement —
  depuis « Ajouter à l'écran d'accueil », l'application s'ouvre SANS
  barre de navigateur, avec le bon nom (« Rosaire — Espaces de prière »
  côté fidèles, « Rosaire — Administration » côté gestionnaire) ;
- **la mémoire du fidèle** : le raccourci posé depuis un lien personnel
  ouvrait l'espace « générique » (le manifeste pointe `/?espace=1`,
  sans matloc) — désormais le navigateur retient le dernier lien
  personnel ouvert et le restitue à l'ouverture suivante : le fidèle
  retrouve SON espace, sa bannière, sa dizaine du jour, sans rien
  ressaisir ; un lien personnel rouvert rafraîchit la mémoire ;
- **100 % navigateur** (localStorage du téléphone) : aucune table,
  aucune donnée serveur, rien à migrer — un appareil qui n'a ouvert que
  le lien public reste neutre, et l'administration n'a aucune mémoire ;
- les deux manifestes gagnent leurs champs d'identité (`id`, `scope`,
  `lang`) : Android distingue proprement l'app « Espaces » de l'app
  « Administration » au moment de l'installation.

### 14. v7.9.8 — Le raccourci porte le bon nom, l'icône se reconnaît d'un coup d'œil 📿

- **Des noms distincts** : le navigateur nomme le raccourci d'après le
  titre de l'onglet — identique des deux côtés avant (« Gestionnaire des
  Équipes du Rosaire… »). Désormais **« Rosaire »** côté Espace de
  prière et **« Rosaire Admin »** côté gestionnaire, onglet compris ;
- **Une icône admin refondue** : la clé dorée passe sur **fond violet**
  (la couleur de l'interface de gestion), l'Espace garde son chapelet
  doré sur bleu nuit — plus aucune confusion une fois les pastilles
  recadrées en rond et réduites ;
- **Le bon geste, rappelé en page** : la carte « raccourcis » de la page
  de recherche du navigateur n'écrit JAMAIS sur l'écran d'accueil — le
  rappel « menu ⋮ → Ajouter à l'écran d'accueil » est affiché dans la
  carte d'accueil de l'Espace et, en légende, sous la connexion ;
- **Plus de version en retard** : la carte d'accueil, la carte membre, la
  bannière « Rosaire selon le thème », la ligne N° méd. et le pied de
  page lisent UNE constante (`_VERSION_APPLI`) — les « v7.6 » figés
  disparaissent ;
- aucun changement de base ni de migration.

### 15. v7.9.9 — La zone du jour devient un écran, le pied de page porte la robe du Mouvement 🕯️

- **🕯️ La zone du jour (diocèse → « 🕯️ Zone du jour »)** : la demande
  « Afin d'harmoniser l'intention du prochain à l'affichage, il est
  nécessaire de la traiter auparavant. Créer donc une zone qui recevra
  toutes les intentions du jour » prend forme d'écran. La table
  `intentions_du_jour` (v7.9.4) reçoit déjà chaque intention confiée ;
  elle est désormais VISIBLE : compteurs (⏳ en attente · ✅ entrées en
  réserve aujourd'hui · 🌙 écartées), puis chaque intention se déplie —
  texte d'origine, **« ✨ Harmoniser le texte »** (l'entrée en réserve du
  lendemain emporte le texte soigné, et c'est lui que la chaîne affiche)
  et **« 🌙 Écarter de la chaîne »** (`traitee=2` : le transfert
  automatique ne la prendra jamais). Aucune migration : la table
  suffit ;
- **🟣 Pied de page refondu sur le modèle du site du Mouvement**
  (equipes-rosaire.org) : trois colonnes — la marque (📿 + nom +
  diocèse), « LE ROSAIRE EN ÉQUIPE » (menus tirés de l'entête de
  l'application), « NOUS CONTACTER » — sur fond **violet nuit**, celui
  du badge « Bienvenue » (`#4A148C`), barre noire de copyright
  (« © 2026 Les Équipes du Rosaire — Diocèse de Grand-Bassam ») et
  emplacement Facebook (constante `LIEN_FACEBOOK` : renseignée → l'icône
  apparaît ; vide → elle reste absente). La « 🔒 Politique de
  confidentialité » complète y demeure, rejointe par une « 🍪 Politique
  de cookies » ;
- **Raccourci, suite** : l'adresse du manifeste porte désormais une
  version (`manifest_*.json?v=799`) — le navigateur relit les bons noms
  et les bonnes icônes au prochain « Ajouter à l'écran d'accueil ».
  Rappel du geste sur le téléphone : **supprimer l'ancien raccourci**
  (il garde pour toujours le visage qu'il avait au moment où il a été
  posé), puis menu ⋮ → « Ajouter à l'écran d'accueil » APRÈS déploiement ;
- **Dénombrement allégé** : le titre paroissial devient
  « 👥 Équipes de {paroisse} — N équipe(s) » (le compte des membres
  disparaît du titre, à la demande) ;
- aucun changement de base ni de migration.

### 16. v7.9.10 — Le sas des intentions, la publication à 00h00, le raccourci incassable 🕊️

- **🕯️ La zone du jour DÉMÉNAGE chez la paroisse** (« Les intentions c'est
  une affaire des paroisses et de ses équipes ») : elle quitte le menu du
  diocèse et devient le **sas des intentions** en tête de « 🙏 Coins des
  Intentions » (📌 Suivi et Agenda - Paroisse), portée sur les intentions
  de LA maison (équipe de la paroisse ou paroisse notée). Chaque
  intention confiée y transite — **aucune ne peut être publiée sans y
  passer** ;
- **🕊️ « Traiter & envoyer en réserve » (immédiat)** : le responsable
  harmonise le texte (orthographe, dignité, clarté) et l'envoie en
  réserve SUR LE CHAMP — plus d'attente du lendemain. **🌙 Écarter de la
  chaîne** demeure (`traitee=2`) ;
- **⏰ La publication se fait à 00h00 du jour suivant** : toute arrivée en
  réserve naît `publiee=0` avec `date_publication` = demain ; le réveil
  `publier_reserve_due()` — appelé à chaque tirage — la rend visible à
  l'heure dite. Le transfert automatique du lendemain (v7.9.4) respecte
  la même règle ; les intentions déjà en place avant v7.9.10 restent
  publiées comme avant (`DEFAULT 1`) ;
- **📱 Le raccourci devient incassable** : le favicon de l'onglet et
  l'icône iPhone sont désormais INCORPORÉS à la page (images base64 —
  ni 404, ni cache possible), le manifeste reste versionné
  (`?v=7910`), et deux **pages d'installation** (`static/install_rosaire.html`
  et `install_rosaire_admin.html`) portent le vrai visage — nom « Rosaire »
  / « Rosaire Admin », chapelet doré / clé — DÈS LE PREMIER OCTET : le
  raccourci posé depuis elles ne peut plus porter le nom ni l'icône de
  Streamlit (c'était le cas quand il était posé pendant l'écran de
  chargement bleu). Les liens vers ces pages sont dans la carte de
  bienvenue (espaces) et sous la connexion (administration) ;
- **🦶 Pied de page — la disposition demandée** : colonne 1 — 🔒
  Politique de confidentialité · 🍪 Politique de cookies ; colonne 2 —
  le logo, LES ÉQUIPES DU ROSAIRE, DIOCÈSE DE GRAND-BASSAM, le nom de la
  paroisse du fidèle, « Contactez le responsable paroissial » (WhatsApp
  quand il est renseigné) ; colonne 3 — 🏠 Actualités · 📿 Rosaire ·
  🕯️ Thème · 🖼️ Galerie + · 📖 Archives (les cinq rubriques, dans
  l'ordre, naviguant dans l'onglet courant). Fond violet nuit du badge
  « Bienvenue », barre © 2026, Facebook conditionnel ;
- **⚠️ Erreurs récurrentes du Cloud, traitées** : le veilleur de fichiers
  est désarmé (`fileWatcherType = "none"` — fini les
  « inotify instance limit reached » au démarrage) et le rattrapage des
  micro-coupures embrasse la transaction rendue au repos trop longtemps
  (SQLITE_BUSY / « idle for too long » / rollback) + un commit rejoué ;
- **Migration douce** : deux colonnes ajoutées à `intentions_reserve`
  (`publiee INTEGER DEFAULT 1`, `date_publication TEXT`) — idempotentes,
  silencieuses, rien à faire manuellement.

### 17. v7.9.11 — Le tableau de la chaîne, la paix des cinq téléphones, le pied de page assagi 📋

- **📋 Le tableau de la chaîne, jour par jour** (à la demande du
  fondateur) : dans « 📿 Chaîne des dizaines » (onglet 📊 Engagement
  spirituel de l'équipe), les deux listes du jour (« ✅ Ont pointé » /
  « ⏳ Pas encore pointé ») laissent place à une **grille jour × membre**
  — « ✅ » dans la case du membre qui a fait sa méditation du jour, vide
  sinon. La ligne du jour vit en tête (✨) ; **à 00h00 elle s'archive
  toute seule** — les lignes passées demeurent consultables à souhait —
  et la ligne du nouveau jour s'affiche. Une ligne « 📿 Total » résume
  la période (7, 14 ou 30 jours au choix) ; **le même tableau sert aux
  visiteurs** (passages anonymes, comptés jour par jour, sans jamais les
  nommer) — `tableau_pointages_equipe()` / `tableau_pointages_visiteurs()`
  dans `database.py`, le journal `dizaines_journal` relu tel quel (rien
  n'est jamais effacé, aucun changement de schéma) ;
- **🤝 La paix des cinq téléphones** (formation pastorale, cinq
  téléphones sur toutes les pages) : toutes les requêtes partageaient le
  même fil de la base — lectures croisées d'un fidèle à l'autre,
  identifiants confondus, transactions rendues au repos (SQLITE_BUSY).
  Désormais (`database.py`) : **un verrou sérialise chaque requête et
  chaque commit**, et **les lignes sont capturées à l'instant de
  l'exécution** — le résultat de chacun appartient à chacun
  (`ResultatRequete`, `lastrowid`/`rowcount`/`description` par fil).
  Aucun changement d'écran, aucune opération : la même prière, sans
  bousculade. Le rattrapage des micro-coupures Hrana/Turso (v7.8.16,
  v7.9.10) demeure à l'identique ;
- **🔐 La connexion tient au copier-coller** (`app.py`) : les deux
  champs forment désormais UN SEUL formulaire — coller l'utilisateur
  puis le mot de passe ne déclenche plus de rechargement intermédiaire
  qui essuyait le premier champ (« Identifiants incorrects » alors que
  tout était pourtant collé). Tout part ensemble, au clic ; la parade
  AUTOFILL (v2) demeure pour les gestionnaires de mots de passe ;
- **🦶 Pied de page assagi** (`view_espace_membre.py`) : la colonne
  centrale porte désormais le **logo des Équipes du Rosaire** (le
  chapelet doré du Mouvement, dessiné pour lui :
  `static/logo_equipes_rosaire.png`) et non plus l'icône de
  l'application ; les trois phrases d'appel sont retirées (« Un jour,
  une dizaine — la chaîne de prière universelle… », « Parle à ton
  responsable d'équipe… », et la signature de version). Restent :
  politiques, identité, paroisse du fidèle, contact responsable, les
  cinq rubriques, © 2026, Facebook conditionnel ;
- **🕯️ Zone du jour** (v7.9.10, vérifiée intacte) : le sas reste en tête
  de 🙏 Coins des Intentions — « 🕊️ Traiter & envoyer en réserve »
  immédiat, publication à 00h00 du jour suivant ;
- **L'icône « Streamlit » du raccourci** : abandon respecté (décision du
  fondateur) — plus aucune retouche de ce côté ; tout le dispositif
  v7.9.8/7.9.10 (manifestes versionnés, pages d'installation, visages
  incorporés) demeure en l'état ;
- `_VERSION_APPLI = "v7.9.11"` ; aucun changement de base.

### 18. v7.9.12 — La sentinelle du paquet complet 🕊️

- **🕊️ La sentinelle du paquet complet** (`app.py`) : le 26 octobre au
  soir, un versement arrivé incomplet chez l'hébergeur (les vues
  nouvelles devant un `database.py` resté ancien) a fait voir un mur de
  code à la place des pages. Désormais le cœur du paquet se fait
  reconnaître AVANT tout autre import ; si l'un des gestes récents lui
  manque (`tableau_pointages_equipe`, `tableau_pointages_visiteurs`,
  `publier_reserve_due`, `envoyer_intention_du_jour_en_reserve`), la
  maison affiche sa note douce — « 🕊️ Un instant — la maison se pare » —
  et s'arrête net : jamais de traceback, ni pour la fondatrice, ni pour
  les fidèles. La note signifie une seule chose : le versement est
  incomplet — tout re-verser (d'abord vider le dépôt, ensuite verser le
  paquet entier) ;
- **Le scénario réel rejoué en test** : un arbre à l'ancien cœur (extrait
  du zip v7.9.10) avec l'`app.py` actuel → la note douce s'affiche,
  l'exécution s'arrête avant tout, zéro exception ; sur le dépôt complet,
  la sentinelle se tait ;
- `scripts/test_v795.py` réécrit à l'image du tableau de la chaîne
  (v7.9.11) : le ✅ doit tomber dans SA case de la grille jour × membre,
  le bug noms↔MatLoc (v7.9.2) reste mort ; cas limite de la membre sans
  MatLoc précisé (pas de colonne, dénominateur des actifs) ;
- `_VERSION_APPLI = "v7.9.12"` ; aucun changement de base.

### 19. v7.9.13 — La main prudente du cœur 🤲

- **🤲 La main prudente** (`database.py`) : le 26 octobre au soir, le
  versement complet étant en place, les journaux du Cloud ont montré une
  dernière pierre — chaque écriture (connexion, compteur de visites,
  préparation de la mémoire) trébuchait au moment où le cœur relevait le
  résultat de la requête, chez l'hébergeur seulement (les essais locaux,
  au dialecte différent, ne pouvaient pas le voir). Désormais le cœur ne
  demande plus de lignes à une écriture — une écriture n'en a pas à
  rendre — et relève chaque métadonnée avec des gants : si le conducteur
  distant se dérobe, la requête poursuit sa route au lieu de s'arrêter.
  Les lectures restent exactement fidèles : une vraie erreur de lecture
  remonte toujours, comme avant ;
- **Le scénario de production rejoué en test** (`scripts/test_v7913.py`)
  : un conducteur simulé au tempérament observé en production, branché
  sur le vrai cœur — la chaîne du login (SELECT → INSERT → DELETE), le
  CREATE TABLE de l'installation, les écritures aux métadonnées
  dérobantes, la lecture honnête, sqlite3 réel et les fils concurrents :
  24 contrôles, zéro exception ;
- `_VERSION_APPLI = "v7.9.13"` ; aucun changement de base de données,
  aucune migration.

### 20. v7.9.14 — Le chapelet qui ne se perd plus, la paroisse qui est dite 📿

- **📿 Le logo qui ne se perd plus** (`views/view_espace_membre.py`) : le
  chapelet doré du pied de page est cherché d'abord À CÔTÉ DU MODULE
  (l'adresse certaine, où que la maison soit installée), puis au coin
  habituel ; relevé une seule fois puis gardé en mémoire, il ne dépend
  plus du lieu d'où la page parle. S'il manque vraiment, un chapelet
  emoji sobre le remplace — jamais de vide qui ressemble à un oubli ;
- **🕯️ Le nom de la paroisse, dit quand il peut l'être** : le pied de
  page montre désormais la paroisse chaque fois qu'il peut la connaître —
  celle du fidèle reconnu (même si son statut dort : le pied ne décide
  rien, il dit bonjour), sinon celle qui a ouvert la porte (QR / lien
  paroissial qui a mené ici), avec le contact de son responsable ;
  sinon, pied sobre — aucune placeholder, jamais ;
- `scripts/test_v7914.py` : 28 contrôles — logo trouvé « ailleurs »
  (maison installée dans un autre dossier), logo vraiment absent
  (remplacement sobre), passant sans rien (pied net), passant accueilli
  par une paroisse (nom + WhatsApp + adresse dans les liens), fidèle
  reconnu, fidèle au statut endormi ;
- `_VERSION_APPLI = "v7.9.14"` ; aucun changement de base de données,
  aucune migration.

### 21. v7.9.15 — Le logo partout, le menu du pied de page à droite 📿

- **📿 Le fichier `images/logo.png` est désormais livré dans le paquet**
  (c'est le chapelet doré sur fond violet). Jusqu'ici, l'application le
  cherchait mais il n'était jamais livré : l'entête de l'Espace, la page
  « Devenir membre » et l'écran de connexion affichaient un simple emoji
  📿 à sa place. Pour passer un jour au logo officiel du Mouvement, il
  suffira de déposer la nouvelle image sous le même nom — aucun code à
  modifier ;
- **📿 Recherche du logo renforcée** (`views/view_espace_membre.py`,
  `app.py`) : le logo est cherché à côté des fichiers de l'application
  (où qu'elle soit installée), puis depuis le dossier de lancement ; en
  dernier recours, le chapelet livré dans `static/` prend le relais.
  S'applique aux 4 emplacements : entête de l'Espace, page « Devenir
  membre », pied de page, écran de connexion (colonne de gauche) ;
- **➡️ Pied de page : la 3e colonne (menu) est décalée à droite** sur
  les écrans larges : elle se cale sur le bord droit, bien séparée de la
  colonne centrale (logo, nom, contact). Sur téléphone, les colonnes
  s'empilent comme avant ;
- `scripts/test_v7915.py` : logo trouvé depuis un autre dossier de
  lancement, logo absent → emoji sobre (jamais de vide), entête et pied
  de page rendus avec le chapelet incorporé, colonne droite présente ;
- `_VERSION_APPLI = "v7.9.15"` ; aucun changement de base de données,
  aucune migration.

### 22. v7.9.16 — Le logo du pied de page en grand, la ligne « Paroisse » 📿

- **📿 Logo du pied de page agrandi** : même largeur que le nom
  « LES ÉQUIPES DU ROSAIRE » (≈ 240 px, proportion carrée conservée —
  l'image est carrée) ; il se réduit proprement si l'écran est étroit
  (`max-width:100%`). L'ombre suit désormais la forme ronde du chapelet
  (`drop-shadow`) au lieu d'un carré (`box-shadow`) ; les attributs
  figés `width="64"` sont retirés (taille pilotée par le CSS) ;
- **🕯️ Ligne paroisse libellée** : « 🕯️ Paroisse : Nom de la paroisse »
  (avant : le nom seul) ;
- `scripts/test_v7916.py` : 12 contrôles (taille CSS 240 px + secours
  `max-width`, ombre ronde, libellé paroisse, pied sobre sans paroisse,
  colonne droite conservée) ; `test_v7914` mis à jour au nouveau
  libellé ; vérification de version de `test_v7915` rendue insensible
  au numéro ;
- `_VERSION_APPLI = "v7.9.16"` ; aucun changement de base de données,
  aucune migration.

### 23. v7.9.18 — Republier, les actualités dans le fil, multi-photos, chaîne de séance ⛓️

- **📤 Bouton « Republier »** (sceau du diocèse, section « 🧹 Déjà publiés —
  à ranger ») : 2e bouton à côté de « ✅ Marquer comme publié (sans
  republier) ». Il ajoute le contenu de la soumission comme une NOUVELLE
  publication (utile quand la version en ligne diffère — ex. bande
  défilante remplacée). L'insertion est factorisée (`_inserer_publie`,
  partagée avec « ✅ Publier ») : une seule logique ;
- **détection des doublons affinée** (`_deja_publie`) : pour prière,
  méditation, bande défilante et actualité, le TEXTE doit correspondre en
  plus du titre — un même titre avec un contenu différent est une NOUVELLE
  version, elle repart dans « En attente de validation » (audio : titre +
  fichier) ;
- **📰 Actualités dans le fil d'actualité** : `_render_actualites` est
  appelée DANS `_render_fil_actualites` (public + membre) — le fil allégé
  v7.9.3 les masquait totalement (publications `actualite` invisibles
  nulle part) ; titre « 📰 Actualités », appels extérieurs retirés ;
- **📷 Multi-photos Galerie +** (Souvenirs / Témoignages) :
  `file_uploader(accept_multiple_files=True)` dans la saisie diocèse
  (téléversement Cloudinary via `sauvegarder_illustration`) ; les URLs
  cohabitent dans `image_url` séparées par « | » (`urls_galerie`,
  `supprimer_photos_galerie` dans services.py) ; l'affichage Espace de
  Prière boucle sur toutes les photos ; rétrocompatible (1 URL = rendu
  inchangé) ;
- **⛓️ Chaîne de la dernière séance** : nouvelle table `chaine_seances`
  (equipe_id, date_seance, ordre = N° méd. « 10,17,09,… », absents =
  « présents spirituellement », date_enregistrement) + `_assurer_table_
  chaine_seances` (création douce), `enregistrer_chaine_seance`,
  `derniere_chaine_seance`, `historique_chaines_seance` (database.py) ;
  bloc `bloc_chaine_seance(equipes, prefixe)` dans components.py :
  traduction maillon par maillon (« X aura pour prochain Y — N° méd. Z,
  méditera et priera son intention jusqu'à la prochaine séance », chaîne
  refermée sur le premier), intention du prochain lue dans la réserve
  (`intention_reserve_pour_numero`), saisie avec aperçu en direct
  (virgules ou flèches), vérification des N°, historique 12 séances ;
  intégré dans l'onglet intentions (équipe) et « 🙏 Coins des Intentions »
  (paroisse) ;
- `scripts/test_v7918.py` : parser de l'ordre (virgules/flèches, boucle
  fermée, doublons), enregistrement + lecture de la dernière chaîne,
  `_inserer_publie` par type, détection titre+texte, `urls_galerie` /
  `supprimer_photos_galerie`, rendus AppTest (bloc chaîne, galerie,
  fil) ;
- `_VERSION_APPLI = "v7.9.18"` ; une seule nouveauté de base :
  la table `chaine_seances` (création douce, idempotente).

### 24. v7.9.19 — Chaîne YouTube, photos sans hébergeur, réserve réunie, carte repliée 📚

- **▶️ Chaîne YouTube dans le pied de page** : la ligne « ▶️ Notre chaîne
  YouTube » rejoint la colonne centrale, sous le contact du responsable
  paroissial (constante `LIEN_YOUTUBE_CHAINE` en tête de
  `view_espace_membre.py` ; vide = ligne absente) ;
- **🛕 Carte vidéo juste avant le pied de page** : la carte « Annonce de
  pèlerinage » quitte la tête du fil d'actualité et s'ouvre maintenant sur
  toutes les pages de l'Espace de Prière, juste avant le pied de page
  (appel dans `show_espace_membre`, entre le corps de page et
  `_render_pied_de_page`) ;
- **🖼️ Galerie + : plus d'échec qui bloque** — quand l'hébergement d'images
  (Cloudinary) n'est pas configuré ou indisponible, chaque photo est quand
  même acceptée : elle est réduite (800 px, JPG) et rangée dans
  `static/galerie/` (nouveau `sauvegarder_photo_locale` dans services.py) ;
  son adresse `/app/static/galerie/…` s'affiche comme n'importe quelle
  photo (affichage Espace de Prière élargi, suppression locale avec
  l'entrée) ; le message d'échec ne survient que si MÊME le rangement
  local a échoué ;
- **➕ Champs de lien additionnels** dans la saisie Galerie + : le bouton
  « ➕ Ajouter un champ photo » (à côté du champ « LIEN de photo ») crée
  autant de champs que voulu (« ➖ Un champ de moins » pour réduire) ; les
  champs sont préservés quand on corrige une saisie (fin de
  `clear_on_submit`, nettoyage par génération `gal_gen`) ;
- **📚 Réserve d'intentions réunie** (paroisse) : titre simplifié
  « 📚 Réserve d'intentions » ; la liste « 🗂️ Intentions en réserve —
  toutes les équipes » réunit les réserves des équipes (membres comme
  visiteurs), lecture seule ; retirés : « ➕ Ajouter une intention à la
  réserve », l'ancienne liste paroissiale et « ⛓️ Chaîne de la dernière
  séance » au niveau paroisse ;
- **📚 Réserve d'équipe : la chaîne d'abord** : « ⛓️ Chaîne de la dernière
  séance » passe AVANT la réserve (c'est elle qui la pourvoit) ; dans
  « ⛓️ Enregistrer la chaîne d'une séance », la liste des membres s'affiche
  à la verticale juste après la date, avec la zone de saisie de SON
  intention en face de chaque membre — elle rejoint directement la réserve
  (jamais par la 🕯️ Zone du jour) ; « ➕ Ajouter une intention à la
  réserve » retiré (équipe et paroisse) ;
- **⛓️ Phrase de chaîne** : « N° 10 — X prie pour Y — N° méd. 17. » (au
  lieu de « X aura pour prochain Y… ») ; sous chaque maillon, TOUTES les
  intentions du N° méd. (principale + surplus) ;
- **➕ Le surplus est bienvenu** : `ajouter_intention_reserve` n'accepte
  plus seulement une intention par N° méd. — un N° peut en porter
  plusieurs ; le membre ou le visiteur qui médite ce N° voit ses
  intentions augmentées selon le surplus (`intentions_reserve_du_numero`,
  `intentions_reserve_surplus` dans database.py ; la ligne du livret
  ajoute « 🕯️ Et elle intercède aussi … » pour chaque surplus) ; la grille
  des compteurs affiche « 1/1 +2 » quand un N° porte un surplus ;
- **🙏 « Vos intentions à une équipe » repliée à l'arrivée** : la rubrique
  reste un expander habillé comme la carte « 📿 Découvrez les Équipes du
  Rosaire ! » (dégradé, liseré or, coins arrondis), se présente repliée
  sous forme de carte, avec la mini-ligne « cliquez pour ouvrir ▾ / cliquez
  pour replier ▴ » (posée et retournée par le mini-script) ;
- **Colonne centrale du pied équidistante** : sur les écrans larges, les
  trois colonnes ont exactement la même largeur (le centre du logo tombe
  au juste milieu des deux extrêmes, le menu reste calé à droite ; mobile
  inchangé) ;
- `_VERSION_APPLI = "v7.9.19"` ; aucun changement de schéma de base.

### 25. v7.9.20 — La vidéo à la demande, la réserve qui se renouvelle, les cartes qui restent closes 📿

- **🛕 La carte vidéo porte son nom d'aujourd'hui** : la date du pèlerinage
  est passée — « Annonce de pèlerinage » devient **« Vidéo à la demande »**
  partout : constante `LIEN_YOUTUBE_VIDÉO_A_LA_DEMANDE`, fonction
  `_carte_vidéo_a_la_demande`, titre de la carte, phrase « Regardez la
  vidéo à la demande sur la chaîne des Équipes du Rosaire — Diocèse de
  Grand-Bassam », `title` du lecteur. Le lecteur, la place (juste avant le
  pied de page) et le remplacement par un simple lien restent inchangés ;
- **📚 La réserve d'intentions a une durée de vie** (`purger_reserve_expiree`
  dans database.py, réveil paresseux appelé aux lectures comme aux tirages) :
  une intention confiée par un **VISITEUR** (🕯️ Zone du jour) vit **20 jours
  après sa prise en charge** — elle quitte la réserve à 00h00 du 21ᵉ jour ;
  une intention de **MEMBRE** (posée en face de son N° dans la ⛓️ Chaîne)
  vit **jusqu'à la prochaine séance** : la nouvelle saisie de la chaîne la
  libère (`enregistrer_chaine_seance` ; celles notées à cette séance suivent
  juste après, intouchées ; une correction de saisie le même jour ne
  détruit rien) ; les vieilles lignes orphelines d'avant les réserves
  d'équipe suivent la règle des 20 jours ; les libérées passent `active=0`
  et quittent vues, compteurs et tirages ; le message d'enregistrement de
  la chaîne signale combien d'intentions ont quitté la réserve ;
- **🔔📿 La mémoire d'un jour des deux cartes tient EN BASE**
  (`cartes_vues`, création douce ; `marquer_carte_vue` / `carte_deja_vue`) :
  la session est vidée à chaque rechargement et les cookies sont refusés
  quand l'Espace est vu depuis une page extérieure — la carte revenait
  donc sans cesse. Désormais « 📌 Marquer l'alerte comme lue » et « J'ai
  honoré mon engagement de ce jour » notent la fermeture en base, pour la
  journée, via une clé du lecteur sans cookie ni session
  (`_cle_lecteur_pdr` : MatLoc du membre dans l'adresse ; empreinte hachée
  navigateur + adresse réseau pour un visiteur — aucune donnée personnelle
  gardée) ; la carte revient le lendemain, ou dès qu'un NOUVEAU feuillet
  paraît ; les cookies (v7.9.17) restent posés en secours quand ils
  marchent ;
- **📿 Le visiteur retrouve sa présence du jour** : après un rechargement,
  « ✅ Merci Sainte Mère pour ton aide de ce jour ! » et le bouton « J'ai
  honoré mon engagement de ce jour » reviennent (la présence du visiteur
  est retrouvée en base par son jour de naissance,
  `dizaine_visiteur_pointee`) — et un passage ne compte plus deux fois
  dans la chaîne quand la page est rechargée ;
- `_VERSION_APPLI = "v7.9.20"` ; un seul ajout de schéma, création douce :
  la table `cartes_vues` (aucune opération demandée à l'hébergeur).

### 26. v7.10.0 — Le questionnaire du feuillet, l'envoi en mission, les dizaines hors ligne 📝✈️📥

- **📝 Le questionnaire du feuillet mensuel** : les questions et exercices du
  feuillet deviennent un questionnaire répondu dans l'Espace de Prière.
  *Composition* (Service Communication → 🕯️ Thème pastoral, zone « 1 Bis. » —
  nommée « 2️⃣ ter » à sa naissance, renumérotée en v7.10.2,
  `gerer_questionnaire_feuillet` dans components.py) : lignes en forme de
  question repérées dans le texte des sections saisies (`feuillet_questions_detecter`,
  reprise d'un clic) ou questions tapées à la main ; trois types de réponse
  (texte libre / Oui-Non / choix proposés), question obligatoire ou non,
  ordre ajustable (⬆️ ⬇️), question active ou retirée ; lecture des réponses
  reçues, par question (compteurs pour Oui-Non et choix, réponses signées
  ligne à ligne) et carnet Excel. *Réponse* (🕯️ Thème → Vue d'ensemble, sous
  la vitrine du feuillet, `_render_questionnaire_mensuel` — appelée pour les
  visiteurs comme pour les membres, la page Thème portant désormais le
  contexte du lecteur) : un membre répond sous son MatLoc (clé « M:… », ses
  réponses reviennent pré-remplies, il peut les corriger et renvoyer) ; un
  visiteur signe du nom qu'il choisit (clé « N:nom-doux ») ; les questions
  obligatoires sont exigées ; répondre à nouveau remplace SES réponses du
  mois, jamais celles des autres (tables `feuillet_questions` et
  `feuillet_reponses`, création douce dès l'init et à la volée) ;
- **✈️ L'envoi en mission** (équipe → 📌 Suivi → onglet « ✈️ Envoi en
  mission », `_onglet_missions` dans view_equipe.py) : le responsable ouvre
  une mission (nom, objectif, date, lieu, personnes de l'équipe choisies
  par cases à cocher + personnes venues d'ailleurs une par ligne) ; le
  Gestionnaire en tire la **FICHE D'ENVOI EN MISSION** imprimable
  (`_fiche_envoi_html` : entête Mouvement/diocèse avec logo, bandeau
  équipe/paroisse/date/lieu, objectif, grille numérotée des envoyés avec
  N° méd. et contact, Marc 16,15, signatures responsable d'équipe +
  responsable paroissial) ; après la mission, le **RAPPORT DE MISSION** se
  remplit (déroulement, grâces reçues, difficultés, propositions,
  participants effectifs) et donne la **FICHE DE RAPPORT DE MISSION**
  imprimable (`_fiche_rapport_html`). L'impression (`_rendre_fiche_imprimable`)
  sort la fiche SEULE sur le papier (CSS @media print ciblé) via le bouton
  « 🖨️ Imprimer la fiche (ou l'enregistrer en PDF) » ; chaque fiche
  s'emporte aussi en fichier HTML autonome (bouton « 📥 Télécharger ») ;
  les fiches se gardent dans l'équipe, re-imprimables à souhait ; mission
  retirée = suppression définitive volontaire (tables `missions`,
  `mission_creer` / `missions_equipe` / `mission_rapport_enregistrer` /
  `mission_supprimer`) ;
- **📥 Les dizaines priées hors ligne** (la récupération « comme ✕
  Terminer ») : en fin de livre « 🕯️ Un jour, une dizaine », sous le
  pointage du jour, l'expander « 📿 Tu as prié hors ligne ? Remets tes
  journées dans la chaîne » (`_recuperer_dizaines_hors_ligne`) reçoit le
  fichier exporté/partagé par l'application Android de méditation du
  quotidien (fonctionne sans internet). Le lecteur (`_lire_jours_dans_fichier`)
  est tolérant : JSON (liste de dates ou d'objets avec un champ
  date/jour/date_prière/…) comme texte simple (une date par ligne, tout
  séparateur) ; formats reconnus 2026-10-28, 28/10/2026, 28-10-2026,
  28.10.2026, « 28 octobre 2026 » ; les dates à venir et les lignes
  incompréhensibles sont écartées (plafond 400 journées par fichier,
  `MAX_IMPORT_DIZAINES`). L'enregistrement (`importer_dizaines_hors_ligne`
  dans database.py) est IDEMPOTENT : membre par MatLoc (UNIQUE matloc+jour)
  et visiteur par (jrnais, jour) — repasser le même fichier ne recompte
  rien ; le jour du fichier qui tombe aujourd'hui vaut présence du jour
  (la bannière « J'ai honoré mon engagement » revient) ; message de
  confirmation : ajoutées / déjà comptées / laissées de côté ;
- `_VERSION_APPLI = "v7.10.0"` ; la sentinelle du paquet complet (app.py)
  connaît désormais `feuillet_reponses_enregistrer`, `mission_creer` et
  `importer_dizaines_hors_ligne` ; trois tables neuves à création douce
  (`feuillet_questions`, `feuillet_reponses`, `missions`) — aucune
  opération demandée à l'hébergeur.

### 26. v7.10.1 — La vidéo reste à l'accueil, la règle d'or pour les membres, la maison rapide 🛕📜⚡

- **🛕 La vidéo ne suit plus le lecteur partout** (demande : « la vidéo à la
  demande se comporte comme un pied de page ») : la carte
  (`_carte_vidéo_a_la_demande` dans `show_espace_membre`) ne s'ouvre PLUS
  sur toutes les pages de l'Espace de Prière. Elle retrouve sa place de
  carte d'accueil : visible uniquement sur la page d'arrivée
  (« 🏠 Actualités », publique comme membre), juste avant le pied de page
  — absente du livre ouvert (dizaine, méditation, prière des intentions,
  livret mensuel) et des autres rubriques (Rosaire, Thème, Galerie,
  Archives, Mes évènements). La prière reste toute à la prière ;
- **⚡ Le lecteur vidéo se réveille en douceur** : `loading="lazy"` sur
  l'iframe YouTube — la carte est en bas de page, le navigateur ne charge
  plus la vidéo à l'ouverture, seulement quand le fidèle descend la voir ;
- **📜 La règle d'or pour les MEMBRES** (demande : « je suis en train de
  prier pour moi-même ») : jusqu'ici seul le VISITEUR était protégé par
  son jour de naissance. Désormais la fiche du membre
  (`fiche_membre(matloc)` : jour de naissance tiré de la date de
  naissance — « 1990-05-17 » comme « 17/05/1991 » — ET nom complet
  prénom+nom, lue une seule fois par visite) écarte SES PROPRES
  intentions : au tirage principal (pool `intentions_equipes`, par jour
  ET par nom), dans le surplus de la réserve
  (`intentions_reserve_du_numero(..., nom_exclu=…)` — une intention notée
  à son nom dans la chaîne de séance ne lui revient plus), et une
  attachement ancienne qui serait la sienne n'est plus montrée (le tirage
  la remplace tout seul). La clé de nom remet les mots en ordre
  (`_nom_cle` : « Odette ONIBONKOU » = « ONIBONKOU Odette » — la fiche
  porte Prénom Nom, la chaîne note Nom Prénom). Le visiteur du même N°
  méd. continue de porter l'intention du membre, et rien ne change pour
  lui ; s'il ne reste que la sienne, le membre reçoit le secours
  universel (« La Paix dans le monde ») — la chaîne ne se casse jamais ;
- **⚡ La maison rapide** (demande : « la lenteur au clic Égrener la
  dizaine et à l'ouverture de l'Espace ») : les contrôles doux de tables
  (`_assurer_*` : 7 fonctions) repartaient À CHAQUE PAGE — le contrôle de
  `intentions_reserve` seul relançait 5 ALTER perdus à chaque appel, et
  il était appelé plusieurs fois par page : jusqu'à 36 requêtes pour
  ouvrir la dizaine, dont 20 allers-retours perdus (chez l'hébergeur
  distant, chaque requête est un aller-retour réseau — c'était la
  lenteur). Désormais chaque table est reconnue UNE FOIS par processus
  (`_TABLES_RECONNUES`, `_table_reconnue` / `_table_averee`) : la même
  ouverture descend à 18 requêtes, et sur un serveur en route chaude les
  contrôles ne coûtent plus AUCUNE requête. Mesures réelles : accueil
  16 → 15 requêtes, dizaine 36 → 18 (et 0 contrôle répété ensuite) ;
- `_VERSION_APPLI = "v7.10.1"` ; AUCUN changement de schéma de base de
  données, aucune opération demandée à l'hébergeur.

### 27. v7.10.2 — La vidéo porte son nouveau lien, les paroisses se partagent les intentions, le questionnaire passe par le diocèse 🛕📚📋

- **🛕 Nouveau lien de la vidéo à la demande** (lien changé par l'utilisatrice
  sur l'application, adopté ici pour que les prochains paquets le portent) :
  `LIEN_YOUTUBE_VIDÉO_A_LA_DEMANDE` =
  `https://www.youtube.com/watch?v=hYv04JVIALI&list=RDhYv04JVIALI&start_radio=1`
  (l'ancien `youtu.be/RHrIgEeepO8` disparaît). La carte extrait l'identifiant
  du format `watch?v=` comme de `youtu.be/` : les deux écritures marchent.
- **📚 Les paroisses se voient et se partagent les intentions** (demande :
  « les paroisses ne se voient pas, par conséquent elles ne peuvent pas se
  partager les intentions ») : la réserve était déjà LA MÊME pour tout le
  diocèse (les tirages de l'Espace puisent dedans sans frontière) — ce qui
  manquait, c'est la VUE. Désormais chaque intention en réserve porte le
  NOM DE SA PAROISSE (celle de son équipe, ou celle notée à l'entrée en
  réserve pour les visiteurs — `reserve_lignes_paroisse_nommee`) : la vue
  paroisse (« 🙏 Coins des Intentions » → 📚 Réserve) liste « toutes les
  paroisses » avec 🏘️ sur chaque ligne, et le diocèse reçoit UN MENU
  PROPRE « 📚 Réserve d'intentions » (entre « 📌 Suivi » et « 🕯️ Espace
  spirituel ») avec la grille des 20 N° méd. et la liste étiquetée par
  paroisse. Chacune voit ce que les autres partagent ; la chaîne fait
  circuler le reste.
- **📋 Le questionnaire SOUMIS AU DIOCÈSE** (question : « le questionnaire
  du feuillet n'est-il pas soumis au diocèse ? ») : SI, désormais — la
  même règle que le feuillet (« le Service Communication ne publie JAMAIS
  d'elle-même », v7.8.6). Zone « 1 Bis. » : après les questions, le bloc
  « 📨 Soumettre le questionnaire au diocèse » (résumé lisible des questions
  actives emporté dans la soumission ; statuts 🟡 attente / ✅ validé le…
  / ❌ refusé + motif / 🗓️ programmée, comme le feuillet) ; côté diocèse au
  SAS, la soumission « 📋 Questionnaire du feuillet » se lit (les questions
  s'affichent une à une) et « ✅ Publier » lève le voile (« ❌ Refuser » le
  garde posé, motif communiqué). TANT QUE le diocèse n'a pas validé le mois,
  le questionnaire NE PARAÎT PAS dans l'Espace de Prière
  (`feuillet_questionnaire_publie` en garde de `_render_questionnaire_mensuel`).
  Une correction se resoumet (version corrigée) comme le feuillet. AUCUNE
  nouvelle table : la soumission vit dans `soumissions_comm`
  (type `questionnaire`, convention date_evenement=année / lieu=mois).
- **✍️ Reprise d'une question d'un clic RÉPARÉE** (défaut : « Écris d'abord
  la question. » au moment d'ajouter, obligeant à copier-coller) : la
  question reprise par « ➕ Reprendre » rejoint le champ par SA CLÉ
  (`qf_new_txt`, posée dans la session avant le dessin du champ) — avant,
  la valeur passée en `value` était ignorée quand le champ avait déjà vécu.
  Le clic remplit, on retouche si on veut, « 💾 Ajouter » prend.
- **🔢 La numérotation redevient la nôtre** (proposition adoptée telle
  quelle) : « 2️⃣ bis. Le feuillet mensuel en Équipe » → **« 1. Le feuillet
  mensuel en Équipe »** et « 2️⃣ ter. Le questionnaire du feuillet » →
  **« 1 Bis. Le questionnaire du feuillet »** — l'ancien préfixe « 2️⃣ »
  portait le souvenir des zones 1️⃣/2️⃣/3️⃣ retirées en v7.8.5 (le « 2️⃣ est
  resté » après l'import).
- `_VERSION_APPLI = "v7.10.2"` ; AUCUN changement de schéma de base de
  données (la soumission du questionnaire réutilise `soumissions_comm`),
  aucune opération demandée à l'hébergeur.

### 28. v7.10.3 — La réserve redevient l'affaire des paroisses, le diocèse s'efface 📚

- **Correction de lecture de la v7.10.2 ②** : l'observation « les paroisses
  ne se voient pas, par conséquent elles ne peuvent pas se partager les
  intentions » n'était pas une demande de partage — c'était le rappel du
  principe posé dès la v7.9.10 (« les intentions, c'est une affaire des
  paroisses ») : **les intentions sont une affaire de paroisse, de ses
  membres et de ses visiteurs ; le diocèse n'a rien à voir dedans.**
- **La rubrique « 📚 Réserve d'intentions » QUITTE le menu du diocèse**
  (entre « 📌 Suivi » et « 🕯️ Espace spirituel ») : l'écran et son entrée de
  menu disparaissent. La réserve se lit là où elle vit : dans la vue
  paroisse (« 🙏 Coins des Intentions » → 📚 Réserve) et dans chaque équipe.
- **La vue paroisse reprend sa liste d'origine** : « 🗂️ Intentions en
  réserve — toutes les ÉQUIPES », sans nom de paroisse sur les lignes
  (la fonction d'étiquetage `reserve_lignes_paroisse_nommee`, v7.10.2, est
  retirée). La réserve réunit les intentions des MEMBRES (posées en face de
  chaque membre dans la ⛓️ Chaîne de la dernière séance) et des VISITEURS
  (passées par la 🕯️ Zone du jour) ; lecture seule ici.
- **Rien d'autre ne bouge** : la grille des 20 N° méd. et les compteurs
  restent ceux de la chaîne universelle ; les tirages de l'Espace de
  Prière, la 🕯️ Zone du jour (paroissiale, v7.9.10), les durées de vie
  (visiteur 20 jours, membre jusqu'à la prochaine séance) et le surplus ne
  changent pas. La vidéo (nouveau lien) et le questionnaire soumis au
  diocèse (v7.10.2 ① et ③) restent tels quels.
- `_VERSION_APPLI = "v7.10.3"` ; AUCUN changement de schéma de base de
  données, aucune opération demandée à l'hébergeur.

### 29. v7.10.4 — Le questionnaire vit sa vie après publication, et tout se lit à nouveau 📝🕯️👁️

- **Le parcours du questionnaire, une fois publié** — il paraît sous le
  feuillet (🕯️ Thème → 🔭 Vue d'ensemble), il y reste pendant son mois, et
  il **revient avec son feuillet à la relecture** : à la FIN de la lecture
  du livret (dernière page, comme les exercices au dos d'un livret papier),
  le questionnaire du mois relu attend le lecteur — celui qui n'avait pas
  répondu peut encore répondre, membre (sous son MatLoc) comme visiteur
  (nom choisi). Les réponses nourrissent toujours le MÊME mois.
- **Nouvel onglet « 🕯️ Thème »** dans « 🕊️ Gestion de l'Espace Spirituel →
  📋 Contenu existant », entre « 🙏 Prières / 📖 Méditations » et
  « 🖼️ Galerie + » : la gestion APRÈS publication, mois par mois (feuillet
  du moment comme mois passés). L'onglet montre l'état du mois (feuillet
  publié ? questionnaire voilé/soumis/paru ?), les questions telles que les
  fidèles les voient, et **les réponses reçues question par question** avec
  le carnet Excel. Les retouches de questions restent en « 1 Bis. » (📡
  Communication) ; la parution reste au SAS.
- **Qui voit les réponses ?** La cellule Communication et le diocèse, dans
  cet onglet — jamais les fidèles entre eux : chacun ne retrouve que SES
  réponses (elles l'attendent dans le formulaire, il peut les corriger et
  renvoyer). Elles demeurent mois après mois ; le carnet les emporte à tout
  moment. La lecture des réponses est devenue une fonction partagée : la
  zone « 1 Bis. » et l'onglet « 🕯️ Thème » servent la même.
- **Les textes invisibles sont revenus à la lumière** : l'Administration
  est peinte sur fond blanc et l'Espace de Prière sur fond bleu nuit, mais
  les libellés des champs, les notes, les alertes et les titres d'expanders
  suivaient le mode (clair/sombre) du téléphone — sur un écran en mode
  sombre, les textes de la ⛓️ chaîne d'une séance et du questionnaire
  devenaient invisibles sur blanc ; sur un écran clair, c'était le tour des
  questions dans l'Espace. Chaque espace verrouille désormais SES couleurs
  de lecture (encre bleue sur blanc / clair sur bleu nuit), quel que soit
  le mode du lecteur — les cartes jaunes gardent leur encre foncée (v7.7.4).
- `_VERSION_APPLI = "v7.10.4"` ; AUCUN changement de schéma de base de
  données, aucune opération demandée à l'hébergeur.

### 30. v7.11.0 — L'intention appartient à celui qui est prié, et tout se lit quelle que soit la page ⛓️🕯️

- **L'appartenance des intentions dans la chaîne** — sous chaque maillon
  « X prie pour Y », l'intention affichée est celle de **Y** (la personne
  PRIÉE), lue dans la 📚 réserve à SON N° méd. ; sans intention, la carte
  ne dit plus « ajoutez-la dans la réserve » mais prie le membre PAR SON
  NOM : « ⚠️ {Nom} — N° méd. Y est prié(e) de communiquer son intention au
  responsable. »
- **L'enregistrement d'une séance pose les intentions maillon par maillon**
  (fin de la liste « une zone par membre » qui faisait écrire l'intention
  du prochain en face du mauvais nom — c'est elle qui attribuait à tort les
  intentions dans la réserve) : après la date, l'ordre et les absents, la
  zone « 🕯️ L'intention de {Nom} (N° méd. Y) » apparaît sous chaque
  maillon, et l'intention rejoint la réserve à la hauteur de Y.
- **Pastorale ouverte à tous** : les « présents spirituellement » (hors
  chaîne) ont aussi leur zone d'intention dans l'enregistrement — leurs
  intentions sont accueillies comme celles des visiteurs, à leur N° méd.
- **Les connecteurs de la carte** (« prie pour », « — N° méd. X. ») et les
  textes d'intention portent leur couleur claire : posés sur la carte bleu
  nuit, ils ne devaient plus rien hériter de l'encre foncée de la page.
- **Les libellés du questionnaire restent lisibles sous toutes leurs
  formes** : chaque espace verrouille ses couleurs de lecture pour TOUTES
  les façons que Streamlit a de dessiner un champ (toutes versions), le
  formulaire du questionnaire ne dessine plus de cadre clair dans l'Espace,
  et ce qui s'écrit dans un champ reste foncé sur blanc — à la vitrine
  comme à la fin de la lecture du livret.
- **Onglet « 🕯️ Thème »** (📋 Contenu existant) : l'étiquette « 📝
  questionnaire » ne se pose plus que sur les mois qui portent réellement
  un questionnaire (questions ou soumission) — avant, tous les mois la
  portaient.
- `_VERSION_APPLI = "v7.11.0"` ; AUCUN changement de schéma de base de
  données, aucune opération demandée à l'hébergeur.

### 31. v7.11.1 — L'alerte d'une semaine, les missions en période et en groupes, les dizaines du jour ⏳✈️

- **🔔 L'alerte « nouveau feuillet » vit UNE SEMAINE** (à la demande : «
  maintenir l'alerte pendant une semaine après sa première diffusion ») :
  la fenêtre passe de 45 jours à 7 jours, comptés depuis la PREMIÈRE
  diffusion. Une nouvelle colonne `feuillets_publications.premiere_diffusion`
  est posée UNE FOIS à la première publication ; républications d'une
  version corrigée ne la touchent plus — l'alerte ne rallonge pas et ne
  revient pas. Pendant la semaine, elle revient chaque jour tant qu'elle
  n'est pas marquée lue ce jour-là (mémoire d'un jour inchangée) ; la
  mention porte « en diffusion depuis le JJ/MM/AAAA » (la première
  diffusion, pas la républication).
- **✈️ Les missions se déroulent sur UNE PÉRIODE** : « une mission se
  déroule sur une période débutant le lendemain de la dernière séance de
  prière mensuelle jusqu'à la prochaine séance ». Le formulaire propose
  d'office le lendemain de la dernière séance enregistrée (chaîne de
  séance de l'équipe) ; la fin se laisse vide = « jusqu'à la prochaine
  séance » — dès que la séance suivante est enregistrée, la période se
  referme toute seule sur sa date (nouvelle fonction
  `mission_prochaine_seance`). Nouvelles colonnes `missions.date_debut`,
  `date_fin` (retro-remplies avec `date_mission`) ; les fiches d'envoi et
  de rapport affichent « 🗓️ Période : du … au … / jusqu'à la prochaine
  séance ».
- **✈️ L'équipe se scinde en groupes** : chaque mission porte son groupe
  (A…Z, choisi à la préparation) et l'onglet se range par groupe — « ✈️
  Les missions de l'équipe : groupe A », « groupe B », … Les missions
  anciennes sans groupe rejoint le groupe A (rien ne se perd). La fiche
  d'envoi porte « Équipe : … — groupe X ».
- **📿 Dizaines du jour (onglet 💬 WhatsApp)** : réponse directe à «
  peut-on alerter une personne sur son téléphone pour faire sa dizaine ?
  » — la liste de ceux qui n'ont PAS encore pointé leur dizaine du jour,
  chacun avec son bouton « 📱 Rappeler sa dizaine » : le message WhatsApp
  s'ouvre déjà écrit chez le membre (le canal qui marche partout,
  aujourd'hui, sans rien installer). Tout le monde a prié ? Un vert «
  merci pour la chaîne » le dit.
- `_VERSION_APPLI = "v7.11.1"` ; changement de schéma : 3 colonnes
  `missions` + 1 colonne `feuillets_publications` (migrations idempotentes,
  rétro-compatibles — aucune opération demandée à l'hébergeur).

### 32. v7.12.0 — La chaîne alerte les téléphones : rondes 4×/jour, visiteurs dénombrés, fiches en PDF 🔔📅📄

- **⏰ La ronde des dizaines (4 fois par jour)** : à **06h00, 12h00,
  18h00 et 21h00** (heures de Côte d'Ivoire — l'hébergeur tourne déjà à
  l'heure ivoirienne), la liste de ceux qui n'ont pas encore fait leur
  dizaine est mise à jour et le rappel part. Mécanisme « lazy cron »
  comme les publications programmées : le premier chargement de page
  après l'heure dite sert la ronde, une seule fois (réclamation en base
  `dizaines_rondes`). L'onglet 💬 WhatsApp affiche la bannière des rondes
  (dernière mise à jour + comptages + rappels partis).
- **🕯️ Les visiteurs de la chaîne rejoignent la liste** : tout visiteur
  ayant confié une intention (zone du jour non traitée + réserve active
  et publiée) doit sa dizaine chaque jour ; il est identifié comme les
  membres — les anonymes portent **« Anonyme 1, Anonyme 2, Anonyme 3, … »
  selon l'index du dénombrement** (l'ordre d'entrée dans la chaîne, stable
  d'un jour à l'autre ; un rang par jour de naissance). Le contact laissé
  à l'envoi voyage désormais avec l'intention (colonne
  `intentions_reserve.auteur_contact`, rétro-remplie depuis la zone du
  jour) : le bouton « 📱 Rappeler sa dizaine » s'ouvre chez le visiteur.
- **📅 Le rappel calendrier (.ics)** — dans la carte « 🔔 Me rappeler ma
  dizaine sur mon téléphone » de l'accueil de l'Espace (membres ET
  visiteurs) : un fichier rendez-vous récurrent « 📿 Ma dizaine du jour »
  à ajouter UNE fois (heure au choix : 06h/12h/18h/21h) — le téléphone
  sonne chaque jour, même sans internet.
- **🔔 La notification de l'application (push PWA)** — même carte : le
  téléphone qui dit oui est noté (`push_abonnements`) ; les rondes lui
  envoient le rappel tant que sa dizaine attend. Clés VAPID nées et
  vivant en base (`parametres_app`) — RIEN à configurer. Le service
  worker `static/sw.js` porte la notification ; sur iPhone, l'appli doit
  être installée (iOS 16.4+). Le jour de naissance dévoilé (dizaine ou
  intention) alimente l'abonnement (`push_abonnement_note_jrnais`) pour
  ne pas réveiller qui a déjà prié.
- **📄 La fiche de mission s'enregistre en PDF** : bouton DÉDIÉ
  « 📄 Enregistrer la fiche en PDF » — un vrai fichier A4 (en-tête du
  mouvement, bandeau d'identité, tableau des envoyés, deux signatures,
  pied) ; dépendance `reportlab` ajoutée. L'aperçu vit DANS SON CADRE
  (document autonome à hauteur juste) : le bouton 🖨️ posé dedans
  n'imprime que la fiche, jamais le reste de la page.
- **✈️ Missions — retouches** : le groupe se choisit de **A à J** (12
  membres max par équipe — 20 à Notre Dame de l'Assomption : même par
  groupes de 2, J suffit) ; le titre identifie l'équipe et le compteur
  disparaît : « ✈️ Les missions de l'équipe 3 : groupe A » ; la fiche de
  rapport porte les DEUX signatures « Le Responsable du groupe » et
  « Le Responsable de l'équipe ».
- `_VERSION_APPLI = "v7.12.0"` ; changement de schéma : colonne
  `intentions_reserve.auteur_contact` + tables `dizaines_rondes`,
  `push_abonnements`, `parametres_app` (migrations douces idempotentes —
  aucune opération demandée à l'hébergeur).

### 33. v7.12.1 — Les messages des membres portent le lien de SON espace (MatLoc) 🙏🌹

- **📿 Le message WhatsApp des dizaines reformulé comme demandé** — pour
  chaque membre en attente, le responsable ouvre un message déjà écrit :

  ```
  Bonjour Ahua Innocent 🙏
  Un petit rappel fraternel : ta dizaine du jour t'attend 🌹

  https://…streamlit.app/?espace=1&matloc=GBA-OISOJ

  Que la Vierge Marie veille sur toi! 🙏
  ```

  Le membre est salué EN ENTIER (nom + prénom) ; la rose 🌹 remplace le
  chapelet sur la ligne du rappel ; et surtout le lien porte **son
  MatLoc** (`?espace=1&matloc=…`) : en le touchant, il arrive DIRECTEMENT
  sur son espace, sans taper son code. Un membre sans MatLoc reçoit le
  lien public — personne n'est exclu.
- **🕯️ Les visiteurs suivent la même voix** : « Bonjour Anonyme 1 🙏 »
  (ou son nom signé), même rappel, même clôture — le lien reste public,
  le visiteur n'ayant pas de MatLoc.
- **🔔 La notification de la ronde s'accorde** : même corps (« Un petit
  rappel fraternel… »), même clôture ; elle portait déjà le lien MatLoc
  de l'abonnement.
- `_VERSION_APPLI = "v7.12.1"` ; aucun changement de schéma.

### 34. v7.12.2 — Les raccourcis, pour de bon

Le dossier des raccourcis est refermé une fois pour toutes : la page
d'installation ne propose plus seulement le geste du menu, elle **pose une
vraie application**.

- **📲 Le bouton or « Installer l'application »** : quand le téléphone
  sait installer (Android, Chrome), un vrai bouton apparaît tout seul en
  haut de la page d'installation — un toucher, une acceptation, et
  l'application est posée : icône au bon visage (chapelet doré / clé
  dorée), ouverture plein écran, directement dans l'Espace ou la
  connexion.
- **🕊️ La page d'installation s'efface ensuite** : quand on ouvre le
  raccourci, elle revoit immédiatement vers l'Espace de Prière (en
  conservant le fidèle mémorisé et sa paroisse) — la carte d'installation
  ne réapparaît jamais après la pose. Idem côté administration.
- **👁️ Veille navigateur intégré** : ouverte depuis WhatsApp, Instagram
  ou Facebook, la page l'annonce et explique le premier geste (« ⋮ →
  Ouvrir dans le navigateur ») — le raccourci ne se pose que depuis le
  navigateur.
- **🔔 Le passeur des rappels s'installe partout** : la page
  d'installation comme l'Espace de Prière installent désormais le service
  worker des rondes dès l'arrivée (silencieusement, sans jamais demander
  la permission) — le téléphone tient une « vraie application », et les
  rondes 06h00 · 12h00 · 18h00 · 21h00 peuvent frapper même app fermée.
- **Versionnage** : manifestes et icônes passent à `?v=7122` (les
  téléphones relisent noms et visages au prochain ajout), le sw.js
  enregistré passe à `?v=7122` des deux côtés.
- `sw.js` : un nouveau maillon « passeur » (chaque demande file au
  réseau, rien n'est retenu) — c'est lui qui rend la page « installable »
  aux yeux du téléphone ; rien d'autre ne change pour l'application.
- `_VERSION_APPLI = "v7.12.2"` ; aucun changement de schéma.

### 35. v7.12.3 — Le dossier invisible retrouvé

La page d'installation tournait le dos aux téléphones : chaque demande
de fichier (carte d'installation, manifeste, icônes, passeur) recevait
en retour la coquille de l'application — d'où la page blanche. Cause :
le réglage qui active le service du dossier `static/` voyage dans un
dossier qui commence par un point (`.streamlit/`) ; invisible dans les
sélections ordinaires, il s'est égaré au versement dans le dépôt.

- **Le réglage est dans l'app depuis v7.8.14** : rien à changer dans le
  code — il faut seulement que le dossier `.streamlit/` (avec son
  `config.toml`) soit présent à la racine du dépôt ;
- **Le geste de réparation** : sur GitHub, « Add file → Create new
  file », nommer `.streamlit/config.toml` (le point crée le dossier),
  coller le contenu et valider — l'application redémarre toute seule ;
- **La chaîne de vérification** : le lien violet « page d'installation »
  ouvre la carte dorée en 2-3 secondes, le bouton or « 📲 Installer
  l'application » attend en haut ; le badge de l'Espace affichera
  v7.12.3 après le versement de ce paquet ;
- `_VERSION_APPLI = "v7.12.3"` ; aucun changement de schéma ; aucun
  changement de comportement pour les membres.

### 36. v7.12.4 — La note au mot près, et les intentions qui se remplacent

- **La note de la ⛓️ Chaîne de la dernière séance au mot près** :
  « le voisin de droite devient le "prochain" de celui de la gauche »,
  « L'ordre peut varier d'une séance à l'autre », et le paragraphe du
  remplacement — « une intention de la chaîne de la dernière séance
  remplace l'ancienne et reste visible dès son enregistrement chez le
  N° méd. qui la porte — c'est elle qui pourvoit la 📚 réserve
  d'intentions ». 🤫 Les intentions se portent, elles ne se commentent
  pas.
- **✏️ Mettre à jour les intentions de la dernière séance** : sous la
  carte de la chaîne en vigueur, un nouvel espace reprend maillon par
  maillon « X prie pour Y » avec, préremplie, l'intention que Y porte
  déjà — ce qui change est remplacé (l'ancienne s'efface, la nouvelle
  devient visible aussitôt sous le maillon), le surplus du N° méd.
  reste intact, et rien à refaire pour ce qui ne bouge pas.
  `database.py` gagne `remplacer_intention_reserve` (remplacement en
  place : l'ordre de la réserve est préservé, le surplus ne bouge pas ;
  s'il n'y a rien en place, l'intention est posée).
- `_VERSION_APPLI = "v7.12.4"` ; aucun changement de schéma.

### 37. v7.13.0 — Les règles de la ⛓️ Chaîne au complet, le livre qui se termine en merci, et l'icône qui ouvre le bon côté

- **⛓️ Les règles de la Chaîne de la dernière séance, encodees** :
  * une intention de la Chaîne est **d'office prise en charge** (elle
    reste visible dès son enregistrement, sans attendre le lendemain) ;
  * une intention de la Chaîne d'une équipe **ne peut pas être portée par
    un membre d'une autre équipe**, quand bien même ils auraient les N°
    méd. identiques — le tirage du membre est désormais limité à la
    réserve de SON équipe (et aux intentions sans équipe) ;
  * la réserve est pourvue par les intentions de la Chaîne de l'équipe et
    de celles des visiteurs ; elle **nourrit** l'intention du prochain du
    visiteur (en premier), les présents spirituellement (en plus de leur
    héritage), et le surplus chez les membres présents physiquement
    **tant qu'il provient d'un visiteur** ;
  * l'équipier absent garde **son héritage** — l'intention qu'il portait à
    sa dernière présence physique — jusqu'à son retour : à
    l'enregistrement d'une séance, l'intention portée est capturée AVANT
    la libération et s'attache à lui sans échéance ; celui qui revient
    dans la chaîne repart à neuf. Le membre EN chaîne lit désormais,
    à chaque ouverture du livret, l'intention EN PLACE au N° méd. de son
    prochain (le remplacement se voit aussitôt) ;
  * la note de la carte ⛓️ porte les règles au mot près ; la carte ne
    montre plus que les intentions de l'équipe (et `remplacer_intention_
    reserve` ne touche jamais la rangée d'une autre équipe) ;
  * colonne `source` sur `intentions_reserve` ('chaine' / 'visiteur',
    migration idempotente) + `fiche_membre_chaine`, `contexte_chaine_
    membre`, `_pose_heritages_equipe`, `serie_dizaines_membre`.
- **🕯️ Lignes d'intercession sans coquille ni redondance** : quand
  l'intention nomme déjà sa bénéficiaire (« pour Jeanne A. … »), la ligne
  ne répète plus « pour {qui} : » — fini le « pour AKA Jeanne : pour
  Jeanne A. … ». Le livret comme l'aperçu paroisse passent par le même
  helper `ligne_intercession` (components.py).
- **📖 Livret « 🕯️ Un jour, une dizaine » réorganisé** : la page du
  pointage (« 📿 La chaîne compte sur Toi » + bouton « ✅ Merci Sainte
  Mère pour ton aide de ce jour ! ») devient l'AVANT-dernière, réduite à
  la présence du jour et à la gratitude ; une NOUVELLE dernière page
  accueille « 📿 Ta dizaine est capitale pour la chaîne — Merci pour ta
  fidélité! — N dizaine(s) ce mois — À demain! 🕊️ » (sans les textes de
  prière) quand le bouton ✅ (ou « ✕ Terminer ») a été touché ; l'expander
  « 📿 Tu as prié hors ligne ? » passe en veilleuse
  (`_RECUP_HORS_LIGNE_ACTIVEE = False`).
- **📿 Ma mémoire du tableau, cadre doré dans le fil** : le membre voit
  dans le fil de l'actualité sa propre ligne du tableau de la chaîne —
  les 14 derniers jours (✅/·), le compteur du mois et la flamme des
  jours de suite (`_carte_memoire_membre` ; le fil des visiteurs ne
  change pas).
- **🙏 « Vos intentions à une équipe » extériorisée** : la carte dorée
  interne devient le visage du dépliant replié — c'est elle que le
  visiteur voit avant d'ouvrir (la bannière est hissée dans le titre du
  dépliant, le vieux libellé texte s'efface).
- **▷ Consignes vivantes des dépliants** : « cliquez pour replier ▴ »
  déplié, « cliquez pour déplier ▾ » plié — sur le dépliant de découverte
  comme sur la carte des intentions.
- **📲 L'icône PWA ouvre le bon côté, même quand le statique trébuche** :
  le manifeste voyage DANS la page (URI data:, adresses absolues, icônes
  incorporées) — le raccourci posé depuis l'Espace ouvre l'Espace
  (?espace=1) et porte le bon visage, même si /app/static/* répond mal ;
  version du manifeste 7130.
- `_VERSION_APPLI = "v7.13.0"` ; schéma : colonne `source` ajoutée à
  `intentions_reserve` (ALTER doux idempotent, aucune autre migration).

### 38. v7.13.1 — La programmation retrouvée, le parchemin qui porte le pointage

- **⏰ LA PROGRAMMATION EN PANNE — trouvée et réparée** : le conducteur de
  base distante (`libsql-experimental`, réinstallé à sa dernière version
  lors du redéploiement de la réparation) rapporte un `rowcount` cumulatif
  non fiable ; la réclamation anti-course du réveil (« != 1 ») se croyait
  toujours devancée et le réveil devenait MUET — les publications
  programmées n'étaient plus jamais effectuées. Désormais la réclamation
  se fait PAR JETON relu (jamais par rowcount), le réveil journalise son
  compte (dûes / publiées) et rend son compte à l'appelant ; les réservations
  de rondes de rappels, le retrait en réserve et le compte des intentions
  libérées passent eux aussi PAR LECTURE. `libsql-experimental` est épinglé
  (`==0.0.55`). Un bouton « ⏰ Réveiller la programmation maintenant »
  accompagne « 🗓️ Programmées » : il déclenche le réveil à la main et dit
  ce qu'il a fait.
- **📖 Le parchemin jaune porte le pointage** : la dernière page de contenu
  du livre (le GLORIA PATRI et ses deux invocations — ou la Salve Regina le
  jour du N° 20) accueille SOUS la prière « 📿 La chaîne compte sur Toi » et
  le bouton « ✅ Merci Sainte Mère de Dieu pour ton aide de ce jour ! » —
  sans Suivant, sans ✕ Terminer, sans expander. Le clic ouvre la page du
  remerciement (« 📿 Ta dizaine est capitale… — À demain! 🕊️ ») dont le
  bouton « ✕ Terminer » ramène au fil de l'actualité. La sortie « déjà
  marquée » est prévue (message + ✕ Terminer).
- **📿 « Mémoire de mes dizaines »** (ex « Ma mémoire du tableau ») : la
  carte dorée se pose entre la carte de bienvenue et « 📿 Ta dizaine du
  jour », les jours les plus récents d'abord (✨03/11 → 02/11 → …).
- **🙏 La carte « Vos intentions à une équipe » n'est plus un pis-aller** :
  le titre est DORÉ dès le premier rendu (CSS `:has` — plus d'attente du
  script), et le script patiente jusqu'à 10 s pour hisser la carte dorée
  complète en titre du dépliant.
- **🌹 Les textes des rappels** (membre : « …Va sur ta page perso en
  cliquant sur ce lien 🌹 » ; visiteur : « …Clique sur ce lien 🌹 ») —
  posés directement dans le dépôt, confirmés.
- `_VERSION_APPLI = "v7.13.1"` ; aucun changement de schéma.

## 🛠️ Maintenance

- Les migrations de schéma sont **idempotentes** : elles s'exécutent une fois
  par session sans risque (`safe_migrate` ignore les doublons).
- « 🗑️ Réinitialiser » (diocèse) purge TOUTES les données opérationnelles —
  confirmation par saisie du mot « SUPPRIMER ».
- Sauvegarde : pour Turso utilisez `turso db export` ; en local copiez
  `gestion_religieuse.db`.
