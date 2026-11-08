// Refreshes the overview counters from the database every 15 seconds.
(function () {
  var box = document.querySelector(".stats[data-url]");
  var status = document.getElementById("live-status");
  if (!box) return;
  var fields = box.querySelectorAll("[data-stat]");

  function refresh() {
    fetch(box.dataset.url, { credentials: "same-origin", headers: { "X-Requested-With": "XMLHttpRequest" } })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (data) {
        fields.forEach(function (f) {
          if (f.dataset.stat in data) f.textContent = data[f.dataset.stat];
        });
        if (status) status.textContent = "Updated " + new Date().toLocaleTimeString() + " · refreshes every 15 seconds.";
      })
      .catch(function () {
        if (status) status.textContent = "Live update failed. Reload the page; figures shown may be out of date.";
      });
  }
  setInterval(refresh, 15000);
})();
