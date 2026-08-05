/** True when this renderer is the dedicated floating Agent window. */
export const isFloatingWindow = new URLSearchParams(window.location.search).get('floating') === '1'
