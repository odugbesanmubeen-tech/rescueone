// Home screen SOS button: confirm, request location, send, and only then show success.
(function () {
  var btn = document.getElementById("sos-btn");
  var dlg = document.getElementById("sos-dialog");
  if (!btn || !dlg || !window.EM) return;

  var sendBtn = document.getElementById("sos-send");
  var cancelBtn = document.getElementById("sos-cancel");
  var statusEl = document.getElementById("sos-status");
  var errorEl = document.getElementById("sos-error");
  var category = document.getElementById("sos-category");
  var address = document.getElementById("sos-address");
  var position = null;
  var locating = null;
  var sending = false;

  function setStatus(t) { statusEl.textContent = t; }
  function setError(t) { errorEl.textContent = t || ""; errorEl.hidden = !t; }

  function locate() {
    position = null;
    setStatus("Your browser will ask permission to use your location. Please allow it.");
    locating = EM.getPosition().then(
      function (p) {
        position = p;
        setStatus("Location found (accurate to about " + Math.round(p.accuracy) + " m).");
      },
      function (e) {
        setStatus(e.message + " Enter your address or a landmark below so responders can find you.");
      }
    );
    return locating;
  }

  btn.addEventListener("click", function () {
    setError("");
    sending = false;
    sendBtn.disabled = false;
    dlg.showModal();
    locate();
  });
  cancelBtn.addEventListener("click", function () { dlg.close(); });

  sendBtn.addEventListener("click", function () {
    if (sending) return;
    sending = true;
    sendBtn.disabled = true;
    setError("");
    setStatus("Sending…");
    Promise.resolve(locating).then(function () {
      var addr = address.value.trim();
      if (!position && !addr) {
        setError("We need your location or an address. Allow location access or type where you are.");
        setStatus("");
        sending = false;
        sendBtn.disabled = false;
        return;
      }
      var fd = new FormData();
      fd.append("category", category.value || "OTHER");
      if (addr) fd.append("address_text", addr);
      if (position) EM.addPosition(fd, position);
      EM.sendReport(fd).then(function (res) {
        if (res.ok) {
          setStatus("Help request sent. Opening your request…");
          window.location.href = res.url;
        } else {
          setError(res.error || "Your request could not be sent.");
          setStatus("");
          sending = false;
          sendBtn.disabled = false;
        }
      });
    });
  });
})();
