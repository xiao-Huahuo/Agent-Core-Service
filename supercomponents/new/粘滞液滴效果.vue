<style scoped>
  .morph-card {
    position: relative;
    width: 180px;
    height: 220px;
    display: flex;
    align-items: center;
    justify-content: center;
    filter: url(#morphGoo);
    cursor: pointer;
  }

  /* Основные блобы формируют карточку */
  .morph-blob {
    position: absolute;
    background: #0a0a0a;
    border-radius: 50%;
    transition: all 0.6s cubic-bezier(0.34, 1.56, 0.64, 1);
  }

  .morph-blob-1 {
    width: 180px;
    height: 180px;
    top: 20px;
    left: 0;
  }

  .morph-blob-2 {
    width: 100px;
    height: 100px;
    top: -10px;
    left: 40px;
  }

  .morph-blob-3 {
    width: 80px;
    height: 80px;
    bottom: -5px;
    left: 50px;
  }

  /* При hover — блобы перестраиваются */
  .morph-card:hover .morph-blob-1 {
    border-radius: 30%;
    width: 170px;
    height: 160px;
    top: 30px;
    left: 5px;
    transform: rotate(-3deg);
  }

  .morph-card:hover .morph-blob-2 {
    width: 70px;
    height: 70px;
    top: -20px;
    left: -15px;
    transform: rotate(10deg);
  }

  .morph-card:hover .morph-blob-3 {
    width: 60px;
    height: 60px;
    bottom: -20px;
    left: 130px;
    transform: rotate(-8deg);
  }

  /* Контент */
  .morph-content {
    position: relative;
    z-index: 2;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
    color: #fff;
    transition: all 0.5s ease;
  }

  .morph-icon {
    width: 40px;
    height: 40px;
    color: rgba(255, 255, 255, 0.7);
    transition: all 0.5s ease;
  }

  .morph-icon svg {
    width: 100%;
    height: 100%;
  }

  .morph-card:hover .morph-icon {
    color: #fff;
    transform: translateY(-5px);
    filter: drop-shadow(0 0 8px rgba(255, 255, 255, 0.3));
  }

  .morph-label {
    font-family: "Segoe UI", system-ui, sans-serif;
    font-size: 13px;
    font-weight: 500;
    color: rgba(255, 255, 255, 0.4);
    letter-spacing: 3px;
    text-transform: uppercase;
    transition: all 0.5s ease;
  }

  .morph-card:hover .morph-label {
    color: rgba(255, 255, 255, 0.6);
    letter-spacing: 5px;
  }

  .morph-count {
    font-family: "Segoe UI", system-ui, sans-serif;
    font-size: 36px;
    font-weight: 300;
    color: #fff;
    transition: all 0.5s ease;
  }

  .morph-card:hover .morph-count {
    transform: scale(1.1);
    text-shadow: 0 0 20px rgba(255, 255, 255, 0.2);
  }

  /* Active — сжатие */
  .morph-card:active .morph-blob {
    transform: scale(0.92) !important;
    transition-duration: 0.15s;
  }
</style>

<template>
  <div class="morph-card">
    <div class="morph-blob morph-blob-1"></div>
    <div class="morph-blob morph-blob-2"></div>
    <div class="morph-blob morph-blob-3"></div>

    <div class="morph-content">
      <div class="morph-icon">
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.5"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <path d="M12 2L2 7l10 5 10-5-10-5z"></path>
          <path d="M2 17l10 5 10-5"></path>
          <path d="M2 12l10 5 10-5"></path>
        </svg>
      </div>
      <div class="morph-label">Layers</div>
      <div class="morph-count">24</div>
    </div>

    <svg
      xmlns="http://www.w3.org/2000/svg"
      version="1.1"
      style="display:block;width:0;height:0"
    >
      <defs>
        <filter id="morphGoo">
          <feGaussianBlur
            in="SourceGraphic"
            stdDeviation="10"
            result="blur"
          ></feGaussianBlur>
          <feColorMatrix
            in="blur"
            mode="matrix"
            values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 20 -9"
            result="goo"
          ></feColorMatrix>
          <feComposite in="SourceGraphic" in2="goo" operator="atop"></feComposite>
        </filter>
      </defs>
    </svg>
  </div>
</template>
