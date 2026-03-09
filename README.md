# agent_deploy

Agent de déploiement d'agents IA sur des serveurs distants via SSH. Installe, configure et démarre de nouveaux agents sur des machines cibles à partir d'un catalogue.

## Rôle

Cet agent est **uniquement** pour déployer de nouveaux agents IA sur de nouvelles machines. Pour des tâches système courantes (apt, services, fichiers), utiliser `agent_debian`. Pour l'automatisation multi-serveurs, utiliser `agent_ansible`.

## Installation

```bash
cd /opt/agent_deploy
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
systemctl enable --now agent_deploy
```

## Skills disponibles

| Skill | Description |
|-------|-------------|
| `deploy` | Déploie un agent sur un serveur distant via SSH |
| `catalog` | Consulte le catalogue des agents déployables |
| `ssh` | Connexion SSH et exécution de commandes distantes |
| `agents_status` | Statut des agents du système |
| `mqtt_send` | Publication sur un topic MQTT |
| `mqtt_subscribe` | Souscription dynamique à un topic MQTT |
| `muc_send` | Message dans le groupe XMPP |

## Structure

```
agent_deploy.py       — Point d'entrée
deployer.py           — Logique de déploiement (AgentCatalog)
skills/               — 7 skills
config/
  config.json         — Configuration
  system_prompt.txt   — Prompt système
  catalog.json        — Catalogue des agents déployables
agent_deploy.service  — Unit systemd
```

## Configuration

`config/config.json` :
```json
{
  "agent_id": "deploy",
  "xmpp": {
    "jid": "deploy@xmpp.ovh",
    "password": "...",
    "admin_jid": "sylvain@xmpp.ovh",
    "muc_room": "agents@muc.xmpp.ovh"
  },
  "mqtt": { "host": "localhost", "port": 1883 },
  "llm": {
    "base_url": "http://192.168.7.119:11434",
    "model": "ministral-3:latest",
    "temperature": 0.3
  },
  "llm_profiles": {
    "local": "ministral-3:latest",
    "cloud": "gpt-oss:120b-cloud"
  },
  "catalog": "/opt/agent_deploy/config/catalog.json"
}
```

## Commandes

```
/catalog  — Liste les agents disponibles dans le catalogue
/report   — Statistiques de déploiement
/status   — État de la queue de tâches
```

## Exemples de tâches (via Nexus)

```
"Déploie un agent debian sur le serveur 10.0.0.5"
"Installe un nouvel agent ansible sur srv-infra-01"
```

> **Note** : l'agent demande toujours confirmation de l'hôte cible. Ne jamais inventer un nom de serveur.
