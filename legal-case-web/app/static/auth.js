"use strict";

const form = document.querySelector("#auth-form");
const inviteWrap = document.querySelector("#invite-wrap");
const inviteInput = document.querySelector("#invite-code");
const toggle = document.querySelector("#toggle-mode");
const submit = document.querySelector("#submit");
const status = document.querySelector("#auth-status");
let registrationAvailable = false;
let registering = false;

function showError(message) {
  status.textContent = message;
  status.classList.add("error");
}

async function loadStatus() {
  const response = await fetch("/api/auth/status", { cache: "no-store", credentials: "same-origin" });
  if (!response.ok) throw new Error("無法確認登入狀態。");
  const data = await response.json();
  if (!data.auth_required) {
    window.location.replace("/");
    return;
  }
  if (data.authenticated) {
    window.location.replace("/");
    return;
  }
  registrationAvailable = data.registration_available === true;
  toggle.hidden = !registrationAvailable;
}

toggle.addEventListener("click", () => {
  registering = !registering;
  inviteWrap.hidden = !registering;
  inviteInput.required = registering;
  document.querySelector("#password").setAttribute("autocomplete", registering ? "new-password" : "current-password");
  submit.textContent = registering ? "註冊並登入" : "登入";
  toggle.textContent = registering ? "返回登入" : "建立帳號";
  status.textContent = registering
    ? "限建立一個帳號；需要管理員提供的邀請碼，密碼至少 8 字元。"
    : "";
  status.classList.remove("error");
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  status.textContent = "處理中…";
  status.classList.remove("error");
  submit.disabled = true;
  const values = new FormData(form);
  const payload = {
    username: String(values.get("username") || ""),
    password: String(values.get("password") || ""),
  };
  if (registering) payload.invite_code = String(values.get("invite_code") || "");
  try {
    const response = await fetch(registering ? "/api/auth/register" : "/api/auth/login", {
      method: "POST",
      credentials: "same-origin",
      cache: "no-store",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.message || "登入或註冊失敗。");
    window.location.replace("/");
  } catch (error) {
    showError(error instanceof Error ? error.message : "登入或註冊失敗。");
  } finally {
    submit.disabled = false;
  }
});

loadStatus().catch((error) => showError(error.message));
