"""La documentación OpenAPI no se desincroniza de las rutas reales."""

import re
from collections.abc import Iterator

import pytest
from openapi_spec_validator import validate_spec

RUTA_PARAM = re.compile(r"<(?:[^:<>]+:)?([^<>]+)>")


def _a_openapi(regla: str) -> str:
    """Convierte /api/clientes/<int:id> en /clientes/{id}."""
    if regla == "/api":
        return "/"
    if regla.startswith("/api/"):
        regla = regla[len("/api") :]
    return RUTA_PARAM.sub(r"{\1}", regla)


def _rutas_flask(app) -> dict[str, set[str]]:
    rutas: dict[str, set[str]] = {}
    for regla in app.url_map.iter_rules():
        if not regla.rule.startswith("/api"):
            continue
        if regla.rule.startswith("/api/docs") or regla.rule == "/api/openapi.json":
            continue
        metodos = set(regla.methods or set()) - {"HEAD", "OPTIONS"}
        if not metodos:
            continue
        ruta = _a_openapi(regla.rule)
        rutas.setdefault(ruta, set()).update(metodos)
    return rutas


def _rutas_spec(spec: dict) -> dict[str, set[str]]:
    return {
        ruta: {metodo.upper() for metodo in operaciones if metodo != "parameters"}
        for ruta, operaciones in spec["paths"].items()
    }


@pytest.fixture()
def spec(client):
    respuesta = client.get("/api/openapi.json")
    assert respuesta.status_code == 200
    return respuesta.get_json()


def _recorrer(valor: object) -> Iterator[str]:
    if isinstance(valor, dict):
        for clave, item in valor.items():
            if clave == "$ref" and isinstance(item, str):
                yield item
            else:
                yield from _recorrer(item)
    elif isinstance(valor, list):
        for item in valor:
            yield from _recorrer(item)


def _resolver(spec: dict, ref: str):
    assert ref.startswith("#/"), f"Sólo se soportan refs locales: {ref}"
    actual = spec
    for parte in ref[2:].split("/"):
        assert parte in actual, f"Referencia rota: {ref}"
        actual = actual[parte]
    return actual


def test_spec_es_openapi_valido(spec):
    assert spec["openapi"].startswith("3.0.")
    assert spec["info"]["title"]
    assert spec["info"]["version"]
    assert spec["servers"]
    validate_spec(spec)


def test_referencias_resuelven(spec):
    refs = list(_recorrer(spec))
    assert refs, "La spec no declara referencias"
    for ref in refs:
        _resolver(spec, ref)


def test_todas_las_rutas_estan_documentadas(app, spec):
    flask = _rutas_flask(app)
    documentadas = _rutas_spec(spec)
    faltantes = {
        ruta: sorted(metodos - documentadas.get(ruta, set()))
        for ruta, metodos in flask.items()
        if metodos - documentadas.get(ruta, set())
    }
    sobrantes = {
        ruta: sorted(metodos - flask.get(ruta, set()))
        for ruta, metodos in documentadas.items()
        if metodos - flask.get(ruta, set())
    }
    assert not faltantes, f"Rutas sin documentar: {faltantes}"
    assert not sobrantes, f"Rutas documentadas que ya no existen: {sobrantes}"


def _nombres_parametros(spec: dict, parametros: list | None) -> set[str]:
    nombres = set()
    for parametro in parametros or []:
        if "$ref" in parametro:
            parametro = _resolver(spec, parametro["$ref"])
        if parametro.get("name"):
            nombres.add(parametro["name"])
    return nombres


def test_cada_operacion_tiene_contexto(spec):
    tags_declarados = {tag["name"] for tag in spec.get("tags", [])}
    for ruta, operaciones in spec["paths"].items():
        for metodo, operacion in operaciones.items():
            if metodo == "parameters":
                continue
            assert operacion.get("summary"), f"{metodo.upper()} {ruta} sin summary"
            assert operacion.get("tags"), f"{metodo.upper()} {ruta} sin tags"
            assert operacion.get("responses"), f"{metodo.upper()} {ruta} sin respuestas"
            assert set(operacion.get("tags", [])) <= tags_declarados, (
                f"{metodo.upper()} {ruta} usa un tag inexistente"
            )

            nombres = _nombres_parametros(spec, operaciones.get("parameters"))
            nombres |= _nombres_parametros(spec, operacion.get("parameters"))
            for nombre in RUTA_PARAM.findall(ruta):
                assert nombre in nombres, f"{metodo.upper()} {ruta} no declara {nombre}"



def test_swagger_ui_y_assets(client):
    html = client.get("/api/docs")
    assert html.status_code == 200
    assert b"/api/openapi.json" in html.data
    assert b"swagger-ui-bundle.js" in html.data
    assert b"Authorize" in html.data or b"persistAuthorization" in html.data

    css = client.get("/api/docs/swagger-ui.css")
    assert css.status_code == 200
    assert "text/css" in css.content_type

    js = client.get("/api/docs/swagger-ui-bundle.js")
    assert js.status_code == 200
    assert "javascript" in js.content_type
