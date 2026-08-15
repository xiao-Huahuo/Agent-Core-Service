<style scoped>
  .card {
    width: 164px;
    height: 276px;
    background: rgb(0, 0, 0);
    border: 3px solid rgb(17, 4, 94);
    border-radius: 15px;
    position: relative;
    padding: 5px;
    display: flex;
    flex-direction: column;
    gap: 22px;
    transition: all 1s ease;
    color: antiquewhite;
  }

  .card::before {
    content: "";
    width: 10px;
    height: 10px;
    position: absolute;
    bottom: 10px;
    right: 77px;
    border-radius: 50%;
    background-color: rgb(17, 4, 94);
  }

  .card__date {
    display: flex;
    flex-direction: column;
    margin-top: 30px;
  }

  .time {
    font-size: 2em;
  }

  .popup {
    background-color: #444746;
    border-radius: 5px;
    display: flex;
    flex-direction: column;
    font-size: .8em;
    padding: 3px;
  }

  .popup .title {
    font-size: 9px;
    color: #9cbde2;
  }

  .card__date , .popup {
    opacity: 0;
    transition: all .5s ease;
  }

  .card:hover {
    transform: rotate3d(5, 5, 10, -45deg);
    box-shadow: -40px 0px 5px 10px #289FED, -80px 0px 10px 20px #9dd2f5, -120px 0px 20px 40px #374650;
    ;
  }

  .card:hover .card__date , .card:hover .popup {
    opacity: 1;
  }
</style>

<template>
  <div class="card">

    <div class="card__date">
      <span class="time">14:34</span>
      <span class="date">Mon.,21 August</span>
    </div>
      <div class="popup">
          <p class="title">Software update</p>
          <p>Postponed update</p>
      </div>

  </div>
</template>
