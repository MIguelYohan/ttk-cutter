"""
Script auxiliar para obter o User Access Token da Twitch utilizando o Device Code Flow.
Totalmente automático para uso pessoal: abre o navegador na página oficial de ativação da Twitch
e salva o token no .env assim que você clicar em 'Autorizar'.
"""
import os
import sys
import time
import webbrowser
import requests
from pathlib import Path
from dotenv import dotenv_values

ENV_PATH = Path(__file__).resolve().parent / ".env"

def save_env_values(updates: dict):
    lines = []
    if ENV_PATH.exists():
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()

    new_lines = []
    seen = set()
    for line in lines:
        stripped = line.strip()
        if "=" in stripped and not stripped.startswith("#"):
            k = stripped.split("=", 1)[0].strip()
            if k in updates:
                new_lines.append(f"{k}={updates[k]}\n")
                seen.add(k)
                continue
        new_lines.append(line)

    for k, v in updates.items():
        if k not in seen:
            new_lines.append(f"{k}={v}\n")

    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

def main():
    print("=" * 65)
    print("      GERADOR AUTOMÁTICO DE TOKEN DA TWITCH (DEVICE FLOW)")
    print("=" * 65)

    env_vals = dotenv_values(ENV_PATH) if ENV_PATH.exists() else {}
    client_id = env_vals.get("TWITCH_CLIENT_ID") or env_vals.get("CLIENT_ID")
    client_secret = env_vals.get("TWITCH_CLIENT_SECRET") or env_vals.get("CLIENT_SECRET")

    if not client_id:
        client_id = input("\nDigite seu CLIENT_ID: ").strip()

    channel = env_vals.get("TWITCH_CHANNEL") or env_vals.get("CHANNEL")
    if not channel:
        channel = input("Digite o nome do canal a monitorar na live (ex: gaules, alanzoka): ").strip()
        if not channel:
            channel = "gaules"

    print("\n[1/3] Solicitando autorização de leitura de chat ('user:read:chat') à Twitch...")
    resp = requests.post("https://id.twitch.tv/oauth2/device", data={
        "client_id": client_id,
        "scopes": "user:read:chat"
    })

    if resp.status_code != 200:
        print(f"\n[ERRO] Falha ao iniciar autenticação ({resp.status_code}): {resp.text}")
        return

    data = resp.json()
    device_code = data["device_code"]
    user_code = data["user_code"]
    verification_uri = data.get("verification_uri", f"https://www.twitch.tv/activate?device-code={user_code}")
    interval = data.get("interval", 5)

    print(f"\n[2/3] Abrindo navegador na página de autorização da Twitch...")
    print(f"URL: {verification_uri}")
    print(f"Código do dispositivo: {user_code}")
    print("\n--> Basta clicar em 'Ativar' ou 'Autorizar' no seu navegador.")

    try:
        webbrowser.open(verification_uri)
    except Exception:
        pass

    print("\n[3/3] Aguardando confirmação no navegador...")
    token_url = "https://id.twitch.tv/oauth2/token"
    token_data = {
        "client_id": client_id,
        "device_code": device_code,
        "grant_type": "urn:ietf:params:oauth:grant-type:device_code"
    }
    if client_secret:
        token_data["client_secret"] = client_secret

    while True:
        time.sleep(interval)
        poll_resp = requests.post(token_url, data=token_data)
        
        if poll_resp.status_code == 200:
            token_json = poll_resp.json()
            access_token = token_json["access_token"]
            print("\n" + "=" * 65)
            print("[✓] SUCESSO! Token de acesso recebido da Twitch.")
            print("=" * 65)
            
            updates = {
                "TWITCH_USER_TOKEN": access_token,
                "TWITCH_CHANNEL": channel
            }
            save_env_values(updates)
            print(f"[✓] Salvo no '.env': TWITCH_USER_TOKEN e TWITCH_CHANNEL={channel}")
            print("\nAgora você pode iniciar o monitoramento com:")
            print("  .\\venv\\Scripts\\python.exe test_chat_stage1.py")
            break
        
        poll_json = poll_resp.json()
        msg = poll_json.get("message", "")
        if msg == "authorization_pending":
            sys.stdout.write(".")
            sys.stdout.flush()
        else:
            print(f"\nStatus: {poll_resp.status_code} - {msg}")
            if poll_resp.status_code != 400:
                break

if __name__ == "__main__":
    main()
