"""Tests de autenticación: Argon2id, login genérico y bloqueo por intentos."""

from app.extensions import db
from tests.conftest import PASSWORD
from tests.helpers import autorizacion, login


def test_password_se_guarda_con_argon2id(admin):
    assert admin.password_hash.startswith("$argon2id$")
    assert PASSWORD not in admin.password_hash


def test_login_ok(client, admin):
    respuesta = login(client)

    assert respuesta.status_code == 200
    datos = respuesta.get_json()["datos"]
    assert datos["usuario"]["email"] == "admin@test.com"
    assert datos["usuario"]["rol"] == "admin"
    assert datos["access_token"]
    assert datos["refresh_token"]


def test_login_password_incorrecta(client, admin):
    respuesta = login(client, password="otra-clave")

    assert respuesta.status_code == 401
    assert respuesta.get_json()["error"]["codigo"] == "credenciales_invalidas"


def test_login_email_inexistente_responde_igual_que_existente(client, admin):
    existente = login(client, email="admin@test.com", password="mala")
    inexistente = login(client, email="nadie@test.com", password="mala")

    assert existente.status_code == inexistente.status_code == 401
    assert existente.get_json() == inexistente.get_json()


def test_login_usuario_inactivo_responde_generico(client, admin):
    admin.activo = False
    db.session.commit()

    respuesta = login(client)

    assert respuesta.status_code == 401
    assert respuesta.get_json()["error"]["codigo"] == "credenciales_invalidas"


def test_refresh_entrega_un_access_nuevo(client, admin):
    tokens = login(client).get_json()["datos"]

    respuesta = client.post(
        "/api/auth/refresh",
        headers={"Authorization": f"Bearer {tokens['refresh_token']}"},
    )

    assert respuesta.status_code == 200
    assert respuesta.get_json()["datos"]["access_token"]


def test_me_sin_token(client):
    respuesta = client.get("/api/auth/me")

    assert respuesta.status_code == 401
    assert respuesta.get_json()["error"]["codigo"] == "token_ausente"


def test_me_con_token(client, admin):
    respuesta = client.get("/api/auth/me", headers=autorizacion(client))

    assert respuesta.status_code == 200
    assert respuesta.get_json()["datos"]["email"] == "admin@test.com"


def test_bloqueo_despues_de_tres_fallos(client, admin):
    for _ in range(3):
        assert login(client, password="mala").status_code == 401

    bloqueado = login(client, password="mala")

    assert bloqueado.status_code == 429
    assert bloqueado.get_json()["error"]["codigo"] == "demasiados_intentos"
    assert bloqueado.get_json()["error"]["detalles"]["reintentar_en_segundos"] > 0
    assert "Retry-After" in bloqueado.headers


def test_bloqueo_ignora_la_password_correcta(client, admin):
    for _ in range(3):
        login(client, password="mala")

    respuesta = login(client)

    assert respuesta.status_code == 429


def test_bloqueo_de_un_email_no_afecta_a_otro(client, admin, contador):
    for _ in range(3):
        login(client, email="admin@test.com", password="mala")

    respuesta = login(client, email="contador@test.com")

    assert respuesta.status_code == 200


def test_bloqueo_tambien_aplica_a_emails_inexistentes(client, admin):
    for _ in range(3):
        login(client, email="fantasma@test.com", password="mala")

    respuesta = login(client, email="fantasma@test.com", password="mala")

    assert respuesta.status_code == 429
