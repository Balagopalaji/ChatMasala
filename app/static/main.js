// main.js — vanilla JS for ChatMasala
// Auto-refresh is handled by <meta http-equiv="refresh"> injected server-side
// when the thread status is "running" or "waiting_for_agent".

(function () {
  "use strict";

  // Smooth scroll agent columns to the bottom on page load so the latest
  // turn is immediately visible without manual scrolling.
  function scrollAgentCols() {
    var cols = document.querySelectorAll(".agent-col-body");
    cols.forEach(function (col) {
      col.scrollTop = col.scrollHeight;
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", scrollAgentCols);
  } else {
    scrollAgentCols();
  }
})();
