// Detailed report form: GPS button, optional voice note, then submit via fetch.
(function () {
  var form = document.getElementById("report-form");
  if (!form || !window.EM) return;
  var gpsBtn = document.getElementById("gps-btn");
  var gpsStatus = document.getElementById("gps-status");
  var errorEl = document.getElementById("report-error");
  var submitBtn = document.getElementById("report-submit");
  var recBtn = document.getElementById("rec-btn");
  var recStatus = document.getElementById("rec-status");
  var position = null;
  var voiceBlob = null;
  var recorder = null;
  var chunks = [];

  function setError(t) { errorEl.textContent = t || ""; errorEl.hidden = !t; }

  gpsBtn.addEventListener("click", function () {
    gpsStatus.textContent = "Your browser will ask for permission to use your location…";
    EM.getPosition().then(
      function (p) {
        position = p;
        gpsStatus.textContent = "Location captured (about " + Math.round(p.accuracy) + " m accuracy).";
      },
      function (e) {
        position = null;
        gpsStatus.textContent = e.message + " Type your address below instead.";
      }
    );
  });

  if (!window.MediaRecorder || !navigator.mediaDevices) {
    recBtn.hidden = true;
    recStatus.textContent = "Voice recording is not supported in this browser.";
  } else {
    recBtn.addEventListener("click", function () {
      if (recorder && recorder.state === "recording") {
        recorder.stop();
        return;
      }
      navigator.mediaDevices.getUserMedia({ audio: true }).then(function (stream) {
        chunks = [];
        recorder = new MediaRecorder(stream);
        recorder.ondataavailable = function (e) { if (e.data.size) chunks.push(e.data); };
        recorder.onstop = function () {
          stream.getTracks().forEach(function (t) { t.stop(); });
          voiceBlob = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
          recBtn.textContent = "Record again";
          recStatus.textContent = "Voice note ready (" + Math.round(voiceBlob.size / 1024) + " KB).";
        };
        recorder.start();
        recBtn.textContent = "Stop recording";
        recStatus.textContent = "Recording…";
      }).catch(function () {
        recStatus.textContent = "Microphone permission was denied.";
      });
    });
  }

  form.addEventListener("submit", function (ev) {
    ev.preventDefault();
    setError("");
    var addr = form.elements.address_text.value.trim();
    if (!position && !addr) {
      setError("Capture your location or type an address so responders can find you.");
      return;
    }
    var fd = new FormData();
    fd.append("category", form.elements.category.value);
    fd.append("description", form.elements.description.value);
    if (addr) fd.append("address_text", addr);
    if (position) EM.addPosition(fd, position);
    Array.prototype.forEach.call(form.elements.media.files, function (f) { fd.append("media", f); });
    if (voiceBlob) {
      var ext = voiceBlob.type.indexOf("mp4") >= 0 ? ".m4a" : voiceBlob.type.indexOf("ogg") >= 0 ? ".ogg" : ".webm";
      fd.append("media", voiceBlob, "voice" + ext);
    }
    submitBtn.disabled = true;
    submitBtn.textContent = "Sending…";
    EM.sendReport(fd).then(function (res) {
      if (res.ok) {
        window.location.href = res.url;
      } else {
        setError(res.error || "Your request could not be sent.");
        submitBtn.disabled = false;
        submitBtn.textContent = "Send emergency report";
      }
    });
  });
})();
