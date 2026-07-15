/**
 * Silent local login for the assessment Chainlit app.
 * If the browser is not authenticated, POST /login with the fixed demo
 * credentials and reload once so the history sidebar can load.
 */
(function () {
  var EMAIL = "john.doe@example.com";
  var PASSWORD = "1234";
  var FLAG = "lmh_chainlit_autologin_attempted";

  function alreadyAttempted() {
    try {
      return sessionStorage.getItem(FLAG) === "1";
    } catch (e) {
      return false;
    }
  }

  function markAttempted() {
    try {
      sessionStorage.setItem(FLAG, "1");
    } catch (e) {
      /* ignore */
    }
  }

  async function isLoggedIn() {
    try {
      var res = await fetch("/user", { credentials: "include" });
      return res.ok;
    } catch (e) {
      return false;
    }
  }

  async function loginWithPassword() {
    var body = new URLSearchParams();
    body.set("username", EMAIL);
    body.set("password", PASSWORD);
    body.set("grant_type", "password");

    var res = await fetch("/login", {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: body.toString(),
    });
    return res.ok;
  }

  async function loginWithHeader() {
    var res = await fetch("/auth/header", {
      method: "POST",
      credentials: "include",
      headers: {
        "X-LMH-Chainlit-Auth": EMAIL,
      },
    });
    return res.ok;
  }

  async function run() {
    if (await isLoggedIn()) {
      return;
    }
    if (alreadyAttempted()) {
      return;
    }
    markAttempted();

    var ok = false;
    try {
      ok = await loginWithPassword();
    } catch (e) {
      ok = false;
    }
    if (!ok) {
      try {
        ok = await loginWithHeader();
      } catch (e) {
        ok = false;
      }
    }
    if (ok) {
      window.location.reload();
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", run);
  } else {
    run();
  }
})();
