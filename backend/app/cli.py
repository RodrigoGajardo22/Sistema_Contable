"""Comandos de línea de comandos de Flask."""

import os
from datetime import date, timedelta
from decimal import Decimal

import click
from flask import Flask
from flask.cli import with_appcontext
from sqlalchemy import select

from app.extensions import db
from app.models.cliente import Cliente
from app.models.cuenta import Cuenta
from app.models.usuario import Rol, Usuario
from app.services.asiento_service import AsientoService
from app.services.cliente_service import ClienteService
from app.services.comprobante_service import ComprobanteService
from app.services.conciliacion_service import ConciliacionService
from app.services.vencimiento_service import VencimientoService
from app.utils.security import hashear_password


def _crear_si_no_existe(
    *,
    nombre: str,
    email: str,
    password: str,
    rol: Rol,
    etiqueta: str,
    es_propietario: bool = False,
) -> Usuario | None:
    email = email.strip().lower()

    existente = db.session.scalar(select(Usuario).where(Usuario.email == email))
    if existente is not None:
        click.echo(f"· {etiqueta}: {email} ya existe; no se modifica.")
        return None

    usuario = Usuario(
        nombre=nombre.strip(),
        email=email,
        password_hash=hashear_password(password),
        rol=rol.value,
        activo=True,
        es_propietario=es_propietario,
        debe_cambiar_password=False,
    )
    db.session.add(usuario)
    db.session.commit()
    click.echo(f"✔ {etiqueta} creado: {email}")
    return usuario


@click.command("seed")
@with_appcontext
def seed() -> None:
    """Crea el administrador inicial y garantiza que haya un propietario."""
    tiene_propietario = db.session.scalar(
        select(Usuario).where(Usuario.es_propietario.is_(True))
    )
    admin = _crear_si_no_existe(
        nombre=os.getenv("ADMIN_NOMBRE") or "Administrador",
        email=os.getenv("ADMIN_EMAIL") or "admin@estudio.com",
        password=os.getenv("ADMIN_PASSWORD") or "Admin1234",
        rol=Rol.ADMIN,
        etiqueta="Administrador",
        es_propietario=tiene_propietario is None,
    )

    if admin is None:
        email = (os.getenv("ADMIN_EMAIL") or "admin@estudio.com").strip().lower()
        admin = db.session.scalar(select(Usuario).where(Usuario.email == email))

    tiene_propietario = db.session.scalar(
        select(Usuario).where(Usuario.es_propietario.is_(True))
    )
    if admin is not None and tiene_propietario is None:
        admin.es_propietario = True
        db.session.commit()
        click.echo("✔ Administrador marcado como propietario.")


def _admin() -> Usuario:
    email = (os.getenv("ADMIN_EMAIL") or "admin@estudio.com").strip().lower()
    usuario = db.session.scalar(select(Usuario).where(Usuario.email == email))
    if usuario is None:
        raise click.ClickException(
            "No existe el administrador. Ejecutá primero `flask seed`."
        )
    return usuario


def _fijar_password_demo(cliente: Cliente, password: str = "Cliente1234") -> None:
    """Deja una clave conocida para que la demo sea reproducible."""
    if cliente.usuario_id is None:
        return
    usuario = db.session.get(Usuario, cliente.usuario_id)
    if usuario is None:
        return
    usuario.password_hash = hashear_password(password)
    usuario.debe_cambiar_password = False
    usuario.password_temporal_expira_en = None
    usuario.activo = True
    db.session.commit()


def _cliente_demo(
    cuit: str,
    razon: str,
    condicion: str,
    email: str,
    actor: Usuario,
    contador_id=None,
):
    existente = db.session.scalar(select(Cliente).where(Cliente.cuit == cuit))
    if existente is not None:
        actual = ClienteService.actual_de(actor, existente.id)
        if not actual.email:
            ClienteService.actualizar(existente.id, {"email": email}, actor)
        if existente.usuario_id is None:
            ClienteService.crear_acceso(existente.id, actor)
        _fijar_password_demo(existente)
        return existente, False

    creado = ClienteService.crear(
        {
            "razon_social": razon,
            "cuit": cuit,
            "condicion_iva": condicion,
            "email": email,
            "telefono": None,
            "direccion": None,
            "contador_id": contador_id,
        },
        actor,
    )
    cliente = db.session.get(Cliente, creado.id)
    _fijar_password_demo(cliente)
    return cliente, True


def _cuentas(cliente_id: int) -> dict[str, Cuenta]:
    return {
        cuenta.codigo: cuenta
        for cuenta in db.session.scalars(
            select(Cuenta).where(Cuenta.cliente_id == cliente_id)
        )
    }


def _asiento_confirmado(actor, cliente_id, concepto, importe, cuentas):
    asiento = AsientoService.crear(
        cliente_id,
        {
            "fecha": date.today(),
            "concepto": concepto,
            "renglones": [
                {"cuenta_id": cuentas["1.1.01"].id, "debe": importe, "haber": "0.00"},
                {"cuenta_id": cuentas["4.1.01"].id, "debe": "0.00", "haber": importe},
            ],
        },
        actor,
    )
    AsientoService.confirmar(asiento.id, actor)
    return asiento


@click.command("seed-demo")
@with_appcontext
def seed_demo() -> None:
    """Datos de demostración: clientes, asientos, comprobantes, vencimientos y extracto."""
    actor = _admin()
    contador = _crear_si_no_existe(
        nombre=os.getenv("DEMO_CONTADOR_NOMBRE") or "Contador Demo",
        email=os.getenv("DEMO_CONTADOR_EMAIL") or "contador.demo@estudio.com",
        password=os.getenv("DEMO_CONTADOR_PASSWORD") or "ClaveSegura123",
        rol=Rol.CONTADOR,
        etiqueta="Contador de demo",
    )
    contador = contador or db.session.scalar(
        select(Usuario).where(Usuario.email == "contador.demo@estudio.com")
    )

    # ---------------------------------------------------------------- clientes
    espiga, nueva_espiga = _cliente_demo(
        "20123456786",
        "Panadería La Espiga SRL",
        "responsable_inscripto",
        "cliente.espiga@estudio.com",
        actor,
        contador.id if contador else None,
    )
    norte, nueva_norte = _cliente_demo(
        "30712345671",
        "Estudio Jurídico Norte",
        "monotributo",
        "cliente@estudio.com",
        actor,
        contador.id if contador else None,
    )
    click.echo(f"· Clientes demo: Espiga={'nuevo' if nueva_espiga else 'existente'}, Norte={'nuevo' if nueva_norte else 'existente'}.")

    cuentas_espiga = _cuentas(espiga.id)

    if nueva_espiga and cuentas_espiga:
        # Asiento manual confirmado.
        _asiento_confirmado(actor, espiga.id, "Venta de mercadería", "1500.50", cuentas_espiga)

        # Comprobante contabilizado (genera su asiento).
        comprobante = ComprobanteService.crear(
            espiga.id,
            {
                "tipo": "venta",
                "numero": "A-0001-00000001",
                "fecha": date.today(),
                "tercero": "Cliente Final SA",
                "neto": Decimal("100000.00"),
                "alicuota_iva": Decimal("21.00"),
            },
            actor,
        )
        ComprobanteService.contabilizar(comprobante.id, actor)

        # Vencimientos: uno vencido, uno próximo y uno pagado.
        vencido = VencimientoService.crear(
            espiga.id,
            {
                "obligacion": "iva",
                "periodo": "2026-10",
                "fecha_vencimiento": date.today() - timedelta(days=10),
                "observaciones": "Presentación vencida",
            },
            actor,
        )
        VencimientoService.cambiar_estado(vencido.id, "presentado", actor)
        VencimientoService.crear(
            espiga.id,
            {
                "obligacion": "ingresos_brutos",
                "periodo": "2026-11",
                "fecha_vencimiento": date.today() + timedelta(days=8),
            },
            actor,
        )
        pagado = VencimientoService.crear(
            espiga.id,
            {
                "obligacion": "ganancias",
                "periodo": "2026",
                "fecha_vencimiento": date.today() - timedelta(days=25),
            },
            actor,
        )
        VencimientoService.cambiar_estado(pagado.id, "presentado", actor)
        VencimientoService.cambiar_estado(pagado.id, "pagado", actor)

        # Extracto con dos movimientos: uno conciliado y uno pendiente.
        extracto = ConciliacionService.importar(
            espiga.id,
            {
                "banco": "Galicia",
                "periodo": "2026-11",
                "saldo_inicial": "0.00",
                "saldo_final": "96000.00",
                "csv": (
                    "fecha;descripcion;importe\n"
                    f"{date.today().isoformat()};Transferencia cliente;121000,00\n"
                    f"{date.today().isoformat()};Pago de servicios;-25000,00\n"
                ),
            },
            actor,
        )
        movimiento = next(m for m in extracto.movimientos if Decimal(str(m.importe)) > 0)
        asiento_comprobante = comprobante.asiento_id
        if asiento_comprobante:
            ConciliacionService.vincular(movimiento.id, actor, asiento_id=asiento_comprobante)

    if nueva_norte:
        VencimientoService.crear(
            norte.id,
            {
                "obligacion": "ingresos_brutos",
                "periodo": "2026-11",
                "fecha_vencimiento": date.today() + timedelta(days=20),
            },
            actor,
        )

    # Clientes viejos sin plan: completarlo (idempotente).
    completados = 0
    from app.services.cuenta_service import CuentaService

    for cliente in db.session.scalars(select(Cliente)):
        if CuentaService.crear_plan_base(cliente.id):
            completados += 1
    if completados:
        db.session.commit()
        click.echo(f"✔ Plan de cuentas base creado para {completados} cliente(s).")


def register_cli(app: Flask) -> None:
    app.cli.add_command(seed)
    app.cli.add_command(seed_demo)
