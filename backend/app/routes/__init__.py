"""Registro de blueprints.

Un blueprint por módulo. Los módulos que todavía no tienen endpoints quedan
declarados para que la estructura sea visible desde el primer día.
"""

from flask import Flask

from app.routes import (
    asientos,
    auditoria,
    auth,
    clientes,
    comprobantes,
    conciliacion,
    cuentas,
    dashboard,
    docs,
    reportes,
    system,
    usuarios,
    vencimientos,
)

BLUEPRINTS = (
    system.bp,
    docs.bp,
    auth.bp,
    usuarios.bp,
    clientes.bp,
    cuentas.bp,
    asientos.bp,
    comprobantes.bp,
    vencimientos.bp,
    conciliacion.bp,
    reportes.bp,
    auditoria.bp,
    dashboard.bp,
)


def register_blueprints(app: Flask) -> None:
    for blueprint in BLUEPRINTS:
        app.register_blueprint(blueprint)
