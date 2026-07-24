<style scoped>
  .button {
    position: relative;
    display: flex;
    cursor: pointer;
    background: none;
    border: none;
    color: white;
    font-size: 2em;
    font-weight: 600;
    transition: 0.5s;
  }

  .hub {
    background: #f7971d;
    color: black;
    padding: 0 4px;
    border-radius: 6px;
  }

  .ui {
    position: relative;
    padding: 0 4px;
  }

  .ui::before,
  .ui::after {
    content: "";
    position: absolute;
    background: radial-gradient(circle at 50% 50%, #f7471d, #f7471d00 75%);
    width: 16px;
    height: 16px;
    bottom: 3px;
    opacity: 0;
    transition: 0.5s;
  }
  .ui::before {
    left: 0px;
  }
  .ui::after {
    left: 16px;
  }

  .button:hover .ui::before,
  .button:hover .ui::after {
    opacity: 1;
  }

  .button:active .ui::before,
  .button:active .ui::after {
    opacity: 0;
  }

  .button:active {
    scale: 0.9;
    rotate: -6deg;
  }

  .hub {
    animation: wee 0.5s ease;
    transition: 0.5s;
  }

  .button:active .hub {
    animation: none;
    rotate: -6deg;
  }

  @keyframes wee {
    0% {
      rotate: -6deg;
    }
    25% {
      rotate: 16deg;
    }
    50% {
      rotate: -12deg;
    }
    75% {
      rotate: 8deg;
    }
    100% {
      rotate: 0deg;
    }
  }
</style>

<template>
  <button class="button">
    <div class="ui">UI</div>
    <div class="hub">hub</div>
  </button>
</template>
