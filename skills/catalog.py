"""
Skill CATALOG — gérer le catalogue des agents déployables.

Usage LLM :
  SKILL:catalog ARGS:list
  SKILL:catalog ARGS:show <type>
  SKILL:catalog ARGS:add <type> | <json_config>
  SKILL:catalog ARGS:remove <type>
"""
import json
import os
import sys

sys.path.insert(0, "/opt/agent_deploy")

from deployer import AgentCatalog, CATALOG_PATH

DESCRIPTION = "Gérer le catalogue des types d'agents déployables"
USAGE = "SKILL:catalog ARGS:list | show <type> | add <type>|<json> | remove <type>"


def run(args: str, context) -> str:
    parts = args.strip().split(None, 1)
    action = parts[0].lower() if parts else "list"
    rest   = parts[1] if len(parts) > 1 else ""

    catalog = AgentCatalog()

    if action == "list":
        return catalog.summary()

    if action == "show":
        agent_type = rest.strip()
        info = catalog.get(agent_type)
        if not info:
            return f"Type '{agent_type}' inconnu."
        return json.dumps(info, indent=2, ensure_ascii=False)

    if action == "add":
        if "|" not in rest:
            return "Format : add <type> | <json_config>"
        agent_type, config_json = rest.split("|", 1)
        agent_type = agent_type.strip()
        try:
            config = json.loads(config_json.strip())
            # Charge le fichier existant et ajoute
            if os.path.exists(CATALOG_PATH):
                with open(CATALOG_PATH) as f:
                    data = json.load(f)
            else:
                data = catalog._default_catalog()
            data[agent_type] = config
            with open(CATALOG_PATH, "w") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return f"Type '{agent_type}' ajouté au catalogue."
        except json.JSONDecodeError as e:
            return f"JSON invalide : {e}"

    if action == "remove":
        agent_type = rest.strip()
        if os.path.exists(CATALOG_PATH):
            with open(CATALOG_PATH) as f:
                data = json.load(f)
            if agent_type in data:
                del data[agent_type]
                with open(CATALOG_PATH, "w") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                return f"Type '{agent_type}' supprimé du catalogue."
        return f"Type '{agent_type}' introuvable."

    return "Action inconnue. Disponible : list, show, add, remove"
