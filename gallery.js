(function () {
  function layoutMasonry(container) {
    if (window.innerWidth < 800) return;
    var items = Array.prototype.slice.call(container.children);
    if (items.length < 2) return;

    var heights = items.map(function (item) { return item.offsetHeight; });
    var col0 = document.createElement("div");
    var col1 = document.createElement("div");
    col0.className = "masonry-col";
    col1.className = "masonry-col";

    function spacer(px) {
      var el = document.createElement("div");
      el.className = "masonry-spacer";
      el.style.height = px + "px";
      return el;
    }

    var h0 = 0, h1 = 0;
    var forceCol = null;
    items.forEach(function (item, i) {
      var useCol0 = forceCol !== null ? forceCol === col0 : h0 <= h1;
      forceCol = null;
      var isHeader = item.classList.contains("section-header");
      if (useCol0) {
        col0.appendChild(item);
        h0 += heights[i];
        if (isHeader) {
          col1.appendChild(spacer(heights[i]));
          h1 += heights[i];
          forceCol = col0;
        }
      } else {
        col1.appendChild(item);
        h1 += heights[i];
        if (isHeader) {
          col0.appendChild(spacer(heights[i]));
          h0 += heights[i];
          forceCol = col1;
        }
      }
    });

    container.textContent = "";
    container.appendChild(col0);
    container.appendChild(col1);
    container.classList.add("masonry-ready");
  }

  document.querySelectorAll(".masonry").forEach(layoutMasonry);
})();
