<!--
  Shared physical theme toggle.

  Usage:
  Place in compact navigation or appearance settings. The owner supplies the
  resolved dark state and handles the toggle through the persisted settings store.
-->
<script setup lang="ts">
import { useId } from 'vue'

defineOptions({ name: 'ThemeToggleButton' })

defineProps<{
  dark: boolean
}>()

defineEmits<{
  toggle: []
}>()

const maskId = `theme-loader-${useId().replace(/[^a-zA-Z0-9_-]/gu, '')}`
const maskUrl = `url(#${maskId})`
</script>

<template>
  <button
    class="theme-toggle-button"
    :class="{ dark }"
    type="button"
    :title="dark ? '切换为浅色主题' : '切换为深色主题'"
    :aria-label="dark ? '切换为浅色主题' : '切换为深色主题'"
    :aria-pressed="dark"
    @click="$emit('toggle')"
  >
    <span class="theme-toggle-face" aria-hidden="true">
      <span v-if="!dark" class="theme-loader">
        <svg width="100" height="100" viewBox="0 0 100 100">
          <defs>
            <mask :id="maskId" class="theme-loader-mask">
              <polygon points="0,0 100,0 100,100 0,100" fill="black" />
              <polygon points="25,25 75,25 50,75" fill="white" />
              <polygon points="50,25 75,75 25,75" fill="white" />
              <polygon v-for="index in 4" :key="index" points="35,35 65,35 50,65" fill="white" />
            </mask>
          </defs>
        </svg>
        <span
          class="theme-loader-box"
          :style="{ mask: maskUrl, WebkitMask: maskUrl }"
        ></span>
      </span>
      <span v-else class="theme-dark-loader"></span>
    </span>
  </button>
</template>

<style scoped>
.theme-toggle-button {
  position: relative;
  display: inline-grid;
  place-items: center;
  flex: 0 0 36px;
  width: 36px;
  height: 36px;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: var(--color-text);
  cursor: pointer;
}

.theme-toggle-button::before {
  position: absolute;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #08090b;
  content: '';
  opacity: 1;
}

.theme-toggle-face {
  position: relative;
  z-index: 1;
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: #08090b;
  box-shadow:
    0 5px 9px -4px rgba(0, 0, 0, 0.58),
    inset 0 -2px 3px -1px rgba(0, 0, 0, 0.72),
    inset 0 2px 2px -1px rgba(255, 255, 255, 0.2),
    inset 0 0 0 1px rgba(255, 255, 255, 0.1);
  transition:
    transform 180ms cubic-bezier(0.23, 1, 0.32, 1),
    box-shadow 180ms cubic-bezier(0.23, 1, 0.32, 1),
    background var(--transition-fast);
}

.theme-loader {
  --color-one: #ffbf48;
  --color-two: #be4a1d;
  --color-three: #ffbf4780;
  --color-four: #bf4a1d80;
  --color-five: #ffbf4740;
  position: absolute;
  top: 50%;
  left: 50%;
  width: 100px;
  height: 100px;
  border-radius: 50%;
  box-shadow:
    0 0 25px var(--color-three),
    0 20px 50px var(--color-four);
  transform: translate(-50%, -50%) scale(0.26);
  animation: theme-loader-colorize 6s ease-in-out infinite;
}

.theme-loader::before {
  position: absolute;
  inset: 0;
  border-top: 1px solid var(--color-one);
  border-bottom: 1px solid var(--color-two);
  border-radius: 50%;
  background: linear-gradient(180deg, var(--color-five), var(--color-four));
  box-shadow:
    inset 0 10px 10px var(--color-three),
    inset 0 -10px 10px var(--color-four);
  content: '';
}

.theme-loader svg {
  position: absolute;
  inset: 0;
}

.theme-loader-box {
  display: block;
  width: 100px;
  height: 100px;
  background: linear-gradient(180deg, var(--color-one) 30%, var(--color-two) 70%);
}

.theme-loader-mask {
  filter: contrast(15);
  animation: theme-loader-roundness 1s linear infinite;
}

.theme-loader-mask polygon {
  filter: blur(7px);
}

.theme-loader-mask polygon:nth-child(1) {
  transform: rotate(90deg);
  transform-origin: 75% 25%;
}

.theme-loader-mask polygon:nth-child(2) {
  transform-origin: 50% 50%;
  animation: theme-loader-rotation 2s linear infinite reverse;
}

.theme-loader-mask polygon:nth-child(3) {
  transform-origin: 50% 60%;
  animation: theme-loader-rotation 2s linear infinite;
  animation-delay: -0.67s;
}

.theme-loader-mask polygon:nth-child(4),
.theme-loader-mask polygon:nth-child(5) {
  transform-origin: 40% 40%;
  animation: theme-loader-rotation 2s linear infinite reverse;
}

.theme-loader-mask polygon:nth-child(5) {
  animation-delay: -1s;
}

.theme-loader-mask polygon:nth-child(6),
.theme-loader-mask polygon:nth-child(7) {
  transform-origin: 60% 40%;
  animation: theme-loader-rotation 2s linear infinite;
}

.theme-loader-mask polygon:nth-child(7) {
  animation-delay: -1.33s;
}

@keyframes theme-loader-rotation {
  to { transform: rotate(360deg); }
}

@keyframes theme-loader-roundness {
  0%, 60%, 100% { filter: contrast(15); }
  20%, 40% { filter: contrast(3); }
}

@keyframes theme-loader-colorize {
  0%, 100% { filter: hue-rotate(0deg); }
  20% { filter: hue-rotate(-30deg); }
  40% { filter: hue-rotate(-60deg); }
  60% { filter: hue-rotate(-90deg); }
  80% { filter: hue-rotate(-45deg); }
}

.theme-dark-loader {
  position: absolute;
  inset: 4px;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  transform: rotate(90deg);
  animation: theme-dark-loader-rotate 2s linear infinite;
}

.theme-dark-loader::before,
.theme-dark-loader::after {
  position: absolute;
  inset: 0;
  border-radius: inherit;
  content: '';
}

.theme-dark-loader::before {
  box-shadow:
    inset 0 2px 4px #fff,
    inset 0 4px 6px #ad5fff,
    inset 0 12px 12px #471eec;
}

.theme-dark-loader::after {
  box-shadow:
    inset 0 2px 4px #fff,
    inset 0 4px 4px #d60a47,
    inset 0 9px 12px #311e80;
  opacity: 0;
  animation: theme-dark-loader-phase 2s ease-in-out infinite;
}

@keyframes theme-dark-loader-rotate {
  to { transform: rotate(450deg); }
}

@keyframes theme-dark-loader-phase {
  50% { opacity: 1; }
}

.theme-toggle-button:hover .theme-toggle-face,
.theme-toggle-button:focus-visible .theme-toggle-face {
  box-shadow:
    0 6px 10px -4px rgba(0, 0, 0, 0.62),
    inset 0 -2px 3px -1px rgba(0, 0, 0, 0.72),
    inset 0 2px 3px -1px rgba(255, 255, 255, 0.24),
    inset 0 0 0 1px rgba(246, 199, 68, 0.18);
}

.theme-toggle-button:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 1px;
}

.theme-toggle-button:active .theme-toggle-face {
  transform: translateY(1px) scale(0.985);
  box-shadow:
    0 4px 7px -4px rgba(0, 0, 0, 0.4),
    inset 0 -2px 4px rgba(255, 255, 255, 0.22),
    inset 0 2px 4px rgba(0, 0, 0, 0.18);
}

@media (prefers-reduced-motion: reduce) {
  .theme-toggle-face {
    transition-duration: 80ms;
  }

  .theme-loader {
    animation-duration: 12s;
  }

  .theme-loader-mask,
  .theme-loader-mask polygon {
    animation: none;
  }

  .theme-dark-loader {
    animation: none;
  }

  .theme-dark-loader::after {
    opacity: 0.35;
    animation: none;
  }
}
</style>
