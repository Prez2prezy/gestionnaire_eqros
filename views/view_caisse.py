# ====================================================================
# views/view_caisse.py — v7.16.7 — LES CAISSES HORS DES ENTITÉS
# VERSION 7.16.7
# La paroisse et le diocèse ont leur caisse : PAS en nouvelle rubrique
# ni en nouvelle section dans les vues des entités — les trésoreries
# existent EN-DEHORS des entités, à la manière de la cellule de
# communication pour le diocèse : un compte propre, une maison propre.
#
# Le trésorier gère (il confirme les déclarations, il expédie les
# cotisations) ; le responsable suit de près depuis sa propre maison
# (état, historique, relances) et accorde l'autorisation : le compte
# du trésorier se désigne chez lui — chez la paroisse (« 🏘️ Ma
# paroisse »), au diocèse (« 🔐 Gérer les accès »).
#
# Deux maisons, une seule vue :
#   show_caisse("paroisse") — rôle tresorier_paroisse (paroisse_id)
#   show_caisse("diocese")  — rôle tresorier_diocese  (diocese_id)
#
# La maison porte « 💰 Versement » — les déclarations adressées à SA
# trésorerie (« ⛪ Trésorerie de la paroisse » / « 🏘️ Trésorerie du
# diocèse ») se confirment ici et le registre ne dit réglé que par
# elle — et « ✨ Cotisations diverses » — l'expédition de la maison :
# toutes les équipes de la paroisse / toutes les paroisses du diocèse
# ou certaines, ⛓️ Obligatoire / 🕊️ À choix avec son échéance. Chez
# l'équipe, une déclaration « paroisse » ou « diocèse » campe pour
# information seule, sans aucun geste. Le jour du paiement en ligne,
# il posera le règlement à la place de la confirmation, sans rien
# casser.
# Marqueurs : Ctrl+F → "VERSION 7.16.7", "show_caisse".
# ====================================================================
import streamlit as st
from database import c
from services import (get_periode_pastorale, periode_affichage,
                      afficher_messages_flash)
from components import maison_versement, formulaire_expedition_zone

# Les maisons — libellés et clefs de l'état, identiques à ceux portés
# depuis la v7.16.6 : les sessions ouvertes ne perdent rien en chemin.
MAISONS = {
    "paroisse": {
        "menu": "💼 Caisse de la paroisse",
        "versement": "💰 Versement — la maison de la paroisse",
        "accroche": "Le trésorier de la paroisse gère la caisse — le "
                    "registre ne dit réglé que par cette maison.",
        "origine": "caisse_paroisse",
        "role": "tresorier_paroisse",
        "cle_portee": "paroisse_id",
    },
    "diocese": {
        "menu": "💼 Caisse du diocèse",
        "versement": "💰 Versement — la maison du diocèse",
        "accroche": "Le trésorier du diocèse gère la caisse — le registre "
                    "ne dit réglé que par cette maison.",
        "origine": "caisse_diocese",
        "role": "tresorier_diocese",
        "cle_portee": "diocese_id",
    },
}


def _bandeau_caisse(titre, accroche):
    """Le bandeau d'entrée de la maison (le même esprit que la cellule
    communication : une maison reconnaissable dès la première seconde)."""
    st.markdown(
        '<div style="background:linear-gradient(135deg,#1A237E 0%,#283593 100%);'
        ' padding:18px; border-radius:15px; text-align:center; margin-bottom:15px;">'
        '<div style="color:#FFD700; font-size:1.15rem; font-weight:bold;">'
        + titre + '</div>'
        '<div style="color:#e8eaf6; font-size:0.85rem; margin-top:4px;">'
        + accroche + '</div></div>', unsafe_allow_html=True)


def show_caisse(zone):
    """LA MAISON DE LA CAISSE — hors des entités. `zone` vaut
    « paroisse » ou « diocèse » : la porte ne s'ouvre qu'au rôle du
    trésorier de CETTE maison (tresorier_paroisse / tresorier_diocese),
    porteur de sa clé (paroisse_id / diocese_id)."""
    maison = MAISONS.get(zone)
    if not maison:
        st.error("Caisse inconnue — reviens en arrière et réessaie.")
        st.stop()

    # LA PORTE : le rôle du trésorier de cette maison, et sa clé portée.
    if st.session_state.get('role') != maison["role"]:
        st.warning("💼 Cette caisse s'ouvre avec le compte de son "
                   "trésorier — l'autorisation se demande auprès du "
                   "responsable de la maison.")
        st.stop()

    cle_portee = st.session_state.get(maison["cle_portee"])
    if zone == "paroisse" and not cle_portee:
        st.warning("La caisse ne trouve pas sa paroisse — reconnecte-toi "
                   "ou demande au responsable de rouvrir l'accès.")
        st.stop()

    # Le nom de la maison (celui qui s'affiche, rien d'autre).
    if zone == "paroisse":
        _ma = c.execute("SELECT nom FROM paroisses WHERE id=?",
                        (cle_portee,)).fetchone()
        nom_maison = _ma[0] if _ma and _ma[0] else "paroisse"
    else:
        _ma = c.execute("SELECT nom FROM diocese WHERE id=1").fetchone()
        nom_maison = _ma[0] if _ma and _ma[0] else "Diocèse"

    _bandeau_caisse(f"{maison['menu']} — {nom_maison}", maison["accroche"])
    afficher_messages_flash()

    # LA RUBRIQUE UNIQUE — la caisse, rien d'autre : le trésorier
    # n'ouvre ni les équipes, ni les membres, ni le suivi (le même
    # esprit que la rubrique unique du 💼 Trésorier d'équipe).
    menu = st.sidebar.radio("Navigation", [maison["menu"]], key="nav_cais")

    st.caption("🕊️ Chez l'équipe, une déclaration « paroisse » ou "
               "« diocèse » campe pour information seule — elle se "
               "confirme ICI, dans sa maison à elle. Le jour du "
               "paiement en ligne, il posera le règlement à la place "
               "de la confirmation, sans rien casser.")

    # L'année de travail de la maison (le même sélecteur que la caisse
    # d'équipe : le trésorier peut encore vendre une année passée).
    annee_pastorale_en_cours = get_periode_pastorale()[0]
    annee = st.number_input("Année de début", 2020, annee_pastorale_en_cours,
                            annee_pastorale_en_cours)
    st.write(f"**Période :** {periode_affichage(annee)}")
    st.markdown("---")

    # LES DEUX PIÈCES DE LA MAISON — les mêmes que celles portées par
    # la v7.16.6, à la clef près : « 💰 Versement » d'abord (les
    # déclarations adressées à SA trésorerie se confirment ici), puis
    # « ✨ Cotisations diverses » (l'expédition de la maison).
    maison_versement(dest_code=zone,
                     titre=maison["versement"],
                     annee=annee,
                     paroisse_id=cle_portee if zone == "paroisse" else None,
                     key_prefix=("mvpar" if zone == "paroisse" else "mvdio"))
    st.markdown("---")
    formulaire_expedition_zone(zone=zone, annee=annee,
                               key_prefix=("exppar" if zone == "paroisse"
                                           else "expdio"),
                               paroisse_id=cle_portee if zone == "paroisse"
                               else None,
                               origine=maison["origine"])
