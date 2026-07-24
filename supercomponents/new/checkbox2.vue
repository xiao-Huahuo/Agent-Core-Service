<style scoped>
  .creative-checkbox {
    --color-idle: #cbd5e1;
    --color-hover: #94a3b8;
    --color-active: #6366f1;
    --color-active-glow: rgba(99, 102, 241, 0.2);
    --size: 44px;
    display: inline-block;
    width: var(--size);
    height: var(--size);
    cursor: pointer;
    position: relative;
    -webkit-tap-highlight-color: transparent;
  }

  .creative-checkbox input {
    position: absolute;
    opacity: 0;
    width: 0;
    height: 0;
  }

  .checkbox-box {
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 12px;
    background: transparent;
    transition:
      background 0.3s,
      transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
  }

  .checkbox-box svg {
    width: 100%;
    height: 100%;
    overflow: visible;
  }

  .box-path {
    fill: none;
    stroke: var(--color-idle);
    stroke-width: 3.5px;
    stroke-linecap: round;
    stroke-linejoin: round;
    stroke-dasharray: 144;
    stroke-dashoffset: 0;
    transition:
      stroke-dashoffset 0.4s cubic-bezier(0.4, 0, 0.2, 1),
      stroke 0.3s,
      stroke-width 0.3s;
  }

  .check-path {
    fill: none;
    stroke: white;
    stroke-width: 4px;
    stroke-linecap: round;
    stroke-linejoin: round;
    stroke-dasharray: 25;
    stroke-dashoffset: 25;
    transition: stroke-dashoffset 0.3s cubic-bezier(0.34, 1.56, 0.64, 1) 0.15s;
  }

  .creative-checkbox:hover .box-path {
    stroke: var(--color-hover);
    stroke-width: 4px;
  }

  .creative-checkbox input:checked ~ .checkbox-box {
    background: var(--color-active);
    box-shadow: 0 0 0 6px var(--color-active-glow);
    animation: dynamic-bounce 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
  }

  .creative-checkbox input:checked ~ .checkbox-box .box-path {
    stroke: var(--color-active);
    stroke-dashoffset: 144;
    stroke-width: 0px;
  }

  .creative-checkbox input:checked ~ .checkbox-box .check-path {
    stroke-dashoffset: 0;
  }

  .creative-checkbox input:focus-visible ~ .checkbox-box {
    outline: 2px solid var(--color-active);
    outline-offset: 4px;
  }

  @keyframes dynamic-bounce {
    0% {
      transform: scale(1);
    }
    30% {
      transform: scale(0.85) rotate(-4deg);
    }
    70% {
      transform: scale(1.12) rotate(4deg);
    }
    100% {
      transform: scale(1) rotate(0deg);
    }
  }
</style>

<template>
  <label class="creative-checkbox">
    <input type="checkbox" />
    <div class="checkbox-box">
      <svg viewBox="0 0 44 44" xmlns="http://www.w3.org/2000/svg">
        <path
          class="box-path"
          d="M12,4 H32 A8,8 0 0 1 40,12 V32 A8,8 0 0 1 32,40 H12 A8,8 0 0 1 4,32 V12 A8,8 0 0 1 12,4 Z"
        ></path>
        <path class="check-path" d="M14,23 L19,28 L30,15"></path>
      </svg>
    </div>
  </label>
</template>
