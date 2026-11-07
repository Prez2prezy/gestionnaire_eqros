# -*- coding: utf-8 -*-
"""v7.14.1 — Compatibilité HTML centralisée (anti-dépréciation, CORRIGÉE).

HISTOIRE DE LA PANNE (constatée au banc d'essai, Chrome réel + CDP) :
  - v7.6.8 → v7.13.x : rendu par `components.v1.html` — son iframe laissait
    passer `window.parent.document` : l'injection PWA touchait la vraie page.
  - v7.8.16 : bascule vers `st.iframe` (1.66+) pour faire taire les
    avertissements de dépréciation. iframe ISOLÉE : le script ne voit plus
    le document parent, l'injection se perd dans une iframe fantôme — la
    page n'a plus NI lien manifeste NI icônes, et Chrome pose le raccourci
    avec le visage par défaut : le bateau Streamlit. (v7.14.0, qui livrait
    pourtant un manifeste statique parfait, a échoué pour cette seule
    raison : le manifeste était bien servi en 200 application/json, mais le
    lien vers lui n'était jamais posé dans la page.)
  - v7.14.1 : retour à `components.v1.html` (toujours disponible en 1.67 —
    validé au banc). Les avertissements de dépréciation réapparaissent dans
    les journaux : ils sont cosmétiques. La chaîne PWA passe AVANT tout.

POUR REVENIR EN ARRIÈRE : remplacez le corps de `comp_html` par un simple
`from streamlit.components.v1 import html as comp_html`."""
import streamlit as st

try:
    # v7.14.1 — L'IFRAME HISTORIQUE : la seule dont le script atteint le
    # document de la page (window.parent.document). Sans elle, ni favicon,
    # ni manifeste, ni icône — l'icône Streamlit revient sur les téléphones.
    from streamlit.components.v1 import html as _comp_html_fb

    def comp_html(body, height=None):
        """Rend un bloc HTML/JS DANS la page (accès parent garanti)."""
        return _comp_html_fb(body, height=height if height is not None else 0)

except ImportError:
    # Repli ultime si Streamlit retire un jour components.v1 : st.iframe
    # (l'injection PWA ne passera plus — prévoir un autre canal avant).
    try:
        from streamlit import iframe as _st_iframe

        def comp_html(body, height=None):
            _h = height if isinstance(height, int) and height > 0 else 1
            return _st_iframe(body, height=_h)
    except (ImportError, AttributeError):
        def comp_html(body, height=None):
            return None
