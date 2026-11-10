// Show/hide password toggle.
(function () {
  var btn = document.getElementById("pw-toggle");
  var input = document.getElementById("id_password");
  if (!btn || !input) return;
  btn.addEventListener("click", function () {
    var show = input.type === "password";
    input.type = show ? "text" : "password";
    btn.textContent = show ? "Hide" : "Show";
  });
})();