<script setup>
defineEmits(['click'])
</script>

<template>
  <button class="Btn" @click="$emit('click')">
    <div class="sign">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M3 6h18"></path>
        <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path>
        <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path>
        <line x1="10" y1="11" x2="10" y2="17"></line>
        <line x1="14" y1="11" x2="14" y2="17"></line>
      </svg>
    </div>
    <div class="text">Clear</div>
  </button>
</template>

<style scoped>
.Btn {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  width: 29px;
  height: 29px;
  border: 1px solid rgb(255, 95, 95);
  border-radius: 50%;
  cursor: pointer;
  position: relative;
  overflow: hidden;
  transition-duration: 0.3s;
  box-shadow: 1px 1px 5px rgba(0, 0, 0, 0.199);
  background-color: transparent;
}

.sign {
  width: 100%;
  transition-duration: 0.3s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.sign svg {
  width: 13px;
  color: rgb(255, 95, 95);
}

.text {
  position: absolute;
  right: 0%;
  width: 0%;
  opacity: 0;
  color: rgb(255, 95, 95);
  font-size: 0.8em;
  font-weight: 600;
  transition-duration: 0.3s;
  white-space: nowrap;
}

.Btn:hover {
  width: 75px;
  border-radius: 40px;
  transition-duration: 0.3s;
}

.Btn:hover .sign {
  width: 30%;
  transition-duration: 0.3s;
  padding-left: 11px;
}

.Btn:hover .text {
  opacity: 1;
  width: 70%;
  transition-duration: 0.3s;
  padding-right: 7px;
}

.Btn:active {
  transform: translate(1px, 1px);
}
</style>
