"""Registro y consulta de la bitácora de auditoría."""

from datetime import date, datetime
from typing import Any

from sqlalchemy import select

from app.extensions import db
from app.models.auditoria import Auditoria
from app.models.usuario import Usuario
from app.utils.errors import ApiError


class AuditoriaService:
    @staticmethod
    def registrar(
        actor: Usuario | None,
        accion: str,
        entidad: str,
        entidad_id: int | None,
        *,
        antes: dict | None = None,
        despues: dict | None = None,
    ) -> None:
        """Agrega la entrada a la sesión; no hace commit."""
        db.session.add(
            Auditoria(
                usuario_id=actor.id if actor else None,
                accion=accion,
                entidad=entidad,
                entidad_id=entidad_id,
                antes=antes,
                despues=despues,
            )
        )

    @staticmethod
    def listar(
        actor: Usuario,
        *,
        entidad: str | None = None,
        accion: str | None = None,
        usuario_id: int | None = None,
        desde: date | None = None,
        hasta: date | None = None,
    ) -> list[Auditoria]:
        if actor.rol != "admin":
            raise ApiError(
                "Sólo el administrador puede ver la auditoría.",
                codigo="sin_permiso",
                status=403,
            )

        consulta = select(Auditoria)

        if entidad:
            consulta = consulta.where(Auditoria.entidad == entidad)
        if accion:
            consulta = consulta.where(Auditoria.accion == accion)
        if usuario_id:
            consulta = consulta.where(Auditoria.usuario_id == usuario_id)
        if desde:
            consulta = consulta.where(
                Auditoria.fecha >= datetime.combine(desde, datetime.min.time())
            )
        if hasta:
            consulta = consulta.where(
                Auditoria.fecha <= datetime.combine(hasta, datetime.max.time())
            )

        consulta = consulta.order_by(Auditoria.id.desc()).limit(300)
        return list(db.session.scalars(consulta))


def serializar(entrada: Auditoria) -> dict[str, Any]:
    return {
        "id": entrada.id,
        "usuario": entrada.usuario.nombre if entrada.usuario else "Sistema",
        "accion": entrada.accion,
        "entidad": entrada.entidad,
        "entidad_id": entrada.entidad_id,
        "antes": entrada.antes,
        "despues": entrada.despues,
        "fecha": entrada.fecha.isoformat() if entrada.fecha else None,
    }
