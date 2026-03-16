# agent_deploy

Agent de déploiement d'agents IA sur des serveurs distants ou en local via SSH. Installe, configure et démarre de nouveaux agents à partir d'un catalogue ou directement depuis une URL git.

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
| `deploy` | Déploie un agent depuis le catalogue sur un serveur distant (SSH) |
| `catalog` | Consulte le catalogue des agents déployables |
| `ssh` | Connexion SSH et exécution de commandes distantes |
| `script` | Bibliothèque de scripts bash (save/list/show/edit/exec/run/delete) |
| `agents_status` | Statut des agents du système |
| `mqtt_send` | Publication sur un topic MQTT |
| `mqtt_subscribe` | Souscription dynamique à un topic MQTT |
| `muc_send` | Message dans le groupe XMPP |

## Modes de déploiement

### Depuis le catalogue
```
"Déploie un agent debian sur le serveur 10.0.0.5"
"Installe un nouvel agent ansible sur srv-infra-01"
```

### Depuis une URL git (distant)
```
SKILL:deploy ARGS:from_git <git_url> <nom> <host> <user> password|key <credential> <xmpp_jid> <xmpp_pass> <mqtt_host> [main_script]
```

### Depuis une URL git (local)
```
SKILL:deploy ARGS:from_git_local <git_url> <nom> <xmpp_jid> <xmpp_pass> <mqtt_host> [main_script]
```

L'agent détecte automatiquement le script principal dans ce ordre : `agent_*.py` > `main.py` > fichier avec `if __name__ == "__main__"` > premier `.py`.

## Structure

```
agent_deploy.py       — Point d'entrée
deployer.py           — Logique de déploiement (AgentCatalog + from_git)
skills/               — 8 skills
scripts/              — Scripts bash persistants
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
    "model": "qwen3:8b",
    "temperature": 0.3
  },
  "llm_profiles": {
    "local": "qwen3:8b",
    "cloud": "gpt-oss:120b-cloud"
  },
  "catalog": "/opt/agent_deploy/config/catalog.json",
  "use_omemo": true,
  "use_llm_coordinator": true
}
```

## Commandes

```
/catalog  — Liste les agents disponibles dans le catalogue
/report   — Statistiques de déploiement
/status   — État de la queue de tâches
/script   — Gestion de la bibliothèque de scripts bash
```

> **Note** : l'agent demande toujours confirmation de l'hôte cible. Ne jamais inventer un nom de serveur.
