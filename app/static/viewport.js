(function () {
  "use strict";
  var viewport = window.visualViewport;
  var root = document.documentElement;

  function fit() {
    // Pinch-zoom verkleint de viewport ook, maar mag de pagina niet herschikken.
    if (viewport && viewport.scale !== 1) return;
    var height = viewport ? viewport.height : window.innerHeight;
    root.style.setProperty("--viewport-height", height + "px");
    root.style.setProperty("--viewport-top", (viewport ? viewport.offsetTop : 0) + "px");
    document.dispatchEvent(new Event("chat:viewport-fitted"));
  }

  fit();
  window.addEventListener("resize", fit);
  window.addEventListener("pageshow", fit);
  if (viewport) {
    viewport.addEventListener("resize", fit);
    viewport.addEventListener("scroll", fit);
  }
})();
