# -*- coding: utf-8 -*-
"""v7.8.16 — Compatibilité HTML centralisée (anti-dépréciation).

L'API `st.components.v1.html` est dépréciée : les journaux Streamlit Cloud
affichent « Please replace st.components.v1.html with st.iframe » (l'API
sera retirée après 2026-06-01). TOUT le rendu HTML/JS de l'application
(scripts invisibles de mesure, injection PWA, lecteurs, cadre doré…)
passe désormais par CE module unique :

  - Streamlit récent (1.66+)  → `st.iframe(body, height=...)` ;
  - Streamlit ancien          → repli automatique `components.v1.html`.

Utilisation :
    from stcompat import comp_html
    comp_html("<script>…</script>", height=0)

POUR REVENIR EN ARRIÈRE : remplacez le corps de `comp_html` par un simple
`from streamlit.components.v1 import html as comp_html` — les avertissements
de dépréciation réapparaîtront dans les journaux (aucun impact visuel)."""
import streamlit as st

try:
    from streamlit import iframe as _st_iframe

    def comp_html(body, height=None):
        """Rend un bloc HTML/JS dans la page — via `st.iframe` (Streamlit 1.66+).

        ⚠️ `st.iframe` REFUSE height=0 (StreamlitInvalidHeightError) : les
        scripts « invisibles » (mesure d'entête, injection PWA, pose du cadre
        doré) sont donc rendus avec une hauteur minimale de 1 px — les scripts
        y exécutent bien `window.parent.document` (comportement validé depuis
        la v7.6.8)."""
        _h = height if isinstance(height, int) and height > 0 else 1
        return _st_iframe(body, height=_h)

except (ImportError, AttributeError):
    # Streamlit ancien : l'API historique (aucun avertissement dans ces versions).
    try:
        from streamlit.components.v1 import html as _comp_html_fb

        def comp_html(body, height=None):
            return _comp_html_fb(body, height=height)
    except ImportError:
        def comp_html(body, height=None):
            return None
