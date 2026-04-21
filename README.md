<p align="center">
  <a href="#"><img alt="HACS" src="https://img.shields.io/badge/HACS-Custom-blue.svg"></a>
  <a href="#"><img alt="Home Assistant" src="https://img.shields.io/badge/Home%20Assistant-2024.6%2B-41BDF5"></a>
  <a href="#"><img alt="License" src="https://img.shields.io/badge/License-MIT-green.svg"></a>
  <a href="https://github.com/austyl/ofoehn-poolpilot-ha/actions/workflows/validate.yml"><img alt="HACS Validate" src="https://github.com/austyl/ofoehn-poolpilot-ha/actions/workflows/validate.yml/badge.svg"></a>
  <a href="https://github.com/austyl/ofoehn-poolpilot-ha/actions/workflows/hassfest.yml"><img alt="Hassfest" src="https://github.com/austyl/ofoehn-poolpilot-ha/actions/workflows/hassfest.yml/badge.svg"></a>
</p>

# O'Foehn PoolPilot – Home Assistant (HACS)

Pilotage **local** de la PAC piscine **O'Foehn** via CGI *PoolPilot* (accueil.cgi, super.cgi, getReg.cgi, setReg.cgi, changeOnOff.cgi, toggleE.cgi).  
Version **v0.2.2** — amélioration de la fiabilité réseau, ajout d'un logo HACS, enrichissement des diagnostics et détection locale de l'IP au moment de la configuration.

## ✨ Fonctionnalités
- Entité **Climate** (OFF/AUTO/CHAUD/FROID, consigne pas de 0,5 °C)
- Capteurs : **Eau In / Eau Out / Air**
- Capteurs diagnostiques avancés : états, module, firmware, numéro de série, MAC, options, températures, pressions et relais
- Capteurs *Raw* : **Super / Accueil / Reg** (valeur affichée limitée à 255 caractères, réponse complète dans les attributs `raw`, `plain_text` et `lines`)
- Switchs : **PAC – Alimentation** & **Éclairage**
- **Config Flow** (IP/Port + Auth) avec tentative de détection locale automatique de l'IP
- Gestion plus robuste des micro-coupures réseau grâce aux retries et au dernier état valide conservé

## 🔐 Authentification
- **NONE** : aucune auth
- **BASIC** : HTTP Basic Auth (user/pass)
- **QUERY** : identifiants injectés en **query string** et payloads
- **COOKIE** : login sur `login_path` (POST par défaut), cookies réutilisés, relogin auto sur 401/403

## 🧭 Détection
Lors de l'ajout de l'intégration, le formulaire tente de détecter automatiquement l'IP de la PAC sur le sous-réseau local de Home Assistant et préremplit le champ si une réponse O'Foehn valide est trouvée.

## ⚙️ Indices DONNEE# (par défaut)
- Eau In `5`, Eau Out `6`, Air `7`, Lumière `16`, Alimentation `24`.  
Personnalisables via **Options**.

## 🚀 Installation via HACS
1. HACS → Dépôts personnalisés → Ajouter cet entrepôt (catégorie **Intégration**)
2. Installer, puis **Redémarrer** Home Assistant
3. **Paramètres → Appareils & services → Ajouter une intégration** → O'Foehn PoolPilot → saisir IP/Port/Auth

## 🛡️ Sécurité
HTTP en clair : isolez la PAC (VLAN/IoT). Évitez le mode `QUERY` si possible (identifiants dans l'URL).

## 🐞 Debug / Regex
Activer les logs détaillés dans `configuration.yaml` :

```yaml
logger:
  default: info
  logs:
    custom_components.ofoehn_poolpilot: debug
```

Une fois activée, la réponse complète est disponible dans l'attribut `raw` et également enregistrée dans les logs.

Exemples de regex :

- Température d'eau : `r"DONNEE5=([0-9.]+)"` (indice `5` par défaut pour `Eau In`, à adapter selon votre configuration).
- Consigne : `r"^([0-9.]+),"` (première valeur renvoyée par `getReg.cgi`).

## 📦 Publication HACS
Le dépôt est prêt pour une publication HACS classique en dépôt personnalisé.

Pour une inclusion dans les dépôts par défaut HACS, il faut en plus :
- des workflows `hacs/action` et `hassfest` au vert
- une GitHub Release publiée
- une PR vers `hacs/default`
