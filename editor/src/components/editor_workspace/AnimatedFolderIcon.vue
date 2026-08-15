<!--
  Animated folder artwork used by the medium and large resource-manager tiles.

  Usage:
  Render inside the existing tile button. The parent remains responsible for
  selection, navigation, dragging, dropping, and context-menu interactions.
-->
<script setup lang="ts">
defineOptions({ name: 'AnimatedFolderIcon' })

const props = withDefaults(defineProps<{
  size: 'medium' | 'large'
  open?: boolean
}>(), {
  open: false,
})
</script>

<template>
  <span
    class="animated-folder-icon"
    :class="[`is-${props.size}`, { 'is-open': props.open }]"
    aria-hidden="true"
  >
    <span class="folder-shape">
      <span class="folder-back"></span>
      <span class="folder-papers">
        <span class="folder-paper folder-paper-1"></span>
        <span class="folder-paper folder-paper-2"></span>
        <span class="folder-paper folder-paper-3"></span>
      </span>
      <span class="folder-front"></span>
    </span>
  </span>
</template>

<style scoped>
.animated-folder-icon {
  --folder-back-1: #f7c14b;
  --folder-back-2: #e9a52f;
  --folder-front-1: #ffd970;
  --folder-front-2: #fbc548;
  --folder-edge: #d68f23;
  --folder-paper: #fdfdfb;
  --folder-paper-line: #f1f0ea;
  --folder-radius: 0.875em;
  --folder-ease: cubic-bezier(0.22, 0.61, 0.36, 1);

  position: relative;
  display: inline-block;
  width: 16em;
  flex: 0 0 auto;
  cursor: inherit;
  user-select: none;
}

.animated-folder-icon.is-medium {
  font-size: 3.25px;
}

.animated-folder-icon.is-large {
  font-size: 7px;
}

.folder-shape {
  position: relative;
  display: block;
  width: 100%;
  aspect-ratio: 5 / 4;
  transition: transform 0.45s var(--folder-ease);
}

.folder-back {
  position: absolute;
  inset: 14% 0 0;
  background: linear-gradient(135deg, var(--folder-back-1), var(--folder-back-2));
  border-radius: 0.25em var(--folder-radius) var(--folder-radius) var(--folder-radius);
  box-shadow: inset 0 0 0 1px rgb(255 255 255 / 25%);
}

.folder-back::before {
  position: absolute;
  top: -13%;
  left: 0;
  width: 46%;
  height: 16%;
  background: linear-gradient(135deg, var(--folder-back-1), var(--folder-back-2));
  border-radius: 0.375em 0.375em 0 0;
  clip-path: polygon(0 0, 82% 0, 100% 100%, 0 100%);
  content: '';
}

.folder-papers {
  position: absolute;
  z-index: 2;
  inset: 6% 8% 12%;
  display: block;
}

.folder-paper {
  position: absolute;
  bottom: 0;
  left: 50%;
  width: 86%;
  height: 78%;
  overflow: hidden;
  translate: -50% 0;
  background: var(--folder-paper);
  border-radius: 0.375em;
  box-shadow: 0 0.25em 0.875em rgb(60 40 10 / 12%);
  transition:
    transform 0.45s var(--folder-ease),
    bottom 0.45s var(--folder-ease);
}

.folder-paper::before,
.folder-paper::after {
  position: absolute;
  right: 24%;
  left: 14%;
  height: 6%;
  background: var(--folder-paper-line);
  border-radius: 0.2em;
  content: '';
}

.folder-paper::before {
  top: 22%;
}

.folder-paper::after {
  top: 40%;
  right: 40%;
}

.folder-paper-1 {
  width: 78%;
  height: 70%;
  background: #f6f4ee;
}

.folder-paper-2 {
  width: 82%;
  height: 74%;
  background: #fbfaf6;
}

.folder-paper-3 {
  width: 86%;
}

.folder-front {
  position: absolute;
  z-index: 3;
  inset: 38% 0 0;
  background: linear-gradient(150deg, var(--folder-front-1), var(--folder-front-2));
  border-radius: var(--folder-radius);
  box-shadow:
    inset 0 1px 0 rgb(255 255 255 / 55%),
    0 -1px 0 var(--folder-edge),
    0 0.875em 1.375em -0.75em rgb(120 80 10 / 35%);
  transform-origin: bottom center;
  transition: transform 0.45s var(--folder-ease);
}

.folder-front::after {
  position: absolute;
  inset: 0;
  background: linear-gradient(120deg, rgb(255 255 255 / 35%) 0%, transparent 45%);
  border-radius: var(--folder-radius);
  content: '';
  pointer-events: none;
}

@media (hover: hover) {
  .animated-folder-icon:hover .folder-shape {
    transform: translateY(-0.375em);
  }

  .animated-folder-icon:hover .folder-front {
    transform: rotateX(-32deg);
  }

  .animated-folder-icon:hover .folder-paper {
    transform: translateY(-26%);
  }

  .animated-folder-icon:hover .folder-paper-1 {
    transform: translate(-26%, -18%) rotate(-7deg);
  }

  .animated-folder-icon:hover .folder-paper-2 {
    transform: translate(22%, -22%) rotate(6deg);
  }
}

.animated-folder-icon:active .folder-shape {
  transform: translateY(-0.125em) scale(0.99);
}

.animated-folder-icon.is-open .folder-shape {
  transform: translateY(-0.375em);
}

.animated-folder-icon.is-open .folder-front {
  transform: rotateX(-32deg);
}

.animated-folder-icon.is-open .folder-paper {
  transform: translateY(-26%);
}

.animated-folder-icon.is-open .folder-paper-1 {
  transform: translate(-26%, -18%) rotate(-7deg);
}

.animated-folder-icon.is-open .folder-paper-2 {
  transform: translate(22%, -22%) rotate(6deg);
}

@media (prefers-reduced-motion: reduce) {
  .folder-shape,
  .folder-front,
  .folder-paper {
    transition: none;
  }
}
</style>
