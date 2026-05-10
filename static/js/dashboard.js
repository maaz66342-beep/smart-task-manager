/* ── WebSocket ── */
const socket = io({ transports: ["websocket"] });

socket.on("connect", () => {
  setBadge(true);
  showToast("🟢 Live updates connected");
});

socket.on("disconnect", () => setBadge(false));

socket.on("task_added",   task => { addOrUpdateCard(task); fetchAnalytics(); showToast(`✅ New task: "${task.title}"`); });
socket.on("task_updated", task => { addOrUpdateCard(task); fetchAnalytics(); showToast(`✏️ Updated: "${task.title}"`); });
socket.on("task_deleted", ({id}) => { removeCard(id); fetchAnalytics(); showToast(`🗑️ Task deleted`); });

function setBadge(online) {
  const b = document.getElementById("ws-badge");
  b.textContent = online ? "● Live" : "● Offline";
  b.className = "ws-badge " + (online ? "online" : "offline");
}

/* ── State ── */
let allTasks = [];

/* ── Logout ── */
document.getElementById("logout-btn").addEventListener("click", async () => {
  await fetch("/api/auth/logout", { method: "POST" });
  window.location.href = "/login";
});

/* ── Fetch tasks ── */
async function fetchTasks() {
  const res = await fetch("/api/tasks");
  if (res.status === 401) { window.location.href = "/login"; return; }
  allTasks = await res.json();
  renderTasks();
}

/* ── Fetch analytics ── */
async function fetchAnalytics() {
  const res  = await fetch("/api/analytics");
  const data = await res.json();
  renderAnalytics(data);
}

function renderAnalytics(d) {
  document.getElementById("stat-total").textContent      = d.total;
  document.getElementById("stat-completed").textContent  = d.completed;
  document.getElementById("stat-pending").textContent    = d.pending;
  document.getElementById("stat-inprogress").textContent = d.in_progress;
  document.getElementById("stat-pct").textContent        = d.completion_percentage + "%";
  document.getElementById("progress-fill").style.width   = d.completion_percentage + "%";

  const total = d.total || 1;
  setPriorityBar("high",   d.priority_breakdown.high,   total);
  setPriorityBar("medium", d.priority_breakdown.medium, total);
  setPriorityBar("low",    d.priority_breakdown.low,    total);
}

function setPriorityBar(level, count, total) {
  document.getElementById(`pb-${level}`).style.width   = (count / total * 100) + "%";
  document.getElementById(`pb-${level}-n`).textContent = count;
}

/* ── Render task list ── */
function renderTasks() {
  const statusFilter   = document.getElementById("filter-status").value;
  const priorityFilter = document.getElementById("filter-priority").value;

  let tasks = allTasks;
  if (statusFilter)   tasks = tasks.filter(t => t.status   === statusFilter);
  if (priorityFilter) tasks = tasks.filter(t => t.priority === priorityFilter);

  const list = document.getElementById("task-list");
  list.innerHTML = "";

  if (!tasks.length) {
    list.innerHTML = `<p class="empty-msg">No tasks found. Add one above!</p>`;
    return;
  }

  tasks.forEach(t => list.appendChild(buildCard(t)));
}

function buildCard(task) {
  const card = document.createElement("div");
  card.className = `task-card ${task.priority}${task.status === "completed" ? " completed" : ""}`;
  card.dataset.id = task.id;

  const date = new Date(task.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric" });
  const desc = task.description ? `<div class="task-desc">${esc(task.description)}</div>` : "";
  const statusLabel = task.status.replace("_", " ");

  card.innerHTML = `
    <div class="task-body">
      <div class="task-title">${esc(task.title)}</div>
      ${desc}
      <div class="task-meta">
        <span class="badge badge-priority ${task.priority}">${task.priority}</span>
        <span class="badge badge-status ${task.status}">${statusLabel}</span>
        <span class="task-date">${date}</span>
      </div>
    </div>
    <div class="task-actions">
      <button class="icon-btn edit"   title="Edit">✏️</button>
      <button class="icon-btn delete" title="Delete">🗑️</button>
    </div>`;

  card.querySelector(".edit").addEventListener("click",   () => openEditModal(task));
  card.querySelector(".delete").addEventListener("click", () => deleteTask(task.id));
  return card;
}

function addOrUpdateCard(task) {
  const idx = allTasks.findIndex(t => t.id === task.id);
  if (idx === -1) allTasks.unshift(task);
  else            allTasks[idx] = task;
  renderTasks();
}

function removeCard(id) {
  allTasks = allTasks.filter(t => t.id !== id);
  renderTasks();
}

/* ── Add task ── */
document.getElementById("add-task-btn").addEventListener("click", async () => {
  const title       = document.getElementById("task-title").value.trim();
  const description = document.getElementById("task-desc").value.trim();
  const priority    = document.getElementById("task-priority").value;
  const status      = document.getElementById("task-status").value;

  if (!title) { showToast("⚠️ Title is required"); return; }

  const res = await fetch("/api/tasks", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, description, priority, status }),
  });

  if (res.ok) {
    document.getElementById("task-title").value = "";
    document.getElementById("task-desc").value  = "";
    // WebSocket event handles DOM update
  } else {
    const d = await res.json();
    showToast("❌ " + (d.error || "Error adding task"));
  }
});

/* ── Delete task ── */
async function deleteTask(id) {
  if (!confirm("Delete this task?")) return;
  await fetch(`/api/tasks/${id}`, { method: "DELETE" });
  // WebSocket handles DOM update
}

/* ── Edit modal ── */
let editingId = null;

function openEditModal(task) {
  editingId = task.id;
  document.getElementById("edit-title").value    = task.title;
  document.getElementById("edit-desc").value     = task.description || "";
  document.getElementById("edit-priority").value = task.priority;
  document.getElementById("edit-status").value   = task.status;
  document.getElementById("edit-modal").classList.remove("hidden");
}

document.getElementById("edit-cancel-btn").addEventListener("click", () => {
  document.getElementById("edit-modal").classList.add("hidden");
});

document.getElementById("edit-save-btn").addEventListener("click", async () => {
  const title       = document.getElementById("edit-title").value.trim();
  const description = document.getElementById("edit-desc").value.trim();
  const priority    = document.getElementById("edit-priority").value;
  const status      = document.getElementById("edit-status").value;

  if (!title) { showToast("⚠️ Title is required"); return; }

  const res = await fetch(`/api/tasks/${editingId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, description, priority, status }),
  });

  document.getElementById("edit-modal").classList.add("hidden");

  if (!res.ok) {
    const d = await res.json();
    showToast("❌ " + (d.error || "Update failed"));
  }
  // WebSocket handles DOM update
});

/* ── Filters ── */
document.getElementById("filter-status").addEventListener("change",   renderTasks);
document.getElementById("filter-priority").addEventListener("change", renderTasks);

/* ── Toast ── */
let toastTimer;
function showToast(msg) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.classList.remove("hidden");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.add("hidden"), 3000);
}

/* ── Helpers ── */
function esc(str) {
  return String(str)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

/* ── Init ── */
fetchTasks();
fetchAnalytics();
