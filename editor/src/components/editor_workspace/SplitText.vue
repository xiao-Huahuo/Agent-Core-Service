<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { gsap } from 'gsap'

const props = withDefaults(defineProps<{
  text: string
  tag?: string
  delay?: number
  duration?: number
  ease?: string
  y?: number
  triggerOnMount?: boolean
}>(), {
  tag: 'h1',
  delay: 35,
  duration: 0.9,
  ease: 'power3.out',
  y: 40,
  triggerOnMount: true,
})

const rootRef = ref<HTMLElement | null>(null)
const chars = computed(() => props.text.split(''))

function animate() {
  const el = rootRef.value
  if (!el) return
  const spans = el.querySelectorAll<HTMLElement>('.split-char')
  if (!spans.length) return
  gsap.fromTo(
    spans,
    { opacity: 0, y: props.y },
    {
      opacity: 1,
      y: 0,
      duration: props.duration,
      ease: props.ease,
      stagger: props.delay / 1000,
      willChange: 'transform, opacity',
      force3D: true,
    },
  )
}

onMounted(async () => {
  if (props.triggerOnMount) {
    await nextTick()
    animate()
  }
})

watch(() => props.text, async () => {
  await nextTick()
  animate()
})
</script>

<template>
  <component :is="tag" ref="rootRef" class="split-text" :style="{ overflow: 'hidden', display: 'inline-block' }">
    <span
      v-for="(ch, i) in chars"
      :key="i"
      class="split-char"
      :style="{ display: 'inline-block', opacity: 0, transform: `translateY(${y}px)` }"
    >{{ ch === ' ' ? ' ' : ch }}</span>
  </component>
</template>
