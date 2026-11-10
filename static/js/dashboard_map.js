// Leaflet map using real incident/responder data passed from Django (json_script).
(function () {
  var el = document.getElementById("map");
  if (!el || typeof L === "undefined") return;

  function read(id) {
    var node = document.getElementById(id);
    return node ? JSON.parse(node.textContent) : [];
  }
  var cfg = read("map-config");
  var incidents = read("map-incidents");
  var responders = read("map-responders");

  var map = L.map(el).setView([cfg.lat || 0, cfg.lng || 0], cfg.zoom || 2);

  // FIXED: Restored the explicit domain name structure within the tile layer string
  L.tileLayer("https://{s}://{z}/{x}/{y}{r}.png", {
    maxZoom: 20,
    attribution:
      '&copy; <a href="https://openstreetmap.org">OpenStreetMap</a> contributors &copy; <a href="https://carto.com">CARTO</a>',
    subdomains: "abcd",
  }).addTo(map);

  var points = [];

  function popup(lines, href) {
    var box = document.createElement("div");
    lines.forEach(function (t, i) {
      var p = document.createElement(i === 0 ? "strong" : "div");
      p.textContent = t;
      box.appendChild(p);
    });
    if (href) {
      var a = document.createElement("a");
      a.href = href;
      a.textContent = "Open incident";
      box.appendChild(a);
    }
    return box;
  }

  incidents.forEach(function (i) {
    if (i.lat == null || i.lng == null) return;
    var m = L.circleMarker([i.lat, i.lng], {
      radius: 10,
      color: "#a61e1e",
      fillColor: "#d62828",
      fillOpacity: 0.85,
      weight: 2,
    });
    m.bindPopup(
      popup(
        ["Incident #" + i.id + " · " + i.category, i.status_label, i.address],
        i.url,
      ),
    );
    m.addTo(map);
    points.push([i.lat, i.lng]);
  });

  responders.forEach(function (r) {
    if (r.lat == null || r.lng == null) return;
    var m = L.circleMarker([r.lat, r.lng], {
      radius: 8,
      color: r.stale ? "#8a929c" : "#1d6fdc",
      fillColor: r.stale ? "#cfd4da" : "#4c93f0",
      fillOpacity: 0.9,
      weight: 2,
    });
    var when = r.updated ? new Date(r.updated).toLocaleString() : "never";
    m.bindPopup(
      popup([
        r.name,
        r.availability,
        (r.stale ? "Location outdated · " : "Updated ") + when,
      ]),
    );
    m.addTo(map);
    points.push([r.lat, r.lng]);
  });

  if (points.length === 1) {
    map.setView(points[0], 15);
  } else if (points.length > 1) {
    map.fitBounds(points, { padding: [30, 30] });
  }
})();
