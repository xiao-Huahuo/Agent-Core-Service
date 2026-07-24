<style scoped>
  .theme-switch {
    position: relative;
    display: inline-block;
    width: 90px;
    height: 90px;
    cursor: pointer;
    border-radius: 50%;
    filter: drop-shadow(0 10px 20px rgba(0, 0, 0, 0.15));
    -webkit-tap-highlight-color: transparent;
  }

  .theme-switch input {
    opacity: 0;
    width: 0;
    height: 0;
    position: absolute;
  }

  .switch-bg {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    border-radius: 50%;
    overflow: hidden;
    border: 4px solid #ffffff;
    box-shadow: inset 0 6px 12px rgba(0, 0, 0, 0.3);
    background: linear-gradient(180deg, #5ab5e6 0%, #aee0ff 100%);
    z-index: 1;
    transition: border-color 0.8s ease;
  }

  .switch-bg::before {
    content: "";
    position: absolute;
    inset: 0;
    background: linear-gradient(180deg, #0b1325 0%, #1a2845 100%);
    opacity: 0;
    transition: opacity 0.8s ease;
    z-index: -1;
  }

  .sky-vault {
    position: absolute;
    width: 100%;
    height: 200%;
    top: 0;
    left: 0;
    transform-origin: 50% 50%;
    transition: transform 0.9s cubic-bezier(0.5, 0.1, 0.3, 1.2);
    z-index: 2;
  }

  .sun,
  .moon {
    position: absolute;
    width: 28px;
    height: 28px;
    left: calc(50% - 14px);
    border-radius: 50%;
  }

  .sun {
    top: 12px;
    background: linear-gradient(145deg, #fffcf0, #ffd300);
    box-shadow:
      0 0 15px rgba(255, 211, 0, 0.6),
      inset -2px -2px 6px rgba(0, 0, 0, 0.1);
  }

  .moon {
    bottom: 12px;
    background: linear-gradient(145deg, #e2e2e5, #8a8e94);
    box-shadow:
      0 0 15px rgba(255, 255, 255, 0.4),
      inset -2px -2px 6px rgba(0, 0, 0, 0.3);
    transform: rotate(180deg);
  }

  .craters {
    position: absolute;
    width: 100%;
    height: 100%;
  }
  .crater {
    position: absolute;
    background: #7a7e85;
    border-radius: 50%;
    box-shadow:
      inset 1px 1px 2px rgba(0, 0, 0, 0.4),
      inset -1px -1px 2px rgba(255, 255, 255, 0.8);
  }
  .crater-1 {
    width: 8px;
    height: 8px;
    top: 6px;
    left: 6px;
  }
  .crater-2 {
    width: 5px;
    height: 5px;
    top: 16px;
    left: 5px;
  }
  .crater-3 {
    width: 6px;
    height: 6px;
    top: 15px;
    left: 16px;
  }

  .sky-clouds {
    position: absolute;
    width: 100%;
    height: 100%;
    transition: 0.8s ease;
    opacity: 1;
    z-index: 1;
  }
  .cloud {
    position: absolute;
    background: white;
    border-radius: 20px;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  }
  .cloud-1 {
    width: 32px;
    height: 12px;
    top: 32px;
    left: -8px;
  }
  .cloud-1::before {
    content: "";
    position: absolute;
    width: 16px;
    height: 16px;
    background: white;
    border-radius: 50%;
    top: -7px;
    left: 8px;
  }
  .cloud-2 {
    width: 26px;
    height: 10px;
    top: 50px;
    right: -6px;
  }
  .cloud-2::before {
    content: "";
    position: absolute;
    width: 14px;
    height: 14px;
    background: white;
    border-radius: 50%;
    top: -6px;
    left: 6px;
  }

  .sky-stars {
    position: absolute;
    width: 100%;
    height: 100%;
    transition: 0.8s ease;
    opacity: 0;
    transform: translateY(-15px);
    z-index: 1;
  }
  .star {
    position: absolute;
    background: white;
    border-radius: 50%;
    box-shadow: 0 0 3px white;
  }
  .star-1 {
    width: 2px;
    height: 2px;
    top: 18px;
    left: 18px;
  }
  .star-2 {
    width: 3px;
    height: 3px;
    top: 28px;
    left: 60px;
  }
  .star-3 {
    width: 2px;
    height: 2px;
    top: 45px;
    left: 22px;
  }
  .star-4 {
    width: 1.5px;
    height: 1.5px;
    top: 18px;
    left: 45px;
  }

  .landscape {
    position: absolute;
    bottom: 0;
    left: 0;
    width: 100%;
    height: 50%;
    z-index: 3;
    pointer-events: none;
  }

  .mountain {
    position: absolute;
    bottom: 12px;
    width: 0;
    height: 0;
    border-left: 24px solid transparent;
    border-right: 24px solid transparent;
    transition: border-bottom-color 0.8s ease;
  }
  .mountain-1 {
    left: -8px;
    border-bottom: 42px solid #4ca382;
  }
  .mountain-2 {
    right: -8px;
    border-bottom: 32px solid #65b899;
  }

  .terrain {
    position: absolute;
    bottom: -20px;
    left: -15px;
    width: 120px;
    height: 40px;
    background: #348e6a;
    border-radius: 50%;
    transition: background 0.8s ease;
  }

  .tree {
    position: absolute;
    width: 18px;
    height: 26px;
    filter: drop-shadow(1px 2px 1px rgba(0, 0, 0, 0.25));
    z-index: 4;
  }
  .tree::before {
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 85%;
    background: linear-gradient(90deg, #3aa673 0%, #236b47 50%, #15452d 100%);
    clip-path: polygon(
      50% 0%,
      80% 35%,
      60% 35%,
      90% 70%,
      65% 70%,
      100% 100%,
      0% 100%,
      35% 70%,
      10% 70%,
      40% 35%,
      20% 35%
    );
    transition: background 0.8s ease;
  }
  .tree::after {
    content: "";
    position: absolute;
    bottom: 0;
    left: 40%;
    width: 20%;
    height: 15%;
    background: linear-gradient(90deg, #704629 0%, #4a2d1a 100%);
    transition: background 0.8s ease;
    border-radius: 1px;
  }

  .tree-1 {
    left: 14px;
    bottom: 12px;
    transform: scale(0.85);
  }
  .tree-2 {
    right: 18px;
    bottom: 14px;
    transform: scale(1.05);
  }
  .tree-3 {
    left: 32px;
    bottom: 7px;
    transform: scale(0.65);
    z-index: 5;
  }
  .tree-3::before {
    background: linear-gradient(90deg, #2d8a5c 0%, #1a5436 50%, #0f3621 100%);
  }

  .theme-switch input:checked + .switch-bg {
    border-color: #2a3b5c;
  }
  .theme-switch input:checked + .switch-bg::before {
    opacity: 1;
  }

  .theme-switch input:checked + .switch-bg .sky-vault {
    transform: rotate(180deg);
  }
  .theme-switch input:checked + .switch-bg .sky-clouds {
    opacity: 0;
    transform: translateY(15px);
  }
  .theme-switch input:checked + .switch-bg .sky-stars {
    opacity: 1;
    transform: translateY(0);
  }

  .theme-switch input:checked + .switch-bg .landscape .mountain-1 {
    border-bottom-color: #162238;
  }
  .theme-switch input:checked + .switch-bg .landscape .mountain-2 {
    border-bottom-color: #1e2c45;
  }
  .theme-switch input:checked + .switch-bg .landscape .terrain {
    background: #0d1526;
  }

  .theme-switch input:checked + .switch-bg .landscape .tree::before {
    background: linear-gradient(90deg, #1a283b 0%, #101a29 50%, #070c14 100%);
  }
  .theme-switch input:checked + .switch-bg .landscape .tree-3::before {
    background: linear-gradient(90deg, #131e2e 0%, #0b121f 50%, #05080f 100%);
  }
  .theme-switch input:checked + .switch-bg .landscape .tree::after {
    background: linear-gradient(90deg, #111a26 0%, #080d14 100%);
  }
</style>

<template>
  <label class="theme-switch" aria-label="Toggle Theme">
    <input type="checkbox" />
    <div class="switch-bg">
      <div class="sky-stars">
        <div class="star star-1"></div>
        <div class="star star-2"></div>
        <div class="star star-3"></div>
        <div class="star star-4"></div>
      </div>

      <div class="sky-clouds">
        <div class="cloud cloud-1"></div>
        <div class="cloud cloud-2"></div>
      </div>

      <div class="sky-vault">
        <div class="sun"></div>
        <div class="moon">
          <div class="craters">
            <div class="crater crater-1"></div>
            <div class="crater crater-2"></div>
            <div class="crater crater-3"></div>
          </div>
        </div>
      </div>

      <div class="landscape">
        <div class="mountain mountain-1"></div>
        <div class="mountain mountain-2"></div>
        <div class="terrain"></div>
        <div class="tree tree-1"></div>
        <div class="tree tree-2"></div>
        <div class="tree tree-3"></div>
      </div>
    </div>
  </label>
</template>
