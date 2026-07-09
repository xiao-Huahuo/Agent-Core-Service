<!--
  Animated light-string background.

  Usage:
  Place this component as an absolutely positioned visual layer behind a page
  surface that needs a lightweight dynamic background. It uses only CSS
  gradients and transforms, so it does not add runtime dependencies.
-->
<template>
  <div class="light-string-background" aria-hidden="true">
    <span class="string string-a"></span>
    <span class="string string-b"></span>
    <span class="string string-c"></span>
    <span class="glow glow-a"></span>
    <span class="glow glow-b"></span>
  </div>
</template>

<style scoped>
.light-string-background {
  --light-string-bg-a: rgba(9, 10, 18, 0.96);
  --light-string-bg-b: rgba(18, 18, 30, 0.94);
  --light-string-primary-glow: rgba(66, 36, 235, 0.20);
  --light-string-accent-glow: rgba(235, 36, 99, 0.16);
  --light-string-line-primary: rgba(66, 36, 235, 0.84);
  --light-string-line-accent: rgba(235, 36, 99, 0.76);
  --light-string-drop: rgba(66, 36, 235, 0.42);
  --light-string-glow-a: rgba(66, 36, 235, 0.36);
  --light-string-glow-b: rgba(235, 36, 99, 0.28);
  position: absolute;
  inset: 0;
  overflow: hidden;
  background:
    radial-gradient(circle at 20% 18%, var(--light-string-primary-glow), transparent 34%),
    radial-gradient(circle at 76% 70%, var(--light-string-accent-glow), transparent 32%),
    linear-gradient(135deg, var(--light-string-bg-a), var(--light-string-bg-b));
  pointer-events: none;
}

:root[data-theme="light"] .light-string-background {
  --light-string-bg-a: rgba(250, 251, 255, 0.98);
  --light-string-bg-b: rgba(239, 243, 255, 0.96);
  --light-string-primary-glow: rgba(66, 36, 235, 0.12);
  --light-string-accent-glow: rgba(235, 36, 99, 0.10);
  --light-string-line-primary: rgba(66, 36, 235, 0.42);
  --light-string-line-accent: rgba(235, 36, 99, 0.34);
  --light-string-drop: rgba(66, 36, 235, 0.20);
  --light-string-glow-a: rgba(66, 36, 235, 0.18);
  --light-string-glow-b: rgba(235, 36, 99, 0.14);
}

.string,
.glow {
  position: absolute;
  display: block;
  pointer-events: none;
}

.string {
  left: -18%;
  width: 136%;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--light-string-line-primary), var(--light-string-line-accent), transparent);
  filter: drop-shadow(0 0 10px var(--light-string-drop));
  opacity: 0.66;
  transform-origin: center;
  animation: light-string-drift 9s ease-in-out infinite alternate;
}

.string-a {
  top: 24%;
  transform: rotate(-8deg);
}

.string-b {
  top: 52%;
  animation-delay: -3s;
  opacity: 0.48;
  transform: rotate(7deg);
}

.string-c {
  top: 78%;
  animation-delay: -6s;
  opacity: 0.38;
  transform: rotate(-4deg);
}

.glow {
  width: 260px;
  height: 260px;
  border-radius: 50%;
  opacity: 0.36;
  filter: blur(42px);
  animation: glow-pulse 7s ease-in-out infinite alternate;
}

.glow-a {
  top: 12%;
  right: 16%;
  background: var(--light-string-glow-a);
}

.glow-b {
  bottom: 8%;
  left: 18%;
  animation-delay: -2.5s;
  background: var(--light-string-glow-b);
}

@keyframes light-string-drift {
  from {
    translate: -20px 0;
  }
  to {
    translate: 24px 10px;
  }
}

@keyframes glow-pulse {
  from {
    scale: 0.92;
    opacity: 0.24;
  }
  to {
    scale: 1.08;
    opacity: 0.42;
  }
}
</style>
