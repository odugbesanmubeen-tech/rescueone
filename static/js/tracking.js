// Live status for one incident: polls the server, never invents data.
(function () {
  var root = document.getElementById("track");
  if (!root) return;
  var url = root.dataset.url;
  var statusEl = document.getElementById("track-status");
  var infoEl = document.getElementById("track-info");
  var cancelBox = document.getElementById("cancel-box");
  var mapEl = document.getElementById("map");
  var map = null, incMarker = null, respMarker = null;
  var initial = JSON.parse(document.getElementById("track-initial").textContent);

  function ensureMap(d) {
    if (!mapEl || typeof L === "undefined" || d.lat == null) return;
    if (!map) {
      map = L.map(mapEl).setView([d.lat, d.lng], 15);
      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
      }).addTo(map);
      incMarker = L.circleMarker([d.lat, d.lng], { radius: 10, color: "#a61e1e", fillColor: "#d62828", fillOpacity: 0.9 })
        .bindPopup("Your location").addTo(map);
    }
    var r = d.responder;
    if (r && r.lat != null) {
      var stale = r.stale;
      var style = { radius: 9, color: stale ? "#8a929c" : "#1d6fdc", fillColor: stale ? "#cfd4da" : "#4c93f0", fillOpacity: 0.9 };
      if (!respMarker) respMarker = L.circleMarker([r.lat, r.lng], style).addTo(map);
      else respMarker.setLatLng([r.lat, r.lng]).setStyle(style);
      respMarker.bindPopup(r.name + (stale ? " (location outdated)" : ""));
      map.fitBounds([[d.lat, d.lng], [r.lat, r.lng]], { padding: [40, 40] });
    }
  }

  function render(d) {
    statusEl.textContent = d.status_label;
    statusEl.className = "badge badge-" + d.status.toLowerCase();
    infoEl.textContent = "";
    function line(text, cls) {
      var p = document.createElement("p");
      if (cls) p.className = cls;
      p.textContent = text;
      infoEl.appendChild(p);
    }
    if (d.responder) {
      var r = d.responder;
      line("Assigned responder: " + r.name + " (" + r.type + ")" + (r.vehicle ? " · vehicle " + r.vehicle : ""));
      if (r.lat == null) line("The responder has not shared a location yet.", "muted");
      else if (r.stale) line("Responder location is outdated; it updates only while their app is open.", "muted");
      else line("Responder location updated " + new Date(r.updated).toLocaleTimeString() + ".", "muted");
    } else if (d.pending_offer) {
      line("A responder has been contacted and we are waiting for them to accept.");
    } else if (d.is_active) {
      line("Your request has been received. A dispatcher is finding a responder.");
    } else {
      line("This request is closed.", "muted");
    }
    if (cancelBox) cancelBox.hidden = !d.can_cancel;
    ensureMap(d);
  }

  render(initial);
  if (!initial.is_active) return;
  var failures = 0;
  var timer = setInterval(function () {
    fetch(url, { credentials: "same-origin" })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (d) {
        failures = 0;
        var changed = d.status !== initial.status;
        render(d);
        initial = d;
        if (!d.is_active) { clearInterval(timer); if (changed) window.location.reload(); }
      })
      .catch(function () {
        failures += 1;
        if (failures >= 3) {
          var p = document.createElement("p");
          p.className = "muted";
          p.textContent = "Connection problem. Status shown may be out of date.";
          infoEl.appendChild(p);
        }
      });
  }, 8000);
})();
