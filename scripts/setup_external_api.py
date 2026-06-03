"""
Setup inicial: registra (ou autentica) na API externa worldcup26.ir
e salva o token retornado em WORLDCUP_API_TOKEN no arquivo .env.

Execute uma única vez durante o setup do projeto:
    python scripts/setup_external_api.py
"""

import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://worldcup26.ir"
ENV_PATH = Path(".env")


def _save_token(token: str) -> None:
    if not ENV_PATH.exists():
        ENV_PATH.write_text(f"WORLDCUP_API_TOKEN={token}\n", encoding="utf-8")
        print(f"Arquivo .env criado com o token.")
        return

    lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
    new_lines = []
    found = False
    for line in lines:
        if line.startswith("WORLDCUP_API_TOKEN="):
            new_lines.append(f"WORLDCUP_API_TOKEN={token}")
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append(f"WORLDCUP_API_TOKEN={token}")
    ENV_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    print("Token salvo em .env (WORLDCUP_API_TOKEN).")


def _try_login(email: str, password: str) -> str | None:
    try:
        resp = httpx.post(
            f"{BASE_URL}/auth/authenticate",
            json={"email": email, "password": password},
            timeout=15.0,
        )
        if resp.status_code == 200:
            return resp.json().get("token")
    except Exception as e:
        print(f"Erro ao fazer login: {e}")
    return None


def _try_register(name: str, email: str, password: str) -> str | None:
    try:
        resp = httpx.post(
            f"{BASE_URL}/auth/register",
            json={"name": name, "email": email, "password": password},
            timeout=15.0,
        )
        if resp.status_code in (200, 201):
            return resp.json().get("token")
        if resp.status_code == 400:
            # Conta já existe, tenta login
            return _try_login(email, password)
    except Exception as e:
        print(f"Erro ao registrar: {e}")
    return None


def main() -> None:
    email = os.getenv("WORLDCUP_API_EMAIL", "").strip()
    password = os.getenv("WORLDCUP_API_PASSWORD", "").strip()

    if not email or not password:
        print(
            "Erro: defina WORLDCUP_API_EMAIL e WORLDCUP_API_PASSWORD no arquivo .env antes de executar este script."
        )
        sys.exit(1)

    name = email.split("@")[0]
    print(f"Tentando registrar/autenticar na API externa com {email}...")

    token = _try_register(name, email, password)
    if not token:
        token = _try_login(email, password)

    if not token:
        print("Falha ao obter token da API externa. Verifique as credenciais.")
        sys.exit(1)

    _save_token(token)
    print(f"Token obtido com sucesso! (primeiros 20 chars): {token[:20]}...")


if __name__ == "__main__":
    main()
