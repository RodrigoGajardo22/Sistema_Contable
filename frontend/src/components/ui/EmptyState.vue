<script setup lang="ts">
withDefaults(
  defineProps<{
    loading?: boolean
    compact?: boolean
  }>(),
  { loading: false, compact: false },
)
</script>

<template>
  <div
    class="estado"
    :class="{ 'estado--compact': compact }"
    :aria-busy="loading ? 'true' : undefined"
  >
    <span v-if="loading" class="estado__punto" aria-hidden="true"></span>
    <slot />
  </div>
</template>
