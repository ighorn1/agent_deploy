"""
Skill DEPLOY — déployer un agent sur une machine distante ou locale.

Le LLM collecte les paramètres via une conversation guidée, puis lance le déploiement.

Usage LLM :
  SKILL:deploy ARGS:start <type> <nom> <host> <user> <auth:password|key> <credential> <xmpp_jid> <xmpp_pass> <mqtt_host>
  SKILL:deploy ARGS:local <type> <nom> <xmpp_jid> <xmpp_pass> <mqtt_host>
  SKILL:deploy ARGS:catalog
  SKILL:deploy ARGS:status <host>
"""
import json
import os
import sys

sys.path.insert(0, "/opt/agent_deploy")

from deployer import Deployer, DeployConfig, AgentCatalog

DESCRIPTION = "Déployer un agent sur une machine distante (SSH) ou locale"
USAGE = (
    "SKILL:deploy ARGS:catalog  — liste les agents déployables\n"
    "SKILL:deploy ARGS:start <type> <nom> <host> <user> password <mdp> <xmpp_jid> <xmpp_pass> <mqtt_host>\n"
    "SKILL:deploy ARGS:local <type> <nom> <xmpp_jid> <xmpp_pass> <mqtt_host>\n"
    "SKILL:deploy ARGS:from_git <git_url> <nom> <host> <user> password|key <credential> <xmpp_jid> <xmpp_pass> <mqtt_host> [main_script]\n"
    "SKILL:deploy ARGS:from_git_local <git_url> <nom> <xmpp_jid> <xmpp_pass> <mqtt_host> [main_script]"
)


def run(args: str, context) -> str:
    parts = args.strip().split(None, 1)
    action = parts[0].lower() if parts else "catalog"
    rest   = parts[1] if len(parts) > 1 else ""

    if action == "catalog":
        catalog = AgentCatalog()
        return catalog.summary()

    if action == "local":
        # ARGS: local <type> <nom> <xmpp_jid> <xmpp_pass> <mqtt_host>
        p = rest.split()
        if len(p) < 5:
            return "Format : local <type> <nom> <xmpp_jid> <xmpp_pass> <mqtt_host>"
        agent_type, agent_name, xmpp_jid, xmpp_pass, mqtt_host = p[0], p[1], p[2], p[3], p[4]

        cfg = DeployConfig(
            agent_type=agent_type,
            agent_name=agent_name,
            host="localhost",
            ssh_user="root",
            ssh_auth="",
            ssh_credential="",
            xmpp_jid=xmpp_jid,
            xmpp_password=xmpp_pass,
            mqtt_host=mqtt_host,
            local=True,
        )
        return _do_deploy(cfg, context)

    if action == "start":
        # ARGS: start <type> <nom> <host> <user> <auth> <credential> <xmpp_jid> <xmpp_pass> <mqtt_host>
        p = rest.split()
        if len(p) < 9:
            return (
                "Format : start <type> <nom> <host> <user> password|key <credential> "
                "<xmpp_jid> <xmpp_pass> <mqtt_host>"
            )
        cfg = DeployConfig(
            agent_type=p[0],
            agent_name=p[1],
            host=p[2],
            ssh_user=p[3],
            ssh_auth=p[4],
            ssh_credential=p[5],
            xmpp_jid=p[6],
            xmpp_password=p[7],
            mqtt_host=p[8],
            mqtt_port=int(p[9]) if len(p) > 9 else 1883,
        )
        return _do_deploy(cfg, context)

    if action == "from_git":
        # ARGS: from_git <git_url> <nom> <host> <user> password|key <credential> <xmpp_jid> <xmpp_pass> <mqtt_host> [main_script]
        p = rest.split()
        if len(p) < 9:
            return (
                "Format : from_git <git_url> <nom> <host> <user> password|key <credential> "
                "<xmpp_jid> <xmpp_pass> <mqtt_host> [main_script]"
            )
        cfg = DeployConfig(
            agent_type="custom",
            agent_name=p[1],
            host=p[2],
            ssh_user=p[3],
            ssh_auth=p[4],
            ssh_credential=p[5],
            xmpp_jid=p[6],
            xmpp_password=p[7],
            mqtt_host=p[8],
            mqtt_port=int(p[9]) if len(p) > 9 and p[9].isdigit() else 1883,
            git_url=p[0],
            main_script=p[10] if len(p) > 10 else None,
        )
        return _do_deploy(cfg, context)

    if action == "from_git_local":
        # ARGS: from_git_local <git_url> <nom> <xmpp_jid> <xmpp_pass> <mqtt_host> [main_script]
        p = rest.split()
        if len(p) < 5:
            return "Format : from_git_local <git_url> <nom> <xmpp_jid> <xmpp_pass> <mqtt_host> [main_script]"
        cfg = DeployConfig(
            agent_type="custom",
            agent_name=p[1],
            host="localhost",
            ssh_user="root",
            ssh_auth="",
            ssh_credential="",
            xmpp_jid=p[2],
            xmpp_password=p[3],
            mqtt_host=p[4],
            local=True,
            git_url=p[0],
            main_script=p[5] if len(p) > 5 else None,
        )
        return _do_deploy(cfg, context)

    if action == "status":
        host = rest.strip()
        if not host:
            return "Précise l'hôte."
        import subprocess
        try:
            result = subprocess.run(
                f"ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no {host} 'systemctl list-units --type=service --state=active | grep agent'",
                shell=True, text=True, capture_output=True, timeout=15
            )
            return result.stdout.strip() or "Aucun agent actif trouvé sur cet hôte."
        except Exception as e:
            return str(e)

    return "Action inconnue. Disponible : catalog, start, local, status"


def _do_deploy(cfg: DeployConfig, context) -> str:
    """Lance le déploiement et notifie via MQTT."""
    messages = []

    def progress(msg: str):
        messages.append(msg)
        # Notifie en temps réel via MQTT
        context.mqtt.send_to(
            "nexus",
            f"[Deploy {cfg.agent_name}] {msg}",
            msg_type="result",
        )

    deployer = Deployer(cfg, progress_cb=progress)
    success, result = deployer.deploy()

    # Notification finale
    if success:
        # Notifie Nexus de l'enregistrement du nouvel agent
        registration = json.dumps({
            "agent_id": cfg.agent_name,
            "agent_type": cfg.agent_type,
            "host": cfg.host,
            "xmpp_jid": cfg.xmpp_jid,
            "mqtt_inbox": f"agents/{cfg.agent_name}/inbox",
        })
        context.mqtt.publish_raw("agents/nexus/inbox", registration)

    return result
