"""Tests de clientes: CUIT, permisos y versionado append-only."""

from app.extensions import db
from app.models.usuario import Rol
from tests.helpers import autorizacion, login

CUIT_A = "20123456786"
CUIT_B = "30712345671"
CUIT_C = "27123456780"


def _cliente(**extra):
    datos = {
        "razon_social": "Panadería La Espiga SRL",
        "cuit": CUIT_A,
        "condicion_iva": "responsable_inscripto",
        "telefono": "2920-123456",
        "direccion": "Belgrano 123, Viedma",
    }
    datos.update(extra)
    datos.setdefault("email", f"contacto-{datos['cuit'].replace('-', '')}@test.com")
    return datos


# --------------------------------------------------------------------------
# Alta y CUIT
# --------------------------------------------------------------------------
def test_crear_cliente_crea_la_primera_version(client, admin):
    respuesta = client.post(
        "/api/clientes", json=_cliente(), headers=autorizacion(client)
    )

    assert respuesta.status_code == 201
    datos = respuesta.get_json()["datos"]
    assert datos["cuit"] == CUIT_A
    assert datos["razon_social"] == "Panadería La Espiga SRL"
    assert datos["condicion_iva_etiqueta"] == "Responsable Inscripto"
    assert datos["version_id"] > 0
    assert datos["actualizado_por"] == "Admin"


def test_cuit_invalido(client, admin):
    respuesta = client.post(
        "/api/clientes",
        json=_cliente(cuit="20123456780"),
        headers=autorizacion(client),
    )

    assert respuesta.status_code == 422
    assert respuesta.get_json()["error"]["codigo"] == "cuit_invalido"


def test_cuit_duplicado_ignora_guiones(client, admin):
    client.post("/api/clientes", json=_cliente(), headers=autorizacion(client))

    respuesta = client.post(
        "/api/clientes",
        json=_cliente(cuit="20-12345678-6"),
        headers=autorizacion(client),
    )

    assert respuesta.status_code == 409
    assert respuesta.get_json()["error"]["codigo"] == "cuit_duplicado"


# --------------------------------------------------------------------------
# Versionado
# --------------------------------------------------------------------------
def test_actualizar_inserta_version_y_la_lista_muestra_la_ultima(client, admin):
    creado = client.post(
        "/api/clientes", json=_cliente(), headers=autorizacion(client)
    ).get_json()["datos"]

    respuesta = client.put(
        f"/api/clientes/{creado['id']}",
        json={"condicion_iva": "monotributo", "direccion": "Saavedra 45"},
        headers=autorizacion(client),
    )

    assert respuesta.status_code == 200
    actualizado = respuesta.get_json()["datos"]
    assert actualizado["condicion_iva"] == "monotributo"
    assert actualizado["direccion"] == "Saavedra 45"
    assert actualizado["razon_social"] == creado["razon_social"]
    assert actualizado["version_id"] > creado["version_id"]

    listado = client.get("/api/clientes", headers=autorizacion(client)).get_json()
    assert listado["datos"][0]["condicion_iva"] == "monotributo"


def test_historial_trae_todas_las_versiones_en_orden(client, admin):
    creado = client.post(
        "/api/clientes", json=_cliente(), headers=autorizacion(client)
    ).get_json()["datos"]

    client.put(
        f"/api/clientes/{creado['id']}",
        json={"condicion_iva": "exento"},
        headers=autorizacion(client),
    )

    respuesta = client.get(
        f"/api/clientes/{creado['id']}/historial", headers=autorizacion(client)
    )

    assert respuesta.status_code == 200
    versiones = respuesta.get_json()["datos"]
    assert len(versiones) == 2
    assert versiones[0]["condicion_iva"] == "exento"
    assert versiones[1]["condicion_iva"] == "responsable_inscripto"


def test_actualizar_sin_cambios_no_crea_version(client, admin):
    creado = client.post(
        "/api/clientes", json=_cliente(), headers=autorizacion(client)
    ).get_json()["datos"]

    respuesta = client.put(
        f"/api/clientes/{creado['id']}",
        json={"razon_social": creado["razon_social"]},
        headers=autorizacion(client),
    )

    assert respuesta.get_json()["datos"]["version_id"] == creado["version_id"]

    historial = client.get(
        f"/api/clientes/{creado['id']}/historial", headers=autorizacion(client)
    ).get_json()
    assert historial["meta"]["total"] == 1


# --------------------------------------------------------------------------
# Permisos
# --------------------------------------------------------------------------
def test_contador_solo_ve_sus_clientes(client, admin, contador):
    propio = client.post(
        "/api/clientes",
        json=_cliente(contador_id=contador.id),
        headers=autorizacion(client),
    ).get_json()["datos"]

    ajeno = client.post(
        "/api/clientes",
        json=_cliente(razon_social="Ferretería Ajena", cuit=CUIT_B),
        headers=autorizacion(client),
    ).get_json()["datos"]

    cabecera = autorizacion(client, "contador@test.com")
    listado = client.get("/api/clientes", headers=cabecera).get_json()

    assert listado["meta"]["total"] == 1
    assert listado["datos"][0]["id"] == propio["id"]

    # 404, no 403: no revelamos que el cliente ajeno existe.
    detalle = client.get(f"/api/clientes/{ajeno['id']}", headers=cabecera)
    assert detalle.status_code == 404


def test_contador_crea_cliente_y_queda_autoasignado(client, admin, contador):
    respuesta = client.post(
        "/api/clientes",
        json=_cliente(cuit=CUIT_C, contador_id=admin.id),
        headers=autorizacion(client, "contador@test.com"),
    )

    assert respuesta.status_code == 201
    assert respuesta.get_json()["datos"]["contador_id"] == contador.id


def test_contador_no_puede_reasignar(client, admin, contador):
    creado = client.post(
        "/api/clientes",
        json=_cliente(contador_id=contador.id),
        headers=autorizacion(client),
    ).get_json()["datos"]

    respuesta = client.put(
        f"/api/clientes/{creado['id']}",
        json={"contador_id": admin.id},
        headers=autorizacion(client, "contador@test.com"),
    )

    assert respuesta.status_code == 403


def test_admin_reasigna_y_el_contador_lo_ve(client, admin, contador):
    creado = client.post(
        "/api/clientes", json=_cliente(), headers=autorizacion(client)
    ).get_json()["datos"]

    cabecera = autorizacion(client, "contador@test.com")
    assert client.get("/api/clientes", headers=cabecera).get_json()["meta"]["total"] == 0

    client.put(
        f"/api/clientes/{creado['id']}",
        json={"contador_id": contador.id},
        headers=autorizacion(client),
    )

    assert client.get("/api/clientes", headers=cabecera).get_json()["meta"]["total"] == 1


# --------------------------------------------------------------------------
# Baja
# --------------------------------------------------------------------------
def test_baja_logica(client, admin):
    creado = client.post(
        "/api/clientes", json=_cliente(), headers=autorizacion(client)
    ).get_json()["datos"]

    respuesta = client.delete(
        f"/api/clientes/{creado['id']}", headers=autorizacion(client)
    )

    assert respuesta.status_code == 200
    assert respuesta.get_json()["datos"]["activo"] is False

    activos = client.get("/api/clientes?activo=true", headers=autorizacion(client))
    assert activos.get_json()["meta"]["total"] == 0


def test_contador_no_puede_dar_de_baja_un_cliente_ajeno(client, admin, contador):
    ajeno = client.post(
        "/api/clientes", json=_cliente(), headers=autorizacion(client)
    ).get_json()["datos"]

    respuesta = client.delete(
        f"/api/clientes/{ajeno['id']}",
        headers=autorizacion(client, "contador@test.com"),
    )

    assert respuesta.status_code == 404


def test_dashboard_cuenta_solo_clientes_activos(client, admin):
    creado = client.post(
        "/api/clientes", json=_cliente(), headers=autorizacion(client)
    ).get_json()["datos"]
    cabecera = autorizacion(client)

    activo = client.get("/api/dashboard", headers=cabecera).get_json()["datos"]
    assert activo["clientes"] == 1

    assert client.delete(f"/api/clientes/{creado['id']}", headers=cabecera).status_code == 200
    inactivo = client.get("/api/dashboard", headers=cabecera).get_json()["datos"]
    assert inactivo["clientes"] == 0


def test_cliente_rol_sin_vinculo_no_ve_nada(client, admin):
    from app.extensions import db
    from app.models.usuario import Usuario
    from app.utils.security import hashear_password

    db.session.add(
        Usuario(
            nombre="Cliente Suelto",
            email="suelto@test.com",
            password_hash=hashear_password("Secreta1234"),
            rol=Rol.CLIENTE.value,
            activo=True,
        )
    )
    db.session.commit()

    client.post("/api/clientes", json=_cliente(), headers=autorizacion(client))

    cabecera = autorizacion(client, "suelto@test.com")
    listado = client.get("/api/clientes", headers=cabecera)
    dashboard = client.get("/api/dashboard", headers=cabecera).get_json()["datos"]

    assert listado.status_code == 403
    assert dashboard["clientes"] == 0
    assert dashboard["responsable"] is None
    assert login(client, "suelto@test.com").status_code == 200
