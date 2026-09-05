"""
CaféTrace SV — Obtener API key de Global Forest Watch (GFW)

Este script hace los DOS POST que necesitas después de crear tu cuenta en GFW:

  1. POST /auth/token   -> a cambio de tu email + password, te da un
                           access_token TEMPORAL (expira).
  2. POST /auth/apikey  -> usando ese access_token, te da la API key
                           DEFINITIVA (dura ~1 año), que es la que vas
                           a guardar en tu .env como GFW_API_KEY.

Requisitos:
    pip install requests

Uso:
    python get_gfw_api_key.py
"""

import getpass
import time

import requests

BASE_URL = "https://data-api.globalforestwatch.org"


def get_access_token(email: str, password: str) -> str:
    """
    Paso 1: intercambia email/password por un access_token temporal.

    Ojo: este POST manda los datos como form-urlencoded (no JSON),
    por eso usamos el parámetro `data=` de requests y no `json=`.
    """
    response = requests.post(
        f"{BASE_URL}/auth/token",
        data={"username": email, "password": password},
    )
    response.raise_for_status()  # lanza una excepción si el status no es 2xx
    body = response.json()
    return body["data"]["access_token"]


def get_api_key(
    access_token: str, email: str, alias: str, organization: str, max_retries: int = 3
) -> str:
    """
    Paso 2: con el access_token como Bearer, pide la API key definitiva.

    Este sí lo mandamos como JSON (`json=`), y el token va en el header
    Authorization, no en el cuerpo.

    Si el alias ya existe (409 Conflict, típicamente porque un intento
    anterior sí creó la key aunque el script fallara después al leerla),
    reintenta con un alias único agregando un timestamp.
    """
    headers = {"Authorization": f"Bearer {access_token}"}

    for attempt in range(max_retries):
        current_alias = alias if attempt == 0 else f"{alias}-{int(time.time())}"

        response = requests.post(
            f"{BASE_URL}/auth/apikey",
            headers=headers,
            json={
                "alias": current_alias,
                "email": email,
                "organization": organization,
                "domains": [],  # vacío = sin restricción de dominio (rate limit más bajo, pero sirve para desarrollo)
            },
        )

        print(f"\n--- Respuesta cruda ({response.status_code}) para alias '{current_alias}' ---")
        print(response.text)
        print("--- fin respuesta cruda ---\n")

        if response.status_code == 409:
            print(f"Ya existe una key con el alias '{current_alias}'. Reintentando con otro alias...")
            continue

        response.raise_for_status()
        body = response.json()
        data = body["data"]

        # La documentación dice que 'data' es una lista de keys, pero puede que
        # tu cuenta reciba un solo objeto en vez de una lista. Manejamos ambos casos.
        if isinstance(data, list):
            return data[0]["api_key"]
        return data["api_key"]

    raise RuntimeError(
        "No se pudo crear la API key tras varios intentos (todos dieron 409). "
        "Es muy probable que ya tengas una key creada: revísala en "
        "https://www.globalforestwatch.org/my-gfw/ en la sección de Apps/API Keys."
    )


if __name__ == "__main__":
    email = input("Email de tu cuenta GFW: ").strip()
    password = getpass.getpass("Password de tu cuenta GFW (no se muestra en pantalla): ")

    print("Pidiendo access token...")
    token = get_access_token(email, password)
    print("Access token obtenido.")

    alias = input("Alias para tu API key (ej: cafetrace-dev): ").strip()
    organization = input("Nombre de tu organización (ej: CafeTrace SV): ").strip()

    print("Pidiendo API key...")
    api_key = get_api_key(token, email, alias, organization)

    print("\n✅ Tu API key:")
    print(api_key)
    print("\nGuárdala en tu .env así:")
    print(f"GFW_API_KEY={api_key}")