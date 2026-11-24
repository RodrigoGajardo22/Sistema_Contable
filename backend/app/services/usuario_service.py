"""Reglas de negocio de usuarios.

Nada acá conoce el objeto ``request``: los controladores traducen HTTP y estos
servicios aplican las reglas del dominio.

Modelo de roles:
- ``propietario``: admin con ``es_propietario=True``. Es el único que crea,
  edita o desactiva administradores y el único que puede transferir la
  propiedad.
- ``admin``: administra contadores y clientes, pero no toca otros admins ni
  al propietario.
- ``contador``: gestiona sus clientes asignados.
- ``cliente``: se crea automáticamente desde la ficha del cliente; no se
  administra desde ``/usuarios``.
"""

from sqlalchemy import func, or_, select

from app.extensions import db
from app.models.cliente import ClienteVersion
from app.models.usuario import Rol, Usuario
from app.services.auditoria_service import AuditoriaService
from app.utils.errors import ApiError
from app.utils.security import hashear_password, verificar_password


def normalizar_email(email: str | None) -> str:
    return (email or "").strip().lower()


class UsuarioService:
    @staticmethod
    def por_email(email: str | None) -> Usuario | None:
        return db.session.scalar(
            select(Usuario).where(Usuario.email == normalizar_email(email))
        )

    @staticmethod
    def listar(
        *,
        q: str | None = None,
        rol: str | None = None,
        activo: bool | None = None,
    ) -> list[Usuario]:
        consulta = select(Usuario).order_by(Usuario.activo.desc(), Usuario.nombre)

        # Los accesos de clientes se gestionan desde la ficha del cliente.
        if rol:
            consulta = consulta.where(Usuario.rol == rol)
        else:
            consulta = consulta.where(Usuario.rol != Rol.CLIENTE.value)

        if q:
            patron = f"%{q.strip()}%"
            consulta = consulta.where(
                or_(Usuario.nombre.ilike(patron), Usuario.email.ilike(patron))
            )
        if activo is not None:
            consulta = consulta.where(Usuario.activo.is_(activo))

        return list(db.session.scalars(consulta))

    @staticmethod
    def obtener(usuario_id: int) -> Usuario:
        usuario = db.session.get(Usuario, usuario_id)
        if usuario is None:
            raise ApiError(
                "El usuario no existe.",
                codigo="no_encontrado",
                status=404,
            )
        return usuario

    @staticmethod
    def crear(datos: dict, actor: Usuario | None = None) -> Usuario:
        email = normalizar_email(datos["email"])

        if UsuarioService.por_email(email) is not None:
            raise ApiError(
                "Ya existe un usuario con ese email.",
                codigo="email_duplicado",
                status=409,
            )

        if (
            datos["rol"] == Rol.ADMIN.value
            and actor is not None
            and not actor.es_propietario
        ):
            raise ApiError(
                "Sólo el propietario puede crear administradores.",
                codigo="sin_permiso",
                status=403,
            )

        usuario = Usuario(
            nombre=datos["nombre"].strip(),
            email=email,
            password_hash=hashear_password(datos["password"]),
            rol=datos["rol"],
            activo=True,
            es_propietario=False,
            debe_cambiar_password=False,
        )
        db.session.add(usuario)
        db.session.flush()
        AuditoriaService.registrar(
            actor,
            "crear",
            "usuario",
            usuario.id,
            despues={
                "email": usuario.email,
                "rol": usuario.rol,
                "activo": True,
                "es_propietario": False,
            },
        )
        db.session.commit()
        return usuario

    @staticmethod
    def actualizar(usuario_id: int, datos: dict, actor: Usuario) -> Usuario:
        usuario = UsuarioService.obtener(usuario_id)

        UsuarioService._validar_gestion(actor, usuario, para_edicion=True)

        if (
            usuario.es_propietario
            and "rol" in datos
            and datos["rol"] != Rol.ADMIN.value
        ):
            raise ApiError(
                "El propietario no puede cambiar de rol. Transferí la propiedad primero.",
                codigo="propietario_protegido",
                status=409,
            )

        if "rol" in datos and datos["rol"] != usuario.rol:
            if not actor.es_propietario:
                raise ApiError(
                    "Sólo el propietario puede cambiar roles de administradores.",
                    codigo="sin_permiso",
                    status=403,
                )
            if not UsuarioService._hay_otro_admin_activo(usuario.id):
                raise ApiError(
                    "El sistema necesita al menos un administrador activo.",
                    codigo="ultimo_admin",
                    status=409,
                )

        antes = {
            "nombre": usuario.nombre,
            "email": usuario.email,
            "rol": usuario.rol,
            "activo": usuario.activo,
        }

        if "email" in datos:
            email = normalizar_email(datos["email"])
            existente = UsuarioService.por_email(email)
            if existente is not None and existente.id != usuario.id:
                raise ApiError(
                    "Ya existe un usuario con ese email.",
                    codigo="email_duplicado",
                    status=409,
                )
            usuario.email = email

        if "nombre" in datos:
            usuario.nombre = datos["nombre"].strip()

        if "rol" in datos:
            usuario.rol = datos["rol"]
            # Si deja de ser admin, tampoco puede conservar la propiedad.
            if usuario.rol != Rol.ADMIN.value:
                usuario.es_propietario = False

        AuditoriaService.registrar(
            actor,
            "actualizar",
            "usuario",
            usuario.id,
            antes=antes,
            despues={
                "nombre": usuario.nombre,
                "email": usuario.email,
                "rol": usuario.rol,
                "activo": usuario.activo,
            },
        )
        db.session.commit()
        return usuario

    @staticmethod
    def desactivar(usuario_id: int, actor: Usuario) -> Usuario:
        usuario = UsuarioService.obtener(usuario_id)

        if usuario.id == actor.id:
            raise ApiError(
                "No podés desactivar tu propio usuario.",
                codigo="accion_invalida",
                status=409,
            )

        UsuarioService._validar_gestion(actor, usuario, para_edicion=False)

        if not usuario.activo:
            return usuario

        if usuario.rol in {Rol.ADMIN.value, Rol.CONTADOR.value}:
            asignados = UsuarioService._clientes_asignados(usuario.id)
            if asignados:
                raise ApiError(
                    "El usuario tiene clientes asignados. Transferilos antes de desactivarlo.",
                    codigo="clientes_asignados",
                    status=409,
                    detalles={"clientes": asignados},
                )

        if usuario.rol == Rol.ADMIN.value and not UsuarioService._hay_otro_admin_activo(
            usuario.id
        ):
            raise ApiError(
                "El sistema necesita al menos un administrador activo.",
                codigo="ultimo_admin",
                status=409,
            )

        usuario.activo = False
        usuario.token_version = (usuario.token_version or 0) + 1
        AuditoriaService.registrar(
            actor,
            "desactivar",
            "usuario",
            usuario.id,
            antes={"activo": True},
            despues={"activo": False},
        )
        db.session.commit()
        return usuario

    @staticmethod
    def activar(usuario_id: int, actor: Usuario) -> Usuario:
        usuario = UsuarioService.obtener(usuario_id)

        UsuarioService._validar_gestion(actor, usuario, para_edicion=False)

        if not usuario.activo:
            usuario.activo = True
            usuario.token_version = (usuario.token_version or 0) + 1
            AuditoriaService.registrar(
                actor,
                "activar",
                "usuario",
                usuario.id,
                antes={"activo": False},
                despues={"activo": True},
            )
            db.session.commit()
        return usuario

    @staticmethod
    def cambiar_password(
        usuario_id: int,
        *,
        actor: Usuario,
        password_nueva: str,
        password_actual: str | None = None,
    ) -> Usuario:
        objetivo = UsuarioService.obtener(usuario_id)
        es_propio = actor.id == objetivo.id

        if not es_propio:
            if objetivo.rol == Rol.CLIENTE.value:
                raise ApiError(
                    "La contraseña de un cliente se restablece desde su ficha.",
                    codigo="usuario_cliente",
                    status=409,
                )
            if objetivo.es_propietario:
                raise ApiError(
                    "Sólo el propietario puede cambiar su propia contraseña.",
                    codigo="propietario_protegido",
                    status=403,
                )
            if objetivo.rol == Rol.ADMIN.value and not actor.es_propietario:
                raise ApiError(
                    "Sólo el propietario puede resetear administradores.",
                    codigo="sin_permiso",
                    status=403,
                )
            if actor.rol != Rol.ADMIN.value:
                raise ApiError(
                    "No podés cambiar la contraseña de otro usuario.",
                    codigo="sin_permiso",
                    status=403,
                )
        elif not verificar_password(password_actual or "", objetivo.password_hash):
            raise ApiError(
                "La contraseña actual no es correcta.",
                codigo="password_incorrecta",
                status=400,
            )

        objetivo.password_hash = hashear_password(password_nueva)
        objetivo.debe_cambiar_password = False
        objetivo.password_temporal_expira_en = None
        objetivo.token_version = (objetivo.token_version or 0) + 1
        AuditoriaService.registrar(
            actor,
            "cambiar_password",
            "usuario",
            objetivo.id,
            despues={"password_actualizada": True},
        )
        db.session.commit()
        return objetivo

    @staticmethod
    def transferir_propiedad(usuario_id: int, actor: Usuario) -> Usuario:
        if not actor.es_propietario:
            raise ApiError(
                "Sólo el propietario puede transferir la propiedad.",
                codigo="sin_permiso",
                status=403,
            )

        nuevo = UsuarioService.obtener(usuario_id)
        if nuevo.id == actor.id:
            raise ApiError(
                "Ya sos el propietario.",
                codigo="accion_invalida",
                status=409,
            )
        if nuevo.rol != Rol.ADMIN.value or not nuevo.activo:
            raise ApiError(
                "El nuevo propietario debe ser un administrador activo.",
                codigo="propietario_invalido",
                status=422,
            )

        actor.es_propietario = False
        nuevo.es_propietario = True
        AuditoriaService.registrar(
            actor,
            "transferir_propiedad",
            "usuario",
            nuevo.id,
            antes={"propietario_id": actor.id},
            despues={"propietario_id": nuevo.id},
        )
        db.session.commit()
        return nuevo

    @staticmethod
    def _validar_gestion(
        actor: Usuario, objetivo: Usuario, *, para_edicion: bool
    ) -> None:
        if objetivo.rol == Rol.CLIENTE.value:
            raise ApiError(
                "Los accesos de clientes se gestionan desde la ficha del cliente.",
                codigo="usuario_cliente",
                status=409,
            )

        if objetivo.es_propietario:
            if actor.id != objetivo.id:
                raise ApiError(
                    "El propietario sólo puede ser gestionado por sí mismo.",
                    codigo="propietario_protegido",
                    status=403,
                )
            if para_edicion:
                return
            raise ApiError(
                "El propietario no puede desactivarse.",
                codigo="propietario_protegido",
                status=409,
            )

        if (
            objetivo.rol == Rol.ADMIN.value
            and not actor.es_propietario
            and actor.id != objetivo.id
        ):
            raise ApiError(
                "Sólo el propietario puede gestionar administradores.",
                codigo="sin_permiso",
                status=403,
            )

    @staticmethod
    def _hay_otro_admin_activo(excluir_id: int) -> bool:
        total = db.session.scalar(
            select(func.count())
            .select_from(Usuario)
            .where(
                Usuario.rol == Rol.ADMIN.value,
                Usuario.activo.is_(True),
                Usuario.id != excluir_id,
            )
        )
        return bool(total)

    @staticmethod
    def _clientes_asignados(usuario_id: int) -> int:
        ultima = (
            select(
                ClienteVersion.cliente_id,
                func.max(ClienteVersion.id).label("version_id"),
            )
            .group_by(ClienteVersion.cliente_id)
            .subquery()
        )
        total = db.session.scalar(
            select(func.count())
            .select_from(ClienteVersion)
            .join(ultima, ultima.c.version_id == ClienteVersion.id)
            .where(ClienteVersion.contador_id == usuario_id)
        )
        return int(total or 0)
