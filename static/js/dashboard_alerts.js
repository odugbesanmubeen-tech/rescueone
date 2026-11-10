// Polls for newly reported incidents and shows a banner (and a short beep if the browser allows).
(function () {
  var root = document.getElementById("alert-root");
  var banner = document.getElementById("alert-banner");
  if (!root || !banner) return;
  var url = root.dataset.url;
  var latest = parseInt(root.dataset.latest || "0", 10);
  var unseen = 0;
  var baseTitle = document.title;

  function beep() {
    try {
      var C = window.AudioContext || window.webkitAudioContext;
      if (!C) return;
      var ctx = new C();
      var osc = ctx.createOscillator();
      var gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.frequency.value = 880;
      gain.gain.value = 0.1;
      osc.start();
      osc.stop(ctx.currentTime + 0.4);
    } catch (e) { /* browsers may block audio until the page has been clicked */ }
  }

  function addRow(item) {
    var row = document.createElement("div");
    row.className = "alert-row";
    var strong = document.createElement("strong");
    strong.textContent = "New emergency #" + item.id + " · " + item.category;
    var info = document.createElement("span");
    info.textContent = " " + (item.where || "") + " (" + item.reporter + ") ";
    var link = document.createElement("a");
    link.href = item.url;
    link.textContent = "Open";
    row.appendChild(strong);
    row.appendChild(info);
    row.appendChild(link);
    banner.appendChild(row);
  }

  var close = document.createElement("button");
  close.type = "button";
  close.className = "btn btn-small btn-ghost";
  close.textContent = "Dismiss";
  close.addEventListener("click", function () {
    banner.hidden = true;
    while (banner.children.length > 1) banner.removeChild(banner.lastChild);
    unseen = 0;
    document.title = baseTitle;
  });
  banner.appendChild(close);

  function poll() {
    fetch(url + "?after=" + latest, { credentials: "same-origin" })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (data) {
        if (data.new.length) {
          data.new.forEach(addRow);
          banner.hidden = false;
          unseen += data.new.length;
          document.title = "(" + unseen + ") " + baseTitle;
          beep();
        }
        latest = data.latest_id;
      })
      .catch(function () { /* transient network error; try again next tick */ });
  }
  setInterval(poll, 8000);
})();
