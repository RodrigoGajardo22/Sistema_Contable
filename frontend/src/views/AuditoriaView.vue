<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { ApiError } from '@/api/client'
import { auditoriaApi, type EntradaAuditoria } from '@/api/panel'
import { usuariosApi } from '@/api/usuarios'
import type { Usuario } from '@/api/tipos'
import EmptyState from '@/components/ui/EmptyState.vue'
import PageHeader from '@/components/ui/PageHeader.vue'

const entradas = ref<EntradaAuditoria[]>([])
const usuarios = ref<Usuario[]>([])
const cargando = ref(true)
const error = ref('')
const entidad = ref('')
const accion = ref('')
const usuario = ref<number | null>(null)
const desde = ref('')
const hasta = ref('')

const fechaHora = new Intl.DateTimeFormat('es-AR', {
  dateStyle: 'medium',
  timeStyle: 'short',
  hour12: false,
})

async function cargar() {
  cargando.value = true
  error.value = ''
  try {
    const respuesta = await auditoriaApi.listar({
      entidad: entidad.value || undefined,
      accion: accion.value || undefined,
      usuario: usuario.value ?? undefined,
      desde: desde.value || undefined,
      hasta: hasta.value || undefined,
    })
    entradas.value = respuesta.datos
  } catch (e) {
    error.value = e instanceof ApiError ? e.mensaje : 'No pudimos cargar la auditoría.'
  } finally {
    cargando.value = false
  }
}

onMounted(async () => {
  try {
    usuarios.value = (await usuariosApi.listar()).datos
  } catch {
    usuarios.value = []
  }
  await cargar()
})

function resumen(entrada: EntradaAuditoria): string {
  const datos = entrada.despues ?? entrada.antes
  if (!datos) return '—'
  return Object.entries(datos)
    .slice(0, 3)
    .map(([clave, valor]) => `${clave}: ${String(valor)}`)
    .join(' · ')
}
</script>

<template>
  <section class="auditoria">
    <PageHeader
      eyebrow="Control"
      title="Auditoría"
      subtitle="Quién hizo qué y cuándo. Las últimas 300 operaciones."
    />

    <div class="toolbar">
      <select v-model="entidad" class="input select" aria-label="Entidad" @change="cargar">
        <option value="">Todas las entidades</option>
        <option value="asiento">Asientos</option>
        <option value="comprobante">Comprobantes</option>
        <option value="usuario">Usuarios</option>
      </select>
      <select v-model="accion" class="input select" aria-label="Acción" @change="cargar">
        <option value="">Todas las acciones</option>
        <option value="crear">Crear</option>
        <option value="confirmar">Confirmar</option>
        <option value="contabilizar">Contabilizar</option>
        <option value="anular">Anular</option>
        <option value="desactivar">Desactivar</option>
      </select>
      <select v-model="usuario" class="input select" aria-label="Usuario" @change="cargar">
        <option :value="null">Todos los usuarios</option>
        <option v-for="u in usuarios" :key="u.id" :value="u.id">{{ u.nombre }}</option>
      </select>
      <input v-model="desde" class="input" type="date" aria-label="Desde" @change="cargar" />
      <input v-model="hasta" class="input" type="date" aria-label="Hasta" @change="cargar" />
    </div>

    <div v-if="error" class="alert alert--error" role="alert">{{ error }}</div>
    <EmptyState v-if="cargando" loading compact>Cargando auditoría…</EmptyState>

    <div v-else class="card bloque">
      <table class="table">
        <thead>
          <tr><th>Fecha</th><th>Usuario</th><th>Acción</th><th>Entidad</th><th>Detalle</th></tr>
        </thead>
        <tbody>
          <tr v-for="e in entradas" :key="e.id">
            <td class="tabular">{{ e.fecha ? fechaHora.format(new Date(e.fecha)) : '—' }}</td>
            <td>{{ e.usuario }}</td>
            <td><span class="badge">{{ e.accion }}</span></td>
            <td>{{ e.entidad }}<span v-if="e.entidad_id" class="tabular id"> #{{ e.entidad_id }}</span></td>
            <td class="detalle">{{ resumen(e) }}</td>
          </tr>
        </tbody>
      </table>
      <p v-if="entradas.length === 0" class="vacio">Sin registros para los filtros elegidos.</p>
    </div>
  </section>
</template>

<style scoped>
.auditoria { display: grid; gap: var(--space-5); }
.toolbar .select { max-width: 14rem; }
.toolbar .input[type='date'] { max-width: 10rem; }
.bloque { overflow-x: auto; }
.tabular { white-space: nowrap; }
.id { color: var(--color-text-faint); }
.detalle { font-size: var(--text-xs); color: var(--color-text-muted); max-width: 30rem; }
.vacio { padding: var(--space-4); color: var(--color-text-faint); font-size: var(--text-sm); }
</style>
