"""Tests de vencimientos, reportes, conciliación y auditoría."""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.extensions import db
from app.models.cuenta import Cuenta
from tests.helpers import autorizacion

HOY = date.today().isoformat()
CUIT = "20123456786"


def _cliente(client, **extra):
    datos = {
        "razon_social": "Panadería La Espiga SRL",
        "cuit": CUIT,
        "condicion_iva": "responsable_inscripto",
    }
    datos.update(extra)
    datos.setdefault("email", f"contacto-{datos['cuit'].replace('-', '')}@test.com")
    return client.post(
        "/api/clientes", json=datos, headers=autorizacion(client)
    ).get_json()["datos"]


def _cuentas(cliente_id: int) -> dict[str, Cuenta]:
    return {
        cuenta.codigo: cuenta
        for cuenta in db.session.scalars(
            select(Cuenta).where(Cuenta.cliente_id == cliente_id)
        )
    }


def _asiento_confirmado(client, cliente_id: int, importe: str = "1000.00"):
    cuentas = _cuentas(cliente_id)
    respuesta = client.post(
        f"/api/clientes/{cliente_id}/asientos",
        json={
            "fecha": HOY,
            "concepto": "Venta de mercadería",
            "renglones": [
                {"cuenta_id": cuentas["1.1.01"].id, "debe": importe, "haber": "0.00"},
                {"cuenta_id": cuentas["4.1.01"].id, "debe": "0.00", "haber": importe},
            ],
        },
        headers=autorizacion(client),
    )
    asiento = respuesta.get_json()["datos"]
    client.post(f"/api/asientos/{asiento['id']}/confirmar", headers=autorizacion(client))
    return asiento


# --------------------------------------------------------------------------
# Slice 6: vencimientos + dashboard
# --------------------------------------------------------------------------
def test_vencimiento_avanza_solo_hacia_adelante(client, admin):
    cliente = _cliente(client)

    creado = client.post(
        f"/api/clientes/{cliente['id']}/vencimientos",
        json={"obligacion": "iva", "periodo": "2026-11", "fecha_vencimiento": HOY},
        headers=autorizacion(client),
    )
    assert creado.status_code == 201
    vencimiento = creado.get_json()["datos"]
    assert vencimiento["estado"] == "pendiente"

    presentado = client.post(
        f"/api/vencimientos/{vencimiento['id']}/estado",
        json={"estado": "presentado"},
        headers=autorizacion(client),
    )
    assert presentado.status_code == 200

    pagado = client.post(
        f"/api/vencimientos/{vencimiento['id']}/estado",
        json={"estado": "pagado"},
        headers=autorizacion(client),
    )
    assert pagado.get_json()["datos"]["estado"] == "pagado"

    retroceso = client.post(
        f"/api/vencimientos/{vencimiento['id']}/estado",
        json={"estado": "presentado"},
        headers=autorizacion(client),
    )
    assert retroceso.status_code == 409
    assert retroceso.get_json()["error"]["codigo"] == "transicion_invalida"


def test_dashboard_cuenta_clientes_y_vencimientos(client, admin):
    cliente = _cliente(client)
    client.post(
        f"/api/clientes/{cliente['id']}/vencimientos",
        json={"obligacion": "ganancias", "periodo": "2026", "fecha_vencimiento": HOY},
        headers=autorizacion(client),
    )

    respuesta = client.get("/api/dashboard", headers=autorizacion(client))

    assert respuesta.status_code == 200
    datos = respuesta.get_json()["datos"]
    assert datos["clientes"] == 1
    assert datos["vencimientos"]["pendientes"] == 1


def test_vencimiento_aislado_por_contador(client, admin, contador):
    cliente = _cliente(client)

    respuesta = client.get(
        f"/api/clientes/{cliente['id']}/vencimientos",
        headers=autorizacion(client, "contador@test.com"),
    )

    assert respuesta.status_code == 404


# --------------------------------------------------------------------------
# Slice 7: reportes
# --------------------------------------------------------------------------
def test_balance_cuadra_y_mayor_acumula(client, admin):
    cliente = _cliente(client)
    _asiento_confirmado(client, cliente["id"], "1000.00")

    balance = client.get(
        f"/api/clientes/{cliente['id']}/reportes/balance",
        headers=autorizacion(client),
    ).get_json()["datos"]

    assert Decimal(balance["total_debe"]) == Decimal("1000.00")
    assert Decimal(balance["total_haber"]) == Decimal("1000.00")
    assert Decimal(balance["diferencia"]) == Decimal("0.00")

    cuenta = _cuentas(cliente["id"])["1.1.01"]
    mayor = client.get(
        f"/api/clientes/{cliente['id']}/reportes/mayor?cuenta={cuenta.id}",
        headers=autorizacion(client),
    ).get_json()["datos"]

    assert mayor["cuenta"]["codigo"] == "1.1.01"
    assert Decimal(mayor["saldo_final"]) == Decimal("1000.00")
    assert len(mayor["movimientos"]) == 1


def test_diario_solo_confirmados(client, admin):
    cliente = _cliente(client)
    _asiento_confirmado(client, cliente["id"])
    _asiento_confirmado(client, cliente["id"])

    diario = client.get(
        f"/api/clientes/{cliente['id']}/reportes/diario",
        headers=autorizacion(client),
    ).get_json()["datos"]

    assert len(diario) == 2
    assert len(diario[0]["renglones"]) == 2


def test_libro_iva_agrupa_ventas(client, admin):
    cliente = _cliente(client)
    comprobante = client.post(
        f"/api/clientes/{cliente['id']}/comprobantes",
        json={
            "tipo": "venta",
            "numero": "A-0001-1",
            "fecha": HOY,
            "tercero": "Cliente SA",
            "neto": "100000.00",
            "alicuota_iva": "21.00",
        },
        headers=autorizacion(client),
    ).get_json()["datos"]
    client.post(
        f"/api/comprobantes/{comprobante['id']}/contabilizar",
        headers=autorizacion(client),
    )

    libro = client.get(
        f"/api/clientes/{cliente['id']}/reportes/libro-iva",
        headers=autorizacion(client),
    ).get_json()["datos"]

    assert Decimal(libro["ventas"]["total"]) == Decimal("121000.00")
    assert Decimal(libro["compras"]["total"]) == Decimal("0.00")


# --------------------------------------------------------------------------
# Slice 8: conciliación
# --------------------------------------------------------------------------
def _importar(client, cliente_id, csv, saldo_final="1500.00"):
    return client.post(
        f"/api/clientes/{cliente_id}/extractos",
        json={
            "banco": "Galicia",
            "periodo": "2026-11",
            "saldo_inicial": "0.00",
            "saldo_final": saldo_final,
            "csv": csv,
        },
        headers=autorizacion(client),
    )


def test_importar_csv_y_resumen(client, admin):
    cliente = _cliente(client)
    csv = "fecha;descripcion;importe\n20/11/2026;Transferencia;1000,00\n21/11/2026;Pago;500,00\n"

    respuesta = _importar(client, cliente["id"], csv)

    assert respuesta.status_code == 201
    datos = respuesta.get_json()["datos"]
    assert len(datos["movimientos"]) == 2
    assert Decimal(datos["movimientos"][0]["importe"]) == Decimal("1000.00")
    assert Decimal(datos["resumen"]["diferencia"]) == Decimal("0.00")


def test_matching_sugiere_asiento_por_importe_y_fecha(client, admin):
    cliente = _cliente(client)
    asiento = _asiento_confirmado(client, cliente["id"], "1000.00")
    extracto = _importar(
        client,
        cliente["id"],
        f"fecha;descripcion;importe\n{HOY};Transferencia;1000,00\n",
        "1000.00",
    ).get_json()["datos"]

    detalle = client.get(
        f"/api/extractos/{extracto['id']}", headers=autorizacion(client)
    ).get_json()["datos"]

    sugerencias = detalle["movimientos"][0]["sugerencias"]
    assert len(sugerencias) == 1
    assert sugerencias[0]["asiento_id"] == asiento["id"]
    assert sugerencias[0]["confianza"] == 100


def test_vincular_y_descartar_movimiento(client, admin):
    cliente = _cliente(client)
    asiento = _asiento_confirmado(client, cliente["id"], "1000.00")
    extracto = _importar(
        client,
        cliente["id"],
        f"fecha;descripcion;importe\n{HOY};Transferencia;1000,00\n{HOY};Otro;50,00\n",
        "1050.00",
    ).get_json()["datos"]

    movimiento = extracto["movimientos"][0]
    vinculado = client.put(
        f"/api/movimientos/{movimiento['id']}/vincular",
        json={"asiento_id": asiento["id"]},
        headers=autorizacion(client),
    )
    assert vinculado.status_code == 200
    assert vinculado.get_json()["datos"]["estado"] == "conciliado"

    otro = extracto["movimientos"][1]
    descartado = client.put(
        f"/api/movimientos/{otro['id']}/descartar", headers=autorizacion(client)
    )
    assert descartado.get_json()["datos"]["estado"] == "descartado"


def test_no_se_vincula_un_asiento_de_otro_cliente(client, admin):
    cliente = _cliente(client)
    otro = _cliente(client, cuit="30712345671", razon_social="Otra SA")
    asiento_ajeno = _asiento_confirmado(client, otro["id"], "1000.00")
    extracto = _importar(
        client,
        cliente["id"],
        f"fecha;descripcion;importe\n{HOY};Transferencia;1000,00\n",
    ).get_json()["datos"]

    respuesta = client.put(
        f"/api/movimientos/{extracto['movimientos'][0]['id']}/vincular",
        json={"asiento_id": asiento_ajeno["id"]},
        headers=autorizacion(client),
    )

    assert respuesta.status_code == 422
    assert respuesta.get_json()["error"]["codigo"] == "asiento_invalido"


# --------------------------------------------------------------------------
# Slice 9: auditoría
# --------------------------------------------------------------------------
def test_auditoria_registra_cambios_y_es_solo_admin(client, admin):
    cliente = _cliente(client)
    _asiento_confirmado(client, cliente["id"])

    respuesta = client.get("/api/auditoria", headers=autorizacion(client))
    assert respuesta.status_code == 200
    entradas = respuesta.get_json()["datos"]
    assert any(e["entidad"] == "asiento" and e["accion"] == "confirmar" for e in entradas)
    assert entradas[0]["usuario"] == "Admin"

    from app.models.usuario import Rol
    from app.models.usuario import Usuario
    from app.utils.security import hashear_password

    db.session.add(
        Usuario(
            nombre="Contador Dos",
            email="contador2@test.com",
            password_hash=hashear_password("Secreta1234"),
            rol=Rol.CONTADOR.value,
            activo=True,
        )
    )
    db.session.commit()

    prohibido = client.get(
        "/api/auditoria", headers=autorizacion(client, "contador2@test.com")
    )
    assert prohibido.status_code == 403
