"""
Moteur de déploiement SSH — installe un agent sur une machine distante ou locale.
Le nom de l'agent est fourni par l'utilisateur et devient son identifiant permanent.
"""
import json
import logging
import os
import socket
import time
from dataclasses import dataclass, field
from typing import Optional, Callable

logger = logging.getLogger(__name__)

CATALOG_PATH = "/opt/agent_deploy/config/catalog.json"


@dataclass
class DeployConfig:
    """Paramètres d'un déploiement."""
    agent_type: str          # type d'agent : debian, ansible, deploy...
    agent_name: str          # nom choisi par l'utilisateur (ex: "debian-prod")
    host: str                # IP ou hostname cible
    ssh_user: str            # utilisateur SSH
    ssh_auth: str            # "password" ou "key"
    ssh_credential: str      # mot de passe ou chemin de clé privée
    xmpp_jid: str
    xmpp_password: str
    mqtt_host: str
    mqtt_port: int = 1883
    local: bool = False      # installation locale (pas de SSH)
    extra: dict = field(default_factory=dict)


class AgentCatalog:
    """Catalogue des types d'agents déployables."""

    def __init__(self, path: str = CATALOG_PATH):
        self.path = path
        self._data = self._load()

    def _load(self) -> dict:
        if not os.path.exists(self.path):
            return self._default_catalog()
        with open(self.path) as f:
            return json.load(f)

    def _default_catalog(self) -> dict:
        return {
            "nexus": {
                "description": "Orchestrateur principal — coordonne tous les agents",
                "repo": "https://github.com/youruser/nexus.git",
                "install_path_tpl": "/opt/{agent_name}",
                "service_name_tpl": "{agent_name}",
                "main_script": "nexus.py",
                "apt_deps": ["python3", "python3-pip", "python3-venv", "git", "mosquitto-clients"],
                "pip_deps": ["apscheduler", "duckduckgo-search", "beautifulsoup4"],
                "config_template": "nexus",
                "extra_config": {
                    "schedules": {"scheduled_tasks": [], "daily_reports": []}
                },
            },
            "debian": {
                "description": "Agent d'administration système Debian",
                "repo": "https://github.com/youruser/agent_debian.git",
                "install_path_tpl": "/opt/{agent_name}",
                "service_name_tpl": "{agent_name}",
                "main_script": "agent_debian.py",
                "apt_deps": ["python3", "python3-pip", "python3-venv", "git", "mosquitto-clients"],
                "pip_deps": [],
                "config_template": "debian",
                "extra_config": {"work_hours": "07:00-23:00"},
            },
            "ansible": {
                "description": "Agent d'automatisation Ansible",
                "repo": "https://github.com/youruser/agent_ansible.git",
                "install_path_tpl": "/opt/{agent_name}",
                "service_name_tpl": "{agent_name}",
                "main_script": "agent_ansible.py",
                "apt_deps": ["python3", "python3-pip", "python3-venv", "git", "ansible", "mosquitto-clients"],
                "pip_deps": [],
                "config_template": "ansible",
                "extra_config": {"work_hours": "07:00-23:00"},
            },
            "deploy": {
                "description": "Agent de déploiement d'autres agents",
                "repo": "https://github.com/youruser/agent_deploy.git",
                "install_path_tpl": "/opt/{agent_name}",
                "service_name_tpl": "{agent_name}",
                "main_script": "agent_deploy.py",
                "apt_deps": ["python3", "python3-pip", "python3-venv", "git", "python3-paramiko", "mosquitto-clients", "sshpass"],
                "pip_deps": ["paramiko"],
                "config_template": "deploy",
                "extra_config": {
                    "work_hours": "08:00-20:00",
                    "catalog": "/opt/{agent_name}/config/catalog.json"
                },
            },
        }

    def get(self, agent_type: str) -> Optional[dict]:
        return self._data.get(agent_type)

    def list_types(self) -> list[str]:
        return list(self._data.keys())

    def summary(self) -> str:
        lines = ["── Agents déployables ──────────────"]
        for name, info in self._data.items():
            lines.append(f"  [{name}] {info['description']}")
        return "\n".join(lines)


class Deployer:
    """
    Orchestre le déploiement complet d'un agent.
    Supporte SSH (distant) et local.
    """

    def __init__(self, config: DeployConfig, progress_cb: Optional[Callable] = None):
        self.cfg      = config
        self.catalog  = AgentCatalog()
        self._cb      = progress_cb or (lambda msg: logger.info(msg))
        self._ssh     = None

    def deploy(self) -> tuple[bool, str]:
        """Lance le déploiement. Retourne (succès, message)."""
        agent_info = self.catalog.get(self.cfg.agent_type)
        if not agent_info:
            return False, f"Type d'agent inconnu : '{self.cfg.agent_type}'. Disponibles : {self.catalog.list_types()}"

        install_path = agent_info["install_path_tpl"].format(agent_name=self.cfg.agent_name)
        service_name = agent_info["service_name_tpl"].format(agent_name=self.cfg.agent_name)
        main_script  = agent_info["main_script"]

        steps = [
            ("Connexion SSH",          lambda: self._connect()),
            ("Dépendances système",    lambda: self._install_apt(agent_info["apt_deps"])),
            ("Clonage du dépôt",       lambda: self._clone_repo(agent_info["repo"], install_path)),
            ("Environnement Python",   lambda: self._setup_venv(install_path, agent_info.get("pip_deps", []))),
            ("Configuration",          lambda: self._write_config(install_path, agent_info["config_template"])),
            ("Service systemd",        lambda: self._setup_service(install_path, service_name, main_script)),
            ("Démarrage",              lambda: self._start_service(service_name)),
        ]

        for step_name, step_fn in steps:
            self._cb(f"⏳ {step_name}...")
            try:
                ok, msg = step_fn()
                if not ok:
                    self._cb(f"❌ {step_name} échoué : {msg}")
                    self._disconnect()
                    return False, f"Échec à l'étape '{step_name}' : {msg}"
                self._cb(f"✓ {step_name}")
            except Exception as e:
                self._disconnect()
                return False, f"Exception lors de '{step_name}' : {e}"

        self._disconnect()
        return True, (
            f"Agent '{self.cfg.agent_name}' ({self.cfg.agent_type}) déployé avec succès sur {self.cfg.host}.\n"
            f"Service : {service_name}\n"
            f"Chemin : {install_path}\n"
            f"JID XMPP : {self.cfg.xmpp_jid}"
        )

    # ──────────────────────────────────────────────
    # Étapes de déploiement
    # ──────────────────────────────────────────────

    def _connect(self) -> tuple[bool, str]:
        if self.cfg.local:
            return True, "local"
        try:
            import paramiko
            self._ssh = paramiko.SSHClient()
            self._ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            kwargs = dict(
                hostname=self.cfg.host,
                username=self.cfg.ssh_user,
                timeout=15,
            )
            if self.cfg.ssh_auth == "password":
                kwargs["password"] = self.cfg.ssh_credential
            else:
                kwargs["key_filename"] = self.cfg.ssh_credential
            self._ssh.connect(**kwargs)
            return True, "ok"
        except Exception as e:
            return False, str(e)

    def _run_remote(self, cmd: str, timeout: int = 120) -> tuple[bool, str]:
        if self.cfg.local:
            import subprocess
            result = subprocess.run(
                cmd, shell=True, text=True,
                capture_output=True, timeout=timeout
            )
            out = (result.stdout + result.stderr).strip()
            return result.returncode == 0, out
        else:
            stdin, stdout, stderr = self._ssh.exec_command(cmd, timeout=timeout)
            exit_code = stdout.channel.recv_exit_status()
            out = stdout.read().decode() + stderr.read().decode()
            return exit_code == 0, out.strip()

    def _install_apt(self, packages: list) -> tuple[bool, str]:
        if not packages:
            return True, "aucune dépendance"
        pkgs = " ".join(packages)
        ok, out = self._run_remote(
            f"DEBIAN_FRONTEND=noninteractive apt-get install -y -q {pkgs}",
            timeout=300
        )
        return ok, out[-500:] if not ok else "ok"

    def _clone_repo(self, repo: str, install_path: str) -> tuple[bool, str]:
        cmd = (
            f"if [ -d '{install_path}/.git' ]; then "
            f"  cd {install_path} && git pull; "
            f"else "
            f"  git clone {repo} {install_path}; "
            f"fi"
        )
        return self._run_remote(cmd, timeout=120)

    def _setup_venv(self, install_path: str, extra_pip: list) -> tuple[bool, str]:
        venv = f"{install_path}/venv"
        cmds = [
            f"python3 -m venv {venv}",
            f"{venv}/bin/pip install --quiet --upgrade pip",
            f"{venv}/bin/pip install --quiet -r {install_path}/requirements.txt",
        ]
        if extra_pip:
            cmds.append(f"{venv}/bin/pip install --quiet {' '.join(extra_pip)}")
        for cmd in cmds:
            ok, out = self._run_remote(cmd, timeout=180)
            if not ok:
                return False, out[-500:]
        return True, "ok"

    def _write_config(self, install_path: str, template: str) -> tuple[bool, str]:
        """Écrit config.json avec les paramètres fournis par l'utilisateur."""
        # Récupère les extra_config du catalogue pour ce type d'agent
        agent_info   = self.catalog.get(self.cfg.agent_type) or {}
        catalog_extra = agent_info.get("extra_config", {})

        # Résout les templates dans les valeurs (ex: /opt/{agent_name}/config/catalog.json)
        resolved_extra = {}
        for k, v in catalog_extra.items():
            if isinstance(v, str):
                resolved_extra[k] = v.format(agent_name=self.cfg.agent_name)
            else:
                resolved_extra[k] = v

        config = {
            "agent_id": self.cfg.agent_name,
            "xmpp": {
                "jid": self.cfg.xmpp_jid,
                "password": self.cfg.xmpp_password,
                "admin_jids": self.cfg.extra.get("admin_jids", [self.cfg.extra.get("admin_jid", "")]),
                "muc_room": self.cfg.extra.get("muc_room", "agents@conference.xmpp.ovh"),
                "use_omemo": False,
            },
            "mqtt": {
                "host": self.cfg.mqtt_host,
                "port": self.cfg.mqtt_port,
                "username": self.cfg.extra.get("mqtt_username"),
                "password": self.cfg.extra.get("mqtt_password"),
                "tls": self.cfg.extra.get("mqtt_tls", False),
            },
            "llm": {
                "base_url": self.cfg.extra.get("ollama_url", "http://localhost:11434"),
                "model": self.cfg.extra.get("model", "mistral"),
                "temperature": 0.3,
            },
            "queue_db": f"{install_path}/data/queue.db",
            "system_prompt": f"{install_path}/config/system_prompt.txt",
        }
        # Fusionne les extra_config du catalogue
        config.update(resolved_extra)
        # Les extra de l'utilisateur ont priorité
        for k, v in self.cfg.extra.items():
            if k not in ("admin_jid", "admin_jids", "muc_room", "mqtt_username",
                         "mqtt_password", "mqtt_tls", "ollama_url", "model"):
                config[k] = v

        config_json = json.dumps(config, indent=2, ensure_ascii=False)
        # Écrit via heredoc pour éviter les problèmes d'échappement
        cmd = (
            f"mkdir -p {install_path}/config {install_path}/data && "
            f"cat > {install_path}/config/config.json << 'DEPLOYEOF'\n"
            f"{config_json}\n"
            f"DEPLOYEOF"
        )
        return self._run_remote(cmd)

    def _setup_service(self, install_path: str, service_name: str, main_script: str) -> tuple[bool, str]:
        service_content = f"""[Unit]
Description=Agent {service_name}
After=network.target mosquitto.service
Wants=mosquitto.service

[Service]
Type=simple
User=root
WorkingDirectory={install_path}
ExecStart={install_path}/venv/bin/python {install_path}/{main_script}
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier={service_name}

[Install]
WantedBy=multi-user.target
"""
        cmd = (
            f"cat > /etc/systemd/system/{service_name}.service << 'SVCEOF'\n"
            f"{service_content}\n"
            f"SVCEOF\n"
            f"systemctl daemon-reload && "
            f"systemctl enable {service_name}"
        )
        return self._run_remote(cmd)

    def _start_service(self, service_name: str) -> tuple[bool, str]:
        ok, out = self._run_remote(f"systemctl start {service_name}")
        if not ok:
            return False, out
        time.sleep(3)
        ok2, status = self._run_remote(f"systemctl is-active {service_name}")
        return status.strip() == "active", status

    def _disconnect(self):
        if self._ssh:
            try:
                self._ssh.close()
            except Exception:
                pass
            self._ssh = None
