/**
 * The end-to-end journey on top of app.js: what to do next, where a request is,
 * and the certificate a finished course earns. Uses app.js helpers (api, esc, icon, state…).
 */

// Home: the few things that need this user now, each one click away.
async function renderNextActions({ dashboard, courses, requests }) {
  const box = document.getElementById("homeNextActions");
  const reviewer = ["manager", "hr_admin"].includes(state.user.role);
  const items = [];
  if (reviewer && dashboard.pending_attention_count) {
    items.push({ icon: "users", text: `${dashboard.pending_attention_count} requests await your decision`,
      action: "Review", run: () => go("team") });
  }
  courses.filter(c => c.assigned && c.status !== "COMPLETED")
    .sort((a, b) => (a.due_date || "9999").localeCompare(b.due_date || "9999"))
    .slice(0, 2).forEach(c => items.push({
      icon: "book", text: c.due_date ? `Finish «${c.title}» by ${formatDate(c.due_date)}` : `Finish «${c.title}»`,
      action: c.progress_percent > 0 ? "Continue learning" : "Start course", run: () => openCoursePlayer(c.id) }));
  requests.filter(r => r.status === "Pending").slice(0, 2).forEach(r => items.push({
    icon: "clock", text: `${r.request_code} awaits approval`, action: "Details", run: () => openRequestDetailModal(r.id) }));
  if (dashboard.unread_notifications_count) {
    items.push({ icon: "bell", text: `${dashboard.unread_notifications_count} unread notifications`,
      action: "Open", run: () => go("notifications") });
  }
  if (reviewer) {
    try {
      const soon = todayIso(7);
      const away = upcomingVacations(await apiAll("/manager/requests?type=Vacation&status=Approved"))
        .filter(v => v.user_id !== state.user.id && v.start_date <= soon);
      if (away.length) items.push({ icon: "calendar", text: `Away this week: ${away.map(v => v.user_name).join(", ")}`,
        action: "Calendar", run: () => go("team") });
    } catch { /* the calendar line is optional */ }
  }
  box.innerHTML = `<div class="section-head"><h3 class="h4">What to do now</h3></div>` + (items.length
    ? items.map((it, i) => `<div class="next-action">
        <span class="notice-icon">${icon(it.icon)}</span>
        <span class="next-text">${esc(it.text)}</span>
        <button class="small-btn primary" data-next="${i}">${esc(it.action)}</button>
      </div>`).join("")
    : `<div class="next-action"><span class="notice-icon">${icon("check")}</span><span class="next-text">All done for now</span></div>`);
  box.querySelectorAll("[data-next]").forEach(b => b.addEventListener("click", () => items[Number(b.dataset.next)].run()));
}

// Request card: the four steps from "How a request works", with where this request stands.
function requestStepper(r) {
  const at = type => r.events.find(e => e.event_type === type)?.created_at;
  const when = value => value ? `<small data-verbatim>${esc(formatDate(value))} ${esc(formatTime(value))}</small>` : "";
  const decided = r.status !== "Pending";
  const rejected = r.status === "Rejected";
  const steps = [
    { label: "Submitted", state: "done", note: when(at("SUBMITTED") || r.created_at) },
    { label: "Manager review", state: rejected ? "bad" : decided ? "done" : "current",
      note: decided ? when(at(rejected ? "REJECTED" : "APPROVED")) : "<small>Waiting for a decision</small>" },
    registrationStep(r, decided, rejected),
    { label: "Notification", state: rejected || decided ? "done" : "todo",
      note: decided ? "<small>Employee notified</small>" : "" },
  ];
  return `<ol class="req-stepper">${steps.map((s, i) => `
    <li class="${s.state}"><span class="step-dot">${s.state === "done" ? "✓" : s.state === "bad" ? "✕" : i + 1}</span>
      <b>${s.label}</b>${s.note}</li>`).join("")}</ol>`;
}

// Approval and document registration are separate: the gateway registers asynchronously.
function registrationStep(r, decided, rejected) {
  if (rejected) return { label: "Registration", state: "skip", note: "" };
  if (!decided) return { label: "Registration", state: "todo", note: "" };
  const sync = r.sync_status || "NOT_REQUIRED";
  if (sync === "REGISTERED" || r.external_sync_id) return { label: "Registration", state: "done", note: "<small>MOCK registration</small>" };
  if (["PENDING", "SENT"].includes(sync)) return { label: "Registration", state: "current", note: "<small>Waiting for the MOCK gateway</small>" };
  if (["FAILED", "DEAD"].includes(sync)) return { label: "Registration", state: "bad", note: "<small>Registration failed; HR is notified</small>" };
  return { label: "Registration", state: "done", note: "<small>Saved locally</small>" };
}

// AI Jana answers from the asker's own records, so the question is phrased in the first person.
async function askAIAboutMyRequests() {
  document.querySelectorAll(".modal-backdrop").forEach(m => m.classList.remove("open"));
  await go("assistant");
  await sendAIQuery(I18n.t("What is the status of my requests?"));
}

// Jana Academy: a printable certificate for a completed course.
function openCertificate(course) {
  document.getElementById("certificateBody").innerHTML = `
    <div class="certificate">
      <span class="chip">Jana Academy</span>
      <h2 class="h3">Certificate of completion</h2>
      <p class="muted">This confirms that</p>
      <h3 class="h2">${esc(state.user.full_name)}</h3>
      <p class="muted">has completed the course</p>
      <h4 class="h4">«${esc(course.title)}»</h4>
      <dl class="detail-grid">
        <div class="detail"><dt>Result</dt><dd>${Math.round(course.score ?? course.progress_percent)}%</dd></div>
        <div class="detail"><dt>Completed</dt><dd>${course.completed_at ? esc(formatDate(course.completed_at)) : "—"}</dd></div>
        <div class="detail"><dt>Certificate ID</dt><dd data-verbatim>${esc(`${course.code}-${state.user.id}`)}</dd></div>
        <div class="detail"><dt>Status</dt><dd>Synthetic demo certificate</dd></div>
      </dl>
    </div>`;
  document.getElementById("certificateModal").classList.add("open");
}
