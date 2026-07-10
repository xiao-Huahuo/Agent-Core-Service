<template>
  <div class="w-full py-4">
    <div class="relative max-w-xl w-full mx-auto">
      <div class="relative flex flex-col bg-black/5">
        <textarea
          class="w-full min-h-[52px] max-h-[200px] rounded-xl rounded-b-none px-4 py-3 bg-black text-white placeholder:text-white/70 border-0 outline-none resize-none focus:ring-0 focus:outline-none leading-[1.2]"
          placeholder="Search the web..."
          id="ai-input"
        ></textarea>

        <div class="h-12 bg-black rounded-b-xl">
          <div class="absolute left-3 bottom-3 flex items-center gap-2">
            <label
              class="cursor-pointer rounded-lg p-2 bg-white/5 hover:bg-white/10"
            >
              <input class="hidden" type="file" />
              <svg
                class="text-white/40 hover:text-white transition-colors"
                stroke-linejoin="round"
                stroke-linecap="round"
                stroke-width="2"
                stroke="currentColor"
                fill="none"
                viewBox="0 0 24 24"
                height="16"
                width="16"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48"
                ></path>
              </svg>
            </label>

            <button
              class="rounded-full flex items-center gap-2 px-1.5 py-1 border h-8 cursor-pointer bg-sky-500/15 hover:bg-sky-500/20 border-sky-400 text-sky-500"
              type="button"
            >
              <div class="w-4 h-4 flex items-center justify-center shrink-0">
                <svg
                  class="text-sky-500"
                  stroke-linejoin="round"
                  stroke-linecap="round"
                  stroke-width="2"
                  stroke="currentColor"
                  fill="none"
                  viewBox="0 0 24 24"
                  height="16"
                  width="16"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <circle r="10" cy="12" cx="12"></circle>
                  <path d="M2 12h20"></path>
                  <path
                    d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"
                  ></path>
                </svg>
              </div>
              <span class="text-sm text-sky-500">Search</span>
            </button>
          </div>

          <div class="absolute right-3 bottom-3">
            <button
              class="rounded-lg p-2 bg-white/5 hover:bg-white/10 text-white/40 hover:text-white cursor-pointer transition-colors"
              type="button"
            >
              <svg
                stroke-linejoin="round"
                stroke-linecap="round"
                stroke-width="2"
                stroke="currentColor"
                fill="none"
                viewBox="0 0 24 24"
                height="16"
                width="16"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path d="m22 2-7 20-4-9-9-4Z"></path>
                <path d="M22 2 11 13"></path>
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
