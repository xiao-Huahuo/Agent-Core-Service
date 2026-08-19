<!--
  Smooth height transition wrapper for stateful forms.

  Usage:
  Wrap mutually exclusive form states and change `watch-key` whenever the
  visible state changes. The wrapper measures the slot's natural height,
  animates between states, and returns to `auto` after the transition.
-->
<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'

defineOptions({ name: 'FormHeightTransition' })

const props = defineProps<{
  watchKey?: string | number
}>()

const wrapper = ref<HTMLDivElement | null>(null)
const content = ref<HTMLDivElement | null>(null)
const height = ref('auto')

async function animateHeight() {
  const wrapperElement = wrapper.value
  const contentElement = content.value
  if (!wrapperElement || !contentElement) return

  const currentHeight = wrapperElement.offsetHeight
  height.value = `${currentHeight}px`
  await nextTick()
  const nextHeight = contentElement.offsetHeight

  requestAnimationFrame(() => {
    if (nextHeight === currentHeight) {
      height.value = 'auto'
      return
    }
    height.value = `${nextHeight}px`
  })
}

function finishTransition(event: TransitionEvent) {
  if (event.target === wrapper.value && event.propertyName === 'height') {
    height.value = 'auto'
  }
}

watch(
  () => props.watchKey,
  () => { void animateHeight() },
)
</script>

<template>
  <div ref="wrapper" class="form-height-transition" :style="{ height }" @transitionend="finishTransition">
    <div ref="content" class="form-height-transition__content">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.form-height-transition {
  min-width: 0;
  overflow: hidden;
  transition: height 280ms cubic-bezier(0.22, 1, 0.36, 1);
}

.form-height-transition__content {
  min-width: 0;
}
</style>
