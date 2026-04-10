import re

import hvac


def parse_vault_params(schema: str) -> dict[str, str]:
    """
    Parse parameters from the schema.

    Schema in the form `!vault KEY1=VALUE1 KEY2=VALUE2 ...`.
    """
    match = re.match(r"!vault\s+(?P<pairs>.+)", schema)

    if match is None:
        raise ValueError(f'Invalid Vault schema: "{schema}"')

    pairs = match.group("pairs")
    params = {}

    for pair in pairs.split():
        key, value = pair.split("=")
        params[key] = value

    return params


def vault_connect(params: dict[str, str]) -> hvac.Client:
    """
    Setup connection with Vault.
    """
    for key in ("URL", "ROLE_ID", "SECRET_ID"):
        if key not in params:
            raise ValueError(f"{key} parameter is required")

    client = hvac.Client(url=params["URL"])

    client.auth.approle.login(role_id=params["ROLE_ID"], secret_id=params["SECRET_ID"])

    return client


def vault_get_value(client: hvac.Client, kv: str, path: str, key: str) -> str:
    """
    Get value from Vault Key-Value store.
    """
    response = client.secrets.kv.v2.read_secret_version(path=path, mount_point=kv)
    return response["data"]["data"][key]
