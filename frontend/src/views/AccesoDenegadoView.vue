<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()
</script>

<template>
  <section class="denegado">
    <div class="card denegado__tarjeta">
      <span class="denegado__icono" aria-hidden="true">
        <svg viewBox="0 0 24 24" width="22" height="22" fill="none">
          <rect
            x="4.5"
            y="10"
            width="15"
            height="10"
            rx="2.5"
            stroke="currentColor"
            stroke-width="1.4"
          />
          <path
            d="M8 10V7.5a4 4 0 0 1 8 0V10"
            stroke="currentColor"
            stroke-width="1.4"
            stroke-linecap="round"
          />
          <circle cx="12" cy="15" r="1.4" fill="currentColor" />
        </svg>
      </span>

      <h1 class="denegado__titulo">Acceso restringido</h1>
      <p class="denegado__texto">
        Tu rol no tiene permiso para ver esta sección. Si necesitás acceso,
        pedile al administrador del estudio que te lo habilite.
      </p>

      <button class="btn" type="button" @click="router.replace({ name: 'dashboard' })">
        Volver al panel
      </button>
    </div>
  </section>
</template>

<style scoped>
.denegado {
  display: grid;
  place-items: center;
  min-height: 60vh;
}

.denegado__tarjeta {
  display: grid;
  justify-items: center;
  gap: var(--space-3);
  max-width: 28rem;
  padding: clamp(1.75rem, 4vw, 2.5rem);
  text-align: center;
}

.denegado__icono {
  display: grid;
  place-items: center;
  width: 3rem;
  height: 3rem;
  border: 1px solid var(--color-line-strong);
  border-radius: 999px;
  color: var(--color-warning);
  background: rgb(224 178 82 / 8%);
}

.denegado__titulo {
  font-size: var(--text-xl);
}

.denegado__texto {
  font-size: var(--text-sm);
  color: var(--color-text-muted);
}
</style>
