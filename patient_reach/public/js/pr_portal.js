(function () {
  const $ = (id) => document.getElementById(id);

  // POST to a whitelisted method; always resolves {ok, data} or {ok:false, error}.
  window.prCall = async function (method, args) {
    const token = (window.frappe && frappe.csrf_token) || "";
    let res;
    try {
      res = await fetch("/api/method/" + method, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
          "X-Frappe-CSRF-Token": token,
        },
        body: JSON.stringify(args || {}),
      });
    } catch (e) {
      return { ok: false, error: "Network problem. Please check your connection and try again." };
    }
    let body = {};
    try { body = await res.json(); } catch (e) {}
    if (res.ok) return { ok: true, data: body.message };
    let msg = "Something went wrong. Please try again.";
    try {
      const sm = JSON.parse(body._server_messages || "[]");
      if (sm.length) msg = JSON.parse(sm[0]).message.replace(/<[^>]*>/g, "");
    } catch (e) {}
    return { ok: false, error: msg, status: res.status };
  };


    // Log out via POST (a plain link to /?cmd=web_logout is GET and is rejected by newer Frappe).
  document.addEventListener("click", async function (e) {
    const link = e.target.closest("#pr-logout");
    if (!link) return;
    e.preventDefault();
    const r = await prCall("logout");
    if (r.ok) window.location.href = "/portal-login";
    else alert("Could not log out. Please refresh the page and try again.");
  });

  window.prSetMsg = function (text, kind) {
    const el = $("pr-msg");
    if (!el) return;
    el.textContent = text || "";
    el.className = "pr-msg" + (text ? " pr-msg-" + (kind || "error") : "");
  };

  window.prDigitsOnly = function (el) {
    el.addEventListener("input", function () {
      let v = el.value.replace(/\D/g, "");
      if (v.length > 10) v = v.slice(0, 10);
      el.value = v;
    });
  };

  // Two-step OTP flow shared by the login and register pages.
  window.prInitOtpFlow = function (purpose) {
    let timer = null;
    const mobile = $("pr-mobile");
    prDigitsOnly(mobile);
    $("pr-otp").addEventListener("input", function () {
      this.value = this.value.replace(/\D/g, "").slice(0, 6);
    });

    function validateMobile() {
      const digits = (mobile.value || "").replace(/\D/g, "");
      if (digits.length !== 10) {
        prSetMsg("Please enter a valid 10-digit mobile number.");
        mobile.focus();
        return false;
      }
      mobile.value = digits.slice(0, 10);
      return true;
    }

    function startTimer(sec) {
      const btn = $("pr-resend");
      let s = sec;
      clearInterval(timer);
      btn.disabled = true;
      btn.textContent = "Resend OTP in " + s + "s";
      timer = setInterval(function () {
        s--;
        if (s <= 0) { clearInterval(timer); btn.disabled = false; btn.textContent = "Resend OTP"; }
        else btn.textContent = "Resend OTP in " + s + "s";
      }, 1000);
    }

    async function send(btn) {
      prSetMsg("");
      if (!validateMobile()) {
        btn.disabled = false;
        return;
      }
      const args = { mobile: mobile.value.trim(), purpose: purpose };
      if ($("pr-name")) args.full_name = $("pr-name").value.trim();
      btn.disabled = true;
      const r = await prCall("patient_reach.portal.auth.send_otp", args);
      if (!r.ok) {
        btn.disabled = false;
        prSetMsg(r.error);
        return;
      }
      $("pr-form1").hidden = true;
      $("pr-form2").hidden = false;
      $("pr-otp").focus();
      startTimer((r.data && r.data.resend_in) || 30);
      prSetMsg(purpose === "login" ? "If this number is registered, an OTP has been sent by SMS. It is valid for 5 minutes." : "OTP sent by SMS. It is valid for 5 minutes.", "info");
    }

    $("pr-form1").addEventListener("submit", function (e) { e.preventDefault(); send($("pr-send")); });
    $("pr-resend").addEventListener("click", function () { send($("pr-resend")); });
    $("pr-change").addEventListener("click", function () {
      clearInterval(timer); prSetMsg("");
      $("pr-form2").hidden = true; $("pr-form1").hidden = false;
      $("pr-send").disabled = false; $("pr-otp").value = "";
    });

    $("pr-form2").addEventListener("submit", async function (e) {
      e.preventDefault();
      prSetMsg("");
      const btn = $("pr-verify");
      btn.disabled = true;
      if (!validateMobile()) {
        btn.disabled = false;
        return;
      }
      const args = { mobile: mobile.value.trim(), otp: $("pr-otp").value.trim(), purpose: purpose };
      if ($("pr-name")) args.full_name = $("pr-name").value.trim();
      const r = await prCall("patient_reach.portal.auth.verify_otp", args);
      if (!r.ok) { btn.disabled = false; prSetMsg(r.error); return; }
      window.location.href = (r.data && r.data.redirect) || "/enquiries";
    });
  };
})();
