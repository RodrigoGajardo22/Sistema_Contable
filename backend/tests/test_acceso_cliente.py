"""Tests del acceso del rol cliente y de la conciliación completa."""

from datetime import date

from tests.helpers import autorizacion

HOY = date.today().isoformat()
CUIT = "20123456786"
PASSWORD_CLIENTE = "ClaveCliente123"


def _cliente(client, email="cliente@test.com", **extra):
    datos = {
        "razon_social": "Panadería La Espiga SRL",
        "cuit": CUIT,
        "condicion_iva": "responsable_inscripto",
        "email": email,
    }
    datos.update(extra)
    respuesta = client.post(
        "/api/clientes", json=datos, headers=autorizacion(client)
    )
    assert respuesta.status_code == 201, respuesta.get_json()
    return respuesta.get_json()["datos"]


def _login_temporal(client, cliente):
    return client.post(
        "/api/auth/login",
        json={
            "email": cliente["email"],
            "password": cliente["acceso_temporal"],
        },
    )


def _cliente_con_acceso(client, email="cliente@test.com", **extra):
    """Crea el cliente, cambia la clave temporal y devuelve una sesión lista."""
    cliente = _cliente(client, email=email, **extra)

    login = _login_temporal(client, cliente)
    assert login.status_code == 200, login.get_json()
    sesion = login.get_json()["datos"]
    cabecera_temporal = {"Authorization": f"Bearer {sesion['access_token']}"}

    cambio = client.put(
        f"/api/usuarios/{sesion['usuario']['id']}/password",
        json={
            "password_actual": cliente["acceso_temporal"],
            "password_nueva": PASSWORD_CLIENTE,
        },
        headers=cabecera_temporal,
    )
    assert cambio.status_code == 200, cambio.get_json()

    return cliente, autorizacion(client, email, PASSWORD_CLIENTE)


# --------------------------------------------------------------------------
# Acceso del rol cliente
# --------------------------------------------------------------------------
def test_alta_de_cliente_crea_acceso_y_obliga_cambio(client, admin):
    cliente = _cliente(client)

    assert cliente["usuario_id"] is not None
    assert cliente["usuario_email"] == "cliente@test.com"
    assert cliente["usuario_activo"] is True
    assert cliente["acceso_temporal"]

    login = _login_temporal(client, cliente)
    assert login.status_code == 200
    datos = login.get_json()["datos"]
    assert datos["usuario"]["rol"] == "cliente"
    assert datos["usuario"]["debe_cambiar_password"] is True
    assert datos["usuario"]["cliente_id"] == cliente["id"]

    cabecera = {"Authorization": f"Bearer {datos['access_token']}"}
    bloqueado = client.get("/api/clientes", headers=cabecera)
    assert bloqueado.status_code == 403
    assert bloqueado.get_json()["error"]["codigo"] == "cambio_password_requerido"

    cambio = client.put(
        f"/api/usuarios/{datos['usuario']['id']}/password",
        json={
            "password_actual": cliente["acceso_temporal"],
            "password_nueva": PASSWORD_CLIENTE,
        },
        headers=cabecera,
    )
    assert cambio.status_code == 200

    # El token anterior queda invalidado por el cambio de clave.
    assert client.get("/api/auth/me", headers=cabecera).status_code == 401

    cabecera = autorizacion(client, "cliente@test.com", PASSWORD_CLIENTE)
    ficha = client.get(f"/api/clientes/{cliente['id']}", headers=cabecera)
    assert ficha.status_code == 200
    assert ficha.get_json()["datos"]["usuario_nombre"] == "Panadería La Espiga SRL"

    listado = client.get("/api/clientes", headers=cabecera)
    assert listado.status_code == 403


def test_dashboard_y_perfil_del_cliente(client, admin):
    cliente, cabecera = _cliente_con_acceso(client)

    perfil = client.get("/api/auth/me", headers=cabecera).get_json()["datos"]
    assert perfil["cliente_id"] == cliente["id"]

    client.post(
        f"/api/clientes/{cliente['id']}/comprobantes",
        json={
            "tipo": "compra",
            "numero": "C-DASH-1",
            "fecha": HOY,
            "tercero": "Proveedor SA",
            "neto": "10.00",
            "alicuota_iva": "21.00",
        },
        headers=cabecera,
    )

    dashboard = client.get("/api/dashboard", headers=cabecera).get_json()["datos"]
    assert dashboard["clientes"] == 1
    assert dashboard["comprobantes_pendientes"] == 1
    assert dashboard["responsable"]["nombre"] == "Admin"
    assert dashboard["responsable"]["email"] == "admin@test.com"


def test_cliente_no_ve_clientes_ajenos(client, admin):
    cliente, cabecera = _cliente_con_acceso(client)
    otro = _cliente(
        client,
        email="otro@test.com",
        cuit="30712345671",
        razon_social="Otra SA",
    )

    assert client.get(f"/api/clientes/{otro['id']}", headers=cabecera).status_code == 404
    assert (
        client.get(
            f"/api/clientes/{otro['id']}/comprobantes", headers=cabecera
        ).status_code
        == 404
    )


def test_cliente_lee_sus_comprobantes_pero_no_escribe(client, admin):
    cliente, cabecera = _cliente_con_acceso(client)

    lectura = client.get(
        f"/api/clientes/{cliente['id']}/comprobantes", headers=cabecera
    )
    assert lectura.status_code == 200

    escritura = client.post(
        f"/api/clientes/{cliente['id']}/comprobantes",
        json={
            "tipo": "venta",
            "numero": "X-1",
            "fecha": HOY,
            "tercero": "Proveedor",
            "neto": "10.00",
            "alicuota_iva": "21.00",
        },
        headers=cabecera,
    )
    assert escritura.status_code == 403

    compra = client.post(
        f"/api/clientes/{cliente['id']}/comprobantes",
        json={
            "tipo": "compra",
            "numero": "C-1",
            "fecha": HOY,
            "tercero": "Proveedor SA",
            "neto": "10.00",
            "alicuota_iva": "21.00",
        },
        headers=cabecera,
    )
    assert compra.status_code == 201
    assert compra.get_json()["datos"]["estado"] == "pendiente"


def test_no_se_crea_rol_cliente_desde_usuarios(client, admin):
    respuesta = client.post(
        "/api/usuarios",
        json={
            "nombre": "Suelto",
            "email": "suelto@test.com",
            "password": "ClaveSegura123",
            "rol": "cliente",
        },
        headers=autorizacion(client),
    )

    assert respuesta.status_code == 422


def test_acceso_duplicado_revocacion_y_restablecimiento(client, admin):
    cliente, _ = _cliente_con_acceso(client)

    duplicado = client.post(
        f"/api/clientes/{cliente['id']}/acceso", headers=autorizacion(client)
    )
    assert duplicado.status_code == 409
    assert duplicado.get_json()["error"]["codigo"] == "acceso_existente"

    revocado = client.delete(
        f"/api/clientes/{cliente['id']}/acceso", headers=autorizacion(client)
    )
    assert revocado.status_code == 200

    detalle = client.get(
        f"/api/clientes/{cliente['id']}", headers=autorizacion(client)
    ).get_json()["datos"]
    assert detalle["usuario_id"] == cliente["usuario_id"]
    assert detalle["usuario_activo"] is False

    login = client.post(
        "/api/auth/login",
        json={"email": "cliente@test.com", "password": PASSWORD_CLIENTE},
    )
    assert login.status_code == 401

    reset = client.post(
        f"/api/clientes/{cliente['id']}/acceso/reset",
        headers=autorizacion(client),
    )
    assert reset.status_code == 200
    nuevo_temporal = reset.get_json()["datos"]["password_temporal"]
    assert nuevo_temporal

    assert (
        client.post(
            "/api/auth/login",
            json={"email": "cliente@test.com", "password": PASSWORD_CLIENTE},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/auth/login",
            json={"email": "cliente@test.com", "password": nuevo_temporal},
        ).status_code
        == 200
    )


def test_contador_gestiona_el_acceso_de_sus_clientes(client, admin, contador):
    cliente = _cliente(client, email="cliente.contador@test.com", contador_id=contador.id)
    cabecera_contador = autorizacion(client, "contador@test.com")

    reset = client.post(
        f"/api/clientes/{cliente['id']}/acceso/reset", headers=cabecera_contador
    )
    assert reset.status_code == 200

    ajeno = _cliente(client, email="ajeno@test.com", cuit="30712345671")
    negado = client.post(
        f"/api/clientes/{ajeno['id']}/acceso/reset", headers=cabecera_contador
    )
    assert negado.status_code == 404


def test_baja_de_cliente_desactiva_el_acceso_y_la_reactivacion_lo_restaura(
    client, admin
):
    cliente, _ = _cliente_con_acceso(client)

    baja = client.delete(
        f"/api/clientes/{cliente['id']}", headers=autorizacion(client)
    )
    assert baja.status_code == 200
    assert baja.get_json()["datos"]["usuario_activo"] is False

    assert (
        client.post(
            "/api/auth/login",
            json={"email": "cliente@test.com", "password": PASSWORD_CLIENTE},
        ).status_code
        == 401
    )

    activar = client.post(
        f"/api/clientes/{cliente['id']}/activar", headers=autorizacion(client)
    )
    assert activar.status_code == 200
    assert activar.get_json()["datos"]["activo"] is True
    assert activar.get_json()["datos"]["usuario_activo"] is True

    assert (
        client.post(
            "/api/auth/login",
            json={"email": "cliente@test.com", "password": PASSWORD_CLIENTE},
        ).status_code
        == 200
    )


# --------------------------------------------------------------------------
# Conciliación completa
# --------------------------------------------------------------------------
def _asiento(client, cliente_id, importe="1000.00"):
    from sqlalchemy import select

    from app.extensions import db
    from app.models.cuenta import Cuenta

    cuentas = {
        c.codigo: c
        for c in db.session.scalars(
            select(Cuenta).where(Cuenta.cliente_id == cliente_id)
        )
    }
    asiento = client.post(
        f"/api/clientes/{cliente_id}/asientos",
        json={
            "fecha": HOY,
            "concepto": "Venta",
            "renglones": [
                {"cuenta_id": cuentas["1.1.01"].id, "debe": importe, "haber": "0.00"},
                {"cuenta_id": cuentas["4.1.01"].id, "debe": "0.00", "haber": importe},
            ],
        },
        headers=autorizacion(client),
    ).get_json()["datos"]
    client.post(f"/api/asientos/{asiento['id']}/confirmar", headers=autorizacion(client))
    return asiento


def _extracto(client, cliente_id, csv="", final="1000.00"):
    return client.post(
        f"/api/clientes/{cliente_id}/extractos",
        json={
            "banco": "Galicia",
            "periodo": "2026-11",
            "saldo_inicial": "0.00",
            "saldo_final": final,
            "csv": csv,
        },
        headers=autorizacion(client),
    ).get_json()["datos"]


def test_desvincular_y_saldo_contable(client, admin):
    cliente = _cliente(client)
    asiento = _asiento(client, cliente["id"])
    extracto = _extracto(
        client, cliente["id"], f"fecha;desc;importe\n{HOY};Transf;1000,00\n"
    )
    movimiento = extracto["movimientos"][0]

    client.put(
        f"/api/movimientos/{movimiento['id']}/vincular",
        json={"asiento_id": asiento["id"]},
        headers=autorizacion(client),
    )

    detalle = client.get(
        f"/api/extractos/{extracto['id']}", headers=autorizacion(client)
    ).get_json()["datos"]
    assert detalle["resumen"]["saldo_contable"] == "1000.00"

    desvinculado = client.put(
        f"/api/movimientos/{movimiento['id']}/desvincular", headers=autorizacion(client)
    )
    assert desvinculado.status_code == 200
    assert desvinculado.get_json()["datos"]["estado"] == "pendiente"


def test_un_asiento_no_se_vincula_dos_veces(client, admin):
    cliente = _cliente(client)
    asiento = _asiento(client, cliente["id"])
    extracto = _extracto(
        client,
        cliente["id"],
        f"fecha;desc;importe\n{HOY};Uno;1000,00\n{HOY};Dos;1000,00\n",
        "2000.00",
    )

    primero, segundo = extracto["movimientos"][0], extracto["movimientos"][1]

    ok = client.put(
        f"/api/movimientos/{primero['id']}/vincular",
        json={"asiento_id": asiento["id"]},
        headers=autorizacion(client),
    )
    assert ok.status_code == 200

    repetido = client.put(
        f"/api/movimientos/{segundo['id']}/vincular",
        json={"asiento_id": asiento["id"]},
        headers=autorizacion(client),
    )
    assert repetido.status_code == 409
    assert repetido.get_json()["error"]["codigo"] == "asiento_ya_vinculado"
