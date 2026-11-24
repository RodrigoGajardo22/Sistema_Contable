"""Bandeja global de comprobantes y agenda de vencimientos del contador."""

from datetime import date

from tests.helpers import autorizacion

HOY = date.today().isoformat()


def _crear_cliente(client, *, cuit: str, email: str, contador_id: int):
    respuesta = client.post(
        "/api/clientes",
        json={
            "razon_social": f"Cliente {cuit}",
            "cuit": cuit,
            "condicion_iva": "responsable_inscripto",
            "email": email,
            "contador_id": contador_id,
        },
        headers=autorizacion(client),
    )
    assert respuesta.status_code == 201, respuesta.get_json()
    return respuesta.get_json()["datos"]


def _crear_contador(client, email: str):
    respuesta = client.post(
        "/api/usuarios",
        json={
            "nombre": "Contador Dos",
            "email": email,
            "password": "ClaveSegura123",
            "rol": "contador",
        },
        headers=autorizacion(client),
    )
    assert respuesta.status_code == 201, respuesta.get_json()
    return respuesta.get_json()["datos"]


def test_bandeja_y_agenda_aislan_la_cartera(client, admin, contador):
    otro = _crear_contador(client, "contador2@test.com")

    cliente_a = _crear_cliente(
        client,
        cuit="20123456786",
        email="cliente.a@test.com",
        contador_id=contador.id,
    )
    cliente_b = _crear_cliente(
        client,
        cuit="30712345671",
        email="cliente.b@test.com",
        contador_id=otro["id"],
    )

    for cliente, numero in ((cliente_a, "C-A-1"), (cliente_b, "C-B-1")):
        client.post(
            f"/api/clientes/{cliente['id']}/comprobantes",
            json={
                "tipo": "compra",
                "numero": numero,
                "fecha": HOY,
                "tercero": "Proveedor SA",
                "neto": "100.00",
                "alicuota_iva": "21.00",
            },
            headers=autorizacion(client),
        )
        client.post(
            f"/api/clientes/{cliente['id']}/vencimientos",
            json={
                "obligacion": "iva",
                "periodo": "2026-11",
                "fecha_vencimiento": HOY,
            },
            headers=autorizacion(client),
        )

    cabecera = autorizacion(client, "contador@test.com")
    bandeja = client.get(
        "/api/comprobantes?estado=pendiente", headers=cabecera
    ).get_json()["datos"]
    agenda = client.get("/api/vencimientos", headers=cabecera).get_json()["datos"]

    assert len(bandeja) == 1
    assert bandeja[0]["cliente_nombre"] == cliente_a["razon_social"]
    assert len(agenda) == 1
    assert agenda[0]["cliente_nombre"] == cliente_a["razon_social"]

    cabecera_otro = autorizacion(
        client, "contador2@test.com", "ClaveSegura123"
    )
    bandeja_otro = client.get(
        "/api/comprobantes?estado=pendiente", headers=cabecera_otro
    ).get_json()["datos"]
    agenda_otro = client.get(
        "/api/vencimientos", headers=cabecera_otro
    ).get_json()["datos"]

    assert len(bandeja_otro) == 1
    assert bandeja_otro[0]["cliente_nombre"] == cliente_b["razon_social"]
    assert len(agenda_otro) == 1
    assert agenda_otro[0]["cliente_nombre"] == cliente_b["razon_social"]

    # El admin ve las dos carteras.
    assert (
        len(
            client.get(
                "/api/comprobantes?estado=pendiente",
                headers=autorizacion(client),
            ).get_json()["datos"]
        )
        == 2
    )
    assert (
        len(
            client.get("/api/vencimientos", headers=autorizacion(client)).get_json()[
                "datos"
            ]
        )
        == 2
    )


def test_bandeja_y_agenda_no_son_para_clientes(client, admin, contador):
    cliente = _crear_cliente(
        client,
        cuit="27123456780",
        email="cliente.global@test.com",
        contador_id=contador.id,
    )

    login = client.post(
        "/api/auth/login",
        json={
            "email": cliente["email"],
            "password": cliente["acceso_temporal"],
        },
    )
    cabecera = {
        "Authorization": f"Bearer {login.get_json()['datos']['access_token']}"
    }

    assert client.get("/api/comprobantes", headers=cabecera).status_code == 403
    assert client.get("/api/vencimientos", headers=cabecera).status_code == 403
