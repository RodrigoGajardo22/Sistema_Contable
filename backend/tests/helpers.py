"""Helpers para hablar con la API en los tests."""

from flask.testing import FlaskClient

from tests.conftest import PASSWORD


def login(client: FlaskClient, email: str = "admin@test.com", password: str = PASSWORD):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def autorizacion(
    client: FlaskClient,
    email: str = "admin@test.com",
    password: str = PASSWORD,
) -> dict[str, str]:
    respuesta = login(client, email, password)
    assert respuesta.status_code == 200, respuesta.get_json()
    token = respuesta.get_json()["datos"]["access_token"]
    return {"Authorization": f"Bearer {token}"}
