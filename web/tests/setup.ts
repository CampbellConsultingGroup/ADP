import "@testing-library/react";

// React Flow v12 uses ResizeObserver internally — jsdom doesn't provide it
class MockResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}
global.ResizeObserver = MockResizeObserver as unknown as typeof ResizeObserver;

// ADP-SPEC-052: editor/ui/Modal.tsx (web/src/diagrams) uses the native <dialog> element's
// showModal()/close() — jsdom doesn't implement either, so calling showModal() throws
// "dialog.showModal is not a function". Minimal polyfill: just enough behavior for React's own
// effect (open the element; on close, fire the "close" event some code may listen for).
if (typeof HTMLDialogElement !== "undefined" && !HTMLDialogElement.prototype.showModal) {
  HTMLDialogElement.prototype.showModal = function (this: HTMLDialogElement) {
    this.setAttribute("open", "");
  };
  HTMLDialogElement.prototype.close = function (this: HTMLDialogElement) {
    this.removeAttribute("open");
    this.dispatchEvent(new Event("close"));
  };
}

// React Flow uses DOMMatrix for transforms — polyfill for jsdom
if (typeof global.DOMMatrix === "undefined") {
  global.DOMMatrix = class {
    a = 1; b = 0; c = 0; d = 1; e = 0; f = 0;
    m11 = 1; m12 = 0; m13 = 0; m14 = 0;
    m21 = 0; m22 = 1; m23 = 0; m24 = 0;
    m31 = 0; m32 = 0; m33 = 1; m34 = 0;
    m41 = 0; m42 = 0; m43 = 0; m44 = 1;
    is2D = true;
    isIdentity = true;
  } as unknown as typeof DOMMatrix;
}
