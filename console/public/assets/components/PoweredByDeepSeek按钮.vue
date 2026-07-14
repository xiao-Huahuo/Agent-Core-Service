<style scoped>
  .button-container {
    display: flex;
    justify-content: center;
    gap: 20px;
    padding: 20px;
  }

  .brutalist-button {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    border: 3px solid #ffffff;
    border-radius: 12px;
    padding: 0;
    text-decoration: none;
    color: #000000;
    font-weight: bold;
    position: relative;
    box-shadow: 4px 4px 0px dodgerblue;
    overflow: hidden;
    transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    height: 130px;
    width: 130px;
    cursor: pointer;
  }

  .brutalist-button.deepseek {
    background: linear-gradient(135deg, #0a2a66, #1e3d8f, #a0c1f1, #ffffff);
    background-size: 300% 300%;
    animation: gradientShift 6s ease infinite;
  }

  @keyframes gradientShift {
    0% {
      background-position: 0% 50%;
    }
    50% {
      background-position: 100% 50%;
    }
    100% {
      background-position: 0% 50%;
    }
  }

  .brutalist-button::before {
    content: "";
    position: absolute;
    left: 50%;
    bottom: -150%;
    width: 300%;
    height: 300%;
    border-radius: 50%;
    transform: translateX(-50%) scale(0);
    transition: transform 0.6s cubic-bezier(0.19, 1, 0.22, 1);
    z-index: 1;
  }

  .brutalist-button.deepseek::before {
    background: llinear-gradient(135deg, #0a2a66, #1e3d8f, #a0c1f1, #ffffff);
    background-size: 300% 300%;
    animation: gradientShift 6s ease infinite;
  }

  .brutalist-button:hover::before {
    transform: translateX(-50%) scale(1);
  }

  .brutalist-button:hover {
    transform: translate(-4px, -4px);
    box-shadow: 8px 8px 0px dodgerblue;
  }

  .brutalist-button:active {
    transform: translate(2px, 2px);
    box-shadow: 2px 2px 0px dodgerblue;
  }

  /* Shared circular logo style */
  .deepseek-logo {
    display: flex;
    align-items: center;
    justify-content: center;
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    z-index: 2;
    width: 90px;
    height: 90px;
    background: linear-gradient(135deg, #ffffff, #a0c1f1, #1e3d8f, #0a2a66);
    background-size: 200% 200%;
    animation: gradientShift 6s ease infinite;
    border-radius: 50%;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2);
    transition: all 0.6s cubic-bezier(0.68, -0.55, 0.265, 1.55);
  }

  @keyframes gradientShift {
    0% {
      background-position: 0% 50%;
    }
    50% {
      background-position: 100% 50%;
    }
    100% {
      background-position: 0% 50%;
    }
  }

  /* Gemini icon style */
  .deepseek-icon {
    width: 54px;
    height: 54px;
    fill: dodgerblue;
    stroke: dodgerblue;
    stroke-width: 16;
    transition: all 0.6s ease-in-out;
  }

  /* Hover animations */
  @keyframes spin {
    0% {
      transform: translate(-50%, -50%) rotate(0deg);
    }
    100% {
      transform: translate(-50%, -50%) rotate(360deg);
    }
  }

  .brutalist-button:hover .deepseek-logo {
    animation: spin 5s linear infinite;
    width: 50px;
    height: 50px;
    top: 28%;
  }

  .brutalist-button:hover .deepseek-icon {
    transform: scale(0.6);
  }

  /* Button text */
  .button-text {
    display: flex;
    flex-direction: column;
    align-items: center;
    line-height: 1.3;
    transition: all 0.6s cubic-bezier(0.68, -0.55, 0.265, 1.55);
    text-align: center;
    opacity: 0;
    transform: translateY(20px);
    z-index: 2;
    position: absolute;
    bottom: 18px;
    left: 0;
    right: 0;
  }

  .button-text span:first-child {
    font-size: 13px;
    font-weight: 500;
    margin-bottom: 2px;
  }

  .button-text span:last-child {
    font-size: 16px;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: #ffffff;
  }

  .brutalist-button:hover .button-text {
    opacity: 1;
    transform: translateY(0);
  }

  @media (hover: hover) and (pointer: fine) {
    .brutalist-button:hover {
      transform: translate(-4px, -4px);
      box-shadow: 8px 8px 0px dodgerblue;
    }
  }
</style>

<template>
  <div class="button-container">
    <button class="brutalist-button deepseek">
      <div class="deepseek-logo">
        <svg
          width="22mm"
          height="297mm"
          viewBox="0 0 210 237"
          version="1.1"
          id="svg1"
          xml:space="preserve"
          xmlns:xlink="http://www.w3.org/1999/xlink"
          xmlns="http://www.w3.org/2000/svg"
        >
          <defs id="defs1"></defs>
          <g id="layer1">
            <image
              width="200.70386"
              height="174.32936"
              preserveAspectRatio="none"
              xlink:href="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAABAAAAAQACAYAAAB/HSuDAAAACXBIWXMAAAsTAAALEwEAmpwYAAAg
  AElEQVR4nOzdeZxkVXXA8R5WEQUEVFwQBdS4xwU1uIwaB3umzq2eUUsBjShqzdS51TOOGNG4tFsU
  l6hE4x41xhWXGHfFHWQTRHFXFFQkIrtsA8zpk8/tHvbpmV6q+tSr9/t+Pr8/oga63rv31auq9+4b
  AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAwsCYmfJtmxxuS7UNJ7ZeS7RLJtlGynSvZfpCyHd3s
  +hPL/y76bwUAAAAAAPOQuv6olO2nKU/61pJsv5Xsh46M+JLovxsAAAAAAMySZH+OqF09mw//N80+
  3VrvO0X//QAAAAAAYCtS11889w/+N7oaQO3EVtt3jX4dAAAAAABgBpL9KaJmC/kCYCq1r7Vavm30
  6wEAAAAAADezouP3EbUrF/zh//orAfzl0a8JAAAAAADcSFnFX9SO79WH/01XAWxorPV7Rr82AAAA
  AACwiWR/YU8//N/wdIDPRr82AAAAAAAwMjIyOu63l2yX9OMLgJRtsrHG7x/9GgEAAAAAqD3J9q7+
  fPi//iqAD0W/RgAAAAAAaq057vdNatf28wuAqbUAOn676NcKAAAAAEBtSbav9vXD/3VXAaivjn6t
  AAAAAADUUlP9sYvx4X/6CwA7Pvr1AgAAAABQS0nthMX6AqC0PPu9ol8zAAAAAAC1ktTHFvPD/3T2
  qujXDQAAAABAbUxM+DaidkbAFwC/iH7tAAAAAADUhmQ/dPE//G9Kff/o1w8AAAAAQA34kpTtp1Ff
  AIj6+ugtAAAAAGAItSZ8h7TW79hc4/duqj+i2fUnllJ2aXa9VZLsz0nZ26Xyy+h1/3nq+JPL/7aR
  /7tHnfHWTsr0q
  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
  AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
  AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
  AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
  AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
  AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
  AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
  AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
  AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
  AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAGDPDvR/Abf7yFKZF6SyAAAAAElFTkSuQmCC"
              id="image1"
              x="8.0129299"
              y="46.236866"
            ></image>
            <path
              style="fill:#000000"
              d="M 81.218878,196.11612 C 64.791364,194.9619 51.296728,190.24201 38.098909,181.03448 33.950857,178.14056 28.446577,173.38624 25.198607,169.89184 17.155755,161.23876 11.631554,150.68187 9.4001276,139.70056 6.1503127,123.70753 9.128229,109.53194 18.233752,97.650408 26.062397,87.435032 36.043803,80.95782 48.557472,77.972504 c 9.373067,-2.23608 20.536267,-2.522076 32.469763,-0.831862 0.889377,0.125968 2.695113,-0.35314 9.207637,-2.443019 8.111284,-2.602925 13.722188,-3.605828 18.913988,-3.380718 3.64692,0.158125 6.18279,1.055396 6.03748,2.136245 -0.0463,0.344206 -0.30958,0.5569 -1.18574,0.957839 -2.51633,1.151492 -4.39207,2.801108 -5.51837,4.853119 -0.5398,0.983478 -0.60737,1.277036 -0.60737,2.638775 0,1.361739 0.0676,1.655296 0.60737,2.638774 1.00083,1.823412 1.9679,2.713557 4.72132,4.345757 6.66835,3.952931 10.12132,6.599802 19.57463,15.004876 6.63417,5.89854 9.43102,8.09366 12.82665,10.06704 3.22139,1.87212 7.62676,3.77981 8.7286,3.77981 0.66156,0 0.92332,-0.086 1.1655,-0.38304 0.44705,-0.54826 2.84589,-7.09806 2.84589,-7.77043 0,-0.67703 -0.55266,-1.17563 -2.9451,-2.65699 -0.90732,-0.5618 -2.66775,-1.90247 -3.91204,-2.97926 -4.11019,-3.55687 -6.72987,-7.384235 -8.32338,-12.160517 -1.91843,-5.750136 -1.7894,-12.925639 0.32607,-18.133184 0.62325,-1.534228 1.89123,-3.846298 2.56003,-4.668044 0.87623,-1.076615 2.56122,-1.121209 3.55621,-0.09412 0.31234,0.322415 0.83729,1.450838 1.40345,3.016841 1.0834,2.996649 1.8336,4.227411 3.35253,5.500031 1.57661,1.320953 2.41053,1.774056 6.34081,3.445233 1.98572,0.844338 3.9996,1.839715 4.79542,2.370176 2.74059,1.826779 4.71618,4.446476 5.61417,7.444584 0.23839,0.795888 0.4639,1.480756 0.50114,1.521928 0.0373,0.04117 0.48463,-0.273975 0.9942,-0.700326 2.89315,-2.420679 6.3309,-4.067633 10.26331,-4.916932 1.26351,-0.272885 2.62736,-0.383839 5.95116,-0.484146 3.91308,-0.118091 4.44368,-0.170638 5.73534,-0.567994 2.28319,-0.702377 4.13905,-1.831406 7.03424,-4.279351 1.45375,-1.229173 2.8675,-2.337545 3.14166,-2.463049 0.69875,-0.319877 1.69631,-0.116251 2.52443,0.515299 1.34718,1.027402 1.56241,1.988069 1.14598,5.114993 -1.37846,10.350785 -6.13347,17.789024 -14.46706,22.630764 -4.34786,2.52606 -9.34668,4.17319 -14.61342,4.81517 -2.15582,0.26278 -2.93019,0.56508 -2.97669,1.16203 -0.0162,0.20852 -0.009,1.71979 0.0153,3.35838 0.0413,2.7478 -0.0101,3.25702 -0.66215,6.55438 -2.12351,10.73846 -5.3332,19.60205 -9.81752,27.11123 -3.16038,5.2922 -6.88059,9.87319 -12.56817,15.47622 -1.06035,1.04458 -2.71743,2.68107 -3.6824,3.63663 l -1.75448,1.73738 0.67648,0.48809 c 0.37207,0.26845 1.02929,0.59673 1.46049,0.72952 0.4312,0.13279 1.7101,0.52722 2.842,0.87653 2.38884,0.73719 7.71797,2.69464 11.00556,4.04245 2.61431,1.07179 2.94621,1.38016 3.06871,2.85116 0.10225,1.22789 -0.17106,1.9632 -1.06805,2.87342 -1.27562,1.29444 -3.38656,1.92106 -8.30223,2.46448 -5.15583,0.56997 -8.50047,0.51546 -14.76996,-0.24071 -3.8366,-0.46274 -6.13807,-1.01196 -9.63202,-2.29857 -0.1078,-0.0397 -1.078,0.54324 -2.156,1.29542 -3.58574,2.50197 -9.11291,5.5195 -12.7813,6.97788 -8.85303,3.51955 -17.75834,5.02759 -30.534667,5.17077 -3.018398,0.0338 -5.928995,0.0305 -6.467995,-0.007 z m 49.037532,-14.60244 c 0.0871,-0.0789 -0.008,-0.23017 -0.2114,-0.33623 -0.20341,-0.10606 -1.30591,-0.79807 -2.45,-1.53781 -6.41128,-4.14532 -12.41481,-9.30182 -17.80062,-15.28917 -2.64219,-2.93729 -5.08841,-5.92388 -9.63909,-11.76836 -8.154885,-10.47339 -11.691186,-14.38154 -17.192665,-19.00053 -12.677256,-10.6437 -27.182897,-16.98237 -44.33513,-19.37357 -2.860436,-0.39877 -9.375949,-0.39542 -11.994588,0.006 -3.289176,0.50442 -4.236466,0.88303 -4.9874,1.99335 -0.349245,0.51639 -0.398491,0.85472 -0.371613,2.55307 0.115781,7.31595 2.68951,17.17055 6.529354,25.00036 5.913576,12.05836 13.984313,20.93271 25.512374,28.05266 5.145897,3.17821 7.831881,4.39309 11.582721,5.23893 4.342864,0.97934 7.545272,0.92806 10.097845,-0.16171 1.786023,-0.7625 2.400683,-1.46081 2.400683,-2.72738 0,-0.74472 -0.143036,-1.0732 -1.002127,-2.30133 -2.351055,-3.36101 -3.340485,-5.67572 -3.356167,-7.85155 -0.01,-1.38256 0.317246,-1.90349 1.521634,-2.42249 0.729297,-0.31428 0.832104,-0.31702 2.260856,-0.0604 4.415639,0.79307 12.789204,5.32078 25.075313,13.55861 4.19875,2.81525 5.68102,3.65878 7.87464,4.48128 2.68215,1.00567 5.14229,1.54567 9.47182,2.07908 1.06763,0.13153 10.85183,0.0134 11.01356,-0.13297 z m 7.21521,-39.10193 c 4.45892,-1.23092 4.94831,-2.38709 2.67968,-6.33068 -4.13308,-7.18461 -11.67198,-14.39607 -16.92965,-16.19435 -4.28999,-1.4673 -8.22802,-1.17164 -10.23631,0.76853 -1.07798,1.04142 -1.29457,1.77346 -0.76036,2.57 0.60124,0.89649 1.74229,1.33233 3.93694,1.50376 2.86853,0.22407 4.03692,0.622 5.46714,1.86199 1.32467,1.14849 1.54657,1.69356 1.45577,3.57592 -0.0429,0.88952 -0.087,2.61324 -0.098,3.83048 -0.0195,2.16226 -0.005,2.24015 0.6197,3.38639 1.03424,1.89691 4.06949,4.19967 6.6341,5.03312 2.44158,0.79347 4.34294,0.79211 7.23099,-0.005 z"
              id="path1"
            ></path>
          </g>
        </svg>
      </div>
      <div class="button-text">
        <span>Powered By</span>
        <span>DeepSeek</span>
      </div>
    </button>
  </div>
</template>
