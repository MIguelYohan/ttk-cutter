import requests
from typing import Dict, Any, Optional

class TwitchAuthHelper:
    def __init__(self, client_id: str, user_token: str):
        self.client_id = client_id
        # Remove prefixo 'oauth:' se o usuário tiver colado com ele
        self.user_token = user_token.replace("oauth:", "").strip()
        self.headers = {
            "Client-Id": self.client_id,
            "Authorization": f"Bearer {self.user_token}"
        }

    def validate_token(self) -> Dict[str, Any]:
        """
        Valida o token na API da Twitch e verifica se possui o escopo 'user:read:chat'.
        """
        url = "https://id.twitch.tv/oauth2/validate"
        headers = {"Authorization": f"OAuth {self.user_token}"}
        
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            raise ValueError(f"Token inválido ou expirado ({resp.status_code}): {resp.text}")
        
        data = resp.json()
        scopes = data.get("scopes", [])
        if "user:read:chat" not in scopes:
            raise PermissionError(
                f"O token não possui o escopo necessário 'user:read:chat'. Escopos atuais: {scopes}"
            )
        return data

    def get_user_id(self, login: Optional[str] = None) -> str:
        """
        Obtém o ID numérico da Twitch a partir do login.
        Se login for None, retorna o ID do próprio usuário autenticado.
        """
        url = "https://api.twitch.tv/helix/users"
        params = {"login": login} if login else {}
        
        resp = requests.get(url, headers=self.headers, params=params, timeout=10)
        if resp.status_code != 200:
            raise ValueError(f"Falha ao consultar usuário na API Helix ({resp.status_code}): {resp.text}")
        
        data = resp.json().get("data", [])
        if not data:
            raise ValueError(f"Usuário/Canal '{login}' não foi encontrado na Twitch.")
        
        return data[0]["id"]
