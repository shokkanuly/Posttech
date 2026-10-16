/**
 * JanaMen Digital HR - Core Application Client Controller
 * Connected to FastAPI backend with JWT authorization and real persistent data.
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
};

// Preset demo accounts with real backend passwords
const DEMO_ACCOUNTS = {
  employee: { email: "aruzhan@janapost.kz", password: "Password123!" },
  manager: { email: "timur@janapost.kz", password: "Password123!" },
  hr_admin: { email: "aigerim@janapost.kz", password: "Password123!" },
};

// --- HTTP CLIENT HELPERS ---
async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (state.token) {
    headers["Authorization"] = `Bearer ${state.token}`;
  }

  try {
    const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
    if (res.status === 401 && !path.includes("/auth/login")) {
      // Token expired, log in as default employee
      await switchRole("employee");
      return;
    }
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(data.detail || `Request failed (${res.status})`);
    }
    return data;
  } catch (err) {
    console.error("API error on", path, err);
    throw err;
  }
}

function toast(msg) {
  const el = document.getElementById("toast");
  if (!el) return;
  el.textContent = msg;
  el.classList.add("show");
  clearTimeout(window.toastTimer);
  window.toastTimer = setTimeout(() => el.classList.remove("show"), 3000);
}

function esc(s) {
  return String(s || "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// --- INITIALIZATION & AUTH ---
async function initApp() {
  // Bind listeners
  setupNavigation();
  setupRoleSwitch();
  setupLanguageSwitch();
  setupModals();
  setupAIChat();

  // Initial login with employee persona
  await switchRole("employee");
}

async function switchRole(roleKey) {
  const account = DEMO_ACCOUNTS[roleKey];
  if (!account) return;

  try {
    const loginData = await api("/auth/login", {
      method: "POST",
      body: JSON.stringify(account),
    });

    state.token = loginData.access_token;
    state.user = loginData.user;

    // Fetch full profile and dashboard
    const meData = await api("/me");
    state.profile = meData.profile;

    updateUserUI();
    await refreshCurrentPage();
    toast(`Authenticated as ${state.user.full_name} (${state.user.role})`);
  } catch (err) {
    toast(`Login error: ${err.message}`);
  }
}

function updateUserUI() {
  if (!state.user) return;

  const role = state.user.role;
  const parts = state.user.full_name.split(" ");
  const initials = parts.map(p => p[0]).join("").toUpperCase();

  document.getElementById("userName").textContent = state.user.full_name;
  document.getElementById("userRole").textContent = state.profile ? state.profile.position : role;
  document.getElementById("avatar").textContent = initials;
  document.getElementById("roleSwitch").value = role;

  // Manage navigation visibility by role
  const teamNav = document.getElementById("teamNav");
  const adminNav = document.getElementById("adminNav");

  teamNav.style.display = (role === "manager" || role === "hr_admin") ? "flex" : "none";
  adminNav.style.display = (role === "hr_admin") ? "flex" : "none";

  // If user was on a page they no longer have access to, redirect
  if (role === "employee" && (state.page === "team" || state.page === "admin")) {
    go("home");
  } else if (role === "manager" && state.page === "admin") {
    go("team");
  }
}

// --- NAVIGATION ---
function setupNavigation() {
  document.getElementById("nav").addEventListener("click", e => {
    const btn = e.target.closest("[data-page]");
    if (btn) go(btn.dataset.page);
  });

  document.querySelectorAll("[data-goto]").forEach(el => {
    el.addEventListener("click", () => go(el.dataset.goto));
  });

  const menuBtn = document.getElementById("menuBtn");
  if (menuBtn) {
    menuBtn.addEventListener("click", () => {
      document.getElementById("sidebar").classList.toggle("open");
    });
  }
}

const pageTitles = {
  home: "Overview",
  profile: "My profile",
  requests: "My requests",
  academy: "Jana Academy",
  assistant: "AI Jana",
  notifications: "Notifications",
  team: "Team & approvals",
  admin: "HR administration",
};

async function go(page) {
  // Check permission
  if (page === "team" && state.user?.role === "employee") {
    toast("Access denied: Team workspace requires a manager or HR admin role.");
    return;
  }
  if (page === "admin" && state.user?.role !== "hr_admin") {
    toast("Access denied: HR Administration is reserved for HR administrators.");
    return;
  }

  state.page = page;

  // Toggle page visibility
  document.querySelectorAll(".page").forEach(p => p.classList.remove("active"));
  const targetPage = document.getElementById(`page-${page}`);
  if (targetPage) targetPage.classList.add("active");

  // Toggle nav buttons
  document.querySelectorAll("[data-page]").forEach(b => {
    b.classList.toggle("active", b.dataset.page === page);
  });

  // Update breadcrumb
  const crumb = document.getElementById("crumb");
  if (crumb) crumb.textContent = pageTitles[page] || page;

  // Close mobile sidebar if open
  document.getElementById("sidebar")?.classList.remove("open");

  window.scrollTo({ top: 0, behavior: "smooth" });
  await refreshCurrentPage();
}

async function refreshCurrentPage() {
  switch (state.page) {
    case "home":
      await loadDashboard();
      break;
    case "profile":
      await loadProfilePage();
      break;
    case "requests":
      await loadRequestsPage();
      break;
    case "academy":
      await loadAcademyPage();
      break;
    case "notifications":
      await loadNotificationsPage();
      break;
    case "team":
      await loadTeamPage();
      break;
    case "admin":
      await loadAdminPage();
      break;
  }
  await updateNotificationBadge();
}

// --- PAGE LOADERS ---

// 1. DASHBOARD
async function loadDashboard() {
  try {
    const data = await api("/me/dashboard");

    document.getElementById("greeting").innerHTML = `${data.greeting} <span>✳</span>`;
    document.getElementById("leaveDays").textContent = data.leave_balance_days.toFixed(1);
    document.getElementById("statRequests").textContent = data.open_requests_count;
    document.getElementById("statLearning").textContent = `${data.learning_progress_percent}%`;
    document.getElementById("statCourses").textContent = data.assigned_courses_count;
    document.getElementById("statNotifications").textContent = data.unread_notifications_count;

    // Load recent requests for the quick list
    const requests = await api("/requests");
    const listEl = document.getElementById("homeRequests");
    if (requests && requests.length > 0) {
      listEl.innerHTML = requests.slice(0, 3).map(r => `
        <div class="request-row">
          <div class="req-icon">${r.type === "Vacation" ? "◷" : "＄"}</div>
          <div>
            <div class="req-title">${esc(r.type)}</div>
            <div class="req-sub">${esc(r.request_code)} · ${esc(r.period_or_details)}</div>
          </div>
          <span class="status ${r.status.toLowerCase()}">${r.status}</span>
        </div>
      `).join("");
    } else {
      listEl.innerHTML = `<div style="padding:15px 0;color:var(--muted)">No requests yet.</div>`;
    }
  } catch (err) {
    console.error("Error loading dashboard", err);
  }
}

// 2. PROFILE
async function loadProfilePage() {
  try {
    const p = await api("/me/profile");
    document.getElementById("profName").textContent = p.full_name;
    document.getElementById("profPosition").textContent = p.position;
    document.getElementById("profEmpCode").textContent = p.employee_code;
    document.getElementById("profDept").textContent = p.department;
    document.getElementById("profCompany").textContent = p.company;
    document.getElementById("profManager").textContent = p.manager_name || "None (Department Head)";
    document.getElementById("profHireDate").textContent = new Date(p.hire_date).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
    document.getElementById("profLocation").textContent = p.location;
    document.getElementById("profLeaveBalance").textContent = `${p.leave_balance_days.toFixed(1)} days`;

    // Fetch learning summary
    const courses = await api("/courses");
    const avg = courses.length ? (courses.reduce((a, b) => a + b.progress_percent, 0) / courses.length).toFixed(0) : 0;
    document.getElementById("profLearningPct").textContent = `${avg}%`;
  } catch (err) {
    toast(`Error loading profile: ${err.message}`);
  }
}

// 3. REQUESTS
async function loadRequestsPage() {
  const sf = document.getElementById("statusFilter")?.value || "";
  const tf = document.getElementById("typeFilter")?.value || "";

  let path = "/requests?";
  if (sf && sf !== "all") path += `status=${encodeURIComponent(sf)}&`;
  if (tf && tf !== "all") path += `type=${encodeURIComponent(tf)}&`;

  try {
    const requests = await api(path);
    const tbody = document.getElementById("requestTable");
    if (!requests || requests.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:25px;color:var(--muted)">No requests found.</td></tr>`;
      return;
    }

    tbody.innerHTML = requests.map(r => `
      <tr>
        <td>
          <b>${esc(r.type)}</b>
          <div class="req-sub">${esc(r.request_code)}</div>
        </td>
        <td>${esc(r.submitted_date_formatted)}</td>
        <td>
          ${esc(r.period_or_details)}
          <div class="req-sub">${esc(r.reason || "No comment")}</div>
        </td>
        <td><span class="status ${r.status.toLowerCase()}">${r.status}</span></td>
        <td>
          <button class="text-link" onclick="openRequestDetailModal(${r.id})">Details ↗</button>
        </td>
      </tr>
    `).join("");
  } catch (err) {
    toast(`Error loading requests: ${err.message}`);
  }
}

// 4. JANA ACADEMY
async function loadAcademyPage() {
  try {
    const courses = await api("/courses");
    state.courses = courses;
    const grid = document.getElementById("academyGrid");

    grid.innerHTML = courses.map(c => `
      <div class="card course-tile">
        <div class="tile-art" style="background:${c.cover_gradient}">▤</div>
        <span class="eyebrow">${c.is_mandatory ? "MANDATORY" : "RECOMMENDED"} · ${c.duration_minutes} MIN</span>
        <h3>${esc(c.title)}</h3>
        <p>${esc(c.description)}</p>
        <div class="progress"><span style="width:${c.progress_percent}%"></span></div>
        <div class="progress-label">
          <span>${c.progress_percent.toFixed(0)}% complete</span>
          <span>${c.status === "COMPLETED" ? "Completed ✓" : (c.due_date ? `Due ${c.due_date}` : "Self-paced")}</span>
        </div>
        <button class="${c.progress_percent === 100 ? 'small-btn' : 'primary'}" style="margin-top:16px" onclick="openCoursePlayer(${c.id})">
          ${c.progress_percent === 100 ? "Review course →" : (c.progress_percent > 0 ? "Continue course →" : "Start course →")}
        </button>
      </div>
    `).join("");
  } catch (err) {
    toast(`Error loading academy courses: ${err.message}`);
  }
}

// 5. NOTIFICATIONS
async function loadNotificationsPage() {
  try {
    const notifs = await api("/notifications");
    state.notifications = notifs;
    const listEl = document.getElementById("notificationsList");

    if (!notifs || notifs.length === 0) {
      listEl.innerHTML = `<div style="padding:20px;color:var(--muted);text-align:center">No notifications in your inbox.</div>`;
      return;
    }

    listEl.innerHTML = notifs.map(n => `
      <div class="notice" style="cursor:pointer" onclick="markNotificationRead(${n.id})">
        <div class="notice-icon">${n.type === "REQUEST" ? "◷" : (n.type === "ACADEMY" ? "▧" : "✓")}</div>
        <div style="flex:1">
          <b>${esc(n.title)}</b>
          <p>${esc(n.message)} · <span style="opacity:0.8">${esc(n.time_ago)}</span></p>
        </div>
        ${!n.is_read ? `<span class="dot" style="position:static;margin:6px 0 0 8px"></span>` : ""}
      </div>
    `).join("");
  } catch (err) {
    toast(`Error loading notifications: ${err.message}`);
  }
}

async function markNotificationRead(id) {
  try {
    await api(`/notifications/${id}`, { method: "PATCH", body: JSON.stringify({ is_read: true }) });
    await loadNotificationsPage();
    await updateNotificationBadge();
  } catch (err) {
    console.error(err);
  }
}

async function markAllNotificationsRead() {
  try {
    await api("/notifications/read-all", { method: "POST" });
    toast("All notifications marked as read.");
    await loadNotificationsPage();
    await updateNotificationBadge();
  } catch (err) {
    toast(`Error: ${err.message}`);
  }
}

async function updateNotificationBadge() {
  try {
    const notifs = await api("/notifications");
    const unread = notifs.filter(n => !n.is_read).length;
    const dot = document.getElementById("notifDot");
    if (dot) dot.style.display = unread > 0 ? "block" : "none";
    const navBadge = document.getElementById("navNotifCount");
    if (navBadge) {
      navBadge.textContent = unread;
      navBadge.style.display = unread > 0 ? "inline-block" : "none";
    }
  } catch (e) {
    // silently ignore badge refresh error
  }
}

// 6. MANAGER PORTAL
async function loadTeamPage() {
  try {
    const requests = await api("/manager/requests?status=Pending");
    const teamTable = document.getElementById("teamTable");

    if (!requests || requests.length === 0) {
      teamTable.innerHTML = `<tr><td colspan="5" style="text-align:center;padding:25px;color:var(--muted)">No pending requests from your team.</td></tr>`;
      document.getElementById("teamPendingBadge").textContent = "0 pending";
      return;
    }

    document.getElementById("teamPendingBadge").textContent = `${requests.length} pending review`;

    teamTable.innerHTML = requests.map(r => `
      <tr>
        <td>
          <b>${esc(r.user_name)}</b>
          <div class="req-sub">${esc(r.department)}</div>
        </td>
        <td>${esc(r.type)}</td>
        <td>
          ${esc(r.period_or_details)}
          <div class="req-sub">${esc(r.reason || "No comment")}</div>
        </td>
        <td><span class="status pending">Pending</span></td>
        <td>
          <button class="small-btn primary" onclick="reviewRequestPrompt(${r.id}, 'approve')">Approve</button>
          <button class="small-btn danger" style="margin-left:4px" onclick="reviewRequestPrompt(${r.id}, 'reject')">Decline</button>
        </td>
      </tr>
    `).join("");

    // Load team members count
    const teamMembers = await api("/manager/team");
    document.getElementById("teamCount").textContent = teamMembers.length;
    document.getElementById("teamPendingStat").textContent = requests.length;
  } catch (err) {
    toast(`Error loading manager portal: ${err.message}`);
  }
}

async function reviewRequestPrompt(requestId, action) {
  const comment = prompt(`Add a comment for this ${action.toUpperCase()} action (optional):`, action === "approve" ? "Approved by direct manager." : "Please reschedule with team.");
  if (comment === null) return; // user cancelled

  try {
    const res = await api(`/requests/${requestId}/${action}`, {
      method: "POST",
      body: JSON.stringify({ action, comment: comment.trim() }),
    });

    toast(`Request ${res.request_code} successfully ${res.status.toLowerCase()}!`);
    await loadTeamPage();
  } catch (err) {
    toast(`Review failed: ${err.message}`);
  }
}

// 7. HR ADMIN PORTAL
async function loadAdminPage() {
  try {
    // Load Knowledge Sources
    const chunks = await api("/admin/knowledge");
    document.getElementById("adminKnowledgeCount").textContent = chunks.length;
    const kList = document.getElementById("knowledgeList");
    kList.innerHTML = chunks.map(c => `
      <div class="notice">
        <div class="notice-icon">▤</div>
        <div style="flex:1">
          <b>${esc(c.document_title)} · ${esc(c.section_title)}</b>
          <p>${esc(c.content.substring(0, 140))}...</p>
        </div>
      </div>
    `).join("");

    // Load Integrations Telemetry
    const adapters = await api("/admin/integrations");
    const integList = document.getElementById("adminIntegrationsList");
    integList.innerHTML = adapters.map(a => `
      <div class="notice">
        <div class="notice-icon">↔</div>
        <div style="flex:1">
          <b>${esc(a.adapter_name)}</b>
          <span class="status approved" style="margin-left:8px;font-size:9.5px">${a.status}</span>
          <p>${esc(a.notes)}</p>
          <div style="font-size:11px;color:var(--muted);margin-top:4px">
            <b>Endpoint:</b> <code>${esc(a.endpoint_template)}</code> · <b>Mode:</b> ${a.mode}
          </div>
        </div>
      </div>
    `).join("");

    // Load Audit Log
    const logs = await api("/admin/audit?limit=10");
    const auditTable = document.getElementById("adminAuditTable");
    auditTable.innerHTML = logs.map(l => `
      <tr>
        <td><code>${esc(l.action)}</code></td>
        <td>${esc(l.actor_name)}</td>
        <td>${esc(l.target_type || "—")}: ${esc(l.target_id || "—")}</td>
        <td><small>${esc(new Date(l.timestamp).toLocaleTimeString())}</small></td>
      </tr>
    `).join("");
  } catch (err) {
    toast(`Error loading admin portal: ${err.message}`);
  }
}

// --- MODALS & WORKFLOWS ---
function setupModals() {
  // New Request Modal
  document.querySelectorAll('[data-action="new-request"]').forEach(b => {
    b.addEventListener("click", () => {
      document.getElementById("requestModal").classList.add("open");
    });
  });

  const closeModal = () => document.getElementById("requestModal").classList.remove("open");
  document.getElementById("closeModal").onclick = closeModal;
  document.getElementById("cancelModal").onclick = closeModal;

  // Toggle amount field if Advance Payment is selected
  document.getElementById("reqType").addEventListener("change", e => {
    const isAdv = e.target.value === "Advance payment";
    document.getElementById("reqAmountGroup").style.display = isAdv ? "grid" : "none";
    document.getElementById("reqEndGroup").style.display = isAdv ? "none" : "grid";
  });

  // Submit request form
  document.getElementById("requestForm").addEventListener("submit", async e => {
    e.preventDefault();
    const type = document.getElementById("reqType").value;
    const startDate = document.getElementById("reqStart").value;
    const endDate = document.getElementById("reqEnd").value;
    const amountVal = document.getElementById("reqAmount").value;
    const reason = document.getElementById("reqReason").value.trim();

    const payload = {
      type,
      start_date: startDate,
      end_date: type === "Vacation" && endDate ? endDate : null,
      amount: type === "Advance payment" && amountVal ? parseFloat(amountVal) : null,
      reason: reason || null,
    };

    try {
      const res = await api("/requests", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      toast(`Request ${res.request_code} successfully created!`);
      closeModal();
      e.target.reset();
      await loadDashboard();
      if (state.page === "requests") await loadRequestsPage();
    } catch (err) {
      toast(`Submission failed: ${err.message}`);
    }
  });

  // Request detail modal close
  document.getElementById("closeDetailModal").onclick = () => {
    document.getElementById("requestDetailModal").classList.remove("open");
  };

  // Course player modal close
  document.getElementById("closeCourseModal").onclick = () => {
    document.getElementById("coursePlayerModal").classList.remove("open");
  };

  // Citation modal close
  document.getElementById("closeCitationModal").onclick = () => {
    document.getElementById("citationModal").classList.remove("open");
  };
}

// Request detail viewer modal
async function openRequestDetailModal(id) {
  try {
    const r = await api(`/requests/${id}`);
    document.getElementById("detailModalTitle").textContent = `${r.request_code} · ${r.type}`;
    document.getElementById("detailModalCode").textContent = r.request_code;
    document.getElementById("detailModalStatus").innerHTML = `<span class="status ${r.status.toLowerCase()}">${r.status}</span>`;
    document.getElementById("detailModalRequester").textContent = r.user_name;
    document.getElementById("detailModalDept").textContent = r.department;
    document.getElementById("detailModalDates").textContent = r.period_or_details;
    document.getElementById("detailModalSync").textContent = r.external_sync_id || "Documentolog integration pending";

    // Build timeline of events
    const timeline = document.getElementById("detailModalTimeline");
    timeline.innerHTML = r.events.map(ev => `
      <div class="activity">
        <span class="activity-dot" style="${ev.event_type === 'APPROVED' ? 'background:var(--green)' : (ev.event_type === 'REJECTED' ? 'background:var(--red)' : '')}"></span>
        <div>
          <b>${esc(ev.event_type)} by ${esc(ev.actor_name)}</b>
          <p>${esc(ev.comment || '')} · <span style="font-size:10px">${new Date(ev.created_at).toLocaleString()}</span></p>
        </div>
      </div>
    `).join("");

    document.getElementById("requestDetailModal").classList.add("open");
  } catch (err) {
    toast(`Error opening request details: ${err.message}`);
  }
}

// Course Player Modal with interactive quiz
async function openCoursePlayer(courseId) {
  try {
    const course = await api(`/courses/${courseId}`);
    state.currentCourse = course;

    document.getElementById("playerCourseTitle").textContent = course.title;
    document.getElementById("playerProgressBar").style.width = `${course.progress_percent}%`;
    document.getElementById("playerProgressLabel").textContent = `${course.progress_percent.toFixed(0)}% complete`;

    // Render lessons list
    const lessonsList = document.getElementById("playerLessonsList");
    lessonsList.innerHTML = course.lessons.map(l => `
      <button class="small-btn ${l.id === course.current_lesson_id ? 'primary' : ''}" style="width:100%;justify-content:space-between;margin-bottom:6px" onclick="loadLessonInPlayer(${l.id})">
        <span>${esc(l.title)}</span>
        <span>${l.is_completed ? "✓" : "○"}</span>
      </button>
    `).join("");

    if (course.current_lesson_id) {
      await loadLessonInPlayer(course.current_lesson_id);
    }

    document.getElementById("coursePlayerModal").classList.add("open");
  } catch (err) {
    toast(`Error opening course: ${err.message}`);
  }
}

async function loadLessonInPlayer(lessonId) {
  try {
    const lesson = await api(`/courses/lessons/${lessonId}`);
    state.currentLesson = lesson;

    document.getElementById("playerLessonTitle").textContent = lesson.title;
    document.getElementById("playerLessonContent").textContent = lesson.content_markdown;

    // Quiz container
    const quizBox = document.getElementById("playerQuizBox");
    if (lesson.quiz_question && lesson.quiz_options.length > 0) {
      quizBox.style.display = "block";
      document.getElementById("playerQuizQuestion").textContent = lesson.quiz_question;
      const opts = document.getElementById("playerQuizOptions");
      opts.innerHTML = lesson.quiz_options.map((opt, idx) => `
        <label style="display:flex;align-items:center;gap:10px;padding:8px 12px;background:var(--surface2);border-radius:10px;cursor:pointer;margin-bottom:6px">
          <input type="radio" name="lessonQuiz" value="${idx}">
          <span>${esc(opt)}</span>
        </label>
      `).join("");
      document.getElementById("playerQuizFeedback").style.display = "none";
    } else {
      quizBox.style.display = "none";
    }
  } catch (err) {
    toast(`Error loading lesson: ${err.message}`);
  }
}

async function submitLessonQuiz() {
  if (!state.currentLesson) return;
  const selected = document.querySelector('input[name="lessonQuiz"]:checked');
  if (!selected) {
    toast("Please select an answer option.");
    return;
  }

  const answerIdx = parseInt(selected.value, 10);
  try {
    const res = await api(`/courses/lessons/${state.currentLesson.id}/quiz`, {
      method: "POST",
      body: JSON.stringify({ answer_index: answerIdx }),
    });

    const fb = document.getElementById("playerQuizFeedback");
    fb.style.display = "block";
    fb.className = res.passed ? "status approved" : "status rejected";
    fb.textContent = res.explanation;

    // Update progress
    document.getElementById("playerProgressBar").style.width = `${res.new_progress_percent}%`;
    document.getElementById("playerProgressLabel").textContent = `${res.new_progress_percent.toFixed(0)}% complete`;

    if (res.course_completed) {
      toast("🎉 Congratulations! You have successfully completed this course!");
    }

    // Refresh academy page in background
    if (state.page === "academy") await loadAcademyPage();
    await loadDashboard();
  } catch (err) {
    toast(`Quiz error: ${err.message}`);
  }
}

// --- AI JANA CHAT ---
function setupAIChat() {
  const form = document.getElementById("chatForm");
  const input = document.getElementById("chatInput");

  form.addEventListener("submit", async e => {
    e.preventDefault();
    const q = input.value.trim();
    if (!q) return;
    input.value = "";
    await sendAIQuery(q);
  });

  document.querySelectorAll("[data-question]").forEach(btn => {
    btn.addEventListener("click", async () => {
      await sendAIQuery(btn.dataset.question);
    });
  });

  document.getElementById("clearChat").onclick = () => {
    document.getElementById("chatMessages").innerHTML = `
      <div class="message">
        Hi! I'm AI Jana, your corporate HR companion. Ask me anything about vacations, leave balances, working hours, or HR policies.
        <small>AI Jana · Knowledge-Grounded</small>
      </div>
    `;
  };
}

async function sendAIQuery(question) {
  const container = document.getElementById("chatMessages");

  // Append user bubble
  const userBubble = document.createElement("div");
  userBubble.className = "message user";
  userBubble.textContent = question;
  container.appendChild(userBubble);
  container.scrollTop = container.scrollHeight;

  // Placeholder bot bubble
  const botBubble = document.createElement("div");
  botBubble.className = "message";
  botBubble.innerHTML = `<i>Checking verified HR knowledge base…</i>`;
  container.appendChild(botBubble);
  container.scrollTop = container.scrollHeight;

  try {
    const res = await api("/ai/chat", {
      method: "POST",
      body: JSON.stringify({ question }),
    });

    let html = `<div style="white-space:pre-wrap">${esc(res.answer)}</div>`;

    // Render citations pills
    if (res.sources && res.sources.length > 0) {
      html += `<div style="margin-top:10px">`;
      res.sources.forEach(s => {
        html += `<span class="source-pill" onclick="showCitationModal('${esc(s.document_title)}', '${esc(s.section_title)}', '${esc(s.snippet)}')">📖 ${esc(s.document_title)} · ${esc(s.section_title)}</span>`;
      });
      html += `</div>`;
    }

    // Fallback guidance badge
    if (res.answer_status === "fallback") {
      botBubble.classList.add("fallback");
      html += `
        <div style="margin-top:10px;padding:8px 12px;background:var(--surface);border-left:3px solid var(--orange);border-radius:6px;font-size:11.5px">
          <b>Safe Fallback:</b> ${esc(res.escalation_guidance)}
        </div>
      `;
    }

    html += `<small>AI Jana · Status: ${res.answer_status} · Response time: ${res.processing_time_ms} ms</small>`;
    botBubble.innerHTML = html;
  } catch (err) {
    botBubble.innerHTML = `<span style="color:var(--red)">Error: ${esc(err.message)}</span>`;
  }

  container.scrollTop = container.scrollHeight;
}

function showCitationModal(docTitle, secTitle, snippet) {
  document.getElementById("citationDocTitle").textContent = docTitle;
  document.getElementById("citationSecTitle").textContent = secTitle;
  document.getElementById("citationSnippet").textContent = snippet;
  document.getElementById("citationModal").classList.add("open");
}

// --- LANGUAGE & ROLE SWITCHERS ---
function setupRoleSwitch() {
  const sel = document.getElementById("roleSwitch");
  sel.addEventListener("change", async e => {
    await switchRole(e.target.value);
  });
}

function setupLanguageSwitch() {
  const sel = document.getElementById("langSwitch");
  if (!sel) return;
  sel.addEventListener("change", e => {
    state.lang = e.target.value;
    applyLanguage(state.lang);
  });
}

function applyLanguage(lang) {
  const dict = I18N[lang] || I18N.en;
  document.querySelectorAll("[data-i18n]").forEach(el => {
    const key = el.dataset.i18n;
    if (dict[key]) {
      el.textContent = dict[key];
    }
  });
  toast(`Language changed to ${lang.toUpperCase()}`);
}

// Start application when DOM is ready
document.addEventListener("DOMContentLoaded", initApp);
