"""Tests del plan de cuentas."""

from app.extensions import db
from app.models.cuenta import Cuenta
from tests.helpers import autorizacion

CUIT = "20123456786"
TOTAL_PLAN_BASE = 27


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


def _cuenta(cliente_id, client, **extra):
    datos = {
        "codigo": "6",
        "nombre": "Cuenta de prueba",
        "tipo": "egreso",
        "imputable": True,
    }
    datos.update(extra)
    return client.post(
        f"/api/clientes/{cliente_id}/cuentas",
        json=datos,
        headers=autorizacion(client),
    )


def test_crear_cliente_precarga_el_plan_base(client, admin):
    cliente = _cliente(client)

    respuesta = client.get(
        f"/api/clientes/{cliente['id']}/cuentas", headers=autorizacion(client)
    )

    assert respuesta.status_code == 200
    cuentas = respuesta.get_json()["datos"]
    assert len(cuentas) == TOTAL_PLAN_BASE
    assert cuentas[0]["codigo"] == "1"
    assert {c["codigo"] for c in cuentas if c["imputable"]} >= {"1.1.01", "4.1.01"}


def test_crear_cuenta_y_codigo_duplicado(client, admin):
    cliente = _cliente(client)

    creada = _cuenta(cliente["id"], client)
    assert creada.status_code == 201
    assert creada.get_json()["datos"]["tipo_etiqueta"] == "Egreso"

    duplicada = _cuenta(cliente["id"], client)
    assert duplicada.status_code == 409
    assert duplicada.get_json()["error"]["codigo"] == "codigo_duplicado"


def test_padre_de_otro_cliente_es_rechazado(client, admin):
    cliente_a = _cliente(client)
    cliente_b = _cliente(client, cuit="30712345671", razon_social="Otra SA")

    cuenta_b = db.session.scalar(
        db.select(Cuenta).where(Cuenta.cliente_id == cliente_b["id"], Cuenta.codigo == "1")
    )

    respuesta = _cuenta(cliente_a["id"], client, padre_id=cuenta_b.id)

    assert respuesta.status_code == 422
    assert respuesta.get_json()["error"]["codigo"] == "padre_invalido"


def test_no_se_puede_generar_un_ciclo(client, admin):
    cliente = _cliente(client)

    padre = db.session.scalar(
        db.select(Cuenta).where(Cuenta.cliente_id == cliente["id"], Cuenta.codigo == "1.1")
    )
    hija = db.session.scalar(
        db.select(Cuenta).where(Cuenta.cliente_id == cliente["id"], Cuenta.codigo == "1.1.01")
    )

    # La cuenta 1.1 no puede pasar a depender de su hija 1.1.01.
    respuesta = client.put(
        f"/api/cuentas/{padre.id}",
        json={"padre_id": hija.id},
        headers=autorizacion(client),
    )

    assert respuesta.status_code == 422
    assert respuesta.get_json()["error"]["codigo"] == "ciclo_cuenta"


def test_no_se_elimina_una_cuenta_con_subcuentas(client, admin):
    cliente = _cliente(client)
    padre = db.session.scalar(
        db.select(Cuenta).where(Cuenta.cliente_id == cliente["id"], Cuenta.codigo == "1")
    )

    respuesta = client.delete(
        f"/api/cuentas/{padre.id}", headers=autorizacion(client)
    )

    assert respuesta.status_code == 409
    assert respuesta.get_json()["error"]["codigo"] == "cuenta_con_hijos"


def test_eliminar_hoja(client, admin):
    cliente = _cliente(client)
    creada = _cuenta(cliente["id"], client).get_json()["datos"]

    respuesta = client.delete(
        f"/api/cuentas/{creada['id']}", headers=autorizacion(client)
    )

    assert respuesta.status_code == 200
    assert db.session.get(Cuenta, creada["id"]) is None


def test_actualizar_nombre_e_imputable(client, admin):
    cliente = _cliente(client)
    cuenta = db.session.scalar(
        db.select(Cuenta).where(Cuenta.cliente_id == cliente["id"], Cuenta.codigo == "1.1.01")
    )

    respuesta = client.put(
        f"/api/cuentas/{cuenta.id}",
        json={"nombre": "Caja chica", "imputable": False},
        headers=autorizacion(client),
    )

    assert respuesta.status_code == 200
    assert respuesta.get_json()["datos"]["nombre"] == "Caja chica"
    assert respuesta.get_json()["datos"]["imputable"] is False


def test_contador_no_ve_el_plan_de_un_cliente_ajeno(client, admin, contador):
    cliente = _cliente(client)

    respuesta = client.get(
        f"/api/clientes/{cliente['id']}/cuentas",
        headers=autorizacion(client, "contador@test.com"),
    )

    assert respuesta.status_code == 404


def test_contador_ve_el_plan_de_su_cliente(client, admin, contador):
    cliente = _cliente(client, contador_id=contador.id)

    respuesta = client.get(
        f"/api/clientes/{cliente['id']}/cuentas",
        headers=autorizacion(client, "contador@test.com"),
    )

    assert respuesta.status_code == 200
    assert respuesta.get_json()["meta"]["total"] == TOTAL_PLAN_BASE
