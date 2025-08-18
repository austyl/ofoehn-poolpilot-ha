<p align="center">
  <a href="https://github.com/jfbrassens/ofoehn-poolpilot-ha/releases"><img alt="Release" src="https://img.shields.io/github/v/release/jfbrassens/ofoehn-poolpilot-ha"></a>
  <a href="https://github.com/hacs/integration"><img alt="HACS Custom" src="https://img.shields.io/badge/HACS-Custom-blue.svg"></a>
  <a href="https://www.home-assistant.io/"><img alt="Home Assistant" src="https://img.shields.io/badge/Home%20Assistant-2024.6%2B-41BDF5"></a>
  <a href="https://github.com/jfbrassens/ofoehn-poolpilot-ha/blob/main/LICENSE"><img alt="License" src="https://img.shields.io/badge/License-MIT-green.svg"></a>
</p>

# O'Foehn PoolPilot – Intégration Home Assistant (HACS)

**But :** piloter une pompe à chaleur piscine **O'Foehn** via les endpoints HTTP/CGI compatibles *PoolPilot*.
Aucune configuration YAML requise. Installation et configuration 100% UI.

## Fonctionnalités
- Entité `climate` (modes **OFF/AUTO/CHAUD/FROID**, consigne, pas 0,5 °C)
- Capteurs **Eau In / Eau Out / Air**
- Interrupteurs **PAC – Alimentation** et **Éclairage piscine**
- Commandes **On/Off** (via CGI)
- Polling local, sans cloud (HTTP)

## Installation via HACS
1. Ouvrez **HACS → Intégrations → Menu (⋮) → Dépôts personnalisés**.
2. Ajoutez l'URL de ce dépôt (catégorie **Intégration**).
3. Recherchez **O'Foehn PoolPilot** dans HACS et installez.
4. Redémarrez Home Assistant.
5. **Paramètres → Appareils & services → Ajouter une intégration → O'Foehn PoolPilot**.
6. Entrez l'**adresse IP** de la PAC (et le port si différent, 80 par défaut).

## Options (firmware variants)
Dans **l'intégration → Options**, vous pouvez ajuster les indices `DONNEE#` si votre firmware diffère :
- `water_in_idx` (défaut : 5)
- `water_out_idx` (défaut : 6)
- `air_idx` (défaut : 7)
- `light_idx` (défaut : 16, source `accueil.cgi`)
- `power_idx` (défaut : 24, indicateur marche)

> Astuce : ouvrez `http://<IP>/super.cgi` et `http://<IP>/accueil.cgi` pour vérifier les `DONNEE#`.

## Sécurité & réseau
- Communication locale **HTTP non chiffrée** : isolez la PAC sur un VLAN/SSID IoT si possible.
- Aucun compte cloud requis.

## Exemples Lovelace
- Vue complète : `examples/lovelace_piscine_full.yaml`
- Vue compacte : `examples/lovelace_piscine_compact.yaml`

> Remplacez les `entity_id` si vos noms diffèrent.

## Nouveautés v0.1.0
- **Mode OFF** dans l'entité `climate` (basé sur l'index `power_idx`) et **interrupteur `PAC – Alimentation`** dédié.
- **Traductions** `fr`/`en` pour l'UI.
- **Options** supplémentaires : `power_idx` (par défaut 24).
- **Icône & captures** (voir `/assets` et `/screenshots`).

## Dépannage
- Vérifiez que la PAC répond à `http://<IP>/super.cgi` et `http://<IP>/getReg.cgi`.
- Si authentification requise sur votre modèle, ouvrez un ticket : elle sera ajoutée dans une version ultérieure.

## Licence
MIT