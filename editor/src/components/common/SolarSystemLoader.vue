<template>
  <div class="solar-system-container">
    <div class="solar-system">
      <div class="sun"></div>
      <div class="earth-orbit">
        <div class="earth">
          <div class="moon-orbit">
            <div class="moon"></div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.solar-system-container {
  perspective: 1500px;
  width: 200px;
  height: 200px;
}

.solar-system {
  position: relative;
  width: 100%;
  height: 100%;
  transform-style: preserve-3d;
  animation: rotate-center 6s linear infinite;
}

.sun {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 50px;
  height: 50px;
  background: radial-gradient(circle at 30% 30%, #fff, #ffd700, #ffa500);
  border-radius: 50%;
  transform: translate(-50%, -50%) translateZ(0);
  box-shadow: 0 0 20px #ffd700;
}

.earth-orbit {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 150px;
  height: 150px;
  border: 2px dashed rgba(255, 255, 255, 0.1);
  border-radius: 50%;
  transform: translate(-50%, -50%) translateZ(-50px);
  transform-style: preserve-3d;
}

.earth {
  position: absolute;
  top: -10px;
  left: 50%;
  width: 20px;
  height: 20px;
  background: radial-gradient(circle at 30% 30%, #4b9cd3, #1b4f72);
  border-radius: 50%;
  transform: translateX(-50%) translateZ(0);
  transform-style: preserve-3d;
}

.moon-orbit {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 40px;
  height: 40px;
  border: 1px dashed rgba(255, 255, 255, 0.1);
  border-radius: 50%;
  transform: translate(-50%, -50%) translateZ(-10px);
  animation: rotate-orbit 2s linear infinite;
  transform-style: preserve-3d;
}

.moon {
  position: absolute;
  top: -3px;
  left: 50%;
  width: 6px;
  height: 6px;
  background: radial-gradient(circle at 30% 30%, #fff, #ccc);
  border-radius: 50%;
  transform: translateX(-50%) translateZ(0);
}

@keyframes rotate-orbit {
  from { transform: translate(-50%, -50%) rotate(0deg); }
  to { transform: translate(-50%, -50%) rotate(360deg); }
}

@keyframes rotate-center {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
