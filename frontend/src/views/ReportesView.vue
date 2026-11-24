<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import { ApiError } from '@/api/client'
import { cuentasApi } from '@/api/cuentas'
import {
  reportesApi,
  type AsientoDiario,
  type Balance,
  type LibroIva,
  type Mayor,
} from '@/api/reportes'
import type { Cuenta } from '@/api/tipos'
import EmptyState from '@/components/ui/EmptyState.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import { useAuthStore } from '@/stores/auth'

type Pestania = 'resumen' | 'diario' | 'mayor' | 'balance' | 'iva'

const route = useRoute()
const auth = useAuthStore()
const esCliente = computed(() => auth.rol === 'cliente')
const clienteId = computed(() => Number(route.params.id))

const pestania = ref<Pestania>(esCliente.value ? 'resumen' : 'balance')
const hoy = new Date()
const desde = ref(
  `${hoy.getFullYear()}-${String(hoy.getMonth() + 1).padStart(2, '0')}-01`,
)
const hasta = ref(
  `${hoy.getFullYear()}-${String(hoy.getMonth() + 1).padStart(2, '0')}-${String(hoy.getDate()).padStart(2, '0')}`,
)

const cargando = ref(false)
const error = ref('')

const diario = ref<AsientoDiario[]>([])
const balance = ref<Balance | null>(null)
const mayor = ref<Mayor | null>(null)
const libro = ref<LibroIva | null>(null)

const resumenCliente = computed(() => {
  if (!libro.value) return null
  const ivaVentas = Number(libro.value.ventas.iva)
  const ivaCompras = Number(libro.value.compras.iva)
  return {
    ventas: Number(libro.value.ventas.total),
    compras: Number(libro.value.compras.total),
    ivaVentas,
    ivaCompras,
    saldoIva: ivaVentas - ivaCompras,
    operaciones:
      libro.value.ventas.items.length + libro.value.compras.items.length,
  }
})

const itemsCliente = computed(() => {
  if (!libro.value) return []
  return [
    ...libro.value.ventas.items.map((item) => ({ ...item, tipo: 'Venta' as const })),
    ...libro.value.compras.items.map((item) => ({ ...item, tipo: 'Compra' as const })),
  ].sort((a, b) => b.fecha.localeCompare(a.fecha))
})

const cuentas = ref<Cuenta[]>([])
const cuentaId = ref<number | null>(null)

const PESTANIAS = computed<{ id: Pestania; etiqueta: string }[]>(() =>
  esCliente.value
    ? [{ id: 'resumen', etiqueta: 'Resumen' }]
    : [
        { id: 'balance', etiqueta: 'Balance' },
        { id: 'diario', etiqueta: 'Diario' },
        { id: 'mayor', etiqueta: 'Mayor' },
        { id: 'iva', etiqueta: 'Libro IVA' },
      ],
)

const formato = new Intl.NumberFormat('es-AR', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

function monto(valor: string | number | null | undefined): string {
  return formato.format(Number(valor ?? 0))
}

const fecha = new Intl.DateTimeFormat('es-AR', { dateStyle: 'medium' })

function fechaVisible(iso: string): string {
  const [anio, mes, dia] = iso.split('-')
  return fecha.format(new Date(Number(anio), Number(mes) - 1, Number(dia)))
}

async function cargar() {
  cargando.value = true
  error.value = ''
  const rango = { desde: desde.value, hasta: hasta.value }

  try {
    if (pestania.value === 'balance') {
      balance.value = await reportesApi.balance(clienteId.value, rango)
    } else if (pestania.value === 'diario') {
      diario.value = await reportesApi.diario(clienteId.value, rango)
    } else if (pestania.value === 'mayor') {
      if (!cuentaId.value) {
        cuentas.value = (await cuentasApi.listar(clienteId.value))
          .filter((c) => c.imputable)
          .sort((a, b) => a.codigo.localeCompare(b.codigo))
        cuentaId.value = cuentas.value[0]?.id ?? null
      }
      if (cuentaId.value) {
        mayor.value = await reportesApi.mayor(clienteId.value, cuentaId.value, rango)
      }
    } else {
      libro.value = await reportesApi.libroIva(clienteId.value, rango)
    }
  } catch (e) {
    error.value = e instanceof ApiError ? e.mensaje : 'No pudimos generar el reporte.'
  } finally {
    cargando.value = false
  }
}

onMounted(cargar)

function cambiar(p: Pestania) {
  pestania.value = p
  if (p !== 'mayor') cuentaId.value = null
  void cargar()
}

async function cambiarCuenta() {
  if (!cuentaId.value) return
  cargando.value = true
  try {
    mayor.value = await reportesApi.mayor(clienteId.value, cuentaId.value, {
      desde: desde.value,
      hasta: hasta.value,
    })
  } finally {
    cargando.value = false
  }
}
</script>

<template>
  <section class="reportes">
    <RouterLink :to="{ name: 'cliente', params: { id: clienteId } }" class="volver">
      <svg viewBox="0 0 16 16" width="14" height="14" fill="none" aria-hidden="true">
        <path d="M13 8H4M7.4 4.4 3.8 8l3.6 3.6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
      {{ esCliente ? 'Mi información' : 'Ficha del cliente' }}
    </RouterLink>

    <PageHeader
      eyebrow="Informes"
      :title="esCliente ? 'Mis reportes' : 'Reportes'"
      :subtitle="
        esCliente
          ? 'Resumen básico de ventas, compras e IVA del período.'
          : 'Sólo asientos confirmados. Los borradores y anulados no afectan.'
      "
    >
      <template #actions>
        <div class="rango">
          <input v-model="desde" class="input" type="date" aria-label="Desde" />
          <input v-model="hasta" class="input" type="date" aria-label="Hasta" />
          <button class="btn btn--sm" type="button" @click="cargar">Actualizar</button>
        </div>
      </template>
    </PageHeader>

    <div v-if="error" class="alert alert--error" role="alert">{{ error }}</div>
    <EmptyState v-else-if="cargando" loading compact>Generando reporte…</EmptyState>

    <!-- Reporte básico del cliente -->
    <template v-else-if="esCliente">
      <div v-if="resumenCliente" class="resumen-cliente">
        <div class="tarjetas-reporte">
          <article class="card tarjeta-reporte">
            <p class="tarjeta-reporte__rotulo">Ventas</p>
            <p class="tarjeta-reporte__valor tabular">
              {{ monto(resumenCliente.ventas) }}
            </p>
            <p class="tarjeta-reporte__nota">
              IVA {{ monto(resumenCliente.ivaVentas) }}
            </p>
          </article>

          <article class="card tarjeta-reporte">
            <p class="tarjeta-reporte__rotulo">Compras</p>
            <p class="tarjeta-reporte__valor tabular">
              {{ monto(resumenCliente.compras) }}
            </p>
            <p class="tarjeta-reporte__nota">
              IVA {{ monto(resumenCliente.ivaCompras) }}
            </p>
          </article>

          <article class="card tarjeta-reporte">
            <p class="tarjeta-reporte__rotulo">Saldo IVA</p>
            <p
              class="tarjeta-reporte__valor tabular"
              :class="{ negativo: resumenCliente.saldoIva < 0 }"
            >
              {{ monto(resumenCliente.saldoIva) }}
            </p>
            <p class="tarjeta-reporte__nota">IVA ventas menos IVA compras</p>
          </article>

          <article class="card tarjeta-reporte">
            <p class="tarjeta-reporte__rotulo">Operaciones</p>
            <p class="tarjeta-reporte__valor tabular">
              {{ resumenCliente.operaciones }}
            </p>
            <p class="tarjeta-reporte__nota">Comprobantes contabilizados</p>
          </article>
        </div>

        <article class="card bloque">
          <header class="bloque__cabecera">
            <h2 class="bloque__titulo">Detalle del período</h2>
            <span class="bloque__nota">
              {{ itemsCliente.length }}
              {{ itemsCliente.length === 1 ? 'comprobante' : 'comprobantes' }}
            </span>
          </header>

          <table v-if="itemsCliente.length" class="table">
            <thead>
              <tr>
                <th>Tipo</th>
                <th>Número</th>
                <th>Fecha</th>
                <th>Tercero</th>
                <th class="num">Neto</th>
                <th class="num">IVA</th>
                <th class="num">Total</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in itemsCliente" :key="`${item.tipo}-${item.numero}`">
                <td>
                  <span class="badge" :class="item.tipo === 'Venta' ? 'badge--strong' : ''">
                    {{ item.tipo }}
                  </span>
                </td>
                <td class="tabular">{{ item.numero }}</td>
                <td class="tabular">{{ fechaVisible(item.fecha) }}</td>
                <td>{{ item.tercero }}</td>
                <td class="num tabular">{{ monto(item.neto) }}</td>
                <td class="num tabular">{{ monto(item.iva) }}</td>
                <td class="num tabular">{{ monto(item.total) }}</td>
              </tr>
            </tbody>
          </table>
          <p v-else class="vacio">
            No hay comprobantes contabilizados en el período.
          </p>
        </article>
      </div>

      <p v-else class="vacio">No hay datos para el período elegido.</p>
    </template>

    <!-- Reportes completos del estudio -->
    <template v-else>
      <div class="pestanias" role="tablist">
        <button
          v-for="p in PESTANIAS"
          :key="p.id"
          class="pestania"
          :class="{ 'is-activa': pestania === p.id }"
          type="button"
          role="tab"
          :aria-selected="pestania === p.id"
          @click="cambiar(p.id)"
        >
          {{ p.etiqueta }}
        </button>
      </div>

      <!-- Balance -->
      <div v-if="pestania === 'balance' && balance" class="card bloque">
        <table class="table">
          <thead>
            <tr><th>Cuenta</th><th class="num">Debe</th><th class="num">Haber</th><th class="num">Saldo</th></tr>
          </thead>
          <tbody>
            <tr v-for="c in balance.cuentas" :key="c.codigo">
              <td><span class="tabular codigo">{{ c.codigo }}</span>{{ c.nombre }}</td>
              <td class="num tabular">{{ monto(c.debe) }}</td>
              <td class="num tabular">{{ monto(c.haber) }}</td>
              <td class="num tabular" :class="{ negativo: Number(c.saldo) < 0 }">{{ monto(c.saldo) }}</td>
            </tr>
          </tbody>
          <tfoot>
            <tr>
              <td>Totales</td>
              <td class="num tabular">{{ monto(balance.total_debe) }}</td>
              <td class="num tabular">{{ monto(balance.total_haber) }}</td>
              <td class="num tabular">{{ monto(balance.diferencia) }}</td>
            </tr>
          </tfoot>
        </table>
        <p v-if="balance.cuentas.length === 0" class="vacio">Sin movimientos confirmados en el período.</p>
      </div>

      <!-- Diario -->
      <div v-else-if="pestania === 'diario'" class="diario">
        <article v-for="a in diario" :key="a.numero" class="card bloque">
          <header class="asiento__head">
            <span class="tabular">Nº {{ String(a.numero).padStart(4, '0') }}</span>
            <span class="tabular">{{ fechaVisible(a.fecha) }}</span>
          </header>
          <p class="asiento__concepto">{{ a.concepto }}</p>
          <table class="table table--compacta">
            <thead><tr><th>Cuenta</th><th class="num">Debe</th><th class="num">Haber</th></tr></thead>
            <tbody>
              <tr v-for="(r, i) in a.renglones" :key="i">
                <td><span class="tabular codigo">{{ r.cuenta_codigo }}</span>{{ r.cuenta_nombre }}</td>
                <td class="num tabular">{{ Number(r.debe) ? monto(r.debe) : '—' }}</td>
                <td class="num tabular">{{ Number(r.haber) ? monto(r.haber) : '—' }}</td>
              </tr>
            </tbody>
          </table>
        </article>
        <p v-if="diario.length === 0" class="vacio">Sin asientos confirmados en el período.</p>
      </div>

      <!-- Mayor -->
      <div v-else-if="pestania === 'mayor'" class="card bloque">
        <select v-model="cuentaId" class="input select selector" aria-label="Cuenta" @change="cambiarCuenta">
          <option v-for="c in cuentas" :key="c.id" :value="c.id">{{ c.codigo }} · {{ c.nombre }}</option>
        </select>

        <template v-if="mayor">
          <p class="saldo-inicial">Saldo inicial: <strong class="tabular">{{ monto(mayor.saldo_inicial) }}</strong></p>
          <table class="table">
            <thead><tr><th>Fecha</th><th>Nº</th><th>Concepto</th><th class="num">Debe</th><th class="num">Haber</th><th class="num">Saldo</th></tr></thead>
            <tbody>
              <tr v-for="(m, i) in mayor.movimientos" :key="i">
                <td class="tabular">{{ fechaVisible(m.fecha) }}</td>
                <td class="tabular">{{ m.numero }}</td>
                <td>{{ m.concepto }}</td>
                <td class="num tabular">{{ monto(m.debe) }}</td>
                <td class="num tabular">{{ monto(m.haber) }}</td>
                <td class="num tabular">{{ monto(m.saldo) }}</td>
              </tr>
            </tbody>
          </table>
          <p class="saldo-final">Saldo final: <strong class="tabular">{{ monto(mayor.saldo_final) }}</strong></p>
        </template>
      </div>

      <!-- Libro IVA -->
      <div v-else-if="pestania === 'iva' && libro" class="iva">
        <article v-for="bloque in [{ k: 'ventas', t: 'Ventas' }, { k: 'compras', t: 'Compras' }]" :key="bloque.k" class="card bloque">
          <h2 class="bloque__titulo">{{ bloque.t }}</h2>
          <table class="table">
            <thead><tr><th>Número</th><th>Fecha</th><th>Tercero</th><th class="num">Neto</th><th class="num">IVA</th><th class="num">Total</th></tr></thead>
            <tbody>
              <tr v-for="item in (bloque.k === 'ventas' ? libro.ventas.items : libro.compras.items)" :key="item.numero">
                <td class="tabular">{{ item.numero }}</td>
                <td class="tabular">{{ fechaVisible(item.fecha) }}</td>
                <td>{{ item.tercero }}</td>
                <td class="num tabular">{{ monto(item.neto) }}</td>
                <td class="num tabular">{{ monto(item.iva) }}</td>
                <td class="num tabular">{{ monto(item.total) }}</td>
              </tr>
            </tbody>
            <tfoot>
              <tr>
                <td colspan="3">Total</td>
                <td class="num tabular">{{ monto(bloque.k === 'ventas' ? libro.ventas.neto : libro.compras.neto) }}</td>
                <td class="num tabular">{{ monto(bloque.k === 'ventas' ? libro.ventas.iva : libro.compras.iva) }}</td>
                <td class="num tabular">{{ monto(bloque.k === 'ventas' ? libro.ventas.total : libro.compras.total) }}</td>
              </tr>
            </tfoot>
          </table>
        </article>
      </div>
    </template>
  </section>
</template>

<style scoped>
.reportes { display: grid; gap: var(--space-5); }
.rango { display: flex; gap: var(--space-2); align-items: center; flex-wrap: wrap; }
.rango .input { max-width: 10rem; }
.pestanias { display: flex; gap: var(--space-1); border-bottom: 1px solid var(--color-line); }
.pestania { padding: 0.6rem var(--space-4); border: 0; border-bottom: 2px solid transparent; background: transparent; color: var(--color-text-muted); font-size: var(--text-sm); cursor: pointer; }
.pestania:hover { color: var(--color-text); }
.pestania.is-activa { border-bottom-color: var(--color-accent); color: var(--color-accent); }
.bloque { padding: var(--space-4); overflow-x: auto; }
.bloque__titulo { font-size: var(--text-lg); margin-bottom: var(--space-3); }
.num { text-align: right; white-space: nowrap; }
.codigo { margin-right: var(--space-2); color: var(--color-text-faint); font-size: var(--text-xs); }
tfoot td { font-weight: 600; border-top: 1px solid var(--color-line-strong); }
.negativo { color: var(--color-danger); }
.diario { display: grid; gap: var(--space-4); }
.asiento__head { display: flex; justify-content: space-between; font-size: var(--text-xs); color: var(--color-text-faint); }
.asiento__concepto { margin: var(--space-2) 0; font-size: var(--text-sm); }
.saldo-inicial, .saldo-final { font-size: var(--text-sm); color: var(--color-text-muted); margin: var(--space-2) 0; }
.saldo-final { text-align: right; }
.selector { max-width: 24rem; margin-bottom: var(--space-3); }
.vacio { padding: var(--space-4); color: var(--color-text-faint); font-size: var(--text-sm); }

.resumen-cliente { display: grid; gap: var(--space-4); }
.tarjetas-reporte { display: grid; grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr)); gap: var(--space-3); }
.tarjeta-reporte { display: grid; gap: var(--space-2); padding: var(--space-4); }
.tarjeta-reporte__rotulo { font-size: var(--text-xs); letter-spacing: 0.1em; text-transform: uppercase; color: var(--color-text-faint); }
.tarjeta-reporte__valor { font-family: var(--font-display); font-size: var(--text-xl); line-height: 1; }
.tarjeta-reporte__nota { font-size: var(--text-xs); color: var(--color-text-faint); }
.bloque__cabecera { display: flex; align-items: baseline; justify-content: space-between; gap: var(--space-3); margin-bottom: var(--space-3); }
.bloque__nota { font-size: var(--text-xs); color: var(--color-text-faint); }
</style>
