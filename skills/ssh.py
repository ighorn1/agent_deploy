"""
Skill SSH — exécuter des commandes sur une machine distante via SSH.

Usage LLM :
  SKILL:ssh ARGS:<host> <user> password <mdp> | <commande>
  SKILL:ssh ARGS:<host> <user> key <chemin_cle> | <commande>
  SKILL:ssh ARGS:copy <host> <user> password <mdp> | <fichier_local> <chemin_distant>
"""
import subprocess

DESCRIPTION = "Exécuter des commandes SSH sur une machine distante"
USAGE = "SKILL:ssh ARGS:<host> <user> password <mdp> | <commande>  ou  key <chemin_cle> | <commande>"


def _ssh_cmd(host: str, user: str, auth: str, credential: str, cmd: str, timeout: int = 30) -> str:
    if auth == "password":
        full_cmd = (
            f"sshpass -p '{credential}' ssh "
            f"-o StrictHostKeyChecking=no "
            f"-o ConnectTimeout=10 "
            f"{user}@{host} '{cmd}'"
        )
    else:
        full_cmd = (
            f"ssh -i {credential} "
            f"-o StrictHostKeyChecking=no "
            f"-o ConnectTimeout=10 "
            f"{user}@{host} '{cmd}'"
        )
    try:
        result = subprocess.run(
            full_cmd, shell=True, text=True,
            capture_output=True, timeout=timeout
        )
        out = (result.stdout + result.stderr).strip()
        return out[:4000] if out else f"(code retour : {result.returncode})"
    except subprocess.TimeoutExpired:
        return f"Timeout ({timeout}s)"
    except Exception as e:
        return str(e)


def run(args: str, context) -> str:
    if "|" not in args:
        return "Format : <host> <user> password|key <credential> | <commande>"

    left, command = args.split("|", 1)
    command = command.strip()
    parts   = left.strip().split()

    if len(parts) < 4:
        return "Format : <host> <user> password|key <credential> | <commande>"

    host, user, auth, credential = parts[0], parts[1], parts[2], parts[3]

    if auth not in ("password", "key"):
        return "Auth doit être 'password' ou 'key'"

    # Sous-commande copy
    if command.startswith("COPY "):
        file_parts = command[5:].split()
        if len(file_parts) < 2:
            return "Format copy : COPY <fichier_local> <chemin_distant>"
        local_file, remote_path = file_parts[0], file_parts[1]
        if auth == "password":
            scp_cmd = (
                f"sshpass -p '{credential}' scp "
                f"-o StrictHostKeyChecking=no "
                f"{local_file} {user}@{host}:{remote_path}"
            )
        else:
            scp_cmd = (
                f"scp -i {credential} "
                f"-o StrictHostKeyChecking=no "
                f"{local_file} {user}@{host}:{remote_path}"
            )
        try:
            result = subprocess.run(
                scp_cmd, shell=True, text=True,
                capture_output=True, timeout=60
            )
            return (result.stdout + result.stderr).strip() or f"Fichier copié vers {host}:{remote_path}"
        except Exception as e:
            return str(e)

    return _ssh_cmd(host, user, auth, credential, command)
