"""Reglas de negocio de clientes.

Los datos no se actualizan in-place: cada cambio inserta una versión nueva.
La lectura siempre toma la última versión de cada cliente.

Cada cliente tiene un usuario ``cliente`` vinculado, creado automáticamente
con una clave temporal. La clave se muestra una sola vez al administrador o
al contador responsable y el cliente debe cambiarla al ingresar.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select

from app.extensions import db
from app.models.cliente import Cliente, ClienteVersion, CondicionIva
from app.models.usuario import Rol, Usuario
from app.services.auditoria_service import AuditoriaService
from app.utils.cuit import cuit_valido, normalizar_cuit
from app.utils.errors import ApiError
from app.utils.security import generar_password_temporal, hashear_password

CAMPOS_VERSION = (
    "razon_social",
    "condicion_iva",
    "email",
    "telefono",
    "direccion",
    "contador_id",
)

PASSWORD_TEMPORAL_HORAS = 72


@dataclass
class ClienteActual:
    """Cliente con los datos de su versión vigente (lo que ven las pantallas)."""

    id: int
    cuit: str
    activo: bool
    razon_social: str
    condicion_iva: str
    condicion_iva_etiqueta: str
    email: str | None
    telefono: str | None
    direccion: str | None
    contador_id: int | None
    contador_nombre: str | None
    contador_email: str | None
    usuario_id: int | None
    usuario_nombre: str | None
    usuario_email: str | None
    usuario_activo: bool | None
    version_id: int
    actualizado_en: datetime
    actualizado_por: str | None
    acceso_temporal: str | None = None


def _consulta_actual():
    ultima = (
        select(
            ClienteVersion.cliente_id,
            func.max(ClienteVersion.id).label("version_id"),
        )
        .group_by(ClienteVersion.cliente_id)
        .subquery()
    )

    return (
        select(Cliente, ClienteVersion)
        .join(ClienteVersion, ClienteVersion.cliente_id == Cliente.id)
        .join(ultima, ultima.c.version_id == ClienteVersion.id)
    )


def _normalizar_email(email: str | None) -> str:
    return (email or "").strip().lower()


def _expiracion_temporal() -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=PASSWORD_TEMPORAL_HORAS)


def _actual(cliente: Cliente, version: ClienteVersion) -> ClienteActual:
    usuario = cliente.usuario
    return ClienteActual(
        id=cliente.id,
        cuit=cliente.cuit,
        activo=cliente.activo,
        razon_social=version.razon_social,
        condicion_iva=version.condicion_iva,
        condicion_iva_etiqueta=CondicionIva(version.condicion_iva).etiqueta,
        email=version.email,
        telefono=version.telefono,
        direccion=version.direccion,
        contador_id=version.contador_id,
        contador_nombre=version.contador.nombre if version.contador else None,
        contador_email=version.contador.email if version.contador else None,
        usuario_id=cliente.usuario_id,
        usuario_nombre=usuario.nombre if usuario else None,
        usuario_email=usuario.email if usuario else None,
        usuario_activo=usuario.activo if usuario else None,
        version_id=version.id,
        actualizado_en=version.creado_en,
        actualizado_por=version.creado_por.nombre if version.creado_por else None,
        acceso_temporal=None,
    )


class ClienteService:
    @staticmethod
    def listar(
        usuario: Usuario,
        *,
        q: str | None = None,
        activo: bool | None = None,
        contador_id: int | None = None,
    ) -> list[ClienteActual]:
        consulta = _consulta_actual()

        if usuario.rol == Rol.CONTADOR.value:
            consulta = consulta.where(ClienteVersion.contador_id == usuario.id)
        elif usuario.rol == Rol.CLIENTE.value:
            consulta = consulta.where(Cliente.usuario_id == usuario.id)

        if q:
            patron = f"%{q.strip()}%"
            consulta = consulta.where(
                or_(
                    ClienteVersion.razon_social.ilike(patron),
                    Cliente.cuit.like(f"%{normalizar_cuit(q)}%"),
                )
            )

        if activo is not None:
            consulta = consulta.where(Cliente.activo.is_(activo))

        if contador_id is not None:
            consulta = consulta.where(ClienteVersion.contador_id == contador_id)

        consulta = consulta.order_by(Cliente.activo.desc(), ClienteVersion.razon_social)

        filas = db.session.execute(consulta).all()
        return [_actual(cliente, version) for cliente, version in filas]

    @staticmethod
    def obtener(cliente_id: int, usuario: Usuario) -> tuple[Cliente, ClienteVersion]:
        fila = db.session.execute(
            _consulta_actual().where(Cliente.id == cliente_id)
        ).first()

        if fila is None:
            raise ApiError("El cliente no existe.", codigo="no_encontrado", status=404)

        cliente, version = fila

        if not ClienteService.puede_ver(usuario, cliente, version):
            # 404 a propósito: no revelamos que existe un cliente ajeno.
            raise ApiError("El cliente no existe.", codigo="no_encontrado", status=404)

        return cliente, version

    @staticmethod
    def puede_ver(usuario: Usuario, cliente: Cliente, version: ClienteVersion) -> bool:
        if usuario.rol == Rol.ADMIN.value:
            return True
        if usuario.rol == Rol.CONTADOR.value:
            return version.contador_id == usuario.id
        if usuario.rol == Rol.CLIENTE.value:
            return cliente.usuario_id == usuario.id
        return False

    @staticmethod
    def _puede_gestionar(usuario: Usuario, actual: ClienteActual) -> bool:
        if usuario.rol == Rol.ADMIN.value:
            return True
        if usuario.rol == Rol.CONTADOR.value:
            return actual.contador_id == usuario.id
        return False

    @staticmethod
    def actual_de(usuario: Usuario, cliente_id: int) -> ClienteActual:
        cliente, version = ClienteService.obtener(cliente_id, usuario)
        return _actual(cliente, version)

    @staticmethod
    def crear(datos: dict, actor: Usuario) -> ClienteActual:
        cuit = normalizar_cuit(datos["cuit"])

        if not cuit_valido(cuit):
            raise ApiError(
                "El CUIT no es válido (revisá los 11 dígitos y el verificador).",
                codigo="cuit_invalido",
                status=422,
                detalles={"cuit": ["CUIT inválido."]},
            )

        existente = db.session.scalar(select(Cliente).where(Cliente.cuit == cuit))
        if existente is not None:
            raise ApiError(
                "Ya existe un cliente con ese CUIT.",
                codigo="cuit_duplicado",
                status=409,
                detalles={"cuit": ["CUIT ya registrado."]},
            )

        email = _normalizar_email(datos.get("email"))
        if not email:
            raise ApiError(
                "El email del cliente es obligatorio: es su usuario de acceso.",
                codigo="email_requerido",
                status=422,
                detalles={"email": ["Ingresá un email para crear el acceso."]},
            )

        if db.session.scalar(select(Usuario).where(Usuario.email == email)) is not None:
            raise ApiError(
                "Ya existe un usuario con ese email.",
                codigo="email_duplicado",
                status=409,
                detalles={"email": ["Ese email ya está en uso."]},
            )

        contador_id = ClienteService._resolver_contador(datos.get("contador_id"), actor)

        cliente = Cliente(cuit=cuit, activo=True)
        db.session.add(cliente)
        db.session.flush()

        version = ClienteVersion(
            cliente_id=cliente.id,
            razon_social=datos["razon_social"].strip(),
            condicion_iva=datos["condicion_iva"],
            email=email,
            telefono=(datos.get("telefono") or None),
            direccion=(datos.get("direccion") or None),
            contador_id=contador_id,
            creado_por_id=actor.id,
        )
        db.session.add(version)

        _, password_temporal = ClienteService._crear_usuario_cliente(
            cliente,
            nombre=version.razon_social,
            email=email,
        )

        # Plan de cuentas base del cliente (import local para evitar el ciclo:
        # CuentaService usa ClienteService para validar permisos).
        from app.services.cuenta_service import CuentaService

        CuentaService.crear_plan_base(cliente.id)

        AuditoriaService.registrar(
            actor,
            "crear",
            "cliente",
            cliente.id,
            despues={
                "cuit": cuit,
                "razon_social": version.razon_social,
                "responsable_id": contador_id,
                "usuario_id": cliente.usuario_id,
            },
        )

        db.session.commit()

        actual = _actual(cliente, version)
        actual.acceso_temporal = password_temporal
        return actual

    @staticmethod
    def actualizar(cliente_id: int, datos: dict, actor: Usuario) -> ClienteActual:
        cliente, version_actual = ClienteService.obtener(cliente_id, actor)
        actual = _actual(cliente, version_actual)

        if not ClienteService._puede_gestionar(actor, actual):
            raise ApiError(
                "No podés editar un cliente que no tenés asignado.",
                codigo="sin_permiso",
                status=403,
            )

        if "contador_id" in datos and actor.rol != Rol.ADMIN.value:
            if datos["contador_id"] != actual.contador_id:
                raise ApiError(
                    "Solo un administrador puede reasignar el responsable.",
                    codigo="sin_permiso",
                    status=403,
                )

        valores = {campo: getattr(actual, campo) for campo in CAMPOS_VERSION}

        if "razon_social" in datos:
            valores["razon_social"] = datos["razon_social"].strip()
        for campo in ("condicion_iva", "telefono", "direccion"):
            if campo in datos:
                valores[campo] = datos[campo] or None

        acceso_temporal: str | None = None

        if "email" in datos:
            email = _normalizar_email(datos["email"])
            if cliente.usuario_id is not None and not email:
                raise ApiError(
                    "El email no puede quedar vacío mientras el cliente tenga acceso.",
                    codigo="email_requerido",
                    status=422,
                    detalles={"email": ["Ingresá un email para el acceso."]},
                )
            if email:
                existente = db.session.scalar(
                    select(Usuario).where(Usuario.email == email)
                )
                if existente is not None and existente.id != cliente.usuario_id:
                    raise ApiError(
                        "Ya existe un usuario con ese email.",
                        codigo="email_duplicado",
                        status=409,
                        detalles={"email": ["Ese email ya está en uso."]},
                    )
            valores["email"] = email or None

        if "contador_id" in datos:
            valores["contador_id"] = ClienteService._resolver_contador(
                datos["contador_id"], actor
            )

        if all(valores[campo] == getattr(actual, campo) for campo in CAMPOS_VERSION):
            # Nada cambió: no ensuciamos el historial con versiones vacías.
            return actual

        antes = {campo: getattr(actual, campo) for campo in CAMPOS_VERSION}

        version = ClienteVersion(
            cliente_id=cliente.id,
            creado_por_id=actor.id,
            **valores,
        )
        db.session.add(version)

        usuario = cliente.usuario
        if usuario is not None:
            # El email y el nombre del usuario cliente acompañan a la ficha.
            usuario.nombre = valores["razon_social"]
            if "email" in datos and valores["email"]:
                usuario.email = valores["email"]
        elif cliente.activo and valores["email"]:
            # Cliente viejo sin acceso: al cargarle el email se crea el usuario
            # y se devuelve la clave temporal una sola vez.
            _, acceso_temporal = ClienteService._crear_usuario_cliente(
                cliente,
                nombre=valores["razon_social"],
                email=valores["email"],
            )

        AuditoriaService.registrar(
            actor,
            "actualizar",
            "cliente",
            cliente.id,
            antes=antes,
            despues=valores,
        )

        db.session.commit()

        actualizada = _actual(cliente, version)
        actualizada.acceso_temporal = acceso_temporal
        return actualizada

    @staticmethod
    def desactivar(cliente_id: int, actor: Usuario) -> ClienteActual:
        cliente, version = ClienteService.obtener(cliente_id, actor)
        actual = _actual(cliente, version)

        if not ClienteService._puede_gestionar(actor, actual):
            raise ApiError(
                "No podés dar de baja un cliente que no tenés asignado.",
                codigo="sin_permiso",
                status=403,
            )

        # Un cliente con movimientos contables no se puede dar de baja.
        from app.models.asiento import Asiento
        from app.models.comprobante import Comprobante

        tiene_asientos = db.session.scalar(
            select(func.count()).select_from(Asiento).where(Asiento.cliente_id == cliente.id)
        )
        tiene_comprobantes = db.session.scalar(
            select(func.count())
            .select_from(Comprobante)
            .where(Comprobante.cliente_id == cliente.id)
        )

        if tiene_asientos or tiene_comprobantes:
            raise ApiError(
                "El cliente tiene asientos o comprobantes: no se puede dar de baja.",
                codigo="cliente_con_movimientos",
                status=409,
                detalles={
                    "asientos": tiene_asientos or 0,
                    "comprobantes": tiene_comprobantes or 0,
                },
            )

        cliente.activo = False
        usuario = cliente.usuario
        if usuario is not None and usuario.activo:
            usuario.activo = False
            usuario.token_version = (usuario.token_version or 0) + 1

        AuditoriaService.registrar(
            actor,
            "desactivar",
            "cliente",
            cliente.id,
            antes={"activo": True, "usuario_activo": actual.usuario_activo},
            despues={"activo": False, "usuario_activo": False},
        )
        db.session.commit()

        return _actual(cliente, version)

    @staticmethod
    def activar(cliente_id: int, actor: Usuario) -> ClienteActual:
        cliente, version = ClienteService.obtener(cliente_id, actor)
        actual = _actual(cliente, version)

        if not ClienteService._puede_gestionar(actor, actual):
            raise ApiError(
                "No podés reactivar un cliente que no tenés asignado.",
                codigo="sin_permiso",
                status=403,
            )

        if cliente.activo:
            return actual

        cliente.activo = True
        usuario = cliente.usuario
        if usuario is not None and not usuario.activo:
            # Al reactivar el cliente se restaura el acceso vinculado.
            usuario.activo = True
            usuario.token_version = (usuario.token_version or 0) + 1

        AuditoriaService.registrar(
            actor,
            "activar",
            "cliente",
            cliente.id,
            antes={"activo": False, "usuario_activo": actual.usuario_activo},
            despues={"activo": True, "usuario_activo": True},
        )
        db.session.commit()

        return _actual(cliente, version)

    @staticmethod
    def historial(cliente_id: int, actor: Usuario) -> list[ClienteVersion]:
        ClienteService.obtener(cliente_id, actor)

        return list(
            db.session.scalars(
                select(ClienteVersion)
                .where(ClienteVersion.cliente_id == cliente_id)
                .order_by(ClienteVersion.id.desc())
            )
        )

    @staticmethod
    def crear_acceso(cliente_id: int, actor: Usuario) -> tuple[Usuario, str]:
        """Crea o reactiva el usuario cliente y devuelve la clave temporal."""
        cliente, version = ClienteService.obtener(cliente_id, actor)
        actual = _actual(cliente, version)

        if not ClienteService._puede_gestionar(actor, actual):
            raise ApiError(
                "No podés gestionar el acceso de un cliente que no tenés asignado.",
                codigo="sin_permiso",
                status=403,
            )
        if not cliente.activo:
            raise ApiError(
                "El cliente está inactivo. Reactivalo antes de habilitar el acceso.",
                codigo="cliente_inactivo",
                status=409,
            )

        email = _normalizar_email(actual.email)
        if not email:
            raise ApiError(
                "Cargá un email en la ficha antes de crear el acceso.",
                codigo="email_requerido",
                status=422,
                detalles={"email": ["El cliente no tiene email."]},
            )

        usuario = ClienteService._usuario_vinculado(cliente)
        if usuario is not None:
            if usuario.rol != Rol.CLIENTE.value:
                raise ApiError(
                    "El usuario vinculado no tiene rol cliente.",
                    codigo="acceso_invalido",
                    status=409,
                )
            if usuario.activo:
                raise ApiError(
                    "El cliente ya tiene un acceso activo.",
                    codigo="acceso_existente",
                    status=409,
                )
            password = ClienteService._resetear_usuario(usuario, actual, email)
            AuditoriaService.registrar(
                actor,
                "reactivar_acceso",
                "cliente",
                cliente.id,
                despues={"usuario_id": usuario.id, "email": usuario.email},
            )
            db.session.commit()
            return usuario, password

        if db.session.scalar(select(Usuario).where(Usuario.email == email)) is not None:
            raise ApiError(
                "Ya existe un usuario con ese email.",
                codigo="email_duplicado",
                status=409,
                detalles={"email": ["Ese email ya está en uso."]},
            )

        usuario, password = ClienteService._crear_usuario_cliente(
            cliente,
            nombre=actual.razon_social,
            email=email,
        )
        AuditoriaService.registrar(
            actor,
            "crear_acceso",
            "cliente",
            cliente.id,
            despues={"usuario_id": usuario.id, "email": usuario.email},
        )
        db.session.commit()
        return usuario, password

    @staticmethod
    def restablecer_acceso(cliente_id: int, actor: Usuario) -> tuple[Usuario, str]:
        """Genera una clave temporal nueva y reactiva el acceso si estaba revocado."""
        cliente, version = ClienteService.obtener(cliente_id, actor)
        actual = _actual(cliente, version)

        if not ClienteService._puede_gestionar(actor, actual):
            raise ApiError(
                "No podés gestionar el acceso de un cliente que no tenés asignado.",
                codigo="sin_permiso",
                status=403,
            )
        if not cliente.activo:
            raise ApiError(
                "El cliente está inactivo. Reactivalo antes de restablecer el acceso.",
                codigo="cliente_inactivo",
                status=409,
            )

        usuario = ClienteService._usuario_vinculado(cliente)
        if usuario is None:
            raise ApiError(
                "El cliente todavía no tiene acceso. Creálo primero.",
                codigo="sin_acceso",
                status=404,
            )
        if usuario.rol != Rol.CLIENTE.value:
            raise ApiError(
                "El usuario vinculado no tiene rol cliente.",
                codigo="acceso_invalido",
                status=409,
            )

        email = _normalizar_email(actual.email)
        if not email:
            raise ApiError(
                "Cargá un email en la ficha antes de restablecer el acceso.",
                codigo="email_requerido",
                status=422,
                detalles={"email": ["El cliente no tiene email."]},
            )

        password = ClienteService._resetear_usuario(usuario, actual, email)
        AuditoriaService.registrar(
            actor,
            "reset_acceso",
            "cliente",
            cliente.id,
            despues={"usuario_id": usuario.id, "email": usuario.email},
        )
        db.session.commit()
        return usuario, password

    @staticmethod
    def revocar_acceso(cliente_id: int, actor: Usuario) -> None:
        cliente, version = ClienteService.obtener(cliente_id, actor)
        actual = _actual(cliente, version)

        if not ClienteService._puede_gestionar(actor, actual):
            raise ApiError(
                "No podés gestionar el acceso de un cliente que no tenés asignado.",
                codigo="sin_permiso",
                status=403,
            )

        usuario = ClienteService._usuario_vinculado(cliente)
        if usuario is None:
            raise ApiError(
                "El cliente no tiene un usuario vinculado.",
                codigo="sin_acceso",
                status=404,
            )
        if not usuario.activo:
            raise ApiError(
                "El acceso ya está revocado.",
                codigo="sin_acceso",
                status=409,
            )

        usuario.activo = False
        usuario.token_version = (usuario.token_version or 0) + 1
        AuditoriaService.registrar(
            actor,
            "revocar_acceso",
            "cliente",
            cliente.id,
            antes={"usuario_activo": True},
            despues={"usuario_activo": False},
        )
        db.session.commit()

    @staticmethod
    def _usuario_vinculado(cliente: Cliente) -> Usuario | None:
        if cliente.usuario is not None:
            return cliente.usuario
        if cliente.usuario_id is not None:
            return db.session.get(Usuario, cliente.usuario_id)
        return None

    @staticmethod
    def _crear_usuario_cliente(
        cliente: Cliente, *, nombre: str, email: str
    ) -> tuple[Usuario, str]:
        password = generar_password_temporal()
        usuario = Usuario(
            nombre=nombre.strip(),
            email=_normalizar_email(email),
            password_hash=hashear_password(password),
            rol=Rol.CLIENTE.value,
            activo=True,
            es_propietario=False,
            debe_cambiar_password=True,
            password_temporal_expira_en=_expiracion_temporal(),
            token_version=0,
        )
        db.session.add(usuario)
        db.session.flush()

        cliente.usuario_id = usuario.id
        cliente.usuario = usuario
        return usuario, password

    @staticmethod
    def _resetear_usuario(
        usuario: Usuario, actual: ClienteActual, email: str
    ) -> str:
        password = generar_password_temporal()
        usuario.nombre = actual.razon_social
        usuario.email = email
        usuario.password_hash = hashear_password(password)
        usuario.activo = True
        usuario.debe_cambiar_password = True
        usuario.password_temporal_expira_en = _expiracion_temporal()
        usuario.token_version = (usuario.token_version or 0) + 1
        return password

    @staticmethod
    def _resolver_contador(contador_id: int | None, actor: Usuario) -> int:
        # Un contador siempre se autoasigna; el admin/propietario elige o se
        # asigna a sí mismo por defecto.
        if actor.rol == Rol.CONTADOR.value:
            return actor.id
        if actor.rol != Rol.ADMIN.value:
            raise ApiError(
                "No podés asignar un responsable.",
                codigo="sin_permiso",
                status=403,
            )

        if contador_id is None:
            return actor.id

        responsable = db.session.get(Usuario, contador_id)
        if (
            responsable is None
            or responsable.rol not in {Rol.ADMIN.value, Rol.CONTADOR.value}
            or not responsable.activo
        ):
            raise ApiError(
                "El responsable asignado no es válido.",
                codigo="responsable_invalido",
                status=422,
                detalles={
                    "contador_id": ["Elegí un administrador o contador activo."]
                },
            )

        return responsable.id
