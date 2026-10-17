/**
 * JanaMen Digital HR — client controller.
 * Talks to the FastAPI backend with a bearer token kept in memory only.
 * Authorization is enforced server-side; the UI only hides what a role cannot use.
 * UI text is written in English and translated to RU/KZ by I18n (static/locales/catalog.json).
 */

const API_BASE = "/api/v1";

const state = {
  token: null,
  user: null,
  profile: null,
  page: "home",
  lang: I18n.savedLanguage(),
  notifications: [],
  courses: [],
  currentCourse: null,
  currentLesson: null,
  pendingReview: null,
};

let demoAccounts = {};

// --- HTTP ---
async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", "Accept-Language": localeCode(), ...(options.headers || {}) };
  if (state.token) headers["Authorization"] = `Bearer ${state.token}`;

  const tokenAtStart = state.token;
  const languageAtStart = state.lang;
  let res;
  try { res = await fetch(`${API_BASE}${path}`, { ...options, headers }); }
  catch { throw new Error(I18n.t("Unable to connect. Please try again.")); }
  const data = await res.json().catch(() => ({}));
  if (tokenAtStart !== state.token) throw new Error("Session changed; please retry.");
  if (languageAtStart !== state.lang) throw new Error("Language changed; please retry.");
  if (res.status === 401 && !path.includes("/auth/login")) showLogin();
  if (!res.ok) {
    const fields = data.error?.fields?.map(f => f.message).join("; ");
    throw new Error(fields || data.error?.message || data.detail || `Request failed (${res.status})`);
  }
  return data;
}

// List endpoints are paginated (limit ≤ 100); fetch every page.
async function apiAll(path) {
  const tokenAtStart = state.token;
  const languageAtStart = state.lang;
  const rows = [];
  for (let offset = 0; offset <= 1000000; offset += 100) {
    if (tokenAtStart !== state.token) throw new Error("Session changed; please retry.");
    if (languageAtStart !== state.lang) throw new Error("Language changed; please retry.");
    const page = await api(`${path}${path.includes("?") ? "&" : "?"}limit=100&offset=${offset}`);
    rows.push(...page);
    if (page.length < 100) return rows;
  }
  throw new Error("Too many results; narrow the filter.");
}

// --- HELPERS ---
function toast(msg) {
  // In-flight requests are deliberately cancelled when language or session changes.
  if (["Session changed; please retry.", "Language changed; please retry."]
      .some(reason => String(msg).includes(reason))) return;
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.classList.add("show");
  clearTimeout(window.toastTimer);
  window.toastTimer = setTimeout(() => el.classList.remove("show"), 3200);
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

const icon = name => `<svg class="ic"><use href="#i-${name}"/></svg>`;
const statusBadge = s => `<span class="status ${esc(s).toLowerCase()}">${esc(s)}</span>`;
const initials = name => name.split(/\s+/).slice(0, 2).map(p => p[0] || "").join("").toUpperCase();

function localeCode() { return state.lang === "kz" ? "kk-KZ" : "ru-RU"; }
function formatDate(value) {
  const date = new Date(value.length === 10 ? `${value}T12:00:00` : value);
  const months = state.lang === "kz"
    ? ["қаңтар", "ақпан", "наурыз", "сәуір", "мамыр", "маусым", "шілде", "тамыз", "қыркүйек", "қазан", "қараша", "желтоқсан"]
    : ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"];
  return `${date.getDate()} ${months[date.getMonth()]} ${date.getFullYear()} ${state.lang === "kz" ? "ж." : "г."}`;
}
function formatTime(value) { return new Date(value).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit", hour12: false }); }
const PROFILE_FIELDS = { phone: "Phone", location: "Location", emergency_contact: "Emergency contact" };
function formatPeriod(request) {
  // " · " parts are translated one by one by I18n.
  if (request.type === "Profile update") return Object.keys(request.profile_changes || {}).map(f => PROFILE_FIELDS[f] || f).join(" · ");
  const start = formatDate(request.start_date);
  if (request.type === "Advance payment") return `${new Intl.NumberFormat("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(request.amount)} ₸ · ${start}`;
  return request.end_date && request.end_date !== request.start_date ? `${start} — ${formatDate(request.end_date)}` : start;
}

// Every day of a vacation, marked: weekends are charged, public holidays are not (server rule).
// booked: the employee's other active vacations, outlined so their exact dates are visible.
function renderLeaveCalendar(cal, booked = []) {
  const days = cal ? cal.days : [];
  const byDay = Object.fromEntries(days.map(d => [d.day, d]));
  const kindLabel = { workday: "Working day", weekend: "Weekend", holiday: "Public holiday" };
  const bookedOn = iso => booked.find(b => b.start_date <= iso && iso <= (b.end_date || b.start_date));
  const monthKeys = new Set(days.map(d => d.day.slice(0, 7)));
  booked.forEach(b => {
    for (const d = new Date(`${b.start_date}T12:00:00Z`); d <= new Date(`${b.end_date || b.start_date}T12:00:00Z`); d.setUTCDate(d.getUTCDate() + 1)) {
      monthKeys.add(d.toISOString().slice(0, 7));
    }
  });
  const monthNames = state.lang === "kz"
    ? ["Қаңтар", "Ақпан", "Наурыз", "Сәуір", "Мамыр", "Маусым", "Шілде", "Тамыз", "Қыркүйек", "Қазан", "Қараша", "Желтоқсан"]
    : ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"];
  const months = [...monthKeys].sort().map(ym => {
    const [year, month] = ym.split("-").map(Number);
    const lead = (new Date(Date.UTC(year, month - 1, 1)).getUTCDay() + 6) % 7;
    const total = new Date(Date.UTC(year, month, 0)).getUTCDate();
    const cells = Array.from({ length: total }, (_, i) => {
      const iso = `${ym}-${String(i + 1).padStart(2, "0")}`;
      const d = byDay[iso];
      const b = bookedOn(iso);
      const classes = ["cal-day", d?.kind, b && "booked"].filter(Boolean).join(" ");
      const title = [d && (d.holiday || kindLabel[d.kind]), b && `${b.request_code} · ${b.status}`].filter(Boolean).join(" · ");
      return `<span class="${classes}"${title ? ` title="${esc(title)}"` : ""}>${i + 1}</span>`;
    });
    return `<div class="cal-month"><b data-verbatim>${monthNames[month - 1]} ${year}</b><div class="cal-grid">
      ${["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map(w => `<span class="cal-wd">${w}</span>`).join("")}
      ${"<span></span>".repeat(lead)}${cells.join("")}</div></div>`;
  }).join("");
  const holidays = days.filter(d => d.kind === "holiday")
    .map(d => `<li><span data-verbatim>${esc(formatDate(d.day))}</span> — <span>${esc(d.holiday)}</span></li>`).join("");
  const plans = booked.map(b => `<li><b data-verbatim>${esc(formatPeriod(b))}</b> · <span data-verbatim>${esc(b.request_code)}</span> · <span>${esc(b.status)}</span></li>`).join("");
  const num = value => Math.round(Number(value) * 10) / 10;
  return `<div class="leave-cal">
    ${cal ? `<div class="cal-summary">
      <span><span>Calendar days</span> <b>${cal.days.length}</b></span>
      <span class="weekend"><span>Weekends (charged)</span> <b>${cal.weekend_days}</b></span>
      <span class="holiday"><span>Public holidays (not charged)</span> <b>${cal.holiday_days}</b></span>
      <span class="charged"><span>Will be charged</span> <b>${num(cal.charged_days)}</b></span>
    </div>` : ""}
    ${plans ? `<div class="cal-plans"><b>Your planned vacations</b><ul>${plans}</ul></div>` : ""}
    <div class="cal-legend"><span><i class="workday"></i><span>Working day</span></span><span><i class="weekend"></i><span>Weekend</span></span><span><i class="holiday"></i><span>Public holiday</span></span>${plans ? `<span><i class="booked"></i><span>Your vacation</span></span>` : ""}</div>
    <div class="cal-months">${months}</div>
    ${holidays ? `<ul class="cal-holidays">${holidays}</ul>` : ""}
    <p class="muted small">Annual leave is counted in calendar days: weekends are charged, public holidays are not.</p>
  </div>`;
}

function renderProfileChanges(changes) {
  return `<div class="table-wrap"><table class="table table-compact">
    <thead><tr><th>Field</th><th>Current</th><th>New value</th></tr></thead>
    <tbody>${Object.entries(changes).map(([field, c]) => `
      <tr><td>${esc(PROFILE_FIELDS[field] || field)}</td><td>${esc(c.from || "—")}</td><td><b>${esc(c.to)}</b></td></tr>`).join("")}</tbody>
  </table></div>`;
}

function greetingText() {
  const hour = new Date().getHours();
  const word = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
  return `${word}, ${state.user.full_name.split(" ")[0]}`;
}

// --- INITIALIZATION & AUTH ---
async function initApp() {
  try { await I18n.load(); }
  catch (error) { document.getElementById("loginError").textContent = error.message; return; }

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
    document.getElementById("loginHint").textContent = config.demo_mode
      ? "Synthetic demo. Use a test account and the demo password configured by the operator."
      : "Use your account email and password.";
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
   "chatMessages", "playerLessonsList", "playerQuizOptions", "detailModalTimeline", "profCourses",
   "teamDirectory", "adminDirectory", "employeeModalBody", "employeeModalName", "teamHistory",
   "detailModalTitle", "detailModalCode", "detailModalRequester", "detailModalDept", "detailModalDates",
   "detailModalSync", "playerCourseTitle", "playerLessonTitle", "playerQuizQuestion", "playerQuizFeedback",
   "citationDocTitle", "citationSecTitle"]
    .forEach(id => document.getElementById(id)?.replaceChildren());
  document.querySelectorAll('[id^="prof"], #userName, #userRole, #avatar, #greeting, #citationSnippet, #playerLessonContent')
    .forEach(el => { if (el.childElementCount === 0) el.textContent = "—"; });
  document.querySelectorAll("#app form").forEach(form => form.reset());
  document.getElementById("loginEmail").value = email;
  document.getElementById("loginPassword").value = "";
  document.getElementById("loginGate").hidden = false;
  document.title = I18n.t("JanaМен · People Workspace");
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

const ROLE_ACCESS = { manager: ["manager"], hr_admin: ["hr_admin"] };

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
  home: "Overview", profile: "My profile", requests: "My requests", academy: "Jana Academy",
  assistant: "AI Jana", notifications: "Notifications", team: "Team & approvals", admin: "HR administration",
};

async function go(page) {
  if (!state.token) { showLogin(); return; }
  if (page === "team" && state.user?.role === "hr_admin") {
    go("admin");
    return;
  }
  if (page === "team" && !ROLE_ACCESS.manager.includes(state.user?.role)) {
    toast("Access denied: Team workspace requires a manager role.");
    return;
  }
  if (page === "admin" && state.user?.role !== "hr_admin") {
    toast("Access denied: HR Administration is reserved for HR administrators.");
    return;
  }
  state.page = page;
  document.querySelectorAll(".page").forEach(p => p.classList.toggle("active", p.id === `page-${page}`));
  document.querySelectorAll("[data-page]").forEach(b => b.classList.toggle("active", b.dataset.page === page));
  document.getElementById("navLinks").classList.remove("open");
  document.getElementById("menuBtn").setAttribute("aria-expanded", "false");
  document.title = `${I18n.t(pageTitles[page])} · JanaМен`;
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

function notificationIcon(type) {
  return icon(type === "ACADEMY" ? "book" : type === "REQUEST" ? "file" : "bell");
}

async function loadDashboard() {
  try {
    const [data, courses, notifications, requests] = await Promise.all([
      api("/me/dashboard"), apiAll("/courses"), api("/notifications?limit=3"), apiAll("/requests"),
    ]);
    document.getElementById("greeting").textContent = greetingText();
    document.getElementById("leaveDays").textContent = data.leave_balance_days.toFixed(1);
    document.getElementById("statRequests").textContent = data.open_requests_count;
    document.getElementById("statLearning").textContent = `${Math.round(data.learning_progress_percent)}%`;
    document.getElementById("statCourses").textContent = data.assigned_courses_count;
    document.getElementById("statNotifications").textContent = data.unread_notifications_count;

    document.getElementById("homeRequests").innerHTML = requests.length ? requests.slice(0, 4).map(r => `
      <div class="request-row">
        <div class="req-icon">${icon(r.type === "Vacation" ? "calendar" : "wallet")}</div>
        <div>
          <div class="req-title">${esc(r.type)}</div>
          <div class="req-sub"><span data-verbatim>${esc(r.request_code)}</span> · ${esc(formatPeriod(r))}</div>
        </div>
        ${statusBadge(r.status)}
      </div>`).join("") : `<div class="empty">No requests yet.</div>`;

    const assigned = courses.filter(c => c.assigned);
    const next = assigned.find(c => c.status !== "COMPLETED") || assigned[0];
    const banner = document.getElementById("homeCourseCard");
    banner.innerHTML = next ? `
      <div>
        <h2 class="h2">${esc(next.title)}</h2>
        <p>Jana Academy · ${next.total_lessons} lessons · ${Math.round(next.progress_percent)}% complete</p>
        <div class="progress"><span style="width:${next.progress_percent}%"></span></div>
      </div>
      <button class="btn btn-white" data-course="${next.id}"><span>${next.status === "COMPLETED" ? "Review course" : "Continue learning"}</span>${icon("arrow")}</button>`
      : `<div><h2 class="h2">Jana Academy</h2><p>No courses assigned. Explore Jana Academy to enroll.</p></div>
         <button class="btn btn-white" data-open-academy><span>All courses</span>${icon("arrow")}</button>`;
    banner.querySelector("[data-course]")?.addEventListener("click", e => openCoursePlayer(Number(e.currentTarget.dataset.course)));
    banner.querySelector("[data-open-academy]")?.addEventListener("click", () => go("academy"));

    document.getElementById("homeActivity").innerHTML = notifications.length ? notifications.map(n => `
      <article class="update-card">
        <span class="notice-icon">${notificationIcon(n.type)}</span>
        <b>${esc(n.title)}</b>
        <p>${esc(n.message)}</p>
        <small>${esc(n.time_ago)}</small>
      </article>`).join("") : `<div class="empty">No updates yet.</div>`;
  } catch (err) {
    toast(`Error: ${err.message}`);
  }
}

// --- PROFILE ---
async function loadProfilePage() {
  try {
    const [p, notifications] = await Promise.all([api("/me/profile"), api("/notifications?limit=3")]);
    document.getElementById("profNotifications").innerHTML = notifications.length ? notifications.map(n => `
      <div class="course-line">
        <span class="notice-icon">${notificationIcon(n.type)}</span>
        <div><b>${esc(n.title)}</b><div class="req-sub">${esc(n.time_ago)}</div></div>
        ${n.is_read ? "" : `<span class="unread-dot" aria-label="unread"></span>`}
      </div>`).join("") : `<div class="empty">No updates yet.</div>`;
    document.getElementById("profAvatar").textContent = initials(p.full_name);
    document.getElementById("profName").textContent = p.full_name;
    document.getElementById("profPosition").textContent = p.position;
    document.getElementById("profEmpCode").textContent = p.employee_code;
    document.getElementById("profDept").textContent = p.department;
    document.getElementById("profCompany").textContent = p.company;
    document.getElementById("profManager").textContent = p.manager_name || "None (Department Head)";
    document.getElementById("profHireDate").textContent = formatDate(p.hire_date);
    document.getElementById("profLocation").textContent = p.location;
    document.getElementById("profPhone").textContent = p.phone || "—";
    document.getElementById("profEmergency").textContent = p.emergency_contact || "—";
    state.profile = p;
    const pending = document.getElementById("profPending");
    pending.hidden = !p.pending_profile_change;
    pending.innerHTML = p.pending_profile_change ? `<b>Awaiting approval</b>${renderProfileChanges(p.pending_profile_change)}` : "";
    document.getElementById("editProfileBtn").disabled = Boolean(p.pending_profile_change);
    document.getElementById("profLeaveBalance").textContent = days(p.leave_balance_days);
    document.getElementById("profLearningPct").textContent = `${Math.round(p.learning_progress_percent)}%`;
    document.getElementById("profCourses").innerHTML = p.courses.length ? p.courses.map(c => `
      <div class="course-line">
        <span class="notice-icon">${icon(c.status === "COMPLETED" ? "check" : "book")}</span>
        <div>
          <b>${esc(c.title)}</b>
          <div class="req-sub"><span>${c.is_mandatory ? "Mandatory" : "Recommended"}</span>${c.due_date ? ` · <span>Due ${esc(formatDate(c.due_date))}</span>` : ""}${c.score === null ? "" : ` · <span>${Math.round(c.score)}% lessons passed</span>`}</div>
          <div class="progress"><span style="width:${c.progress_percent}%"></span></div>
        </div>
      </div>`).join("") : `<div class="empty">No courses assigned.</div>`;
  } catch (err) {
    toast(`Error: ${err.message}`);
  }
}

// --- REQUESTS ---
async function loadRequestsPage() {
  const params = new URLSearchParams();
  const sf = document.getElementById("statusFilter").value;
  const tf = document.getElementById("typeFilter").value;
  if (sf !== "all") params.set("status", sf);
  if (tf !== "all") params.set("type", tf);
  try {
    const query = params.toString();
    const requests = await apiAll(`/requests${query ? `?${query}` : ""}`);
    document.getElementById("requestTable").innerHTML = requests.length ? requests.map(r => `
      <tr>
        <td><b>${esc(r.type)}</b><div class="req-sub" data-verbatim>${esc(r.request_code)}</div></td>
        <td>${esc(formatDate(r.created_at))}</td>
        <td>${esc(formatPeriod(r))}<div class="req-sub">${esc(r.reason || "No comment")}</div></td>
        <td>${statusBadge(r.status)}</td>
        <td><button class="text-link" onclick="openRequestDetailModal(${r.id})">Details</button></td>
      </tr>`).join("")
      : `<tr><td colspan="5" class="empty">No requests found.</td></tr>`;
  } catch (err) {
    toast(`Error: ${err.message}`);
  }
}

// --- JANA ACADEMY ---
async function loadAcademyPage() {
  try {
    const courses = await apiAll("/courses");
    state.courses = courses;
    document.getElementById("academyGrid").innerHTML = courses.map(c => {
      const done = c.status === "COMPLETED";
      const action = done ? "Review course" : c.progress_percent > 0 ? "Continue learning" : c.assigned ? "Start course" : "Enroll";
      return `
      <article class="card course-tile ${c.is_mandatory ? "mandatory" : ""}">
        <div class="course-art">${icon(done ? "award" : "book")}</div>
        <div class="course-meta">
          <span class="chip">${c.is_mandatory ? "Mandatory" : "Recommended"}</span>
          <span class="chip">${c.duration_minutes} min</span>
          ${done ? `<span class="status approved">Passed ${Math.round(c.score ?? 100)}% ✓</span>` : ""}
        </div>
        <h3 class="h4">${esc(c.title)}</h3>
        <p>${esc(c.description)}</p>
        <div>
          <div class="progress"><span style="width:${c.progress_percent}%"></span></div>
          <div class="progress-label">
            <span>${Math.round(c.progress_percent)}% complete</span>
            <span>${c.assigned ? (c.due_date ? `Due ${esc(formatDate(c.due_date))}` : "Assigned") : "Available to enroll"}</span>
          </div>
        </div>
        <button class="btn ${done ? "btn-light" : "btn-primary"}" onclick="openCoursePlayer(${c.id})"><span>${action}</span>${icon("arrow")}</button>
      </article>`;
    }).join("");
  } catch (err) {
    toast(`Error: ${err.message}`);
  }
}

// --- NOTIFICATIONS ---
async function loadNotificationsPage() {
  try {
    const notifs = await apiAll("/notifications");
    state.notifications = notifs;
    document.getElementById("notificationsList").innerHTML = notifs.length ? notifs.map(n => `
      <button class="notice" onclick="markNotificationRead(${n.id})">
        <span class="notice-icon">${notificationIcon(n.type)}</span>
        <span style="flex:1">
          <b>${esc(n.title)}</b>
          <p>${esc(n.message)}</p>
          <p class="small">${esc(n.time_ago)}</p>
        </span>
        ${n.is_read ? "" : `<span class="unread-dot" aria-label="unread"></span>`}
      </button>`).join("")
      : `<div class="empty">No notifications in your inbox.</div>`;
  } catch (err) {
    toast(`Error: ${err.message}`);
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
    toast("All notifications marked as read.");
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
const days = value => `${Math.round(Number(value) * 10) / 10} days`;

// Leave figures next to each pending request, so the approver sees the effect before deciding.
function leaveImpact(request, member) {
  if (!member || request.type !== "Vacation") return "—";
  const after = member.leave_balance_days - (request.vacation_days ?? 0);
  return `<b>${days(member.leave_balance_days)}</b><div class="req-sub">after approval: ${days(after)}</div>
    <div class="req-sub"><span>Weekends</span>: ${request.weekend_days ?? 0} · <span>Holidays</span>: ${request.holiday_days ?? 0}</div>`;
}

function renderDirectory(tbodyId, members) {
  const tbody = document.getElementById(tbodyId);
  tbody.innerHTML = members.length ? members.map(m => `
    <tr class="clickable" tabindex="0" data-employee="${m.user_id}">
      <td><b>${esc(m.full_name)}</b><div class="req-sub" data-verbatim>${esc(m.employee_code)}</div></td>
      <td>${esc(m.position)}<div class="req-sub">${esc(m.department)}</div></td>
      <td><b>${days(m.leave_balance_days)}</b></td>
      <td>${days(m.used_days)}</td>
      <td>${days(m.pending_days)}</td>
      <td><b class="green">${days(m.available_days)}</b></td>
      <td>${Math.round(m.learning_progress_percent)}%</td>
    </tr>`).join("") : `<tr><td colspan="7" class="empty">No employees in your scope.</td></tr>`;
  tbody.querySelectorAll("[data-employee]").forEach(row => {
    const open = () => openEmployeeCard(Number(row.dataset.employee));
    row.addEventListener("click", open);
    row.addEventListener("keydown", e => { if (e.key === "Enter") open(); });
  });
}

async function openEmployeeCard(userId) {
  try {
    const e = await api(`/manager/team/${userId}`);
    document.getElementById("employeeModalName").textContent = e.full_name;
    const stat = (value, label, green) => `<div class="mini-stat ${green ? "green" : ""}"><strong>${days(value)}</strong><span>${label}</span></div>`;
    document.getElementById("employeeModalBody").innerHTML = `
      <p class="muted">${esc(e.position)} · ${esc(e.department)}</p>
      <div class="mini-stats">
        ${stat(e.leave_balance_days, "Leave balance")}${stat(e.used_days, "Used")}
        ${stat(e.pending_days, "Pending")}${stat(e.available_days, "Available", true)}
      </div>
      <dl class="detail-grid">
        <div class="detail"><dt>Employee ID</dt><dd data-verbatim>${esc(e.employee_code)}</dd></div>
        <div class="detail"><dt>Company</dt><dd>${esc(e.company)}</dd></div>
        <div class="detail"><dt>Manager</dt><dd>${esc(e.manager_name || "—")}</dd></div>
        <div class="detail"><dt>Hire date</dt><dd>${esc(formatDate(e.hire_date))}</dd></div>
        <div class="detail"><dt>Location</dt><dd>${esc(e.location)}</dd></div>
        <div class="detail"><dt>Learning progress</dt><dd>${Math.round(e.learning_progress_percent)}%</dd></div>
        <div class="detail"><dt>Phone</dt><dd data-verbatim>${esc(e.phone || "—")}</dd></div>
      </dl>
      ${e.email ? `
      <h4 class="sub-title"><span>Personal and account data</span> · <span>Visible to HR only</span></h4>
      <dl class="detail-grid">
        <div class="detail"><dt>Email</dt><dd data-verbatim>${esc(e.email)}</dd></div>
        <div class="detail"><dt>Role</dt><dd>${esc(e.role)}</dd></div>
        <div class="detail"><dt>Account status</dt><dd>${e.is_active ? "Active" : "Disabled"}</dd></div>
        <div class="detail"><dt>Emergency contact</dt><dd data-verbatim>${esc(e.emergency_contact || "—")}</dd></div>
        <div class="detail"><dt>Account created</dt><dd>${esc(formatDate(e.account_created_at))}</dd></div>
        <div class="detail"><dt>Last sign-in</dt><dd>${e.last_sign_in_at ? esc(`${formatDate(e.last_sign_in_at)} ${formatTime(e.last_sign_in_at)}`) : "Never"}</dd></div>
      </dl>` : ""}
      <h4 class="sub-title">Vacation and request history</h4>
      <div class="table-wrap"><table class="table">
        <thead><tr><th>Request</th><th>Period / details</th><th>Days</th><th>Status</th></tr></thead>
        <tbody>${e.requests.length ? e.requests.map(r => `
          <tr>
            <td><b>${esc(r.type)}</b><div class="req-sub" data-verbatim>${esc(r.request_code)}</div></td>
            <td>${esc(formatPeriod(r))}</td>
            <td>${r.vacation_days == null ? "—" : days(r.vacation_days)}</td>
            <td>${statusBadge(r.status)}</td>
          </tr>`).join("") : `<tr><td colspan="4" class="empty">No requests yet.</td></tr>`}</tbody>
      </table></div>
      <h4 class="sub-title">Training</h4>
      ${e.courses.length ? e.courses.map(c => `
        <div class="course-line">
          <span class="notice-icon">${icon(c.status === "COMPLETED" ? "check" : "book")}</span>
          <div>
            <b>${esc(c.title)}</b>
            <div class="req-sub"><span>${Math.round(c.progress_percent)}% complete</span>${c.score === null ? "" : ` · <span>${Math.round(c.score)}% lessons passed</span>`}</div>
            <div class="progress"><span style="width:${c.progress_percent}%"></span></div>
          </div>
        </div>`).join("") : `<div class="empty">No courses assigned.</div>`}
      <h4 class="sub-title">History</h4>
      <div class="timeline">${e.history.length ? e.history.map(h => `
        <div class="activity">
          <span class="activity-dot ${["APPROVED", "COURSE_COMPLETED", "LESSON_PASSED"].includes(h.event) ? "ok" : h.event === "REJECTED" ? "bad" : ""}"></span>
          <div>
            <b><span>${esc(h.event)}</span> · <span ${h.kind === "request" ? "data-verbatim" : ""}>${esc(h.reference)}</span></b>
            <p>${h.detail ? `<span>${esc(h.detail)}</span> · ` : ""}${h.actor ? `<span>${esc(h.actor)}</span> · ` : ""}${esc(formatDate(h.at))} ${esc(formatTime(h.at))}</p>
          </div>
        </div>`).join("") : `<div class="empty">No history yet.</div>`}</div>`;
    document.getElementById("employeeModal").classList.add("open");
  } catch (err) {
    toast(err.message);
  }
}

async function loadTeamPage() {
  try {
    const [requests, members] = await Promise.all([apiAll("/manager/requests?status=Pending"), apiAll("/manager/team")]);
    const byUser = Object.fromEntries(members.map(m => [m.user_id, m]));
    document.getElementById("teamScope").textContent = state.user.role === "hr_admin" ? "Company" : "Direct reports";
    document.getElementById("teamCount").textContent = members.length;
    document.getElementById("teamPendingStat").textContent = requests.length;
    document.getElementById("teamPendingBadge").textContent = `${requests.length} pending`;
    document.getElementById("teamTable").innerHTML = requests.length ? requests.map(r => `
      <tr>
        <td><button class="text-link" onclick="openEmployeeCard(${r.user_id})"><b>${esc(r.user_name)}</b></button><div class="req-sub">${esc(r.department)}</div></td>
        <td>${esc(r.type)}<div class="req-sub" data-verbatim>${esc(r.request_code)}</div></td>
        <td>${esc(formatPeriod(r))}<div class="req-sub">${esc(r.reason || "No comment")}</div></td>
        <td>${leaveImpact(r, byUser[r.user_id])}</td>
        <td>${statusBadge(r.status)}</td>
        <td style="white-space:nowrap">
          <button class="small-btn primary" onclick="reviewRequestPrompt(${r.id}, 'approve')">Approve</button>
          <button class="small-btn danger" onclick="reviewRequestPrompt(${r.id}, 'reject')">Decline</button>
          <button class="text-link" onclick="openRequestDetailModal(${r.id})">Details</button>
        </td>
      </tr>`).join("")
      : `<tr><td colspan="6" class="empty">No pending requests from your team.</td></tr>`;
    renderDirectory("teamDirectory", members);
    const history = await api("/manager/requests?limit=100");
    document.getElementById("teamHistory").innerHTML = history.length ? history.map(r => `
      <tr>
        <td><button class="text-link" onclick="openEmployeeCard(${r.user_id})"><b>${esc(r.user_name)}</b></button></td>
        <td>${esc(r.type)}<div class="req-sub" data-verbatim>${esc(r.request_code)}</div></td>
        <td>${esc(formatPeriod(r))}</td>
        <td>${r.vacation_days == null ? "—" : days(r.vacation_days)}</td>
        <td>${statusBadge(r.status)}</td>
        <td>${esc(r.reviewer_name || "—")}<div class="req-sub">${esc(formatDate(r.updated_at))}</div></td>
      </tr>`).join("") : `<tr><td colspan="6" class="empty">No requests yet.</td></tr>`;
  } catch (err) {
    toast(`Error: ${err.message}`);
  }
}

function reviewRequestPrompt(requestId, action) {
  state.pendingReview = { requestId, action };
  const approve = action === "approve";
  document.getElementById("reviewTitle").textContent = approve ? "Approve request" : "Decline request";
  document.getElementById("reviewComment").value = "";
  document.getElementById("submitReview").textContent = approve ? "Confirm approval" : "Confirm rejection";
  document.getElementById("reviewModal").classList.add("open");
}

// --- HR ADMIN ---
async function loadAdminPage() {
  try {
    const [summary, chunks, documents, adapters, logs, requests, members] = await Promise.all([
      api("/admin/summary"), apiAll("/admin/knowledge"), apiAll("/admin/knowledge/documents"),
      api("/admin/integrations"), api("/admin/audit?limit=15"),
      apiAll("/manager/requests?status=Pending"), apiAll("/manager/team"),
    ]);
    const byUser = Object.fromEntries(members.map(m => [m.user_id, m]));
    renderDirectory("adminDirectory", members);
    document.getElementById("adminEmployeeCount").textContent = summary.active_accounts;
    document.getElementById("adminKnowledgeCount").textContent = chunks.length;
    document.getElementById("adminPendingBadge").textContent = `${requests.length} pending`;
    document.getElementById("adminApprovalsTable").innerHTML = requests.length ? requests.map(r => `
      <tr>
        <td><button class="text-link" onclick="openEmployeeCard(${r.user_id})"><b>${esc(r.user_name)}</b></button><div class="req-sub">${esc(r.department)}</div></td>
        <td>${esc(r.type)}<div class="req-sub" data-verbatim>${esc(r.request_code)}</div></td>
        <td>${esc(formatPeriod(r))}<div class="req-sub">${esc(r.reason || "No comment")}</div></td>
        <td>${leaveImpact(r, byUser[r.user_id])}</td>
        <td>${statusBadge(r.status)}</td>
        <td style="white-space:nowrap">
          <button class="small-btn primary" onclick="reviewRequestPrompt(${r.id}, 'approve')">Approve</button>
          <button class="small-btn danger" onclick="reviewRequestPrompt(${r.id}, 'reject')">Decline</button>
          <button class="text-link" onclick="openRequestDetailModal(${r.id})">Details</button>
        </td>
      </tr>`).join("")
      : `<tr><td colspan="6" class="empty">No pending requests across the company.</td></tr>`;

    document.getElementById("knowledgeList").innerHTML = chunks.map(c => `
      <div class="notice">
        <span class="notice-icon">${icon("file")}</span>
        <div style="flex:1">
          <b>${esc(c.document_title)} · ${esc(c.section_title)}</b>
          <p>${c.is_approved ? "Approved" : "Draft"}${c.is_synthetic ? " · Synthetic example" : ""}</p>
          <details><summary>Review full source text</summary><p data-verbatim style="white-space:pre-wrap">${esc(c.content)}</p></details>
        </div>
      </div>`).join("");

    const documentList = document.getElementById("knowledgeDocuments");
    documentList.innerHTML = documents.map(doc => {
      const ownChunks = chunks.filter(c => c.document_id === doc.id);
      const reviewedRevision = ownChunks.length ? Math.min(...ownChunks.map(c => c.document_revision)) : doc.revision;
      return `
      <div class="notice">
        <span class="notice-icon">${icon("book")}</span>
        <div style="flex:1">
          <b>${esc(doc.title)} · v${esc(doc.version)}</b>
          <p>${doc.is_synthetic ? "Synthetic example · " : ""}${doc.is_approved ? "Approved" : "Draft"} · ${doc.is_active ? "Active" : "Inactive"}</p>
          ${!doc.is_approved && doc.is_active ? `<button class="small-btn primary" data-approve-document="${doc.id}" data-revision="${reviewedRevision}">Approve reviewed source</button>` : ""}
          ${doc.is_active ? `<button class="small-btn" data-deactivate-document="${doc.id}" data-revision="${doc.revision}">Deactivate</button>` : ""}
        </div>
      </div>`;
    }).join("");
    documentList.querySelectorAll("[data-approve-document], [data-deactivate-document]").forEach(button => {
      button.addEventListener("click", async () => {
        try {
          const id = button.dataset.approveDocument || button.dataset.deactivateDocument;
          const change = button.dataset.approveDocument ? { is_approved: true } : { is_active: false };
          await api(`/admin/knowledge/documents/${id}`, { method: "PATCH",
            body: JSON.stringify({ ...change, expected_revision: Number(button.dataset.revision) }) });
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
        <td><code>${esc(I18n.t(l.action))}</code></td>
        <td>${esc(l.actor_name)}</td>
        <td>${esc(I18n.t(l.target_type || "—"))}: ${esc(l.target_id || "—")}</td>
        <td>${esc(formatTime(l.timestamp))}</td>
      </tr>`).join("");
  } catch (err) {
    toast(`Error: ${err.message}`);
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
        title: form.elements.title.value, language: state.lang === "kz" ? "kk" : "ru", is_synthetic: form.elements.synthetic.checked,
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
  document.querySelectorAll(".modal-backdrop").forEach(backdrop => {
    backdrop.addEventListener("click", e => { if (e.target === backdrop) backdrop.classList.remove("open"); });
  });
  document.addEventListener("keydown", e => {
    if (e.key === "Escape") document.querySelectorAll(".modal-backdrop").forEach(m => m.classList.remove("open"));
  });
  ["closeModal", "cancelModal", "closeDetailModal", "closeCourseModal", "closeCitationModal", "cancelReview", "closeEmployeeModal", "closeContactModal", "cancelContactModal"].forEach(id => {
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
      toast(`${result.request_code} ${result.status.toLowerCase()}`);
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

  // Mirror the server rule (today in Kazakhstan, UTC+5, up to one year ahead) in the picker.
  const isoDay = offsetDays => new Date(Date.now() + 5 * 3600e3 + offsetDays * 86400e3).toISOString().slice(0, 10);
  const reqStart = document.getElementById("reqStart");
  const reqEnd = document.getElementById("reqEnd");
  reqStart.addEventListener("change", () => { reqEnd.min = reqStart.value || reqStart.min; });

  // Live day breakdown while dates are picked; submit is blocked when the balance is short.
  const reqCalendar = document.getElementById("reqCalendar");
  const reqSubmit = document.querySelector('#requestForm button[type="submit"]');
  let previewSeq = 0;
  // The employee's pending/approved vacations still ahead, shown before any date is picked.
  const loadBookedLeave = async () => {
    try {
      const today = isoDay(0);
      state.bookedLeave = (await apiAll("/requests?type=Vacation"))
        .filter(r => r.status !== "Rejected" && (r.end_date || r.start_date) >= today)
        .sort((a, b) => a.start_date.localeCompare(b.start_date));
    } catch { state.bookedLeave = []; }
  };
  const previewLeave = async () => {
    const start = reqStart.value;
    const end = reqEnd.value || start;
    const seq = ++previewSeq;
    const booked = reqType.value === "Vacation" ? state.bookedLeave || [] : [];
    const picked = Boolean(start && end >= start);
    reqSubmit.disabled = false;
    reqCalendar.hidden = reqType.value !== "Vacation" || (!picked && !booked.length);
    if (reqCalendar.hidden) return;
    if (!picked) { reqCalendar.innerHTML = renderLeaveCalendar(null, booked); return; }
    try {
      const cal = await api(`/requests/leave-calendar?start_date=${start}&end_date=${end}`);
      if (seq !== previewSeq) return;
      const short = cal.charged_days > cal.available_days;
      const overlap = booked.filter(b => b.start_date <= end && (b.end_date || b.start_date) >= start);
      reqCalendar.innerHTML = renderLeaveCalendar(cal, booked) + `<p class="cal-balance ${short ? "bad" : ""}">
        <span>Available days</span>: <b>${Math.round(cal.available_days * 10) / 10}</b>${short ? ` · <span>Not enough leave days for these dates</span>` : ""}</p>
        ${overlap.length ? `<p class="cal-balance bad"><span>These dates overlap your vacation</span>: <span data-verbatim>${esc(overlap.map(b => `${formatPeriod(b)} (${b.request_code})`).join(", "))}</span></p>` : ""}`;
      reqSubmit.disabled = short || overlap.length > 0;
    } catch { reqCalendar.hidden = true; }
  };
  [reqStart, reqEnd, reqType].forEach(el => el.addEventListener("change", previewLeave));

  document.querySelectorAll('[data-action="new-request"]').forEach(b => {
    b.addEventListener("click", () => {
      if (b.dataset.type) reqType.value = b.dataset.type;
      reqStart.min = reqEnd.min = isoDay(0);
      reqStart.max = reqEnd.max = isoDay(365);
      syncRequestType();
      reqCalendar.hidden = true;
      loadBookedLeave().then(previewLeave);
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
      toast(`Request ${res.request_code} successfully created!`);
      document.getElementById("requestModal").classList.remove("open");
      e.target.reset();
      syncRequestType();
      previewLeave();
      await refreshCurrentPage();
    } catch (err) {
      toast(`Submission failed: ${err.message}`);
    } finally {
      submit.disabled = false;
    }
  });

  // Contact details change through a "Profile update" request; the approver applies it.
  const profileInputs = [["contactPhone", "phone"], ["contactLocation", "location"], ["contactEmergency", "emergency_contact"]];
  document.getElementById("editProfileBtn").addEventListener("click", () => {
    const p = state.profile || {};
    profileInputs.forEach(([id, field]) => { document.getElementById(id).value = p[field] || ""; });
    document.getElementById("contactReason").value = "";
    document.getElementById("contactModal").classList.add("open");
    document.getElementById("contactPhone").focus();
  });
  document.getElementById("contactForm").addEventListener("submit", async e => {
    e.preventDefault();
    const changes = {};
    profileInputs.forEach(([id, field]) => {
      const value = document.getElementById(id).value.trim();
      if (value && value !== (state.profile?.[field] || "")) changes[field] = value;
    });
    if (!Object.keys(changes).length) { toast("Change at least one field"); return; }
    const submit = e.target.querySelector('button[type="submit"]');
    submit.disabled = true;
    try {
      const reason = document.getElementById("contactReason").value.trim();
      await api("/requests", { method: "POST", body: JSON.stringify({ type: "Profile update", profile_changes: changes, reason: reason || null }) });
      document.getElementById("contactModal").classList.remove("open");
      toast("Profile changes were sent for approval");
      await refreshCurrentPage();
    } catch (err) {
      toast(err.message);
    } finally {
      submit.disabled = false;
    }
  });
}

async function openRequestDetailModal(id) {
  try {
    const r = await api(`/requests/${id}`);
    document.getElementById("detailModalTitle").innerHTML = `<span data-verbatim>${esc(r.request_code)}</span> · <span>${esc(r.type)}</span>`;
    document.getElementById("detailModalCode").textContent = r.request_code;
    document.getElementById("detailModalStatus").innerHTML = statusBadge(r.status);
    document.getElementById("detailModalRequester").textContent = r.user_name;
    document.getElementById("detailModalDept").textContent = r.department;
    document.getElementById("detailModalDates").textContent = formatPeriod(r);
    // Approvers see exactly which days are charged, or which profile fields change.
    document.getElementById("detailModalExtra").innerHTML = r.leave_days.length
      ? `<h4 class="sub-title">Day breakdown</h4>${renderLeaveCalendar({ days: r.leave_days, weekend_days: r.weekend_days, holiday_days: r.holiday_days, charged_days: r.vacation_days })}`
      : r.profile_changes ? `<h4 class="sub-title">Requested changes</h4>${renderProfileChanges(r.profile_changes)}` : "";
    document.getElementById("detailModalSync").textContent = r.external_sync_id || I18n.t("Documentolog is unconnected; no external registration");
    document.getElementById("detailModalTimeline").innerHTML = r.events.map(ev => `
      <div class="activity">
        <span class="activity-dot ${ev.event_type === "APPROVED" ? "ok" : ev.event_type === "REJECTED" ? "bad" : ""}"></span>
        <div>
          <b>${esc(ev.event_type)} by ${esc(ev.actor_name)}</b>
          <p>${ev.comment ? `<span>${esc(ev.comment)}</span> · ` : ""}${esc(formatDate(ev.created_at))} ${esc(formatTime(ev.created_at))}</p>
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
  document.getElementById("playerProgressLabel").textContent = `${Math.round(course.progress_percent)}% complete`;
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
  if (!selected) { toast("Please select an answer option."); return; }
  try {
    const res = await api(`/courses/lessons/${state.currentLesson.id}/quiz`, {
      method: "POST", body: JSON.stringify({ answer_index: parseInt(selected.value, 10) }),
    });
    const fb = document.getElementById("playerQuizFeedback");
    fb.hidden = false;
    fb.className = res.passed ? "ok" : "bad";
    fb.textContent = res.explanation;
    renderCourse(await api(`/courses/${state.currentCourse.id}`));
    if (res.course_completed) toast("🎉 Congratulations! You have successfully completed this course!");
    await refreshCurrentPage();
  } catch (err) {
    toast(`Quiz error: ${err.message}`);
  }
}

// --- AI JANA ---
async function loadKnowledgeSummary() {
  try {
    const documents = await apiAll("/ai/documents");
    document.getElementById("approvedKnowledgeList").innerHTML = documents.length
      ? documents.map(doc => `<div class="notice"><span class="notice-icon">${icon("file")}</span><div><b>${esc(doc.title)}</b><p>v${esc(doc.version)} · ${doc.is_synthetic ? "Synthetic example" : "Approved source"}</p></div></div>`).join("")
      : `<p class="muted">No approved sources are available for your account.</p>`;
  } catch (error) { toast(error.message); }
}

function resetChat() {
  document.getElementById("chatMessages").innerHTML = `<div class="message">Hi! I'm AI Jana. I assist Jana Post employees with HR policy questions. Every answer I provide is grounded in verified documentation and cites the exact source.<small>AI Jana · Ready to help</small></div>`;
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
  // data-question is translated by I18n, so the chips ask in the interface language.
  document.querySelectorAll("[data-question]").forEach(btn => btn.addEventListener("click", () => sendAIQuery(btn.dataset.question)));
  document.getElementById("clearChat").onclick = resetChat;
  resetChat();
}

async function sendAIQuery(question) {
  const container = document.getElementById("chatMessages");
  const userBubble = document.createElement("div");
  userBubble.className = "message user";
  userBubble.dataset.verbatim = "";
  userBubble.textContent = question;
  const botBubble = document.createElement("div");
  botBubble.className = "message";
  botBubble.innerHTML = `<i>Checking verified HR knowledge base…</i>`;
  container.append(userBubble, botBubble);
  container.scrollTop = container.scrollHeight;

  try {
    const res = await api("/ai/chat", { method: "POST", body: JSON.stringify({ question }) });
    let html = `<div data-verbatim style="white-space:pre-wrap">${esc(res.answer)}</div>`;
    if (res.sources?.length) {
      html += `<div class="citation-buttons">${res.sources.map((source, index) =>
        `<button class="source-pill" type="button" data-verbatim data-source-index="${index}">${icon("file")}${esc(source.document_title)} · ${esc(source.section_title)}</button>`).join("")}</div>`;
    }
    if (res.answer_status !== "grounded") {
      botBubble.classList.add("fallback");
      if (res.escalation_guidance) html += `<div class="fallback-note"><b>Safe Fallback:</b> <span data-verbatim>${esc(res.escalation_guidance)}</span></div>`;
    }
    html += `<small><span>AI Jana</span> · <span>${esc(res.answer_status)}</span>${res.engine?.startsWith("gemini") ? ` · <span data-verbatim>${esc(res.engine)}</span>` : ""} · <span>${Math.round(res.processing_time_ms)} ms</span></small>`;
    botBubble.innerHTML = html;
    botBubble.querySelectorAll("[data-source-index]").forEach(button => {
      const source = res.sources[Number(button.dataset.sourceIndex)];
      button.addEventListener("click", async () => {
        try {
          const full = await api(`/ai/sources/${source.chunk_id}?revision=${source.document_revision}&language=${source.language}`);
          document.getElementById("citationDocTitle").textContent = `${full.document_title} · v${full.version}`;
          document.getElementById("citationSecTitle").textContent = full.section_title;
          document.getElementById("citationSnippet").textContent =
            `${full.is_synthetic ? I18n.t("Synthetic example; not official HR policy.") + "\n\n" : ""}${full.content}`;
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
  document.querySelectorAll("[data-language-select]").forEach(select => {
    select.value = state.lang;
    select.addEventListener("change", async event => {
      state.lang = event.target.value;
      I18n.apply(state.lang);
      document.querySelectorAll(".modal-backdrop").forEach(modal => modal.classList.remove("open"));
      if (state.token) {
        try {
          const me = await api("/me");
          state.user = me.user;
          state.profile = me.profile;
          updateUserUI();
          document.title = `${I18n.t(pageTitles[state.page])} · JanaМен`;
          await refreshCurrentPage();
        } catch (error) { toast(error.message); }
      }
    });
  });
}

document.addEventListener("DOMContentLoaded", initApp);
