// Shared helpers for the citizen app: geolocation, submitting a report, service worker.
(function () {
  var csrf = (document.querySelector('meta[name="csrf-token"]') || {}).content || "";
  var sosUrl = document.body.dataset.sosUrl;

  function getPosition() {
    return new Promise(function (resolve, reject) {
      if (!navigator.geolocation) {
        reject({ message: "This browser cannot provide your location." });
        return;
      }
      navigator.geolocation.getCurrentPosition(
        function (p) {
          resolve({ lat: p.coords.latitude, lng: p.coords.longitude, accuracy: p.coords.accuracy });
        },
        function (e) {
          var msgs = {
            1: "Location permission was denied.",
            2: "Your location is unavailable right now.",
            3: "Finding your location took too long."
          };
          reject({ message: msgs[e.code] || "Could not get your location." });
        },
        { enableHighAccuracy: true, timeout: 12000, maximumAge: 0 }
      );
    });
  }

  // Resolves with the server's JSON. Rejects only when the request could not reach the server.
  function sendReport(formData) {
    return fetch(sosUrl, {
      method: "POST",
      body: formData,
      credentials: "same-origin",
      headers: { "X-CSRFToken": csrf, "X-Requested-With": "XMLHttpRequest" }
    })
      .then(function (r) {
        return r
          .json()
          .catch(function () { return { ok: false, error: "Unexpected response from the server." }; })
          .then(function (d) { d.http = r.status; return d; });
      })
      .catch(function () {
        return {
          ok: false,
          network: true,
          error: "No connection. Your request was NOT sent. If this is urgent, call your local emergency number now."
        };
      });
  }

  function addPosition(fd, pos) {
    fd.append("latitude", pos.lat);
    fd.append("longitude", pos.lng);
    fd.append("accuracy", pos.accuracy);
  }

  window.EM = { getPosition: getPosition, sendReport: sendReport, addPosition: addPosition };

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/app/sw.js", { scope: "/app/" }).catch(function () {});
  }
})();
