<p align="center">
  <a href="#"><img alt="HACS" src="https://img.shields.io/badge/HACS-Custom-blue.svg"></a>
  <a href="#"><img alt="Home Assistant" src="https://img.shields.io/badge/Home%20Assistant-2024.6%2B-41BDF5"></a>
  <a href="#"><img alt="License" src="https://img.shields.io/badge/License-MIT-green.svg"></a>
</p>

# O'Foehn PoolPilot – Home Assistant (HACS)

Pilotage **local** de la PAC piscine **O'Foehn** via CGI *PoolPilot* (accueil.cgi, super.cgi, getReg.cgi, setReg.cgi, changeOnOff.cgi, toggleE.cgi).  
Version **v0.2.1** — Ajout de l'**authentification**: NONE / BASIC / QUERY / COOKIE.

## ✨ Fonctionnalités
- Entité **Climate** (OFF/AUTO/CHAUD/FROID, consigne pas de 0,5 °C)
- Capteurs : **Eau In / Eau Out / Air**
- Switchs : **PAC – Alimentation** & **Éclairage**
- **Config Flow** avec test de connexion, prévention des doublons et options avancées
- Exemples Lovelace (`examples/`)

## 🔐 Authentification
- **NONE** : aucune auth
- **BASIC** : HTTP Basic Auth (user/pass)
- **QUERY** : identifiants injectés en **query string** et payloads
- **COOKIE** : login sur `login_path` (POST par défaut), cookies réutilisés, relogin auto sur 401/403

## ⚙️ Options avancées
- Eau In `5`, Eau Out `6`, Air `7`, Lumière `16`, Alimentation `24`.  
Personnalisables via **Options**.
- Intervalle de rafraîchissement ajustable de `5` à `300` secondes.

## 🚀 Installation via HACS
1. HACS → Dépôts personnalisés → Ajouter cet entrepôt (catégorie **Intégration**)
2. Installer, puis **Redémarrer** Home Assistant
3. **Paramètres → Appareils & services → Ajouter une intégration** → O'Foehn PoolPilot → saisir IP/Port/Auth

## 🧩 Exemples Lovelace
Voir `examples/` (full et compact) : jauges Eau In/Out/Air, carte Thermostat, historique 24 h, boutons PAC/Éclairage.

## 🛡️ Sécurité
HTTP en clair : isolez la PAC (VLAN/IoT). Évitez le mode `QUERY` si possible (identifiants dans l'URL).
