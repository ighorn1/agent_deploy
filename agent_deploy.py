#!/usr/bin/env python3
"""
Agent Deploy — déploiement d'agents sur machines distantes ou locales via SSH.
Le nom de l'agent cible est choisi par l'utilisateur au déploiement.
"""
import os
import sys
import logging


from agents_core import BaseAgent, AgentContext, Message, MessageType

logger = logging.getLogger(__name__)


class AgentDeploy(BaseAgent):
    AGENT_TYPE = "deploy"
    DESCRIPTION = (
        "Déploiement et installation de NOUVEAUX agents IA sur des serveurs distants via SSH. "
        "Uniquement pour : installer un nouvel agent, déployer un agent sur une nouvelle machine. "
        "NE PAS utiliser pour des tâches système courantes (apt, services, fichiers, etc.)."
    )
    DEFAULT_CONFIG_PATH = "/opt/agent_deploy/config/config.json"

    def get_skills_dir(self) -> str:
        return os.path.join(os.path.dirname(__file__), "skills")

    def on_start(self):
        self.mqtt.send_to("nexus", f"Agent Deploy ({self.agent_id}) en ligne.")

    def setup_extra_subscriptions(self):
        self.mqtt.subscribe(
            f"agents/{self.agent_id}/control",
            self._on_control,
        )

    def _on_control(self, msg, topic: str):
        from agents_core.message_bus import Message as Msg
        payload = msg.payload if isinstance(msg, Msg) else str(msg)
        result = self._handle_system_command(payload)
        if result and isinstance(msg, Msg):
            self.mqtt.reply(msg, result)

    def handle_custom_command(self, cmd: str, args: str, source_msg=None):
        if cmd == "report":
            return self._build_report()
        if cmd == "catalog":
            from deployer import AgentCatalog
            catalog = AgentCatalog(
                self.config.get("catalog", "/opt/agent_deploy/config/catalog.json")
            )
            return catalog.summary()
        return f"Commande inconnue : /{cmd}"

    def _build_report(self) -> str:
        stats = self.queue.daily_stats()
        return (
            f"── Rapport {self.agent_id} ──\n"
            f"Déploiements : {stats['total']} total / "
            f"{stats['completed']} OK / {stats['failed']} erreurs / "
            f"durée moy. {stats['avg_duration_s']}s"
        )


if __name__ == "__main__":
    AgentDeploy().run()
