"""Tests del CRUD de usuarios y sus reglas de negocio."""

from app.extensions import db
from tests.conftest import PASSWORD
from tests.helpers import autorizacion, login


def _nuevo(**extra):
    datos = {
        "nombre": "Nuevo Usuario",
        "email": "nuevo@test.com",
        "password": "ClaveSegura123",
        "rol": "contador",
    }
    datos.update(extra)
    return datos


# --------------------------------------------------------------------------
# Permisos
# --------------------------------------------------------------------------
def test_listar_requiere_admin(client, contador):
    respuesta = client.get(
        "/api/usuarios",
        headers=autorizacion(client, "contador@test.com"),
    )

    assert respuesta.status_code == 403
    assert respuesta.get_json()["error"]["codigo"] == "sin_permiso"


def test_admin_lista_y_filtra(client, admin, contador):
    respuesta = client.get("/api/usuarios", headers=autorizacion(client))
    assert respuesta.status_code == 200
    assert respuesta.get_json()["meta"]["total"] == 2

    solo_contadores = client.get(
        "/api/usuarios?rol=contador", headers=autorizacion(client)
    )
    assert solo_contadores.get_json()["meta"]["total"] == 1

    busqueda = client.get("/api/usuarios?q=admin", headers=autorizacion(client))
    assert busqueda.get_json()["meta"]["total"] == 1


# --------------------------------------------------------------------------
# Alta
# --------------------------------------------------------------------------
def test_crear_usuario(client, admin):
    respuesta = client.post(
        "/api/usuarios", json=_nuevo(), headers=autorizacion(client)
    )

    assert respuesta.status_code == 201
    datos = respuesta.get_json()["datos"]
    assert datos["email"] == "nuevo@test.com"
    assert datos["activo"] is True
    assert "password_hash" not in datos
    assert "password" not in datos


def test_email_duplicado_ignora_mayusculas(client, admin, contador):
    respuesta = client.post(
        "/api/usuarios",
        json=_nuevo(email="CONTADOR@test.com"),
        headers=autorizacion(client),
    )

    assert respuesta.status_code == 409
    assert respuesta.get_json()["error"]["codigo"] == "email_duplicado"


def test_password_corta_es_rechazada(client, admin):
    respuesta = client.post(
        "/api/usuarios",
        json=_nuevo(password="corta"),
        headers=autorizacion(client),
    )

    assert respuesta.status_code == 422
    assert respuesta.get_json()["error"]["codigo"] == "validacion"


# --------------------------------------------------------------------------
# Baja lógica
# --------------------------------------------------------------------------
def test_baja_logica_impide_el_login(client, admin, contador):
    respuesta = client.delete(
        f"/api/usuarios/{contador.id}", headers=autorizacion(client)
    )

    assert respuesta.status_code == 200
    assert respuesta.get_json()["datos"]["activo"] is False
    assert login(client, "contador@test.com").status_code == 401


def test_no_puedo_desactivarme(client, admin):
    respuesta = client.delete(
        f"/api/usuarios/{admin.id}", headers=autorizacion(client)
    )

    assert respuesta.status_code == 409
    assert respuesta.get_json()["error"]["codigo"] == "accion_invalida"


def test_reactivar_usuario(client, admin, contador):
    client.delete(f"/api/usuarios/{contador.id}", headers=autorizacion(client))

    respuesta = client.post(
        f"/api/usuarios/{contador.id}/activar", headers=autorizacion(client)
    )

    assert respuesta.status_code == 200
    assert respuesta.get_json()["datos"]["activo"] is True
    assert login(client, "contador@test.com").status_code == 200


def test_el_propietario_no_puede_degradarse(client, admin):
    respuesta = client.put(
        f"/api/usuarios/{admin.id}",
        json={"rol": "contador"},
        headers=autorizacion(client),
    )

    assert respuesta.status_code == 409
    assert respuesta.get_json()["error"]["codigo"] == "propietario_protegido"


def test_admin_delegado_no_gestiona_administradores(client, admin, admin_delegado, contador):
    cabecera = autorizacion(client, "delegado@test.com")

    crear_admin = client.post(
        "/api/usuarios",
        json=_nuevo(rol="admin", email="otro-admin@test.com"),
        headers=cabecera,
    )
    assert crear_admin.status_code == 403

    baja_propietario = client.delete(
        f"/api/usuarios/{admin.id}", headers=cabecera
    )
    assert baja_propietario.status_code == 403

    reset_propietario = client.put(
        f"/api/usuarios/{admin.id}/password",
        json={"password_nueva": "OtraClave123"},
        headers=cabecera,
    )
    assert reset_propietario.status_code == 403

    promover = client.put(
        f"/api/usuarios/{contador.id}",
        json={"rol": "admin"},
        headers=cabecera,
    )
    assert promover.status_code == 403


def test_propietario_transfiere_la_propiedad(client, admin, admin_delegado):
    respuesta = client.post(
        f"/api/usuarios/{admin_delegado.id}/propietario",
        headers=autorizacion(client),
    )
    assert respuesta.status_code == 200
    assert respuesta.get_json()["datos"]["es_propietario"] is True

    perfil = client.get("/api/auth/me", headers=autorizacion(client)).get_json()["datos"]
    assert perfil["es_propietario"] is False

    nuevo = autorizacion(client, "delegado@test.com")
    perfil_nuevo = client.get("/api/auth/me", headers=nuevo).get_json()["datos"]
    assert perfil_nuevo["es_propietario"] is True

    # El admin degradado ya no puede crear administradores.
    crear = client.post(
        "/api/usuarios",
        json=_nuevo(email="otro-admin@test.com", rol="admin"),
        headers=autorizacion(client),
    )
    assert crear.status_code == 403


def test_no_se_desactiva_contador_con_clientes(client, admin, contador):
    cliente = client.post(
        "/api/clientes",
        json={
            "razon_social": "Cliente del contador",
            "cuit": "20123456786",
            "condicion_iva": "responsable_inscripto",
            "email": "cliente.contador@test.com",
            "contador_id": contador.id,
        },
        headers=autorizacion(client),
    ).get_json()["datos"]

    bloqueada = client.delete(
        f"/api/usuarios/{contador.id}", headers=autorizacion(client)
    )
    assert bloqueada.status_code == 409
    assert bloqueada.get_json()["error"]["codigo"] == "clientes_asignados"

    client.put(
        f"/api/clientes/{cliente['id']}",
        json={"contador_id": admin.id},
        headers=autorizacion(client),
    )

    ok = client.delete(f"/api/usuarios/{contador.id}", headers=autorizacion(client))
    assert ok.status_code == 200


def test_los_clientes_no_se_gestionan_desde_usuarios(client, admin):
    cliente = client.post(
        "/api/clientes",
        json={
            "razon_social": "Cliente con acceso",
            "cuit": "20123456786",
            "condicion_iva": "responsable_inscripto",
            "email": "cliente.usuarios@test.com",
        },
        headers=autorizacion(client),
    ).get_json()["datos"]

    editar = client.put(
        f"/api/usuarios/{cliente['usuario_id']}",
        json={"nombre": "Otro nombre"},
        headers=autorizacion(client),
    )
    assert editar.status_code == 409
    assert editar.get_json()["error"]["codigo"] == "usuario_cliente"

    baja = client.delete(
        f"/api/usuarios/{cliente['usuario_id']}", headers=autorizacion(client)
    )
    assert baja.status_code == 409

    reset = client.put(
        f"/api/usuarios/{cliente['usuario_id']}/password",
        json={"password_nueva": "OtraClave123"},
        headers=autorizacion(client),
    )
    assert reset.status_code == 409


# --------------------------------------------------------------------------
# Contraseñas
# --------------------------------------------------------------------------
def test_cambio_de_password_propia(client, admin):
    respuesta = client.put(
        f"/api/usuarios/{admin.id}/password",
        json={"password_actual": PASSWORD, "password_nueva": "NuevaClave123"},
        headers=autorizacion(client),
    )

    assert respuesta.status_code == 200
    assert login(client, password="NuevaClave123").status_code == 200


def test_cambio_de_password_actual_incorrecta(client, admin):
    respuesta = client.put(
        f"/api/usuarios/{admin.id}/password",
        json={"password_actual": "no-es", "password_nueva": "NuevaClave123"},
        headers=autorizacion(client),
    )

    assert respuesta.status_code == 400
    assert respuesta.get_json()["error"]["codigo"] == "password_incorrecta"


def test_contador_no_puede_cambiar_password_ajena(client, admin, contador):
    respuesta = client.put(
        f"/api/usuarios/{admin.id}/password",
        json={"password_nueva": "NuevaClave123"},
        headers=autorizacion(client, "contador@test.com"),
    )

    assert respuesta.status_code == 403


def test_admin_resetea_password_sin_la_actual(client, admin, contador):
    respuesta = client.put(
        f"/api/usuarios/{contador.id}/password",
        json={"password_nueva": "Reseteada123"},
        headers=autorizacion(client),
    )

    assert respuesta.status_code == 200
    assert login(client, "contador@test.com", "Reseteada123").status_code == 200


def test_un_cambio_de_password_invalida_los_tokens_viejos(client, admin):
    cabecera = autorizacion(client)

    cambio = client.put(
        f"/api/usuarios/{admin.id}/password",
        json={"password_actual": PASSWORD, "password_nueva": "NuevaClave123"},
        headers=cabecera,
    )
    assert cambio.status_code == 200

    viejo = client.get("/api/auth/me", headers=cabecera)
    assert viejo.status_code == 401
    assert viejo.get_json()["error"]["codigo"] == "token_revocado"


# --------------------------------------------------------------------------
# Aislamiento de la sesión
# --------------------------------------------------------------------------
def test_token_de_usuario_desactivado_deja_de_servir(client, admin, contador):
    cabecera = autorizacion(client, "contador@test.com")

    contador.activo = False
    db.session.commit()

    respuesta = client.get("/api/auth/me", headers=cabecera)

    assert respuesta.status_code == 401
    assert respuesta.get_json()["error"]["codigo"] == "usuario_inactivo"
