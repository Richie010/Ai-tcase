const API_BASE = "/api";

const fileInput = document.getElementById("file-input");
const dropzone = document.getElementById("dropzone");
const fileListEl = document.getElementById("file-list");
const generateBtn = document.getElementById("generate-btn");

const progressSection = document.getElementById("progress-section");
const progressStage = document.getElementById("progress-stage");
const progressPercent = document.getElementById("progress-percent");
const progressBar = document.getElementById("progress-bar");
const errorMessage = document.getElementById("error-message");

const resultsSection = document.getElementById("results-section");
const resultsSummary = document.getElementById("results-summary");
const resultsTableBody = document.getElementById("results-table-body");
const downloadLink = document.getElementById("download-link");

const historyList = document.getElementById("history-list");

let selectedFiles = [];

// ── History ──

function loadHistory() {
  try {
    return JSON.parse(sessionStorage.getItem("tc_portal_history") || "[]");
  } catch {
    return [];
  }
}

function saveHistoryEntry(entry) {
  const history = loadHistory();
  history.unshift(entry);
  sessionStorage.setItem("tc_portal_history", JSON.stringify(history.slice(0, 10)));
  renderHistory();
}

function deleteHistoryItem(index) {
  const history = loadHistory();
  history.splice(index, 1);
  sessionStorage.setItem("tc_portal_history", JSON.stringify(history));
  renderHistory();
}

function renderHistory() {
  const history = loadHistory();
  historyList.innerHTML = "";
  if (history.length === 0) {
    historyList.innerHTML = '<li class="text-slate-400">No jobs yet this session.</li>';
    return;
  }
  history.forEach((entry, index) => {
    const li = document.createElement("li");
    li.className = "flex items-center justify-between bg-white border border-slate-200 rounded-lg px-3 py-2";
    li.innerHTML = `
      <span class="text-slate-700">${entry.documentNames.join(", ")} — <span class="text-slate-400">${entry.status}</span></span>
      <div style="display:flex;align-items:center;gap:8px;">
        ${entry.status === "completed" ? `<a class="text-indigo-600 hover:underline" href="${API_BASE}/jobs/${entry.jobId}/download">Download</a>` : ""}
        <button onclick="deleteHistoryItem(${index})" title="Remove"
          style="background:none;border:none;cursor:pointer;color:#94a3b8;padding:4px;border-radius:4px;display:flex;align-items:center;"
          onmouseover="this.style.color='#ef4444'" onmouseout="this.style.color='#94a3b8'">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>
      </div>
    `;
    historyList.appendChild(li);
  });
}

// ── File list ──

function renderFileList() {
  fileListEl.innerHTML = "";
  for (const file of selectedFiles) {
    const li = document.createElement("li");
    li.textContent = `${file.name} (${(file.size / 1024).toFixed(0)} KB)`;
    fileListEl.appendChild(li);
  }
  generateBtn.disabled = selectedFiles.length === 0;
}

function addFiles(fileArray) {
  const allowed = [".pdf", ".docx", ".xlsx", ".xls"];
  for (const file of fileArray) {
    const ext = "." + file.name.split(".").pop().toLowerCase();
    if (!allowed.includes(ext)) {
      alert(`${file.name}: unsupported file type (${ext})`);
      continue;
    }
    selectedFiles.push(file);
  }
  renderFileList();
}

// ── Drag & drop ──

dropzone.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", (e) => addFiles(Array.from(e.target.files)));

dropzone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropzone.classList.add("drag-over");
});
dropzone.addEventListener("dragleave", () => dropzone.classList.remove("drag-over"));
dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.classList.remove("drag-over");
  addFiles(Array.from(e.dataTransfer.files));
});

// ── Progress & results ──

function resetUIForNewRun() {
  progressSection.classList.remove("hidden");
  resultsSection.classList.add("hidden");
  errorMessage.classList.add("hidden");
  progressBar.style.width = "0%";
  progressPercent.textContent = "0%";
  progressStage.textContent = "Starting…";
}

async function pollJob(jobId, documentNames) {
  const poll = async () => {
    const resp = await fetch(`${API_BASE}/jobs/${jobId}`);
    if (!resp.ok) {
      showError("Could not fetch job status.");
      return;
    }
    const job = await resp.json();

    progressBar.style.width = `${job.progress_percent}%`;
    progressPercent.textContent = `${job.progress_percent}%`;
    progressStage.textContent = job.current_stage || job.status;

    if (job.status === "completed") {
      showResults(job, jobId);
      saveHistoryEntry({ jobId, documentNames, status: "completed" });
      return;
    }
    if (job.status === "failed") {
      showError(job.error_message || "Generation failed.");
      saveHistoryEntry({ jobId, documentNames, status: "failed" });
      return;
    }
    setTimeout(poll, 800);
  };
  poll();
}

function showError(message) {
  errorMessage.textContent = message;
  errorMessage.classList.remove("hidden");
}

function showResults(job, jobId) {
  resultsSection.classList.remove("hidden");
  const total = job.test_cases.length;
  const byType = {};
  for (const tc of job.test_cases) byType[tc.case_type] = (byType[tc.case_type] || 0) + 1;
  const typeSummary = Object.entries(byType).map(([k, v]) => `${v} ${k}`).join(", ");
  resultsSummary.textContent = `${total} test cases generated — ${typeSummary}`;

  resultsTableBody.innerHTML = "";
  for (const tc of job.test_cases) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td class="px-3 py-2 font-mono text-xs">${tc.tc_id}</td>
      <td class="px-3 py-2">${tc.module}</td>
      <td class="px-3 py-2">${tc.case_type}</td>
      <td class="px-3 py-2">${tc.priority}</td>
      <td class="px-3 py-2">${tc.scenario}</td>
      <td class="px-3 py-2">${tc.expected_result}</td>
    `;
    resultsTableBody.appendChild(tr);
  }

  downloadLink.href = `${API_BASE}/jobs/${jobId}/download`;
}

// ── Generate ──

generateBtn.addEventListener("click", async () => {
  if (selectedFiles.length === 0) return;
  resetUIForNewRun();
  generateBtn.disabled = true;

  const formData = new FormData();
  for (const file of selectedFiles) formData.append("files", file);

  try {
    const resp = await fetch(`${API_BASE}/jobs`, { method: "POST", body: formData });
    if (!resp.ok) {
      const body = await resp.json().catch(() => ({}));
      showError(body.detail || `Upload failed (${resp.status})`);
      generateBtn.disabled = false;
      return;
    }
    const { job_id } = await resp.json();
    const documentNames = selectedFiles.map((f) => f.name);
    pollJob(job_id, documentNames);
  } catch (err) {
    showError("Could not reach the server. Is the backend running?");
  } finally {
    generateBtn.disabled = false;
  }
});

// ── Init ──
renderHistory();