<script setup lang="ts">
withDefaults(
  defineProps<{
    eyebrow?: string
    title: string
    subtitle?: string
    showSub?: boolean
  }>(),
  { showSub: true },
)
</script>

<template>
  <header class="page-header">
    <div class="page-header__titles">
      <p v-if="eyebrow" class="eyebrow">{{ eyebrow }}</p>
      <h1 class="page-header__title">{{ title }}</h1>
      <p v-if="showSub && (subtitle || $slots.sub)" class="page-header__sub">
        <slot name="sub">{{ subtitle }}</slot>
      </p>
    </div>

    <div v-if="$slots.actions" class="page-header__actions">
      <slot name="actions" />
    </div>
  </header>
</template>

<style scoped>
.page-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--space-4);
  flex-wrap: wrap;
}

.page-header__titles {
  display: grid;
  gap: var(--space-2);
  max-width: 65ch;
}

.page-header__title {
  font-size: var(--text-2xl);
}

.page-header__sub {
  font-size: var(--text-sm);
  color: var(--color-text-muted);
}

.page-header__actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}
</style>
