<style scoped>
  .radio-inputs {
    position: relative;
    display: flex;
    border-top-left-radius: 0.5rem;
    border-top-right-radius: 0.5rem;
    background-color: #70c489;
    font-size: 14px;
    width: 90%;
    padding: 0.5rem 1.5rem 0 1.5rem;
  }

  .radio-inputs .radio input {
    display: none;
  }

  .radio-inputs .radio .name {
    display: flex;
    cursor: pointer;
    align-items: center;
    justify-content: center;
    border: none;
    transition: all 0.15s ease-in-out;
    position: relative;
    border-top-left-radius: 0.5rem;
    border-top-right-radius: 0.5rem;
  }

  .radio-inputs .radio input + .name:hover {
    color: #fff;
  }

  .radio-inputs .radio input + .name .pre-name,
  .radio-inputs .radio input + .name .pos-name {
    content: "";
    position: absolute;
    width: 10px;
    height: 10px;
    background-color: #70c489;
    bottom: 0;
    opacity: 0;
  }

  .radio-inputs .radio input + .name .pre-name {
    right: -10px;
    border-bottom-left-radius: 300px;
    box-shadow: -3px 3px 0px 3px #e8e8e8;
  }

  .radio-inputs .radio input + .name .pos-name {
    left: -10px;
    border-bottom-right-radius: 300px;
    box-shadow: 3px 3px 0px 3px #e8e8e8;
  }

  .radio-inputs .radio input:checked + .name {
    animation: name-activated;
    animation-duration: 0.1s;
    animation-fill-mode: forwards;
  }

  @keyframes name-activated {
    from {
      background-color: #70c489;
      font-weight: 400;
      cursor: pointer;
      color: white;
    }

    to {
      background-color: #e8e8e8;
      font-weight: 600;
      cursor: default;
      color: black;
    }
  }

  .radio-inputs .radio input:checked + .name .pre-name,
  .radio-inputs .radio input:checked + .name .pos-name {
    animation: name-border-activated;
    animation-duration: 0.1s;
    animation-fill-mode: forwards;
    z-index: 0;
  }

  @keyframes name-border-activated {
    from {
      opacity: 0;
    }

    to {
      opacity: 1;
    }
  }

  .radio-inputs .radio .name span:last-child {
    z-index: 1;
    padding: 0.5rem 0.8rem;
    border-top-left-radius: 0.5rem;
    border-top-right-radius: 0.5rem;
  }

  .radio-inputs .radio input:checked + .name span:last-child {
    animation: name-text-activated;
    animation-duration: 0.1s;
    animation-fill-mode: forwards;
  }

  @keyframes name-text-activated {
    from {
      background-color: #70c489;
    }

    to {
      background-color: #e8e8e8;
    }
  }

  .radio-inputs > .radio > .content {
    display: none;
  }

  .radio-inputs > label.radio > input:checked ~ div.content {
    display: block;
  }

  .radio-inputs > label.radio > input:checked ~ div.content div * {
    animation: content-activated;
    animation-duration: 1s;
    animation-fill-mode: forwards;
  }

  .content {
    background-color: #70c489;
    position: absolute;
    left: 0px;
    right: 0px;
    border-bottom-left-radius: 0.5rem;
    border-bottom-right-radius: 0.5rem;
  }

  .content > div {
    background-color: #e8e8e8;
    border-radius: 0.5rem;
    padding: 1rem;
    padding-bottom: 1.2rem;
    border: 4px solid #70c489;
    border-top-width: 0px;
  }

  @keyframes content-activated {
    from {
      opacity: 0;
    }

    to {
      opacity: 1;
    }
  }
</style>

<template>
  <div class="radio-inputs">
    <label class="radio">
      <input type="radio" name="radio" checked="" />
      <span class="name">
        <span class="pre-name"></span>
        <span class="pos-name"></span>
        <span> Tabs </span>
      </span>
      <div class="content">
        <div>
          <div>Content</div>
        </div>
      </div>
    </label>
    <label class="radio">
      <input type="radio" name="radio" />
      <span class="name">
        <span class="pre-name"></span>
        <span class="pos-name"></span>
        <span> And </span>
      </span>
      <div class="content">
        <div>
          <div>And content</div>
        </div>
      </div>
    </label>

    <label class="radio">
      <input type="radio" name="radio" />
      <span class="name">
        <span class="pre-name"></span>
        <span class="pos-name"></span>
        <span> More </span>
      </span>
      <div class="content">
        <div>
          <div>More content</div>
        </div>
      </div>
    </label>

    <label class="radio">
      <input type="radio" name="radio" />
      <span class="name">
        <span class="pre-name"></span>
        <span class="pos-name"></span>
        <span> Tabs </span>
      </span>
      <div class="content">
        <div>
          <div>And Even More content</div>
        </div>
      </div>
    </label>
  </div>
</template>
