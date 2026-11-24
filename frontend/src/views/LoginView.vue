<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { ApiError, getCrudo } from '@/api/client'
import { useAuthStore } from '@/stores/auth'

interface HealthResponse {
  status: string
  service: string
}

interface Renglon {
  cuenta: string
  importe: number
  tipo: 'debe' | 'haber'
}

/**
 * Asiento de ejemplo que se muestra a la izquierda.
 * Debe = Caja 1.250.000 + Banco 850.000 = 2.100.000
 * Haber = Ventas 2.100.000
 */
const RENGLONES: Renglon[] = [
  { cuenta: 'Caja', importe: 1_250_000, tipo: 'debe' },
  { cuenta: 'Banco Galicia', importe: 850_000, tipo: 'debe' },
  { cuenta: 'Ventas', importe: 2_100_000, tipo: 'haber' },
]

const totalDebe = computed(() =>
  RENGLONES.filter((renglon) => renglon.tipo === 'debe').reduce(
    (total, renglon) => total + renglon.importe,
    0,
  ),
)

const totalHaber = computed(() =>
  RENGLONES.filter((renglon) => renglon.tipo === 'haber').reduce(
    (total, renglon) => total + renglon.importe,
    0,
  ),
)

const formato = new Intl.NumberFormat('es-AR', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

const money = (valor: number) => formato.format(valor)

const movimientoReducido = () =>
  window.matchMedia('(prefers-reduced-motion: reduce)').matches

/* --- Animación del asiento ------------------------------------------------ */
const debeMostrado = ref(0)
const haberMostrado = ref(0)
const asientoCerrado = ref(false)

const frames: number[] = []

function contar(
  asignar: (valor: number) => void,
  total: number,
  retardo: number,
  duracion: number,
) {
  if (movimientoReducido()) {
    asignar(total)
    return
  }

  const inicio = performance.now() + retardo

  const paso = (ahora: number) => {
    const progreso = Math.min(Math.max((ahora - inicio) / duracion, 0), 1)
    const suave = 1 - Math.pow(1 - progreso, 3)

    asignar(total * suave)

    if (progreso < 1) {
      frames.push(requestAnimationFrame(paso))
    }
  }

  frames.push(requestAnimationFrame(paso))
}

/* --- Foco que sigue al puntero -------------------------------------------- */
const raiz = ref<HTMLElement | null>(null)
const foco = ref({ x: 64, y: 18 })
let framePuntero = 0

function moverPuntero(evento: PointerEvent) {
  const elemento = raiz.value
  if (!elemento || framePuntero) return

  framePuntero = requestAnimationFrame(() => {
    const caja = elemento.getBoundingClientRect()
    foco.value = {
      x: ((evento.clientX - caja.left) / caja.width) * 100,
      y: ((evento.clientY - caja.top) / caja.height) * 100,
    }
    framePuntero = 0
  })
}

/* --- Estado del formulario ------------------------------------------------ */
type EstadoApi = 'cargando' | 'ok' | 'error'

const estadoApi = ref<EstadoApi>('cargando')
const email = ref('')
const contrasena = ref('')
const verContrasena = ref(false)
const mensaje = ref('')
const tono = ref<'info' | 'ok' | 'error'>('info')
const enviando = ref(false)

const emailInvalido = ref(false)
const contrasenaInvalida = ref(false)

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const segundosBloqueo = ref(0)
let temporizadorBloqueo: number | undefined

const bloqueado = computed(() => segundosBloqueo.value > 0)

function mmss(total: number): string {
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`
}

const textoBoton = computed(() => {
  if (enviando.value) return 'Verificando…'
  if (bloqueado.value) return `Reintentá en ${mmss(segundosBloqueo.value)}`
  return 'Ingresar'
})

function iniciarCuentaRegresiva(segundos: number) {
  segundosBloqueo.value = Math.max(1, Math.round(segundos))
  window.clearInterval(temporizadorBloqueo)

  temporizadorBloqueo = window.setInterval(() => {
    segundosBloqueo.value -= 1

    if (segundosBloqueo.value <= 0) {
      window.clearInterval(temporizadorBloqueo)
      segundosBloqueo.value = 0
      mensaje.value = ''
      tono.value = 'info'
    }
  }, 1000)
}

async function consultarApi() {
  try {
    await getCrudo<HealthResponse>('/health')
    estadoApi.value = 'ok'
  } catch {
    estadoApi.value = 'error'
  }
}

async function ingresar() {
  if (enviando.value || bloqueado.value) return

  mensaje.value = ''
  emailInvalido.value = !email.value.trim()
  contrasenaInvalida.value = !contrasena.value

  if (emailInvalido.value || contrasenaInvalida.value) {
    tono.value = 'error'
    mensaje.value = 'Completá el email y la contraseña para continuar.'
    return
  }

  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value.trim())) {
    emailInvalido.value = true
    tono.value = 'error'
    mensaje.value = 'El email no tiene un formato válido.'
    return
  }

  enviando.value = true

  try {
    await auth.iniciarSesion(email.value.trim(), contrasena.value)

    if (auth.debeCambiarPassword) {
      await router.replace({ name: 'cambiar-password' })
      return
    }

    const destino =
      typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    await router.replace(destino === '/login' ? '/' : destino)
  } catch (error) {
    tono.value = 'error'

    if (error instanceof ApiError) {
      mensaje.value = error.mensaje

      if (error.status === 429) {
        const segundos = Number(error.detalles?.reintentar_en_segundos ?? 60)
        iniciarCuentaRegresiva(Number.isFinite(segundos) ? segundos : 60)
      }
    } else {
      mensaje.value = 'No pudimos iniciar sesión. Intentá de nuevo.'
    }
  } finally {
    enviando.value = false
  }
}

/* --- Ciclo de vida --------------------------------------------------------- */
const seguirPuntero = ref(false)

onMounted(() => {
  if (route.query.password === 'cambiada') {
    tono.value = 'ok'
    mensaje.value = 'Contraseña actualizada. Ingresá con la nueva.'
  }

  contar((valor) => (debeMostrado.value = valor), totalDebe.value, 260, 1150)
  contar((valor) => (haberMostrado.value = valor), totalHaber.value, 400, 1150)

  window.setTimeout(
    () => (asientoCerrado.value = true),
    movimientoReducido() ? 0 : 1650,
  )

  seguirPuntero.value =
    !movimientoReducido() && window.matchMedia('(pointer: fine)').matches

  void consultarApi()
})

onBeforeUnmount(() => {
  frames.forEach((frame) => cancelAnimationFrame(frame))
  if (framePuntero) cancelAnimationFrame(framePuntero)
  window.clearInterval(temporizadorBloqueo)
})
</script>

<template>
  <div
    ref="raiz"
    class="auth"
    @pointermove="seguirPuntero && moverPuntero($event)"
  >
    <!-- Capas de fondo decorativas -->
    <div class="auth__aura" aria-hidden="true"></div>
    <div class="auth__grid" aria-hidden="true"></div>
    <div
      class="auth__spotlight"
      aria-hidden="true"
      :style="{ '--mx': `${foco.x}%`, '--my': `${foco.y}%` }"
    ></div>
    <div class="auth__grain" aria-hidden="true"></div>

    <div class="auth__shell">
      <header class="brand">
        <span class="brand__mark" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none">
            <path
              d="M4 7h16M4 12h11M4 17h7"
              stroke="currentColor"
              stroke-width="1.5"
              stroke-linecap="round"
            />
            <circle cx="18" cy="17" r="2.2" fill="currentColor" />
          </svg>
        </span>
        <span class="brand__text">
          <span class="brand__name">Sistema Contable</span>
          <span class="brand__tag">Estudio contable · Viedma</span>
        </span>
      </header>

      <div class="auth__inner">
        <!-- Relato + asiento -->
        <section class="stage">
          <div class="stage__intro">
            <p class="eyebrow">Libro diario · Ejercicio 2026</p>

            <h1 class="stage__title">
              La contabilidad, en su forma más
              <em>clara</em>.
            </h1>

            <p class="lede">
              Asientos, comprobantes y vencimientos de todo el estudio en un solo
              lugar. Partida doble verificada en cada movimiento.
            </p>
          </div>

          <article class="ledger" aria-label="Asiento contable de ejemplo">
            <div class="ledger__head">
              <span>Asiento Nº 0001</span>
              <span>Diario general</span>
            </div>

            <ul class="ledger__rows">
              <li
                v-for="(renglon, indice) in RENGLONES"
                :key="renglon.cuenta"
                class="ledger__row"
                :class="`is-${renglon.tipo}`"
                :style="{ '--i': indice }"
              >
                <span class="ledger__cuenta">
                  <span v-if="renglon.tipo === 'haber'" class="ledger__a">a</span>
                  {{ renglon.cuenta }}
                </span>
                <span class="ledger__importe tabular">
                  {{ money(renglon.importe) }}
                </span>
              </li>
            </ul>

            <div class="ledger__totales">
              <div>
                <span class="ledger__label">Debe</span>
                <span class="ledger__total tabular">{{ money(debeMostrado) }}</span>
              </div>
              <div>
                <span class="ledger__label">Haber</span>
                <span class="ledger__total tabular">{{ money(haberMostrado) }}</span>
              </div>
            </div>

            <p class="balance" :class="{ 'is-visible': asientoCerrado }">
              <svg viewBox="0 0 16 16" width="14" height="14" fill="none" aria-hidden="true">
                <path
                  d="M3 8.4 6.2 11.6 13 4.8"
                  stroke="currentColor"
                  stroke-width="1.7"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                />
              </svg>
              Asiento balanceado · debe = haber
            </p>
          </article>
        </section>

        <!-- Acceso -->
        <section class="panel">
          <form class="card login" novalidate @submit.prevent="ingresar">
            <div class="login__head">
              <h2 class="login__title">Acceso al estudio</h2>
              <p class="login__sub">
                Ingresá con las credenciales que te asignó el administrador.
              </p>
            </div>

            <div class="field">
              <label class="field__label" for="email">Email</label>
              <input
                id="email"
                v-model="email"
                class="input"
                type="email"
                name="email"
                autocomplete="username"
                placeholder="nombre@estudio.com"
                :aria-invalid="emailInvalido"
                :aria-describedby="mensaje ? 'acceso-mensaje' : undefined"
                @input="emailInvalido = false"
              />
            </div>

            <div class="field">
              <label class="field__label" for="contrasena">Contraseña</label>
              <div class="campo-clave">
                <input
                  id="contrasena"
                  v-model="contrasena"
                  class="input"
                  :type="verContrasena ? 'text' : 'password'"
                  name="password"
                  autocomplete="current-password"
                  placeholder="••••••••"
                  :aria-invalid="contrasenaInvalida"
                  @input="contrasenaInvalida = false"
                />
                <button
                  type="button"
                  class="campo-clave__toggle"
                  :aria-label="verContrasena ? 'Ocultar contraseña' : 'Mostrar contraseña'"
                  :aria-pressed="verContrasena"
                  @click="verContrasena = !verContrasena"
                >
                  <svg viewBox="0 0 16 16" width="16" height="16" fill="none" aria-hidden="true">
                    <path
                      d="M1.6 8S4 4.2 8 4.2 14.4 8 14.4 8 12 11.8 8 11.8 1.6 8 1.6 8Z"
                      stroke="currentColor"
                      stroke-width="1.3"
                      stroke-linejoin="round"
                    />
                    <circle cx="8" cy="8" r="1.7" stroke="currentColor" stroke-width="1.3" />
                    <path
                      v-if="verContrasena"
                      d="M3 13 13 3"
                      stroke="currentColor"
                      stroke-width="1.3"
                      stroke-linecap="round"
                    />
                  </svg>
                </button>
              </div>
            </div>

            <button
              class="btn btn--primary login__submit"
              type="submit"
              :disabled="enviando || bloqueado"
            >
              {{ textoBoton }}
              <svg viewBox="0 0 16 16" width="15" height="15" fill="none" aria-hidden="true">
                <path
                  d="M3 8h9M8.6 4.4 12.2 8l-3.6 3.6"
                  stroke="currentColor"
                  stroke-width="1.5"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                />
              </svg>
            </button>

            <p
              v-if="mensaje"
              id="acceso-mensaje"
              class="login__mensaje"
              :class="{ 'is-error': tono === 'error', 'is-ok': tono === 'ok' }"
              role="status"
              aria-live="polite"
            >
              {{ mensaje }}
            </p>

            <p class="login__nota">
              ¿No tenés acceso? El administrador del estudio crea las cuentas.
            </p>
          </form>

          <p class="sistema-estado">
            <span class="sistema-estado__dot" :class="`is-${estadoApi}`" aria-hidden="true"></span>
            <span v-if="estadoApi === 'cargando'">Verificando el sistema…</span>
            <span v-else-if="estadoApi === 'ok'">Sistema operativo · API conectada</span>
            <span v-else>API sin respuesta</span>
          </p>
        </section>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ==========================================================================
   Estructura
   ========================================================================== */
.auth {
  position: relative;
  min-height: 100dvh;
  overflow: hidden;
  isolation: isolate;
  background: var(--color-bg);
}

.auth__shell {
  position: relative;
  z-index: var(--z-content);
  display: flex;
  flex-direction: column;
  gap: clamp(2rem, 5vw, 3.5rem);
  width: min(74rem, 100% - 3rem);
  min-height: 100dvh;
  margin-inline: auto;
  padding-block: clamp(1.5rem, 4vw, 2.5rem) var(--space-10);
}

.auth__inner {
  display: grid;
  flex: 1;
  grid-template-columns: minmax(0, 1.1fr) minmax(19rem, 0.9fr);
  gap: clamp(2rem, 5vw, 5rem);
  align-items: center;
}

/* ==========================================================================
   Fondo
   ========================================================================== */
.auth__aura {
  position: absolute;
  inset: -30% -10% auto -20%;
  height: 85vh;
  background:
    radial-gradient(48% 60% at 30% 40%, rgb(43 217 138 / 16%), transparent 70%),
    radial-gradient(40% 50% at 75% 10%, rgb(22 160 106 / 12%), transparent 70%);
  filter: blur(10px);
  animation: deriva 26s var(--ease-in-out) infinite;
  pointer-events: none;
}

.auth__grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(to right, rgb(255 255 255 / 4%) 1px, transparent 1px),
    linear-gradient(to bottom, rgb(255 255 255 / 4%) 1px, transparent 1px);
  background-size: 72px 72px;
  mask-image: radial-gradient(70% 60% at 40% 30%, #000 20%, transparent 85%);
  opacity: 0.5;
  pointer-events: none;
}

.auth__spotlight {
  position: absolute;
  inset: 0;
  background: radial-gradient(
    34rem circle at var(--mx, 64%) var(--my, 18%),
    rgb(43 217 138 / 9%),
    transparent 65%
  );
  transition: background-position var(--dur-fast) linear;
  pointer-events: none;
}

.auth__grain {
  position: absolute;
  inset: 0;
  opacity: 0.035;
  mix-blend-mode: overlay;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='140' height='140'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='140' height='140' filter='url(%23n)'/%3E%3C/svg%3E");
  pointer-events: none;
}

/* ==========================================================================
   Marca
   ========================================================================== */
.brand {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  animation: subir var(--dur-slow) var(--ease-out) both;
}

.brand__mark {
  display: grid;
  place-items: center;
  width: 2.5rem;
  height: 2.5rem;
  border: 1px solid var(--color-line-strong);
  border-radius: var(--radius-md);
  background: linear-gradient(150deg, rgb(43 217 138 / 14%), transparent 65%);
  color: var(--color-accent);
}

.brand__text {
  display: grid;
  line-height: 1.25;
}

.brand__name {
  font-size: var(--text-sm);
  font-weight: 600;
  letter-spacing: 0.01em;
}

.brand__tag {
  font-size: var(--text-xs);
  color: var(--color-text-faint);
}

/* ==========================================================================
   Columna izquierda
   ========================================================================== */
.stage {
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
}

.stage__intro {
  display: grid;
  gap: var(--space-4);
}

.stage__title {
  max-width: 17ch;
  font-size: var(--text-3xl);
  animation: subir var(--dur-slow) var(--ease-out) both;
  animation-delay: 120ms;
}

.stage__title em {
  font-style: italic;
  color: var(--color-accent);
}

.lede {
  max-width: 44ch;
  font-size: var(--text-sm);
  color: var(--color-text-muted);
  animation: subir var(--dur-slow) var(--ease-out) both;
  animation-delay: 180ms;
}

/* ==========================================================================
   Asiento
   ========================================================================== */
.ledger {
  padding: var(--space-5);
  border: 1px solid var(--color-line);
  border-radius: var(--radius-lg);
  background: linear-gradient(180deg, rgb(16 19 25 / 92%), rgb(8 10 14 / 96%));
  box-shadow: var(--shadow-card);
  animation: subir 700ms var(--ease-out) both;
  animation-delay: 240ms;
}

.ledger__head {
  display: flex;
  justify-content: space-between;
  gap: var(--space-4);
  font-size: var(--text-xs);
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--color-text-faint);
}

.ledger__rows {
  display: grid;
  gap: var(--space-2);
  margin-top: var(--space-4);
  padding: 0;
  list-style: none;
}

.ledger__row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-4);
  font-size: var(--text-sm);
  opacity: 0;
  animation: subir var(--dur-slow) var(--ease-out) forwards;
  animation-delay: calc(var(--i) * 90ms + 420ms);
}

.ledger__row.is-haber {
  padding-left: var(--space-5);
  color: var(--color-text-muted);
}

.ledger__a {
  margin-right: 0.5ch;
  color: var(--color-text-faint);
}

.ledger__importe {
  color: var(--color-text);
}

.ledger__row.is-haber .ledger__importe {
  color: var(--color-text-muted);
}

.ledger__totales {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-4);
  margin-top: var(--space-3);
  padding-top: var(--space-3);
  border-top: 1px solid var(--color-line-strong);
}

.ledger__label {
  display: block;
  margin-bottom: 0.15rem;
  font-size: var(--text-xs);
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--color-text-faint);
}

.ledger__total {
  font-size: var(--text-lg);
  color: var(--color-text);
}

.balance {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  margin-top: var(--space-4);
  font-size: var(--text-xs);
  color: var(--color-accent);
  opacity: 0;
  transform: translateY(4px);
  transition:
    opacity var(--dur-slow) var(--ease-out),
    transform var(--dur-slow) var(--ease-out);
}

.balance.is-visible {
  opacity: 1;
  transform: none;
}

/* ==========================================================================
   Panel de acceso
   ========================================================================== */
.panel {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  animation: subir 700ms var(--ease-out) both;
  animation-delay: 160ms;
}

.login {
  position: relative;
  display: grid;
  gap: var(--space-4);
  padding: clamp(1.5rem, 3vw, 2.25rem);
}

/* Borde degradado de 1px sin engrosar el layout */
.login::before {
  content: '';
  position: absolute;
  inset: 0;
  padding: 1px;
  border-radius: inherit;
  background: linear-gradient(
    145deg,
    rgb(43 217 138 / 55%),
    rgb(255 255 255 / 8%) 38%,
    transparent 72%
  );
  -webkit-mask:
    linear-gradient(#000 0 0) content-box,
    linear-gradient(#000 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
  pointer-events: none;
}

.login__head {
  display: grid;
  gap: var(--space-2);
}

.login__title {
  font-size: var(--text-xl);
}

.login__sub {
  font-size: var(--text-sm);
  color: var(--color-text-muted);
}

.campo-clave {
  position: relative;
}

.campo-clave .input {
  padding-right: 2.75rem;
}

.campo-clave__toggle {
  position: absolute;
  top: 50%;
  right: 0.375rem;
  display: grid;
  place-items: center;
  width: 2.25rem;
  height: 2.25rem;
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text-faint);
  cursor: pointer;
  transform: translateY(-50%);
  transition: color var(--dur-fast) var(--ease-out);
}

.campo-clave__toggle:hover {
  color: var(--color-text);
}

.login__mensaje {
  font-size: var(--text-sm);
  line-height: 1.45;
  color: var(--color-text-muted);
}

.login__mensaje.is-ok {
  color: var(--color-accent);
}

.login__mensaje.is-error {
  color: var(--color-danger);
}

.login__submit {
  width: 100%;
}

.eyebrow {
  animation: subir var(--dur-slow) var(--ease-out) both;
  animation-delay: 60ms;
}

.login__nota {
  font-size: var(--text-xs);
  color: var(--color-text-faint);
}

/* ==========================================================================
   Estado del sistema
   ========================================================================== */
.sistema-estado {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding-left: var(--space-1);
  font-size: var(--text-xs);
  color: var(--color-text-faint);
}

.sistema-estado__dot {
  width: 0.4375rem;
  height: 0.4375rem;
  border-radius: 999px;
  background: var(--color-text-faint);
  flex: none;
}

.sistema-estado__dot.is-ok {
  background: var(--color-accent);
  box-shadow: 0 0 0 3px rgb(43 217 138 / 12%);
}

.sistema-estado__dot.is-error {
  background: var(--color-danger);
}

.sistema-estado__dot.is-cargando {
  animation: parpadeo 1.4s var(--ease-in-out) infinite;
}

/* ==========================================================================
   Responsive
   ========================================================================== */
@media (max-width: 60rem) {
  .auth__inner {
    grid-template-columns: 1fr;
    gap: var(--space-6);
  }

  .panel {
    order: -1;
    width: 100%;
    max-width: 27rem;
    margin-inline: auto;
  }

  .stage__title {
    max-width: none;
  }
}

@media (max-width: 26rem) {
  .auth__shell {
    width: min(74rem, 100% - 2rem);
  }

  .ledger {
    padding: var(--space-4);
  }
}

/* ==========================================================================
   Animaciones
   ========================================================================== */
@keyframes subir {
  from {
    opacity: 0;
    transform: translateY(14px);
  }
  to {
    opacity: 1;
    transform: none;
  }
}

@keyframes deriva {
  0%,
  100% {
    transform: translate3d(-2%, 0, 0) scale(1);
  }
  50% {
    transform: translate3d(3%, 2%, 0) scale(1.08);
  }
}

@keyframes parpadeo {
  50% {
    opacity: 0.35;
  }
}
</style>
