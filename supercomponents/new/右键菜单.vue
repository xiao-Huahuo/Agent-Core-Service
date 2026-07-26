<style scoped>
  .card {
    background: #222222;
    width: 260px;
    border: 2px solid #313131;
    border-radius: 10px;
    padding: 3px 4px;

    .separator {
      width: 100%;
      border: 1px solid #444444;
      border-radius: 10px;
      margin: 5px 0px;
    }

    .list {
      color: #e9e9e9;
      list-style-type: none;
      display: flex;
      flex-direction: column;
      gap: 3px;

      .item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        transition: all 0.3s ease;
        padding: 6px 8px;
        border-radius: 5px;
        cursor: pointer;
        position: relative;
        overflow: hidden;
        user-select: none;

        svg {
          z-index: 1;
          transition: all 0.3s ease;
        }
        &:hover {
          background: #333333;
        }

        .label {
          font-weight: 400;
          transition: all 0.2s ease;
        }

        &.favorite {
          .fav-label {
            position: absolute;
            transform: translateY(-100%) translateX(-15px) scale(0.8);
            opacity: 0;
          }

          .input {
            width: 100%;
            height: 100%;
            position: absolute;
            appearance: none;
            cursor: pointer;
            z-index: 100;
          }

          .input:checked ~ .fav-label {
            transform: translateY(0);
            opacity: 1;
          }

          .input:checked ~ .label:not(.fav-label) {
            transform: translateY(110%) translateX(-6px) scale(0.8);
            opacity: 0;
          }
          .input:checked ~ svg {
            fill: #fff;
          }
        }

        &.delete {
          color: #e3616a;
          position: relative;
          &:hover {
            background: #6b2c2b;
          }

          .label {
            transform: translateY(0);
          }

          &:active {
            .label {
              opacity: 0;
              visibility: hidden;
              transform: translateY(100%) translateX(-15px) scale(0.8);
            }
            .action {
              opacity: 1;
              visibility: visible;
              transform: translateY(0);
            }

            &:before {
              animation: delete 2.5s ease-in-out forwards 0.2s;
            }
          }

          .action {
            position: absolute;
            opacity: 0;
            visibility: hidden;
            transform: translateY(-50%) translateX(-15px) scale(0.8);
          }

          &::before {
            content: "";
            position: absolute;
            background-color: #89302d;
            left: 0;
            top: 0;
            height: 100%;
          }
        }

        &.rename {
          &:has(.toogler:checked:nth-of-type(1)) {
            background-color: #333333;
            overflow: hidden;
            .label {
              opacity: 0;
              transform: translateY(100%);
            }
            > svg {
              transform: translateY(130%);
            }

            .input-container {
              transform: translateY(0);

              .icons {
                top: 50%;
              }
            }
          }

          .toogler {
            position: absolute;
            appearance: none;
            width: 100%;
            height: 100%;
          }

          .input-container {
            transform: translateY(-100%);
            width: 100%;
            position: absolute;

            .input {
              width: 75%;
              background: transparent;
              border: none;
              outline: none;
              height: 100%;
              color: #fff;
              padding: 8px 8px;
              font-size: 17px;
              z-index: 100;
            }

            .icons {
              position: absolute;
              top: -50%;
              right: 0%;
              transform: translate(-50%, -50%);
              display: flex;
              justify-content: center;
              align-items: center;
              transition: all 0.3s ease;
              gap: 8px;
              svg {
                background-color: #565656;
                border-radius: 4px;
                cursor: pointer;
                transition: all 0.3s ease;
                &:hover {
                  background-color: #757575;
                }
              }
            }
          }
        }
      }
    }
  }

  @keyframes delete {
    from {
      width: 0%;
    }

    to {
      width: 100%;
    }
  }
</style>

<template>
  <div class="card">
    <ul class="list">
      <li class="item favorite">
        <input type="checkbox" class="input" />
        <span class="label">Add favorite</span>
        <span class="label fav-label">Remove from favorite</span>
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="22"
          height="22"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.5"
          stroke-linecap="round"
          stroke-linejoin="round"
          class="lucide lucide-star"
        >
          <polygon
            points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"
          ></polygon>
        </svg>
      </li>
      <li class="item rename">
        <span class="label">Edit Name</span>
        <input class="toogler" type="checkbox" />
        <label class="input-container">
          <input class="input" type="text" />
          <div class="icons">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="22"
              height="22"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.5"
              stroke-linecap="round"
              stroke-linejoin="round"
              class="lucide lucide-check"
            >
              <path d="M20 6 9 17l-5-5"></path>
            </svg>
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="22"
              height="22"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.5"
              stroke-linecap="round"
              stroke-linejoin="round"
              class="lucide lucide-x"
            >
              <path d="M18 6 6 18"></path>
              <path d="m6 6 12 12"></path>
            </svg>
          </div>
        </label>
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="22"
          height="22"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.5"
          stroke-linecap="round"
          stroke-linejoin="round"
          class="lucide lucide-pencil"
        >
          <path
            d="M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z"
          ></path>
          <path d="m15 5 4 4"></path>
        </svg>
      </li>
    </ul>
    <div class="separator"></div>
    <ul class="list">
      <li class="item">
        <span class="label">New Deployment</span>
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="22"
          height="22"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.5"
          stroke-linecap="round"
          stroke-linejoin="round"
          class="lucide lucide-cloud-download"
        >
          <path d="M12 13v8l-4-4"></path>
          <path d="m12 21 4-4"></path>
          <path
            d="M4.393 15.269A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.436 8.284"
          ></path>
        </svg>
      </li>
      <li class="item">
        <span class="label">Duplicate</span>
        <svg
          class="lucide lucide-copy-plus"
          stroke-linejoin="round"
          stroke-linecap="round"
          stroke-width="1.5"
          stroke="currentColor"
          fill="none"
          viewBox="0 0 24 24"
          height="22"
          width="22"
          xmlns="http://www.w3.org/2000/svg"
        >
          <line y2="18" y1="12" x2="15" x1="15"></line>
          <line y2="15" y1="15" x2="18" x1="12"></line>
          <rect ry="2" rx="2" y="8" x="8" height="14" width="14"></rect>
          <path
            d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"
          ></path>
        </svg>
      </li>
      <li class="item">
        <span class="label">Analytics</span>
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="22"
          height="22"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.5"
          stroke-linecap="round"
          stroke-linejoin="round"
          class="lucide lucide-chart-spline"
        >
          <path d="M3 3v16a2 2 0 0 0 2 2h16"></path>
          <path d="M7 16c.5-2 1.5-7 4-7 2 0 2 3 4 3 2.5 0 4.5-5 5-7"></path>
        </svg>
      </li>
      <li class="item">
        <span class="label">Transfer Project</span>
        <svg
          class="lucide lucide-arrow-down-up"
          stroke-linejoin="round"
          stroke-linecap="round"
          stroke-width="1.5"
          stroke="currentColor"
          fill="none"
          viewBox="0 0 24 24"
          height="22"
          width="22"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path d="m3 16 4 4 4-4"></path>
          <path d="M7 20V4"></path>
          <path d="m21 8-4-4-4 4"></path>
          <path d="M17 4v16"></path>
        </svg>
      </li>
      <li class="item">
        <span class="label">Project Settings</span>
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="22"
          height="22"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.5"
          stroke-linecap="round"
          stroke-linejoin="round"
          class="lucide lucide-settings"
        >
          <path
            d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"
          ></path>
          <circle cx="12" cy="12" r="3"></circle>
        </svg>
      </li>
    </ul>
    <div class="separator"></div>
    <ul class="list">
      <li class="item delete">
        <span class="label">Delete Project</span>
        <span class="label action">Hold to Confirm</span>
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="22"
          height="22"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.5"
          stroke-linecap="round"
          stroke-linejoin="round"
          class="lucide lucide-trash-2"
        >
          <path d="M3 6h18"></path>
          <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path>
          <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path>
          <line x1="10" x2="10" y1="11" y2="17"></line>
          <line x1="14" x2="14" y1="11" y2="17"></line>
        </svg>
      </li>
    </ul>
  </div>
</template>
