/**
 * JanaMen Digital HR — client controller.
 * Talks to the FastAPI backend with a bearer token kept in memory only.
 * Authorization is enforced server-side; the UI only hides what a role cannot use.
 */

const API_BASE = "/api/v1";

const state = {
  token: null,
  user: null,
  profile: null,
  page: "home",
  lang: "en",
  notifications: [],
  courses: [],
  currentCourse: null,
  currentLesson: null,
  pendingReview: null,
};

let demoAccounts = {};

// --- HELPERS ---
async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (state.token) headers["Authorization"] = `Bearer ${state.token}`;

  const tokenAtStart = state.token;
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  const data = await res.json().catch(() => ({}));
  if (tokenAtStart !== state.token) throw new Error("Session changed; please retry.");
  if (res.status === 401 && !path.includes("/auth/login")) showLogin();
  if (!res.ok) {
    const fields = data.error?.fields?.map(f => `${f.location.slice(1).join(".")}: ${f.message}`).join("; ");
    throw new Error(fields || data.error?.message || data.detail || `Request failed (${res.status})`);
  }
  return data;
}

function toast(msg) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.classList.add("show");
  clearTimeout(window.toastTimer);
  window.toastTimer = setTimeout(() => el.classList.remove("show"), 3200);
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

const t = key => (I18N[state.lang] || I18N.en)[key] || I18N.en[key] || key;
const icon = name => `<svg class="ic"><use href="#i-${name}"/></svg>`;
const STATUS_KEYS = { Pending: "stPending", Approved: "stApproved", Rejected: "stRejected" };
const TYPE_KEYS = { Vacation: "vacation", "Advance payment": "advancePayment" };
const statusBadge = s => `<span class="status ${esc(s).toLowerCase()}">${esc(t(STATUS_KEYS[s] || s))}</span>`;
const typeLabel = type => esc(t(TYPE_KEYS[type] || type));
const locale = () => ({ ru: "ru-RU", kz: "kk-KZ" }[state.lang] || "en-GB");
const initials = name => name.split(/\s+/).slice(0, 2).map(p => p[0] || "").join("").toUpperCase();

function greetingText() {
  const hour = new Date().getHours();
  const key = hour < 12 ? "greetMorning" : hour < 18 ? "greetAfternoon" : "greetEvening";
  return `${t(key)}, ${state.user.full_name.split(" ")[0]}`;
}

// --- INITIALIZATION & AUTH ---
async function initApp() {
  try { state.lang = localStorage.getItem("janamen.lang") || "en"; } catch { /* storage unavailable */ }
  document.getElementById("langSwitch").value = state.lang;
  applyLanguage(state.lang, false);

  setupNavigation();
  setupRoleSwitch();
  setupLanguageSwitch();
  setupModals();
  setupAIChat();
  setupKnowledgeForm();
  setupHome();

  document.getElementById("logoutBtn").onclick = () => logout();
  document.getElementById("loginForm").addEventListener("submit", async event => {
    event.preventDefault();
    const button = document.getElementById("loginSubmit");
    button.disabled = true;
    document.getElementById("loginError").textContent = "";
    try {
      const result = await api("/auth/login", { method: "POST", body: JSON.stringify({
        email: document.getElementById("loginEmail").value,
        password: document.getElementById("loginPassword").value,
      }) });
      state.token = result.access_token;
      state.user = result.user;
      const me = await api("/me");
      state.profile = me.profile;
      document.getElementById("loginPassword").value = "";
      document.getElementById("loginGate").hidden = true;
      document.getElementById("app").hidden = false;
      updateUserUI();
      await go("home");
    } catch (error) {
      showLogin(document.getElementById("loginEmail").value);
      document.getElementById("loginError").textContent = error.message;
    } finally {
      button.disabled = false;
    }
  });

  document.querySelectorAll("[data-persona]").forEach(card => {
    card.addEventListener("click", () => {
      document.getElementById("loginEmail").value = demoAccounts[card.dataset.persona] || "";
      document.getElementById("loginPassword").focus();
    });
  });

  try {
    const config = await api("/config");
    demoAccounts = config.demo_accounts;
    document.getElementById("personaWrap").hidden = !config.demo_mode;
    document.getElementById("demoPersonas").hidden = !config.demo_mode;
    document.querySelectorAll("[data-persona]").forEach(card => {
      card.querySelector("[data-email]").textContent = demoAccounts[card.dataset.persona] || "";
    });
    document.getElementById("loginHint").textContent = t(config.demo_mode ? "loginHintDemo" : "loginHint");
    showLogin(demoAccounts.employee || "");
  } catch (error) {
    document.getElementById("loginError").textContent = error.message;
  }
}

function showLogin(email = "") {
  state.token = null;
  state.user = null;
  state.profile = null;
  state.currentCourse = null;
  state.currentLesson = null;
  state.courses = [];
  state.notifications = [];
  state.pendingReview = null;
  document.getElementById("app").hidden = true;
  document.querySelectorAll(".modal-backdrop").forEach(el => el.classList.remove("open"));
  ["homeRequests", "homeCourseCard", "homeActivity", "academyGrid", "notificationsList", "teamTable", "requestTable",
   "knowledgeList", "knowledgeDocuments", "approvedKnowledgeList", "adminAuditTable", "adminIntegrationsList",
   "chatMessages", "playerLessonsList", "playerQuizOptions", "detailModalTimeline", "profCourses"]
    .forEach(id => document.getElementById(id)?.replaceChildren());
  document.querySelectorAll('[id^="prof"], #userName, #userRole, #avatar, #greeting, #citationSnippet, #playerLessonContent')
    .forEach(el => { if (el.childElementCount === 0) el.textContent = "—"; });
  document.querySelectorAll("#app form").forEach(form => form.reset());
  document.getElementById("loginEmail").value = email;
  document.getElementById("loginPassword").value = "";
  document.getElementById("loginGate").hidden = false;
  document.title = "JanaМен · HR workspace";
}

async function logout(email = "") {
  try {
    if (state.token) await api("/auth/logout", { method: "POST" });
    showLogin(email);
  } catch (error) {
    // Local data is cleared even if the network is unavailable; the server token expires.
    showLogin(email);
    document.getElementById("loginError").textContent = `Local sign-out complete. ${error.message}`;
  }
}

async function switchRole(roleKey) {
  const email = demoAccounts[roleKey];
  if (email) await logout(email);
}

const ROLE_ACCESS = { manager: ["manager", "hr_admin"], hr_admin: ["hr_admin"] };

function updateUserUI() {
  if (!state.user) return;
  const role = state.user.role;
  document.getElementById("userName").textContent = state.user.full_name;
  document.getElementById("userRole").textContent = state.profile ? state.profile.position : role;
  document.getElementById("avatar").textContent = initials(state.user.full_name);
  document.getElementById("roleSwitch").value = role;
  // Cosmetic only: the backend returns 403 for these endpoints regardless.
  document.querySelectorAll("[data-requires]").forEach(el => {
    el.hidden = !ROLE_ACCESS[el.dataset.requires].includes(role);
  });
}

// --- NAVIGATION ---
function setupNavigation() {
  document.querySelectorAll("[data-page]").forEach(button => button.addEventListener("click", () => go(button.dataset.page)));
  document.querySelectorAll("[data-goto]").forEach(el => el.addEventListener("click", () => go(el.dataset.goto)));
  const menuBtn = document.getElementById("menuBtn");
  menuBtn.addEventListener("click", () => {
    const open = document.getElementById("navLinks").classList.toggle("open");
    menuBtn.setAttribute("aria-expanded", String(open));
  });
}

const pageTitles = {
  home: "overview", profile: "myProfile", requests: "myRequests", academy: "janaAcademy",
  assistant: "aiJana", notifications: "notifications", team: "teamApprovals", admin: "hrAdmin",
};

async function go(page) {
  if (!state.token) { showLogin(); return; }
  const required = { team: "manager", admin: "hr_admin" }[page];
  if (required && !ROLE_ACCESS[required].includes(state.user?.role)) {
    toast(t("accessDenied"));
    return;
  }
  state.page = page;
  document.querySelectorAll(".page").forEach(p => p.classList.toggle("active", p.id === `page-${page}`));
  document.querySelectorAll("[data-page]").forEach(b => b.classList.toggle("active", b.dataset.page === page));
  document.getElementById("navLinks").classList.remove("open");
  document.getElementById("menuBtn").setAttribute("aria-expanded", "false");
  document.title = `${t(pageTitles[page])} · JanaМен`;
  window.scrollTo({ top: 0, behavior: "smooth" });
  await refreshCurrentPage();
}

async function refreshCurrentPage() {
  const loaders = {
    home: loadDashboard, profile: loadProfilePage, requests: loadRequestsPage, academy: loadAcademyPage,
    assistant: loadKnowledgeSummary, notifications: loadNotificationsPage, team: loadTeamPage, admin: loadAdminPage,
  };
  await loaders[state.page]?.();
  await updateNotificationBadge();
}

// --- HOME ---
function setupHome() {
  document.getElementById("heroAskForm").addEventListener("submit", async event => {
    event.preventDefault();
    const input = document.getElementById("heroAskInput");
    const question = input.value.trim();
    if (!question) return;
    input.value = "";
    await go("assistant");
    await sendAIQuery(question);
  });
  document.querySelectorAll("[data-role-tab]").forEach(tab => tab.addEventListener("click", () => {
    document.querySelectorAll("[data-role-tab]").forEach(b => b.classList.toggle("active", b === tab));
    document.querySelectorAll("[data-role-panel]").forEach(p => { p.hidden = p.dataset.rolePanel !== tab.dataset.roleTab; });
  }));
}

function requestRows(requests) {
  return requests.map(r => `
    <div class="request-row">
      <div class="req-icon">${icon(r.type === "Vacation" ? "calendar" : "wallet")}</div>
      <div>
        <div class="req-title">${typeLabel(r.type)}</div>
        <div class="req-sub">${esc(r.request_code)} · ${esc(r.period_or_details)}</div>
      </div>
      ${statusBadge(r.status)}
    </div>`).join("");
}

async function loadDashboard() {
  try {
    const [data, courses, notifications, requests] = await Promise.all([
      api("/me/dashboard"), api("/courses"), api("/notifications?limit=3"), api("/requests"),
    ]);
    document.getElementById("greeting").textContent = greetingText();
    document.getElementById("leaveDays").textContent = data.leave_balance_days.toFixed(1);
    document.getElementById("statRequests").textContent = data.open_requests_count;
    document.getElementById("statLearning").textContent = `${Math.round(data.learning_progress_percent)}%`;
    document.getElementById("statCourses").textContent = data.assigned_courses_count;
    document.getElementById("statNotifications").textContent = data.unread_notifications_count;

    document.getElementById("homeRequests").innerHTML = requests.length
      ? requestRows(requests.slice(0, 4))
      : `<div class="empty">${esc(t("noRequests"))}</div>`;

    const assigned = courses.filter(c => c.assigned);
    const next = assigned.find(c => c.status !== "COMPLETED") || assigned[0];
    const banner = document.getElementById("homeCourseCard");
    banner.innerHTML = next ? `
      <div>
        <h2 class="h2">${esc(next.title)}</h2>
        <p>Jana Academy · ${next.total_lessons} ${esc(t("lessonsUnit"))} · ${Math.round(next.progress_percent)}% ${esc(t("complete"))}</p>
        <div class="progress"><span style="width:${next.progress_percent}%"></span></div>
      </div>
      <button class="btn btn-white" data-course="${next.id}">${esc(t(next.status === "COMPLETED" ? "reviewCourse" : "continueLearning"))} ${icon("arrow")}</button>`
      : `<div><h2 class="h2">Jana Academy</h2><p>${esc(t("noCourses"))}</p></div>
         <button class="btn btn-white" data-open-academy>${esc(t("openCatalog"))} ${icon("arrow")}</button>`;
    banner.querySelector("[data-course]")?.addEventListener("click", e => openCoursePlayer(Number(e.currentTarget.dataset.course)));
    banner.querySelector("[data-open-academy]")?.addEventListener("click", () => go("academy"));

    document.getElementById("homeActivity").innerHTML = notifications.length
      ? notifications.map(n => `
        <article class="update-card">
          <span class="notice-icon">${icon(n.type === "ACADEMY" ? "book" : n.type === "REQUEST" ? "file" : "bell")}</span>
          <b>${esc(n.title)}</b>
          <p>${esc(n.message)}</p>
          <small>${esc(n.time_ago)}</small>
        </article>`).join("")
      : `<div class="empty">${esc(t("noNotifications"))}</div>`;
  } catch (err) {
    toast(`${t("loadError")}: ${err.message}`);
  }
}

// --- PROFILE ---
async function loadProfilePage() {
  try {
    const p = await api("/me/profile");
    document.getElementById("profAvatar").textContent = initials(p.full_name);
    document.getElementById("profName").textContent = p.full_name;
    document.getElementById("profPosition").textContent = `${p.position} · ${p.email}`;
    document.getElementById("profEmpCode").textContent = p.employee_code;
    document.getElementById("profDept").textContent = p.department;
    document.getElementById("profCompany").textContent = p.company;
    document.getElementById("profManager").textContent = p.manager_name || "—";
    document.getElementById("profHireDate").textContent = new Date(p.hire_date).toLocaleDateString(locale(), { day: "2-digit", month: "short", year: "numeric" });
    document.getElementById("profLocation").textContent = p.location;
    document.getElementById("profLeaveBalance").textContent = `${p.leave_balance_days.toFixed(1)} ${t("daysUnit")}`;
    document.getElementById("profLearningPct").textContent = `${Math.round(p.learning_progress_percent)}%`;
    document.getElementById("profCourses").innerHTML = p.courses.length ? p.courses.map(c => `
      <div class="course-line">
        <span class="notice-icon">${icon(c.status === "COMPLETED" ? "check" : "book")}</span>
        <div>
          <b>${esc(c.title)}</b>
          <div class="req-sub">${esc(t(c.is_mandatory ? "mandatory" : "recommended"))}${c.due_date ? ` · ${esc(t("due"))} ${esc(c.due_date)}` : ""}</div>
          <div class="progress"><span style="width:${c.progress_percent}%"></span></div>
        </div>
      </div>`).join("") : `<div class="empty">${esc(t("noCourses"))}</div>`;
  } catch (err) {
    toast(`${t("loadError")}: ${err.message}`);
  }
}

// --- REQUESTS ---
async function loadRequestsPage() {
  const sf = document.getElementById("statusFilter").value;
  const tf = document.getElementById("typeFilter").value;
  const params = new URLSearchParams();
  if (sf !== "all") params.set("status", sf);
  if (tf !== "all") params.set("type", tf);
  try {
    const requests = await api(`/requests?${params}`);
    const tbody = document.getElementById("requestTable");
    tbody.innerHTML = requests.length ? requests.map(r => `
      <tr>
        <td><b>${typeLabel(r.type)}</b><div class="req-sub">${esc(r.request_code)}</div></td>
        <td>${esc(r.submitted_date_formatted)}</td>
        <td>${esc(r.period_or_details)}<div class="req-sub">${esc(r.reason || "—")}</div></td>
        <td>${statusBadge(r.status)}</td>
        <td><button class="text-link" onclick="openRequestDetailModal(${r.id})">${esc(t("details"))} →</button></td>
      </tr>`).join("")
      : `<tr><td colspan="5" class="empty">${esc(t("noRequests"))}</td></tr>`;
  } catch (err) {
    toast(`${t("loadError")}: ${err.message}`);
  }
}

// --- JANA ACADEMY ---
async function loadAcademyPage() {
  try {
    const courses = await api("/courses");
    state.courses = courses;
    document.getElementById("academyGrid").innerHTML = courses.map(c => {
      const done = c.status === "COMPLETED";
      const action = done ? "reviewCourse" : c.progress_percent > 0 ? "continueLearning" : c.assigned ? "startCourse" : "enroll";
      return `
      <article class="card course-tile ${c.is_mandatory ? "mandatory" : ""}">
        <div class="course-art">${icon(done ? "award" : "book")}</div>
        <div class="course-meta">
          <span class="chip">${esc(t(c.is_mandatory ? "mandatory" : "recommended"))}</span>
          <span class="chip">${c.duration_minutes} ${esc(t("minUnit"))}</span>
          ${done ? `<span class="status approved">${esc(t("passed"))} ${Math.round(c.score ?? 100)}%</span>` : ""}
        </div>
        <h3 class="h4">${esc(c.title)}</h3>
        <p>${esc(c.description)}</p>
        <div>
          <div class="progress"><span style="width:${c.progress_percent}%"></span></div>
          <div class="progress-label">
            <span>${Math.round(c.progress_percent)}% ${esc(t("complete"))}</span>
            <span>${c.assigned ? (c.due_date ? `${esc(t("due"))} ${esc(c.due_date)}` : esc(t("assigned"))) : esc(t("availableToEnroll"))}</span>
          </div>
        </div>
        <button class="btn ${done ? "btn-light" : "btn-primary"}" onclick="openCoursePlayer(${c.id})">${esc(t(action))} ${icon("arrow")}</button>
      </article>`;
    }).join("");
  } catch (err) {
    toast(`${t("loadError")}: ${err.message}`);
  }
}

// --- NOTIFICATIONS ---
async function loadNotificationsPage() {
  try {
    const notifs = await api("/notifications");
    state.notifications = notifs;
    document.getElementById("notificationsList").innerHTML = notifs.length ? notifs.map(n => `
      <button class="notice" onclick="markNotificationRead(${n.id})">
        <span class="notice-icon">${icon(n.type === "ACADEMY" ? "book" : n.type === "REQUEST" ? "file" : "bell")}</span>
        <span style="flex:1">
          <b>${esc(n.title)}</b>
          <p>${esc(n.message)} · ${esc(n.time_ago)}</p>
        </span>
        ${n.is_read ? "" : `<span class="unread-dot" aria-label="unread"></span>`}
      </button>`).join("")
      : `<div class="empty">${esc(t("noNotifications"))}</div>`;
  } catch (err) {
    toast(`${t("loadError")}: ${err.message}`);
  }
}

async function markNotificationRead(id) {
  try {
    await api(`/notifications/${id}`, { method: "PATCH", body: JSON.stringify({ is_read: true }) });
    await loadNotificationsPage();
    await updateNotificationBadge();
  } catch (err) {
    toast(err.message);
  }
}

async function markAllNotificationsRead() {
  try {
    await api("/notifications/read-all", { method: "POST" });
    toast(t("allRead"));
    await loadNotificationsPage();
    await updateNotificationBadge();
  } catch (err) {
    toast(err.message);
  }
}

async function updateNotificationBadge() {
  try {
    const { unread } = await api("/notifications/unread-count");
    const badge = document.getElementById("navNotifCount");
    badge.textContent = unread;
    badge.hidden = unread === 0;
  } catch {
    // badge refresh is best-effort
  }
}

// --- MANAGER ---
async function loadTeamPage() {
  try {
    const [requests, members] = await Promise.all([api("/manager/requests?status=Pending"), api("/manager/team")]);
    document.getElementById("teamScope").textContent = t(state.user.role === "hr_admin" ? "scopeCompany" : "scopeDirect");
    document.getElementById("teamCount").textContent = members.length;
    document.getElementById("teamPendingStat").textContent = requests.length;
    document.getElementById("teamPendingBadge").textContent = `${requests.length} ${t("pendingUnit")}`;
    document.getElementById("teamTable").innerHTML = requests.length ? requests.map(r => `
      <tr>
        <td><b>${esc(r.user_name)}</b><div class="req-sub">${esc(r.department)}</div></td>
        <td>${typeLabel(r.type)}<div class="req-sub">${esc(r.request_code)}</div></td>
        <td>${esc(r.period_or_details)}<div class="req-sub">${esc(r.reason || "—")}</div></td>
        <td>${statusBadge(r.status)}</td>
        <td style="white-space:nowrap">
          <button class="small-btn primary" onclick="reviewRequestPrompt(${r.id}, 'approve')">${esc(t("approve"))}</button>
          <button class="small-btn danger" onclick="reviewRequestPrompt(${r.id}, 'reject')">${esc(t("reject"))}</button>
          <button class="text-link" onclick="openRequestDetailModal(${r.id})">${esc(t("details"))}</button>
        </td>
      </tr>`).join("")
      : `<tr><td colspan="5" class="empty">${esc(t("noPending"))}</td></tr>`;
  } catch (err) {
    toast(`${t("loadError")}: ${err.message}`);
  }
}

function reviewRequestPrompt(requestId, action) {
  state.pendingReview = { requestId, action };
  const approve = action === "approve";
  document.getElementById("reviewTitle").textContent = t(approve ? "approveRequest" : "declineRequest");
  document.getElementById("reviewComment").value = "";
  document.getElementById("submitReview").textContent = t(approve ? "confirmApproval" : "confirmRejection");
  document.getElementById("reviewModal").classList.add("open");
}

// --- HR ADMIN ---
async function loadAdminPage() {
  try {
    const [summary, chunks, documents, adapters, logs] = await Promise.all([
      api("/admin/summary"), api("/admin/knowledge"), api("/admin/knowledge/documents"),
      api("/admin/integrations"), api("/admin/audit?limit=15"),
    ]);
    document.getElementById("adminEmployeeCount").textContent = summary.active_accounts;
    document.getElementById("adminKnowledgeCount").textContent = chunks.length;

    document.getElementById("knowledgeList").innerHTML = chunks.map(c => `
      <div class="notice">
        <span class="notice-icon">${icon("file")}</span>
        <div style="flex:1">
          <b>${esc(c.document_title)} · ${esc(c.section_title)}</b>
          <p>${c.is_approved ? "Approved" : "Draft"}${c.is_synthetic ? " · Synthetic example" : ""}</p>
          <p>${esc(c.content.substring(0, 140))}…</p>
        </div>
      </div>`).join("");

    const documentList = document.getElementById("knowledgeDocuments");
    documentList.innerHTML = documents.map(doc => `
      <div class="notice">
        <span class="notice-icon">${icon("book")}</span>
        <div style="flex:1">
          <b>${esc(doc.title)} · v${esc(doc.version)}</b>
          <p>${doc.is_synthetic ? "Synthetic example · " : ""}${doc.is_approved ? "Approved" : "Draft"} · ${doc.is_active ? "Active" : "Inactive"}</p>
          ${!doc.is_approved && doc.is_active ? `<button class="small-btn primary" data-approve-document="${doc.id}">Approve reviewed source</button>` : ""}
          ${doc.is_active ? `<button class="small-btn" data-deactivate-document="${doc.id}">Deactivate</button>` : ""}
        </div>
      </div>`).join("");
    documentList.querySelectorAll("[data-approve-document], [data-deactivate-document]").forEach(button => {
      button.addEventListener("click", async () => {
        try {
          const id = button.dataset.approveDocument || button.dataset.deactivateDocument;
          await api(`/admin/knowledge/documents/${id}`, { method: "PATCH", body: JSON.stringify(
            button.dataset.approveDocument ? { is_approved: true } : { is_active: false }) });
          await loadAdminPage();
        } catch (error) { toast(error.message); }
      });
    });

    document.getElementById("adminIntegrationsList").innerHTML = adapters.map(a => `
      <div class="notice">
        <span class="notice-icon">${icon("link")}</span>
        <div style="flex:1">
          <b>${esc(a.adapter_name)}</b> <span class="status pending">${esc(a.status)}</span>
          <p>${esc(a.notes)}</p>
          <p class="small"><b>Endpoint:</b> <code>${esc(a.endpoint_template)}</code> · <b>Mode:</b> ${esc(a.mode)}</p>
        </div>
      </div>`).join("");

    document.getElementById("adminAuditTable").innerHTML = logs.map(l => `
      <tr>
        <td><code>${esc(l.action)}</code></td>
        <td>${esc(l.actor_name)}</td>
        <td>${esc(l.target_type || "—")}: ${esc(l.target_id || "—")}</td>
        <td>${esc(new Date(l.timestamp).toLocaleTimeString(locale()))}</td>
      </tr>`).join("");
  } catch (err) {
    toast(`${t("loadError")}: ${err.message}`);
  }
}

function setupKnowledgeForm() {
  document.getElementById("knowledgeForm").addEventListener("submit", async event => {
    event.preventDefault();
    const form = event.target;
    const submit = form.querySelector('button[type="submit"]');
    submit.disabled = true;
    try {
      const doc = await api("/admin/knowledge/documents", { method: "POST", body: JSON.stringify({
        title: form.elements.title.value, is_synthetic: form.elements.synthetic.checked,
      }) });
      await api("/admin/knowledge", { method: "POST", body: JSON.stringify({ document_id: doc.id,
        section_title: form.elements.section.value, content: form.elements.content.value,
        access_level: form.elements.access.value }) });
      form.reset();
      toast("Draft saved. Review its text, then approve it for AI retrieval.");
      await loadAdminPage();
    } catch (error) { toast(error.message); }
    finally { submit.disabled = false; }
  });
}

// --- MODALS & WORKFLOWS ---
function setupModals() {
  const closeAll = () => document.querySelectorAll(".modal-backdrop").forEach(m => m.classList.remove("open"));
  document.querySelectorAll(".modal-backdrop").forEach(backdrop => {
    backdrop.addEventListener("click", e => { if (e.target === backdrop) backdrop.classList.remove("open"); });
  });
  document.addEventListener("keydown", e => { if (e.key === "Escape") closeAll(); });
  ["closeModal", "cancelModal", "closeDetailModal", "closeCourseModal", "closeCitationModal", "cancelReview"].forEach(id => {
    document.getElementById(id).addEventListener("click", () => document.getElementById(id).closest(".modal-backdrop").classList.remove("open"));
  });

  document.getElementById("reviewForm").addEventListener("submit", async event => {
    event.preventDefault();
    if (!state.pendingReview) return;
    const { requestId, action } = state.pendingReview;
    const button = document.getElementById("submitReview");
    button.disabled = true;
    try {
      const result = await api(`/requests/${requestId}/${action}`, { method: "POST", body: JSON.stringify({
        action, comment: document.getElementById("reviewComment").value.trim() || null,
      }) });
      document.getElementById("reviewModal").classList.remove("open");
      state.pendingReview = null;
      toast(`${result.request_code}: ${t(STATUS_KEYS[result.status] || result.status)}`);
      await refreshCurrentPage();
    } catch (error) { toast(error.message); }
    finally { button.disabled = false; }
  });

  const reqType = document.getElementById("reqType");
  const syncRequestType = () => {
    const isAdvance = reqType.value === "Advance payment";
    document.getElementById("reqAmountGroup").hidden = !isAdvance;
    document.getElementById("reqEndGroup").hidden = isAdvance;
    document.getElementById("reqAmount").required = isAdvance;
    document.getElementById("reqEnd").required = !isAdvance;
  };
  reqType.addEventListener("change", syncRequestType);
  syncRequestType();

  document.querySelectorAll('[data-action="new-request"]').forEach(b => {
    b.addEventListener("click", () => {
      if (b.dataset.type) reqType.value = b.dataset.type;
      syncRequestType();
      document.getElementById("requestModal").classList.add("open");
      document.getElementById("reqStart").focus();
    });
  });

  document.getElementById("requestForm").addEventListener("submit", async e => {
    e.preventDefault();
    const type = reqType.value;
    const amount = document.getElementById("reqAmount").value;
    const reason = document.getElementById("reqReason").value.trim();
    const submit = e.target.querySelector('button[type="submit"]');
    submit.disabled = true;
    try {
      const res = await api("/requests", { method: "POST", body: JSON.stringify({
        type,
        start_date: document.getElementById("reqStart").value,
        end_date: type === "Vacation" ? document.getElementById("reqEnd").value || null : null,
        amount: type === "Advance payment" && amount ? parseFloat(amount) : null,
        reason: reason || null,
      }) });
      toast(`${res.request_code} — ${t("requestCreated")}`);
      document.getElementById("requestModal").classList.remove("open");
      e.target.reset();
      syncRequestType();
      await refreshCurrentPage();
    } catch (err) {
      toast(`${t("submitFailed")}: ${err.message}`);
    } finally {
      submit.disabled = false;
    }
  });
}

async function openRequestDetailModal(id) {
  try {
    const r = await api(`/requests/${id}`);
    document.getElementById("detailModalTitle").textContent = `${r.request_code} · ${t(TYPE_KEYS[r.type] || r.type)}`;
    document.getElementById("detailModalCode").textContent = r.request_code;
    document.getElementById("detailModalStatus").innerHTML = statusBadge(r.status);
    document.getElementById("detailModalRequester").textContent = r.user_name;
    document.getElementById("detailModalDept").textContent = r.department;
    document.getElementById("detailModalDates").textContent = r.period_or_details;
    document.getElementById("detailModalSync").textContent = r.external_sync_id || t("notRegistered");
    document.getElementById("detailModalTimeline").innerHTML = r.events.map(ev => `
      <div class="activity">
        <span class="activity-dot ${ev.event_type === "APPROVED" ? "ok" : ev.event_type === "REJECTED" ? "bad" : ""}"></span>
        <div>
          <b>${esc(ev.event_type)} · ${esc(ev.actor_name)}</b>
          <p>${esc(ev.comment || "")}${ev.comment ? " · " : ""}${esc(new Date(ev.created_at).toLocaleString(locale()))}</p>
        </div>
      </div>`).join("");
    document.getElementById("requestDetailModal").classList.add("open");
  } catch (err) {
    toast(err.message);
  }
}

// --- COURSE PLAYER ---
function renderCourse(course) {
  state.currentCourse = course;
  document.getElementById("playerCourseTitle").textContent = course.title;
  document.getElementById("playerProgressBar").style.width = `${course.progress_percent}%`;
  document.getElementById("playerProgressLabel").textContent = `${Math.round(course.progress_percent)}% ${t("complete")}`;
  const currentId = state.currentLesson?.id ?? course.current_lesson_id;
  document.getElementById("playerLessonsList").innerHTML = course.lessons.map(l => `
    <button class="${l.id === currentId ? "current" : ""}" data-lesson="${l.id}" onclick="loadLessonInPlayer(${l.id})">
      <span>${esc(l.title)}</span><span class="done">${l.is_completed ? "✓" : "○"}</span>
    </button>`).join("");
}

async function openCoursePlayer(courseId) {
  try {
    let course = await api(`/courses/${courseId}`);
    if (!course.assigned) course = await api(`/courses/${courseId}/enroll`, { method: "POST" });
    state.currentLesson = null;
    renderCourse(course);
    const firstLesson = course.current_lesson_id || course.lessons[0]?.id;
    if (firstLesson) await loadLessonInPlayer(firstLesson);
    document.getElementById("coursePlayerModal").classList.add("open");
  } catch (err) {
    toast(err.message);
  }
}

async function loadLessonInPlayer(lessonId) {
  try {
    const lesson = await api(`/courses/lessons/${lessonId}`);
    state.currentLesson = lesson;
    document.querySelectorAll("#playerLessonsList [data-lesson]").forEach(b => b.classList.toggle("current", Number(b.dataset.lesson) === lesson.id));
    document.getElementById("playerLessonTitle").textContent = lesson.title;
    document.getElementById("playerLessonContent").textContent = lesson.content_markdown;
    const quizBox = document.getElementById("playerQuizBox");
    quizBox.hidden = !(lesson.quiz_question && lesson.quiz_options.length);
    document.getElementById("playerQuizFeedback").hidden = true;
    if (!quizBox.hidden) {
      document.getElementById("playerQuizQuestion").textContent = lesson.quiz_question;
      document.getElementById("playerQuizOptions").innerHTML = lesson.quiz_options.map((opt, idx) => `
        <label class="quiz-option"><input type="radio" name="lessonQuiz" value="${idx}"><span>${esc(opt)}</span></label>`).join("");
    }
  } catch (err) {
    toast(err.message);
  }
}

async function submitLessonQuiz() {
  if (!state.currentLesson) return;
  const selected = document.querySelector('input[name="lessonQuiz"]:checked');
  if (!selected) { toast(t("pickAnswer")); return; }
  try {
    const res = await api(`/courses/lessons/${state.currentLesson.id}/quiz`, {
      method: "POST", body: JSON.stringify({ answer_index: parseInt(selected.value, 10) }),
    });
    const fb = document.getElementById("playerQuizFeedback");
    fb.hidden = false;
    fb.className = res.passed ? "ok" : "bad";
    fb.textContent = res.explanation;
    renderCourse(await api(`/courses/${state.currentCourse.id}`));
    if (res.course_completed) toast(t("courseCompleted"));
    await refreshCurrentPage();
  } catch (err) {
    toast(err.message);
  }
}

// --- AI JANA ---
async function loadKnowledgeSummary() {
  try {
    const documents = await api("/ai/documents");
    document.getElementById("approvedKnowledgeList").innerHTML = documents.length
      ? documents.map(doc => `<div class="notice"><span class="notice-icon">${icon("file")}</span><div><b>${esc(doc.title)}</b><p>v${esc(doc.version)} · ${doc.is_synthetic ? "Synthetic example" : "Approved source"}</p></div></div>`).join("")
      : `<p class="muted">${esc(t("noSources"))}</p>`;
  } catch (error) { toast(error.message); }
}

function resetChat() {
  document.getElementById("chatMessages").innerHTML = `<div class="message">${esc(t("aiHello"))}<small>AI Jana</small></div>`;
}

function setupAIChat() {
  const input = document.getElementById("chatInput");
  document.getElementById("chatForm").addEventListener("submit", async e => {
    e.preventDefault();
    const q = input.value.trim();
    if (!q) return;
    input.value = "";
    await sendAIQuery(q);
  });
  document.querySelectorAll("[data-question]").forEach(btn => btn.addEventListener("click", () => sendAIQuery(btn.dataset.question)));
  document.getElementById("clearChat").onclick = resetChat;
  resetChat();
}

async function sendAIQuery(question) {
  const container = document.getElementById("chatMessages");
  const userBubble = document.createElement("div");
  userBubble.className = "message user";
  userBubble.textContent = question;
  const botBubble = document.createElement("div");
  botBubble.className = "message";
  botBubble.innerHTML = `<i>${esc(t("aiThinking"))}</i>`;
  container.append(userBubble, botBubble);
  container.scrollTop = container.scrollHeight;

  try {
    const res = await api("/ai/chat", { method: "POST", body: JSON.stringify({ question }) });
    let html = `<div style="white-space:pre-wrap">${esc(res.answer)}</div>`;
    if (res.sources?.length) {
      html += `<div class="citation-buttons">${res.sources.map((source, index) =>
        `<button class="source-pill" type="button" data-source-index="${index}">${icon("file")}${esc(source.document_title)} · ${esc(source.section_title)}</button>`).join("")}</div>`;
    }
    if (res.answer_status !== "grounded") {
      botBubble.classList.add("fallback");
      if (res.escalation_guidance) html += `<div class="fallback-note"><b>${esc(t("safeFallback"))}:</b> ${esc(res.escalation_guidance)}</div>`;
    }
    html += `<small>AI Jana · ${esc(res.answer_status)} · ${Math.round(res.processing_time_ms)} ms</small>`;
    botBubble.innerHTML = html;
    botBubble.querySelectorAll("[data-source-index]").forEach(button => {
      const source = res.sources[Number(button.dataset.sourceIndex)];
      button.addEventListener("click", async () => {
        try {
          const full = await api(`/ai/sources/${source.chunk_id}`);
          document.getElementById("citationDocTitle").textContent = `${full.document_title} · v${full.version}`;
          document.getElementById("citationSecTitle").textContent = full.section_title;
          document.getElementById("citationSnippet").textContent =
            `${full.is_synthetic ? "Synthetic example; not official HR policy.\n\n" : ""}${full.content}`;
          document.getElementById("citationModal").classList.add("open");
        } catch (error) { toast(error.message); }
      });
    });
  } catch (err) {
    botBubble.innerHTML = `<span style="color:var(--error)">${esc(err.message)}</span>`;
  }
  container.scrollTop = container.scrollHeight;
}

// --- LANGUAGE & PERSONA ---
function setupRoleSwitch() {
  document.getElementById("roleSwitch").addEventListener("change", e => switchRole(e.target.value));
}

function setupLanguageSwitch() {
  document.getElementById("langSwitch").addEventListener("change", e => {
    applyLanguage(e.target.value, true);
    if (state.token) refreshCurrentPage();
  });
}

function applyLanguage(lang, announce) {
  state.lang = I18N[lang] ? lang : "en";
  try { localStorage.setItem("janamen.lang", state.lang); } catch { /* storage unavailable */ }
  const dict = I18N[state.lang];
  document.querySelectorAll("[data-i18n]").forEach(el => {
    const text = dict[el.dataset.i18n] || I18N.en[el.dataset.i18n];
    if (!text) return;
    if (el.hasAttribute("placeholder")) el.placeholder = text;
    else el.textContent = text;
  });
  document.documentElement.lang = state.lang === "kz" ? "kk" : state.lang;
  if (state.user) document.title = `${t(pageTitles[state.page])} · JanaМен`;
  if (announce) toast(t("langChanged"));
}

document.addEventListener("DOMContentLoaded", initApp);
