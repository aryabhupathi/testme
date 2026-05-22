const state = {
  testingTypes: [],
  statuses: [],
  priorities: [],
  automationStates: [],
  cases: [],
  analytics: null,
  liveRuns: [],
  automationRuns: [],
  apiRuns: [],
  selectedType: "",
  view: "table",
};

const elements = {};

document.addEventListener("DOMContentLoaded", async () => {
  cacheElements();
  bindEvents();
  updateBackToTopVisibility();
  await loadReferenceData();
  await refreshData();
  await refreshLiveHistory();
  await refreshAutomationHistory();
  await refreshApiHistory();
});

function cacheElements() {
  const ids = [
    "typeNav",
    "caseForm",
    "caseId",
    "formTitle",
    "title",
    "testingType",
    "status",
    "priority",
    "automation",
    "owner",
    "environment",
    "requirement",
    "steps",
    "expectedResult",
    "actualResult",
    "tags",
    "clearFormBtn",
    "deleteCaseBtn",
    "searchInput",
    "filterType",
    "filterStatus",
    "filterPriority",
    "filterAutomation",
    "clearFiltersBtn",
    "caseTableBody",
    "tableView",
    "boardView",
    "tableViewBtn",
    "boardViewBtn",
    "statusBars",
    "typeBars",
    "caseCountPill",
    "metricTotal",
    "metricActive",
    "metricPassRate",
    "metricPassed",
    "metricRisk",
    "metricCritical",
    "metricAutomation",
    "pdfDownloadBtn",
    "exportBtn",
    "importFile",
    "resetDemoBtn",
    "testingSidebar",
    "sidebarToggleBtn",
    "sidebarCloseBtn",
    "sidebarBackdrop",
    "menuToggleBtn",
    "quickMenu",
    "liveTestForm",
    "liveBaseUrl",
    "livePages",
    "liveKeywords",
    "liveCheckLinks",
    "runLiveTestBtn",
    "liveRunStatus",
    "liveSummary",
    "liveResults",
    "liveHistory",
    "automationForm",
    "automationScenario",
    "automationBaseUrl",
    "automationSteps",
    "automationTimeout",
    "automationHeadless",
    "runAutomationBtn",
    "automationRunStatus",
    "automationSummary",
    "automationResults",
    "automationHistory",
    "apiTestForm",
    "apiSuiteName",
    "apiBaseUrl",
    "apiEngine",
    "apiTimeout",
    "apiHeaders",
    "apiRequests",
    "runApiTestBtn",
    "apiRunStatus",
    "apiSummary",
    "apiResults",
    "apiHistory",
    "backToTopBtn",
    "toast",
  ];

  ids.forEach((id) => {
    elements[id] = document.getElementById(id);
  });
}

function bindEvents() {
  elements.caseForm.addEventListener("submit", handleSubmit);
  elements.clearFormBtn.addEventListener("click", clearForm);
  elements.deleteCaseBtn.addEventListener("click", handleDelete);
  elements.clearFiltersBtn.addEventListener("click", clearFilters);
  elements.tableViewBtn.addEventListener("click", () => setView("table"));
  elements.boardViewBtn.addEventListener("click", () => setView("board"));
  elements.pdfDownloadBtn.addEventListener("click", downloadPdfReport);
  elements.exportBtn.addEventListener("click", exportCases);
  elements.importFile.addEventListener("change", importCases);
  elements.resetDemoBtn.addEventListener("click", resetDemo);
  elements.sidebarToggleBtn.addEventListener("click", toggleMobileSidebar);
  elements.sidebarCloseBtn.addEventListener("click", closeMobileSidebar);
  elements.sidebarBackdrop.addEventListener("click", closeMobileSidebar);
  elements.menuToggleBtn.addEventListener("click", toggleQuickMenu);
  elements.quickMenu.querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", () => openMenuTarget(button.dataset.target));
  });
  document.addEventListener("click", closeQuickMenuOnOutsideClick);
  document.addEventListener("keydown", closeQuickMenuOnEscape);
  document.addEventListener("keydown", closeMobileSidebarOnEscape);
  window.addEventListener("scroll", updateBackToTopVisibility, { passive: true });
  elements.backToTopBtn.addEventListener("click", scrollToTop);
  elements.liveTestForm.addEventListener("submit", handleLiveTestSubmit);
  elements.automationForm.addEventListener("submit", handleAutomationSubmit);
  elements.apiTestForm.addEventListener("submit", handleApiTestSubmit);

  ["searchInput", "filterType", "filterStatus", "filterPriority", "filterAutomation"].forEach((id) => {
    elements[id].addEventListener("input", debounce(refreshData, 180));
    elements[id].addEventListener("change", refreshData);
  });
}

function updateBackToTopVisibility() {
  const shouldShow = window.scrollY > 16;
  elements.backToTopBtn.classList.toggle("hidden", !shouldShow);
}

function scrollToTop() {
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function toggleMobileSidebar(event) {
  event.stopPropagation();
  const willOpen = !elements.testingSidebar.classList.contains("open");
  setMobileSidebarOpen(willOpen);
}

function closeMobileSidebar() {
  setMobileSidebarOpen(false);
}

function closeMobileSidebarOnEscape(event) {
  if (event.key === "Escape") {
    closeMobileSidebar();
  }
}

function setMobileSidebarOpen(isOpen) {
  elements.testingSidebar.classList.toggle("open", isOpen);
  elements.sidebarBackdrop.classList.toggle("hidden", !isOpen);
  elements.sidebarToggleBtn.setAttribute("aria-expanded", String(isOpen));
  document.body.classList.toggle("sidebar-open", isOpen);
}

async function loadReferenceData() {
  const data = await requestJSON("/api/testing-types");
  state.testingTypes = data.testing_types;
  state.statuses = data.statuses;
  state.priorities = data.priorities;
  state.automationStates = data.automation_states;

  renderTypeNav();
  fillSelect(elements.testingType, state.testingTypes.map((item) => item.name));
  fillSelect(elements.status, state.statuses);
  fillSelect(elements.priority, state.priorities);
  fillSelect(elements.automation, state.automationStates);

  fillSelect(elements.filterType, state.testingTypes.map((item) => item.name), "All testing types");
  fillSelect(elements.filterStatus, state.statuses, "All statuses");
  fillSelect(elements.filterPriority, state.priorities, "All priorities");
  fillSelect(elements.filterAutomation, state.automationStates, "All automation");

  clearForm();
}

async function refreshData() {
  const params = getFilterParams();
  const query = params.toString() ? `?${params.toString()}` : "";
  const [caseData, analyticsData] = await Promise.all([
    requestJSON(`/api/test-cases${query}`),
    requestJSON(`/api/analytics${query}`),
  ]);

  state.cases = caseData.cases;
  state.analytics = analyticsData.analytics;
  renderEverything();
}

function renderEverything() {
  renderMetrics();
  renderBars();
  renderTable();
  renderBoard();
  updateTypeNavState();
}

function renderTypeNav() {
  elements.typeNav.innerHTML = "";

  const allButton = document.createElement("button");
  allButton.className = "nav-button active";
  allButton.type = "button";
  allButton.dataset.type = "";
  allButton.innerHTML = "<strong>All testing</strong><small>Complete test portfolio</small>";
  allButton.addEventListener("click", () => selectType(""));
  elements.typeNav.appendChild(allButton);

  state.testingTypes.forEach((type) => {
    const button = document.createElement("button");
    button.className = "nav-button";
    button.type = "button";
    button.dataset.type = type.name;
    button.innerHTML = `<strong>${escapeHTML(type.name)}</strong><small>${escapeHTML(type.focus)}</small>`;
    button.addEventListener("click", () => selectType(type.name));
    elements.typeNav.appendChild(button);
  });
}

function updateTypeNavState() {
  document.querySelectorAll(".nav-button").forEach((button) => {
    button.classList.toggle("active", button.dataset.type === state.selectedType);
  });
}

function selectType(typeName) {
  state.selectedType = typeName;
  elements.filterType.value = typeName;
  closeMobileSidebar();
  refreshData();
}

function renderMetrics() {
  const analytics = state.analytics;
  elements.metricTotal.textContent = analytics.total;
  elements.metricActive.textContent = `${analytics.active} active`;
  elements.metricPassRate.textContent = `${analytics.pass_rate}%`;
  elements.metricPassed.textContent = `${analytics.passed} passed`;
  elements.metricRisk.textContent = analytics.risk_score;
  elements.metricCritical.textContent = `${analytics.critical_open} critical open`;
  elements.metricAutomation.textContent = `${analytics.automation_rate}%`;
  elements.caseCountPill.textContent = `${analytics.total} ${analytics.total === 1 ? "case" : "cases"}`;
}

function renderBars() {
  renderBarList(elements.statusBars, state.analytics.by_status, state.analytics.total);
  renderBarList(elements.typeBars, state.analytics.by_type, state.analytics.total, true);
}

function renderBarList(container, source, total, dense = false) {
  container.innerHTML = "";
  Object.entries(source).forEach(([label, value]) => {
    const percentage = total ? Math.round((value / total) * 100) : 0;
    const row = document.createElement("div");
    row.className = `bar-row ${dense ? "dense-row" : ""}`;
    row.innerHTML = `
      <span title="${escapeHTML(label)}">${escapeHTML(label)}</span>
      <div class="bar-track" aria-label="${escapeHTML(label)} ${percentage}%">
        <div class="bar-fill" style="width: ${percentage}%"></div>
      </div>
      <strong>${value}</strong>
    `;
    container.appendChild(row);
  });
}

function renderTable() {
  elements.caseTableBody.innerHTML = "";
  if (!state.cases.length) {
    const row = document.createElement("tr");
    row.innerHTML = '<td colspan="6" class="empty-state">No test cases match the current filters.</td>';
    elements.caseTableBody.appendChild(row);
    return;
  }

  state.cases.forEach((testCase) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>
        <span class="case-title">${escapeHTML(testCase.title)}</span>
        <span class="case-meta">${escapeHTML(testCase.requirement)}</span>
        <div class="row-actions">
          <button class="ghost-button" type="button" data-action="edit" data-id="${testCase.id}">Edit</button>
          <button class="ghost-button" type="button" data-action="quick-pass" data-id="${testCase.id}">Pass</button>
          <button class="ghost-button" type="button" data-action="quick-fail" data-id="${testCase.id}">Fail</button>
        </div>
      </td>
      <td>${escapeHTML(testCase.testing_type)}</td>
      <td>${statusPill(testCase.status)}</td>
      <td>${priorityPill(testCase.priority)}</td>
      <td>${escapeHTML(testCase.owner || "Unassigned")}</td>
      <td><span class="automation-pill">${escapeHTML(testCase.automation)}</span></td>
    `;
    row.querySelector('[data-action="edit"]').addEventListener("click", () => editCase(testCase.id));
    row.querySelector('[data-action="quick-pass"]').addEventListener("click", () => quickStatus(testCase.id, "Passed"));
    row.querySelector('[data-action="quick-fail"]').addEventListener("click", () => quickStatus(testCase.id, "Failed"));
    elements.caseTableBody.appendChild(row);
  });
}

function renderBoard() {
  elements.boardView.innerHTML = "";
  const grouped = Object.fromEntries(state.statuses.map((status) => [status, []]));
  state.cases.forEach((testCase) => {
    grouped[testCase.status] = grouped[testCase.status] || [];
    grouped[testCase.status].push(testCase);
  });

  state.statuses.forEach((status) => {
    const column = document.createElement("section");
    column.className = "board-column";
    const cases = grouped[status] || [];
    column.innerHTML = `
      <h4>${escapeHTML(status)} <span>${cases.length}</span></h4>
      <div class="board-items"></div>
    `;
    const items = column.querySelector(".board-items");
    if (!cases.length) {
      items.innerHTML = '<p class="empty-state">No cases</p>';
    } else {
      cases.forEach((testCase) => {
        const card = document.createElement("article");
        card.className = "case-card";
        card.innerHTML = `
          <strong>${escapeHTML(testCase.title)}</strong>
          <p>${escapeHTML(testCase.testing_type)}</p>
          <div class="card-footer">
            ${priorityPill(testCase.priority)}
            <button class="ghost-button compact" type="button">Edit</button>
          </div>
        `;
        card.querySelector("button").addEventListener("click", () => editCase(testCase.id));
        items.appendChild(card);
      });
    }
    elements.boardView.appendChild(column);
  });
}

function fillSelect(select, options, placeholder = "") {
  select.innerHTML = "";
  if (placeholder) {
    const placeholderOption = document.createElement("option");
    placeholderOption.value = "";
    placeholderOption.textContent = placeholder;
    select.appendChild(placeholderOption);
  }
  options.forEach((option) => {
    const item = document.createElement("option");
    item.value = option;
    item.textContent = option;
    select.appendChild(item);
  });
}

async function handleSubmit(event) {
  event.preventDefault();
  const payload = getFormPayload();
  const caseId = elements.caseId.value;
  const url = caseId ? `/api/test-cases/${caseId}` : "/api/test-cases";
  const method = caseId ? "PUT" : "POST";

  try {
    await requestJSON(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    showToast(caseId ? "Test case updated." : "Test case created.");
    clearForm();
    await refreshData();
  } catch (error) {
    showToast(error.message || "Unable to save test case.");
  }
}

function getFormPayload() {
  return {
    title: elements.title.value,
    testing_type: elements.testingType.value,
    status: elements.status.value,
    priority: elements.priority.value,
    automation: elements.automation.value,
    owner: elements.owner.value,
    environment: elements.environment.value,
    requirement: elements.requirement.value,
    steps: elements.steps.value,
    expected_result: elements.expectedResult.value,
    actual_result: elements.actualResult.value,
    tags: elements.tags.value,
  };
}

function clearForm() {
  elements.caseForm.reset();
  elements.caseId.value = "";
  elements.formTitle.textContent = "Create test case";
  elements.deleteCaseBtn.disabled = true;
  elements.status.value = "Not Started";
  elements.priority.value = "Medium";
  elements.automation.value = "Manual";
  if (state.selectedType) {
    elements.testingType.value = state.selectedType;
  }
}

async function editCase(caseId) {
  const data = await requestJSON(`/api/test-cases/${caseId}`);
  const testCase = data.case;
  elements.caseId.value = testCase.id;
  elements.formTitle.textContent = `Editing #${testCase.id}`;
  elements.title.value = testCase.title;
  elements.testingType.value = testCase.testing_type;
  elements.status.value = testCase.status;
  elements.priority.value = testCase.priority;
  elements.automation.value = testCase.automation;
  elements.owner.value = testCase.owner;
  elements.environment.value = testCase.environment;
  elements.requirement.value = testCase.requirement;
  elements.steps.value = testCase.steps;
  elements.expectedResult.value = testCase.expected_result;
  elements.actualResult.value = testCase.actual_result;
  elements.tags.value = testCase.tags;
  elements.deleteCaseBtn.disabled = false;
  document.querySelector(".form-panel").scrollIntoView({ behavior: "smooth", block: "start" });
}

async function quickStatus(caseId, status) {
  const testCase = state.cases.find((item) => item.id === caseId);
  if (!testCase) return;
  await requestJSON(`/api/test-cases/${caseId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...testCase, status }),
  });
  showToast(`Case marked ${status.toLowerCase()}.`);
  await refreshData();
}

async function handleDelete() {
  const caseId = elements.caseId.value;
  if (!caseId) return;
  const confirmed = window.confirm("Delete this test case?");
  if (!confirmed) return;
  await requestJSON(`/api/test-cases/${caseId}`, { method: "DELETE" });
  showToast("Test case deleted.");
  clearForm();
  await refreshData();
}

function getFilterParams() {
  const params = new URLSearchParams();
  const values = {
    search: elements.searchInput.value.trim(),
    testing_type: elements.filterType.value,
    status: elements.filterStatus.value,
    priority: elements.filterPriority.value,
    automation: elements.filterAutomation.value,
  };

  Object.entries(values).forEach(([key, value]) => {
    if (value) params.set(key, value);
  });
  return params;
}

function clearFilters() {
  elements.searchInput.value = "";
  elements.filterType.value = "";
  elements.filterStatus.value = "";
  elements.filterPriority.value = "";
  elements.filterAutomation.value = "";
  state.selectedType = "";
  return refreshData();
}

function setView(view) {
  state.view = view;
  elements.tableView.classList.toggle("hidden", view !== "table");
  elements.boardView.classList.toggle("hidden", view !== "board");
  elements.tableViewBtn.classList.toggle("active", view === "table");
  elements.boardViewBtn.classList.toggle("active", view === "board");
}

async function exportCases() {
  const response = await fetch("/api/export");
  if (!response.ok) {
    showToast("Export failed.");
    return;
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "test-cases-export.json";
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
  showToast("Export downloaded.");
}

async function downloadPdfReport() {
  const response = await fetch("/api/export-pdf");
  if (!response.ok) {
    showToast("PDF download failed.");
    return;
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "qa-test-report.pdf";
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
  showToast("PDF report downloaded.");
}

async function importCases(event) {
  const file = event.target.files[0];
  if (!file) return;
  try {
    const text = await file.text();
    const json = JSON.parse(text);
    const payload = Array.isArray(json) ? { cases: json } : json;
    const result = await requestJSON("/api/import", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    showToast(`Imported ${result.imported} cases. ${result.skipped.length} skipped.`);
    await refreshData();
  } catch (error) {
    showToast(error.message || "Import failed.");
  } finally {
    event.target.value = "";
  }
}

async function resetDemo() {
  const confirmed = window.confirm("Restore the original demo cases? Current cases will be replaced.");
  if (!confirmed) return;
  await requestJSON("/api/reset-demo", { method: "POST" });
  clearForm();
  await clearFilters();
  showToast("Demo data restored.");
}

function toggleQuickMenu(event) {
  event.stopPropagation();
  const willOpen = elements.quickMenu.classList.contains("hidden");
  elements.quickMenu.classList.toggle("hidden", !willOpen);
  elements.menuToggleBtn.setAttribute("aria-expanded", String(willOpen));
}

function closeQuickMenu() {
  elements.quickMenu.classList.add("hidden");
  elements.menuToggleBtn.setAttribute("aria-expanded", "false");
}

function closeQuickMenuOnOutsideClick(event) {
  const clickedInsideMenu = elements.quickMenu.contains(event.target);
  const clickedToggle = elements.menuToggleBtn.contains(event.target);
  if (!clickedInsideMenu && !clickedToggle) {
    closeQuickMenu();
  }
}

function closeQuickMenuOnEscape(event) {
  if (event.key === "Escape") {
    closeQuickMenu();
  }
}

function openMenuTarget(targetId) {
  const target = document.getElementById(targetId);
  if (!target) return;
  closeQuickMenu();
  target.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function handleLiveTestSubmit(event) {
  event.preventDefault();
  const payload = {
    base_url: elements.liveBaseUrl.value,
    pages: elements.livePages.value,
    expected_keywords: elements.liveKeywords.value,
    check_links: elements.liveCheckLinks.checked,
  };

  elements.runLiveTestBtn.disabled = true;
  elements.runLiveTestBtn.textContent = "Running...";
  elements.liveRunStatus.textContent = "Running";

  try {
    const data = await requestJSON("/api/live-test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    renderLiveRun(data.run);
    await refreshLiveHistory();
    showToast(`Live test ${data.run.summary.status.toLowerCase()}.`);
  } catch (error) {
    elements.liveRunStatus.textContent = "Run failed";
    showToast(error.message || "Live test failed.");
  } finally {
    elements.runLiveTestBtn.disabled = false;
    elements.runLiveTestBtn.textContent = "Run Real Page Test";
  }
}

async function refreshLiveHistory() {
  const data = await requestJSON("/api/live-runs");
  state.liveRuns = data.runs;
  renderLiveHistory();
}

async function openLiveRun(runId) {
  const data = await requestJSON(`/api/live-runs/${runId}`);
  renderLiveRun(data.run);
}

async function deleteLiveRun(runId) {
  const confirmed = window.confirm("Delete this live run history item?");
  if (!confirmed) return;
  await requestJSON(`/api/live-runs/${runId}`, { method: "DELETE" });
  showToast("Live run deleted.");
  await refreshLiveHistory();
}

function renderLiveRun(run) {
  elements.liveRunStatus.textContent = run.summary.status;
  elements.liveRunStatus.className = `live-pill status-${classToken(run.summary.status)}`;
  elements.liveSummary.className = "live-summary";
  elements.liveSummary.innerHTML = `
    <div class="summary-grid">
      <div class="summary-item"><span>Status</span><strong>${escapeHTML(run.summary.status)}</strong></div>
      <div class="summary-item"><span>Pages</span><strong>${run.summary.pages_total}</strong></div>
      <div class="summary-item"><span>Passed</span><strong>${run.summary.passed_pages}</strong></div>
      <div class="summary-item"><span>Warnings</span><strong>${run.summary.warning_pages}</strong></div>
      <div class="summary-item"><span>Broken Links</span><strong>${run.summary.broken_links}</strong></div>
    </div>
  `;

  const pageCards = run.page_results.map(renderPageResult).join("");
  const linkCards = run.link_results.length ? renderLinkResults(run.link_results) : "";
  elements.liveResults.innerHTML = pageCards + linkCards;
}

function renderPageResult(page) {
  const checks = page.checks.map((check) => {
    const typeClass = check.passed ? "pass" : check.severity === "warning" ? "warn" : "fail";
    const icon = check.passed ? "OK" : check.severity === "warning" ? "!" : "X";
    return `
      <div class="check-item ${typeClass}">
        <span class="check-icon">${icon}</span>
        <span><strong>${escapeHTML(check.name)}:</strong> ${escapeHTML(check.message)}</span>
      </div>
    `;
  }).join("");

  const buttonSignals = page.buttons.slice(0, 8).map((button) => `
    <span class="signal-chip"><span>Button: ${escapeHTML(button.text || button.type)}</span></span>
  `).join("");
  const formSignals = page.forms.slice(0, 4).map((form) => `
    <span class="signal-chip"><span>Form: ${escapeHTML(form.method)} ${form.input_count} inputs</span></span>
  `).join("");
  const linkSignals = page.links.slice(0, 8).map((link) => `
    <span class="signal-chip"><span>Link: ${escapeHTML(link.text || link.href)}</span></span>
  `).join("");
  const signals = buttonSignals + formSignals + linkSignals;

  return `
    <article class="page-result">
      <div class="result-head">
        <div>
          <h4>${escapeHTML(page.page)} ${page.title ? `- ${escapeHTML(page.title)}` : ""}</h4>
          <span class="result-url">${escapeHTML(page.url)} | HTTP ${page.status_code || "N/A"} | ${page.load_ms} ms</span>
        </div>
        ${statusPill(page.status)}
      </div>
      <div class="check-list">${checks}</div>
      <div class="signal-list">${signals || '<span class="signal-chip"><span>No page signals detected</span></span>'}</div>
    </article>
  `;
}

function renderLinkResults(links) {
  const items = links.map((link) => {
    const typeClass = link.ok ? "pass" : "fail";
    const icon = link.ok ? "OK" : "X";
    const message = link.status_code ? `HTTP ${link.status_code}` : link.error;
    return `
      <div class="check-item ${typeClass}">
        <span class="check-icon">${icon}</span>
        <span><strong>${escapeHTML(link.label || link.url)}:</strong> ${escapeHTML(message)} <span class="result-url">${escapeHTML(link.url)}</span></span>
      </div>
    `;
  }).join("");

  return `
    <article class="page-result">
      <div class="result-head">
        <div>
          <h4>Internal navigation links</h4>
          <span class="result-url">${links.length} links checked</span>
        </div>
      </div>
      <div class="check-list">${items}</div>
    </article>
  `;
}

function renderLiveHistory() {
  if (!state.liveRuns.length) {
    elements.liveHistory.className = "live-history empty-state";
    elements.liveHistory.textContent = "No live runs saved yet.";
    return;
  }

  elements.liveHistory.className = "live-history";
  elements.liveHistory.innerHTML = "";
  state.liveRuns.forEach((run) => {
    const item = document.createElement("div");
    item.className = "history-item";
    item.innerHTML = `
      <div class="history-main">
        <strong>${escapeHTML(run.base_url)}</strong>
        <span>${escapeHTML(run.created_at)} | ${run.summary.pages_total} pages | ${run.summary.status}</span>
      </div>
      <div class="history-actions">
        <button class="ghost-button compact" type="button" data-action="open">Open</button>
        <button class="danger-button compact" type="button" data-action="delete">Delete</button>
      </div>
    `;
    item.querySelector('[data-action="open"]').addEventListener("click", () => openLiveRun(run.id));
    item.querySelector('[data-action="delete"]').addEventListener("click", () => deleteLiveRun(run.id));
    elements.liveHistory.appendChild(item);
  });
}

async function handleAutomationSubmit(event) {
  event.preventDefault();
  const payload = {
    scenario_name: elements.automationScenario.value,
    base_url: elements.automationBaseUrl.value,
    steps: elements.automationSteps.value,
    timeout_ms: Number(elements.automationTimeout.value),
    headless: elements.automationHeadless.checked,
  };

  elements.runAutomationBtn.disabled = true;
  elements.runAutomationBtn.textContent = "Running...";
  elements.automationRunStatus.textContent = "Running";

  try {
    const data = await requestJSON("/api/automation-run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    renderAutomationRun(data.run);
    await refreshAutomationHistory();
    showToast(`Automation ${data.run.summary.status.toLowerCase()}.`);
  } catch (error) {
    elements.automationRunStatus.textContent = "Run failed";
    showToast(error.message || "Automation failed.");
  } finally {
    elements.runAutomationBtn.disabled = false;
    elements.runAutomationBtn.textContent = "Run Automation";
  }
}

async function refreshAutomationHistory() {
  const data = await requestJSON("/api/automation-runs");
  state.automationRuns = data.runs;
  renderAutomationHistory();
}

async function openAutomationRun(runId) {
  const data = await requestJSON(`/api/automation-runs/${runId}`);
  renderAutomationRun(data.run);
}

async function deleteAutomationRun(runId) {
  const confirmed = window.confirm("Delete this automation run history item?");
  if (!confirmed) return;
  await requestJSON(`/api/automation-runs/${runId}`, { method: "DELETE" });
  showToast("Automation run deleted.");
  await refreshAutomationHistory();
}

function renderAutomationRun(run) {
  elements.automationRunStatus.textContent = run.summary.status;
  elements.automationRunStatus.className = `live-pill status-${classToken(run.summary.status)}`;
  elements.automationSummary.className = "live-summary";
  elements.automationSummary.innerHTML = `
    <div class="summary-grid">
      <div class="summary-item"><span>Status</span><strong>${escapeHTML(run.summary.status)}</strong></div>
      <div class="summary-item"><span>Steps</span><strong>${run.summary.steps_total}</strong></div>
      <div class="summary-item"><span>Passed</span><strong>${run.summary.passed_steps}</strong></div>
      <div class="summary-item"><span>Failed</span><strong>${run.summary.failed_steps}</strong></div>
      <div class="summary-item"><span>Final Page</span><strong>${escapeHTML(run.summary.page_title || "N/A")}</strong></div>
    </div>
    ${run.summary.setup_message ? `<div class="step-line">${escapeHTML(run.summary.setup_message)}</div>` : ""}
    ${run.summary.final_url ? `<div class="step-line">${escapeHTML(run.summary.final_url)}</div>` : ""}
  `;

  elements.automationResults.innerHTML = run.step_results.map((step) => {
    const typeClass = step.passed ? "pass" : "fail";
    const icon = step.passed ? "OK" : "X";
    return `
      <article class="step-result">
        <h4>Line ${step.line || "-"}: ${escapeHTML(step.command)}</h4>
        <div class="check-item ${typeClass}">
          <span class="check-icon">${icon}</span>
          <span><strong>${escapeHTML(step.target || "step")}:</strong> ${escapeHTML(step.message)}</span>
        </div>
        <span class="step-line">${step.duration_ms} ms</span>
      </article>
    `;
  }).join("");
}

function renderAutomationHistory() {
  if (!state.automationRuns.length) {
    elements.automationHistory.className = "live-history empty-state";
    elements.automationHistory.textContent = "No automation runs saved yet.";
    return;
  }

  elements.automationHistory.className = "live-history";
  elements.automationHistory.innerHTML = "";
  state.automationRuns.forEach((run) => {
    const item = document.createElement("div");
    item.className = "history-item";
    item.innerHTML = `
      <div class="history-main">
        <strong>${escapeHTML(run.scenario_name)}</strong>
        <span>${escapeHTML(run.created_at)} | ${run.summary.steps_total} steps | ${run.summary.status}</span>
      </div>
      <div class="history-actions">
        <button class="ghost-button compact" type="button" data-action="open">Open</button>
        <button class="danger-button compact" type="button" data-action="delete">Delete</button>
      </div>
    `;
    item.querySelector('[data-action="open"]').addEventListener("click", () => openAutomationRun(run.id));
    item.querySelector('[data-action="delete"]').addEventListener("click", () => deleteAutomationRun(run.id));
    elements.automationHistory.appendChild(item);
  });
}

async function handleApiTestSubmit(event) {
  event.preventDefault();
  const payload = {
    suite_name: elements.apiSuiteName.value,
    base_url: elements.apiBaseUrl.value,
    engine: elements.apiEngine.value,
    timeout_ms: Number(elements.apiTimeout.value),
    headers: elements.apiHeaders.value,
    requests: elements.apiRequests.value,
  };

  elements.runApiTestBtn.disabled = true;
  elements.runApiTestBtn.textContent = "Running...";
  elements.apiRunStatus.textContent = "Running";

  try {
    const data = await requestJSON("/api/api-test-runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    renderApiRun(data.run);
    await refreshApiHistory();
    showToast(`API test ${data.run.summary.status.toLowerCase()}.`);
  } catch (error) {
    elements.apiRunStatus.textContent = "Run failed";
    showToast(error.message || "API test failed.");
  } finally {
    elements.runApiTestBtn.disabled = false;
    elements.runApiTestBtn.textContent = "Run API Test";
  }
}

async function refreshApiHistory() {
  const data = await requestJSON("/api/api-test-runs");
  state.apiRuns = data.runs;
  renderApiHistory();
}

async function openApiRun(runId) {
  const data = await requestJSON(`/api/api-test-runs/${runId}`);
  renderApiRun(data.run);
}

async function deleteApiRun(runId) {
  const confirmed = window.confirm("Delete this API test run history item?");
  if (!confirmed) return;
  await requestJSON(`/api/api-test-runs/${runId}`, { method: "DELETE" });
  showToast("API test run deleted.");
  await refreshApiHistory();
}

function renderApiRun(run) {
  elements.apiRunStatus.textContent = run.summary.status;
  elements.apiRunStatus.className = `live-pill status-${classToken(run.summary.status)}`;
  elements.apiSummary.className = "live-summary";
  elements.apiSummary.innerHTML = `
    <div class="summary-grid">
      <div class="summary-item"><span>Status</span><strong>${escapeHTML(run.summary.status)}</strong></div>
      <div class="summary-item"><span>Requests</span><strong>${run.summary.requests_total}</strong></div>
      <div class="summary-item"><span>Passed</span><strong>${run.summary.passed_requests}</strong></div>
      <div class="summary-item"><span>Failed</span><strong>${run.summary.failed_requests}</strong></div>
      <div class="summary-item"><span>Avg Time</span><strong>${run.summary.average_ms} ms</strong></div>
    </div>
    <div class="step-line">Engine: ${escapeHTML(run.engine)}</div>
    ${run.summary.setup_message ? `<div class="step-line">${escapeHTML(run.summary.setup_message)}</div>` : ""}
  `;

  elements.apiResults.innerHTML = run.request_results.map((requestResult) => {
    const typeClass = requestResult.passed ? "pass" : "fail";
    const icon = requestResult.passed ? "OK" : "X";
    const checks = requestResult.checks.map((check) => `
      <div class="check-item ${check.passed ? "pass" : "fail"}">
        <span class="check-icon">${check.passed ? "OK" : "X"}</span>
        <span><strong>${escapeHTML(check.name)}:</strong> ${escapeHTML(check.message)}</span>
      </div>
    `).join("");
    return `
      <article class="step-result">
        <h4>${escapeHTML(requestResult.method)} ${escapeHTML(requestResult.url)}</h4>
        <div class="check-item ${typeClass}">
          <span class="check-icon">${icon}</span>
          <span><strong>HTTP ${requestResult.status_code || "N/A"}:</strong> ${requestResult.duration_ms} ms</span>
        </div>
        <div class="check-list">${checks}</div>
        ${requestResult.response_excerpt ? `<span class="step-line">${escapeHTML(requestResult.response_excerpt)}</span>` : ""}
      </article>
    `;
  }).join("");
}

function renderApiHistory() {
  if (!state.apiRuns.length) {
    elements.apiHistory.className = "live-history empty-state";
    elements.apiHistory.textContent = "No API test runs saved yet.";
    return;
  }

  elements.apiHistory.className = "live-history";
  elements.apiHistory.innerHTML = "";
  state.apiRuns.forEach((run) => {
    const item = document.createElement("div");
    item.className = "history-item";
    item.innerHTML = `
      <div class="history-main">
        <strong>${escapeHTML(run.suite_name)}</strong>
        <span>${escapeHTML(run.created_at)} | ${escapeHTML(run.engine)} | ${run.summary.requests_total} requests | ${run.summary.status}</span>
      </div>
      <div class="history-actions">
        <button class="ghost-button compact" type="button" data-action="open">Open</button>
        <button class="danger-button compact" type="button" data-action="delete">Delete</button>
      </div>
    `;
    item.querySelector('[data-action="open"]').addEventListener("click", () => openApiRun(run.id));
    item.querySelector('[data-action="delete"]').addEventListener("click", () => deleteApiRun(run.id));
    elements.apiHistory.appendChild(item);
  });
}

async function requestJSON(url, options = {}) {
  const response = await fetch(url, options);
  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json") ? await response.json() : null;

  if (!response.ok) {
    const message = data?.error || data?.errors?.join(", ") || `Request failed: ${response.status}`;
    throw new Error(message);
  }
  return data;
}

function statusPill(status) {
  return `<span class="status-pill status-${classToken(status)}">${escapeHTML(status)}</span>`;
}

function priorityPill(priority) {
  return `<span class="priority-pill priority-${classToken(priority)}">${escapeHTML(priority)}</span>`;
}

function classToken(value) {
  return String(value).replace(/[^a-zA-Z0-9]+/g, "-").replace(/^-|-$/g, "");
}

function escapeHTML(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function debounce(fn, delay) {
  let timeoutId;
  return (...args) => {
    window.clearTimeout(timeoutId);
    timeoutId = window.setTimeout(() => fn(...args), delay);
  };
}

function showToast(message) {
  elements.toast.textContent = message;
  elements.toast.classList.add("show");
  window.clearTimeout(showToast.timeoutId);
  showToast.timeoutId = window.setTimeout(() => {
    elements.toast.classList.remove("show");
  }, 2800);
}
