"""Fixtures compartidas de la suite."""

# Los parámetros de Argon2 se leen al importar `app`, así que hay que bajarlos
# ANTES de cualquier import del proyecto. Sólo afecta a los tests: producción
# usa los defaults de OWASP.
import os

os.environ.setdefault("ARGON2_TIME_COST", "1")
os.environ.setdefault("ARGON2_MEMORY_COST", "1024")
os.environ.setdefault("ARGON2_PARALLELISM", "1")

import pytest  # noqa: E402

from app import create_app  # noqa: E402
from app.extensions import db, limiter  # noqa: E402
from app.models.usuario import Rol, Usuario  # noqa: E402
from app.utils.security import hashear_password  # noqa: E402

PASSWORD = "Secreta1234"


@pytest.fixture()
def app():
    aplicacion = create_app("testing")
    with aplicacion.app_context():
        db.create_all()
        try:
            limiter.reset()
        except Exception:  # pragma: no cover - defensivo entre versiones
            pass
        yield aplicacion
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def _crear(
    nombre: str,
    email: str,
    rol: Rol,
    *,
    es_propietario: bool = False,
) -> Usuario:
    usuario = Usuario(
        nombre=nombre,
        email=email,
        password_hash=hashear_password(PASSWORD),
        rol=rol.value,
        activo=True,
        es_propietario=es_propietario,
        debe_cambiar_password=False,
    )
    db.session.add(usuario)
    db.session.commit()
    return usuario


@pytest.fixture()
def admin(app):
    return _crear("Admin", "admin@test.com", Rol.ADMIN, es_propietario=True)


@pytest.fixture()
def admin_delegado(app):
    return _crear("Admin Delegado", "delegado@test.com", Rol.ADMIN)


@pytest.fixture()
def contador(app):
    return _crear("Contador", "contador@test.com", Rol.CONTADOR)
