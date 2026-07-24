<style scoped>
  .button {
    position: relative;
    padding: 14px 42px;
    font-size: 18px;
    font-weight: bold;
    color: white;
    border: none;
    border-radius: 50px;
    cursor: pointer;
    overflow: hidden;
    background: transparent;
    display: inline-block;
    z-index: 1;
    transition: transform 0.2s ease;
  }

  .button span {
    position: relative;
    z-index: 15;
  }

  .button:active {
    transform: scale(0.96);
  }

  .button::before {
    content: "";
    background: rgb(0 0 0);
    border-radius: inherit;
    height: calc(100% - 4px);
    width: calc(100% - 4px);
    position: absolute;
    top: 2px;
    left: 2px;
    z-index: 12;
    opacity: 0;
    transform: scale(0.95);
    transition: all 0.5s ease;
  }

  .button:hover::before {
    opacity: 1;
    transform: scale(1);
  }

  .bubble-layer {
    position: absolute;
    width: 150px;
    height: 150px;
    border-radius: 50%;
    filter: blur(10px);
    z-index: 0;
  }

  .bubble-1 {
    background: #ff007f;
    top: -20%;
    left: -10%;
    animation: moveUpRight 6s ease-in-out infinite;
  }
  .bubble-2 {
    background: #ff6a00;
    top: 0%;
    left: 10%;
    animation: moveDownLeft 5s ease-in-out infinite;
    animation-delay: 1s;
  }
  .bubble-3 {
    background: #ffcc00;
    top: 20%;
    left: 50%;
    animation: moveRight 4s ease-in-out infinite;
    animation-delay: 2s;
  }
  .bubble-4 {
    background: #00fff0;
    top: -20%;
    left: 70%;
    animation: moveUpLeft 7s ease-in-out infinite;
    animation-delay: 3s;
  }
  .bubble-5 {
    background: #9d00ff;
    top: 30%;
    left: -10%;
    animation: moveDownRight 3s ease-in-out infinite;
    animation-delay: 4s;
  }
  .bubble-6 {
    background: #ff007f;
    top: -10%;
    left: 30%;
    animation: moveLeft 8s ease-in-out infinite;
    animation-delay: 0.5s;
  }
  .bubble-7 {
    background: #ff6a00;
    top: 40%;
    left: 60%;
    animation: moveUp 6s ease-in-out infinite;
    animation-delay: 1.5s;
  }

  @keyframes moveUpRight {
    0% {
      transform: translate(0, 0);
    }
    25% {
      transform: translate(100%, -100%);
    }
    50% {
      transform: translate(-50%, 50%);
    }
    75% {
      transform: translate(50%, -50%);
    }
    100% {
      transform: translate(0, 0);
    }
  }
  @keyframes moveDownLeft {
    0% {
      transform: translate(0, 0);
    }
    25% {
      transform: translate(-100%, 100%);
    }
    50% {
      transform: translate(50%, -50%);
    }
    75% {
      transform: translate(-50%, 50%);
    }
    100% {
      transform: translate(0, 0);
    }
  }
  @keyframes moveRight {
    0% {
      transform: translate(0, 0);
    }
    25% {
      transform: translate(100%, 0);
    }
    50% {
      transform: translate(-100%, 50%);
    }
    75% {
      transform: translate(50%, -50%);
    }
    100% {
      transform: translate(0, 0);
    }
  }
  @keyframes moveUpLeft {
    0% {
      transform: translate(0, 0);
    }
    25% {
      transform: translate(-100%, -100%);
    }
    50% {
      transform: translate(50%, 50%);
    }
    75% {
      transform: translate(-50%, -50%);
    }
    100% {
      transform: translate(0, 0);
    }
  }
  @keyframes moveDownRight {
    0% {
      transform: translate(0, 0);
    }
    25% {
      transform: translate(100%, 100%);
    }
    50% {
      transform: translate(-50%, -50%);
    }
    75% {
      transform: translate(50%, 50%);
    }
    100% {
      transform: translate(0, 0);
    }
  }
  @keyframes moveLeft {
    0% {
      transform: translate(0, 0);
    }
    25% {
      transform: translate(-100%, 0);
    }
    50% {
      transform: translate(100%, -50%);
    }
    75% {
      transform: translate(-50%, 50%);
    }
    100% {
      transform: translate(0, 0);
    }
  }
  @keyframes moveUp {
    0% {
      transform: translate(0, 0);
    }
    25% {
      transform: translate(0, -100%);
    }
    50% {
      transform: translate(50%, 50%);
    }
    75% {
      transform: translate(-50%, -50%);
    }
    100% {
      transform: translate(0, 0);
    }
  }
</style>

<template>
  <button class="button">
    <div class="bubble-layer bubble-1"></div>
    <div class="bubble-layer bubble-2"></div>
    <div class="bubble-layer bubble-3"></div>
    <div class="bubble-layer bubble-4"></div>
    <div class="bubble-layer bubble-5"></div>
    <div class="bubble-layer bubble-6"></div>
    <div class="bubble-layer bubble-7"></div>
    <span>Animated Buttons</span>
  </button>
</template>
