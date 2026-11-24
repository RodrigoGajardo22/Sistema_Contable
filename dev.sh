#!/usr/bin/env bash
#
# Punto de entrada único del entorno de desarrollo.
#
#   ./dev.sh            levanta todo (equivale a ./dev.sh up)
#   ./dev.sh up         construye las imágenes, levanta y migra la base
#   ./dev.sh down       detiene los servicios (conserva los datos)
#   ./dev.sh restart    reinicia los servicios
#   ./dev.sh logs [svc] sigue los logs (de todos o de un servicio)
#   ./dev.sh status     muestra el estado de los contenedores y de la API
#   ./dev.sh test [..]  pytest rápido (tests montados, sin rebuild)
#   ./dev.sh check      type-check + build del frontend
#   ./dev.sh release    imágenes de producción + smoke test del backend
#   ./dev.sh reset      recrea el entorno y reinstala node_modules
#   ./dev.sh help       muestra esta ayuda
#
# Requiere: podman (con `podman compose`) y curl.
# En Windows se ejecuta desde Git Bash o WSL.
#
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

ENV_FILE="infra/.env.dev"
APP_URL="http://localhost:8080"
API_URL="${APP_URL}/api/health"

# ---------------------------------------------------------------------------
# Salida
# ---------------------------------------------------------------------------
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
  C_RESET=$'\033[0m'
  C_BLUE=$'\033[1;34m'
  C_GREEN=$'\033[1;32m'
  C_RED=$'\033[1;31m'
  C_DIM=$'\033[2m'
else
  C_RESET='' C_BLUE='' C_GREEN='' C_RED='' C_DIM=''
fi

log()  { printf '%s[dev]%s %s\n' "$C_BLUE" "$C_RESET" "$*"; }
ok()   { printf '%s[ ok]%s %s\n' "$C_GREEN" "$C_RESET" "$*"; }
warn() { printf '%s[ !!]%s %s\n' "$C_RED" "$C_RESET" "$*" >&2; }
dim()  { printf '%s%s%s\n' "$C_DIM" "$*" "$C_RESET"; }

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
project_name() {
  local name=''
  if [ -f "$ENV_FILE" ]; then
    name="$(grep -E '^COMPOSE_PROJECT_NAME=' "$ENV_FILE" | tail -n 1 | cut -d '=' -f 2- || true)"
  fi
  printf '%s' "${name:-sistema-contable}"
}

compose() {
  podman compose --env-file "$ENV_FILE" \
    -f infra/compose.yaml \
    -f infra/compose.dev.yaml \
    "$@"
}

require_podman() {
  if ! command -v podman >/dev/null 2>&1; then
    warn 'Podman no está instalado o no está en el PATH.'
    exit 1
  fi

  if ! podman info >/dev/null 2>&1; then
    warn 'La máquina de Podman no responde. Probá: podman machine start'
    exit 1
  fi
}

prepare_env() {
  local pairs=(
    'infra/.env.example:infra/.env.dev'
    'backend/.env.example:backend/.env.dev'
    'frontend/.env.example:frontend/.env.dev'
  )
  local pair src dst

  for pair in "${pairs[@]}"; do
    src="${pair%%:*}"
    dst="${pair##*:}"
    if [ ! -f "$dst" ]; then
      cp "$src" "$dst"
      log "Creado $dst a partir de $src"
    fi
  done
}

wait_for_api() {
  local intentos=60
  log "Esperando a que el backend responda en ${API_URL} …"

  local i
  for ((i = 1; i <= intentos; i++)); do
    if curl -fsS --max-time 2 "$API_URL" >/dev/null 2>&1; then
      ok 'API disponible.'
      return 0
    fi
    sleep 2
  done

  warn "El backend no respondió después de $((intentos * 2)) segundos."
  warn 'Revisá los logs con: ./dev.sh logs'
  return 1
}

esperar_contenedor() {
  local contenedor="$1"
  local intentos=60
  local i

  for ((i = 1; i <= intentos; i++)); do
    if podman exec "$contenedor" true >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done

  warn "El contenedor ${contenedor} no está disponible."
  return 1
}

aplicar_migraciones() {
  log 'Aplicando migraciones…'
  podman exec "$(project_name)-backend" flask --app run.py db upgrade
  ok 'Base de datos al día.'
}

sembrar_datos() {
  log 'Datos iniciales (seed idempotente)…'
  podman exec "$(project_name)-backend" flask --app run.py seed
}

print_urls() {
  printf '\n'
  ok 'Entorno listo.'
  dim '------------------------------------------------------------'
  printf '  Aplicación : %s\n' "$APP_URL"
  printf '  API health : %s\n' "$API_URL"
  printf '  Logs       : ./dev.sh logs\n'
  printf '  Detener    : ./dev.sh down\n'
  dim '------------------------------------------------------------'
  printf '\n'
}

# ---------------------------------------------------------------------------
# Comandos
# ---------------------------------------------------------------------------
cmd_up() {
  require_podman
  prepare_env

  log 'Construyendo imágenes y levantando servicios…'
  compose up -d --build

  # nginx resuelve "backend" al arrancar. Si compose recreó el contenedor,
  # el gateway sigue apuntando a la IP vieja: hay que reiniciarlo.
  log 'Refrescando el gateway (DNS interno de nginx)…'
  podman restart "$(project_name)-gateway" >/dev/null 2>&1 || true

  esperar_contenedor "$(project_name)-backend"
  aplicar_migraciones
  sembrar_datos

  wait_for_api
  print_urls
}

cmd_down() {
  require_podman

  log 'Deteniendo servicios (los datos de Postgres se conservan)…'
  compose down
  ok 'Servicios detenidos.'
}

cmd_restart() {
  cmd_down
  cmd_up
}

cmd_logs() {
  require_podman
  compose logs -f --tail=120 "$@"
}

cmd_status() {
  require_podman

  log 'Contenedores:'
  compose ps

  printf '\n'
  log 'Comprobaciones HTTP:'

  local code
  code="$(curl -fsS -o /dev/null -w '%{http_code}' --max-time 5 "$APP_URL/" || true)"
  printf '  %-22s %s\n' 'frontend (gateway)' "${code:-sin respuesta}"

  local body
  body="$(curl -fsS --max-time 5 "$API_URL" || true)"
  printf '  %-22s %s\n' 'backend /api/health' "${body:-sin respuesta}"

  local redis
  redis="$(podman exec "$(project_name)-redis" redis-cli ping 2>/dev/null || true)"
  printf '  %-22s %s\n' 'redis' "${redis:-sin respuesta}"
}

cmd_test() {
  require_podman

  local contenedor
  contenedor="$(project_name)-backend"

  if ! podman exec "$contenedor" true >/dev/null 2>&1; then
    warn "El contenedor ${contenedor} no está corriendo. Levantá el entorno con ./dev.sh up"
    return 1
  fi

  # pytest se instala una sola vez en el contenedor de desarrollo (que ya
  # tiene el código y los tests montados). Es mucho más rápido que arrancar
  # un contenedor nuevo en cada corrida.
  if ! podman exec "$contenedor" python -c "import pytest" >/dev/null 2>&1; then
    log 'Instalando dependencias de test en el contenedor (una vez)…'
    podman exec "$contenedor" pip install -q -r requirements-dev.txt
  fi

  podman exec "$contenedor" pytest -q "$@"
}

cmd_check() {
  require_podman

  local contenedor
  contenedor="$(project_name)-frontend"

  if ! podman exec "$contenedor" true >/dev/null 2>&1; then
    warn "El contenedor ${contenedor} no está corriendo. Levantá el entorno con ./dev.sh up"
    return 1
  fi

  # El WORKDIR de la imagen ya es /app: no pasamos -w porque MSYS reescribe
  # la ruta y la rompe.
  log 'Type-check (vue-tsc)…'
  podman exec "$contenedor" pnpm type-check

  log 'Build de producción del frontend…'
  podman exec "$contenedor" pnpm build-only

  ok 'Frontend verificado.'
}

cmd_release() {
  require_podman

  local proyecto
  proyecto="$(project_name)"

  log 'Construyendo la imagen de producción del backend…'
  podman build --target prod -f backend/Containerfile -t "${proyecto}-backend:prod" backend

  log 'Construyendo la imagen de producción del frontend…'
  podman build --target prod -f frontend/Containerfile -t "${proyecto}-frontend:prod" .

  # Smoke test: gunicorn + imports + /api/health, sin depender de Postgres
  # (el arranque no toca la base; el health no consulta).
  log 'Smoke test del backend de producción…'
  local smoke="${proyecto}-smoke"

  podman rm -f "$smoke" >/dev/null 2>&1 || true
  podman run -d --name "$smoke" \
    -e DATABASE_URL="sqlite:////tmp/smoke.db" \
    -e REDIS_URL="memory://" \
    -e JWT_SECRET_KEY="smoke-test-clave-de-al-menos-32-bytes" \
    "${proyecto}-backend:prod" >/dev/null

  local intentos=10
  local i
  for ((i = 1; i <= intentos; i++)); do
    if podman exec "$smoke" python -c \
      "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5000/api/health', timeout=2).status == 200 else 1)" \
      >/dev/null 2>&1; then
      podman rm -f "$smoke" >/dev/null 2>&1 || true
      ok 'Imágenes de producción listas y smoke test aprobado.'
      return 0
    fi
    sleep 1
  done

  podman logs --tail=20 "$smoke" 2>&1 || true
  podman rm -f "$smoke" >/dev/null 2>&1 || true
  warn 'El backend de producción no respondió al smoke test.'
  return 1
}

cmd_reset() {
  require_podman

  local volumen
  volumen="$(project_name)_frontend_node_modules"

  warn "Se van a eliminar los contenedores y el volumen '${volumen}'."
  warn 'Los datos de Postgres NO se tocan.'
  printf '¿Continuar? [s/N] '
  read -r respuesta

  case "$respuesta" in
    s | S | si | SI | sí | Sí) ;;
    *)
      log 'Cancelado.'
      return 0
      ;;
  esac

  compose down
  podman volume rm -f "$volumen" >/dev/null 2>&1 || true
  ok 'Volumen de node_modules eliminado.'

  cmd_up
}

cmd_help() {
  sed -n '2,20p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------
case "${1:-up}" in
  up)      cmd_up ;;
  down)    cmd_down ;;
  restart) cmd_restart ;;
  logs)    shift; cmd_logs "$@" ;;
  status)  cmd_status ;;
  test)    shift; cmd_test "$@" ;;
  check)   cmd_check ;;
  release) cmd_release ;;
  reset)   cmd_reset ;;
  help | -h | --help) cmd_help ;;
  *)
    warn "Comando desconocido: $1"
    printf '\n'
    cmd_help
    exit 1
    ;;
esac
