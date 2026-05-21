import "@testing-library/jest-dom";

// Suppress expected unhandled rejection warnings from retry tests
// These are intentional rejections that get caught by expect().rejects.toThrow()
process.on('unhandledRejection', () => {
  // Intentionally empty - these are expected in retry tests
});

Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => {},
  }),
});
