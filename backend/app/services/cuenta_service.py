"""Plan de cuentas: reglas de negocio y plan base."""

from sqlalchemy import func, select

from app.extensions import db
from app.models.cliente import Cliente
from app.models.cuenta import Cuenta, TipoCuenta
from app.models.usuario import Usuario
from app.services.cliente_service import ClienteService
from app.utils.errors import ApiError

# Plan base que se precarga al crear un cliente.
# (codigo, nombre, tipo, padre, imputable)
PLAN_BASE: list[tuple[str, str, str, str | None, bool]] = [
    ("1", "Activo", "activo", None, False),
    ("1.1", "Caja y bancos", "activo", "1", False),
    ("1.1.01", "Caja", "activo", "1.1", True),
    ("1.1.02", "Banco", "activo", "1.1", True),
    ("1.2", "Créditos por ventas", "activo", "1", False),
    ("1.2.01", "Deudores por ventas", "activo", "1.2", True),
    ("1.3", "IVA", "activo", "1", False),
    ("1.3.01", "IVA crédito fiscal", "activo", "1.3", True),
    ("2", "Pasivo", "pasivo", None, False),
    ("2.1", "Deudas comerciales", "pasivo", "2", False),
    ("2.1.01", "Proveedores", "pasivo", "2.1", True),
    ("2.2", "IVA", "pasivo", "2", False),
    ("2.2.01", "IVA débito fiscal", "pasivo", "2.2", True),
    ("3", "Patrimonio neto", "patrimonio", None, False),
    ("3.1", "Capital", "patrimonio", "3", False),
    ("3.1.01", "Capital social", "patrimonio", "3.1", True),
    ("3.2", "Resultados", "patrimonio", "3", False),
    ("3.2.01", "Resultados del ejercicio", "patrimonio", "3.2", True),
    ("4", "Ingresos", "ingreso", None, False),
    ("4.1", "Ventas", "ingreso", "4", False),
    ("4.1.01", "Ventas", "ingreso", "4.1", True),
    ("5", "Egresos", "egreso", None, False),
    ("5.1", "Compras", "egreso", "5", False),
    ("5.1.01", "Compras", "egreso", "5.1", True),
    ("5.2", "Gastos", "egreso", "5", False),
    ("5.2.01", "Sueldos", "egreso", "5.2", True),
    ("5.2.02", "Gastos generales", "egreso", "5.2", True),
]


class CuentaService:
    @staticmethod
    def listar(cliente_id: int, actor: Usuario) -> list[Cuenta]:
        ClienteService.obtener(cliente_id, actor)

        return list(
            db.session.scalars(
                select(Cuenta)
                .where(Cuenta.cliente_id == cliente_id)
                .order_by(Cuenta.codigo)
            )
        )

    @staticmethod
    def obtener(cuenta_id: int, actor: Usuario) -> Cuenta:
        cuenta = db.session.get(Cuenta, cuenta_id)
        if cuenta is None:
            raise ApiError("La cuenta no existe.", codigo="no_encontrado", status=404)

        # Valida existencia y permisos sobre el cliente dueño del plan.
        ClienteService.obtener(cuenta.cliente_id, actor)
        return cuenta

    @staticmethod
    def crear(cliente_id: int, datos: dict, actor: Usuario) -> Cuenta:
        ClienteService.obtener(cliente_id, actor)

        codigo = datos["codigo"].strip()
        CuentaService._validar_codigo_unico(cliente_id, codigo)

        padre = CuentaService._resolver_padre(
            cliente_id, datos.get("padre_id"), cuenta_id=None
        )

        cuenta = Cuenta(
            cliente_id=cliente_id,
            codigo=codigo,
            nombre=datos["nombre"].strip(),
            tipo=datos["tipo"],
            padre_id=padre.id if padre else None,
            imputable=bool(datos.get("imputable", False)),
            activa=True,
        )
        db.session.add(cuenta)
        db.session.commit()
        return cuenta

    @staticmethod
    def actualizar(cuenta_id: int, datos: dict, actor: Usuario) -> Cuenta:
        cuenta = CuentaService.obtener(cuenta_id, actor)

        if "nombre" in datos:
            cuenta.nombre = datos["nombre"].strip()

        if "imputable" in datos:
            cuenta.imputable = bool(datos["imputable"])

        if "activa" in datos:
            cuenta.activa = bool(datos["activa"])

        if "padre_id" in datos:
            padre = CuentaService._resolver_padre(
                cuenta.cliente_id, datos["padre_id"], cuenta_id=cuenta.id
            )
            cuenta.padre_id = padre.id if padre else None

        db.session.commit()
        return cuenta

    @staticmethod
    def eliminar(cuenta_id: int, actor: Usuario) -> None:
        cuenta = CuentaService.obtener(cuenta_id, actor)

        hijos = db.session.scalar(
            select(func.count())
            .select_from(Cuenta)
            .where(Cuenta.padre_id == cuenta.id)
        )
        if hijos:
            raise ApiError(
                "La cuenta tiene subcuentas: no se puede eliminar.",
                codigo="cuenta_con_hijos",
                status=409,
            )

        from app.models.asiento import RenglonAsiento

        movimientos = db.session.scalar(
            select(func.count())
            .select_from(RenglonAsiento)
            .where(RenglonAsiento.cuenta_id == cuenta.id)
        )
        if movimientos:
            raise ApiError(
                "La cuenta tiene movimientos: no se puede eliminar.",
                codigo="cuenta_con_movimientos",
                status=409,
                detalles={"movimientos": movimientos},
            )

        db.session.delete(cuenta)
        db.session.commit()

    @staticmethod
    def crear_plan_base(cliente_id: int) -> int:
        """Precarga el plan si el cliente no tiene cuentas. Devuelve cuántas creó."""
        existentes = db.session.scalar(
            select(func.count()).select_from(Cuenta).where(Cuenta.cliente_id == cliente_id)
        )
        if existentes:
            return 0

        por_codigo: dict[str, Cuenta] = {}

        for codigo, nombre, tipo, padre_codigo, imputable in PLAN_BASE:
            padre = por_codigo.get(padre_codigo) if padre_codigo else None
            cuenta = Cuenta(
                cliente_id=cliente_id,
                codigo=codigo,
                nombre=nombre,
                tipo=tipo,
                padre_id=padre.id if padre else None,
                imputable=imputable,
                activa=True,
            )
            db.session.add(cuenta)
            db.session.flush()
            por_codigo[codigo] = cuenta

        return len(por_codigo)

    # ------------------------------------------------------------------ utils
    @staticmethod
    def _validar_codigo_unico(cliente_id: int, codigo: str, excluir_id: int | None = None) -> None:
        consulta = select(Cuenta).where(
            Cuenta.cliente_id == cliente_id, Cuenta.codigo == codigo
        )
        existente = db.session.scalar(consulta)

        if existente is not None and existente.id != excluir_id:
            raise ApiError(
                "Ya existe una cuenta con ese código en el cliente.",
                codigo="codigo_duplicado",
                status=409,
                detalles={"codigo": ["Código ya usado en este plan."]},
            )

    @staticmethod
    def _resolver_padre(
        cliente_id: int, padre_id: int | None, *, cuenta_id: int | None
    ) -> Cuenta | None:
        if padre_id is None:
            return None

        padre = db.session.get(Cuenta, padre_id)
        if padre is None or padre.cliente_id != cliente_id:
            raise ApiError(
                "La cuenta padre no pertenece a este cliente.",
                codigo="padre_invalido",
                status=422,
                detalles={"padre_id": ["Elegí una cuenta del mismo plan."]},
            )

        if cuenta_id is not None:
            # Recorremos hacia arriba: el padre no puede ser la cuenta ni un
            # descendiente (evita ciclos).
            actual: Cuenta | None = padre
            while actual is not None:
                if actual.id == cuenta_id:
                    raise ApiError(
                        "Una cuenta no puede depender de sí misma ni de una subcuenta.",
                        codigo="ciclo_cuenta",
                        status=422,
                        detalles={"padre_id": ["Ese padre genera un ciclo."]},
                    )
                actual = actual.padre

        return padre
