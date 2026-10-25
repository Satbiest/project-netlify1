'use strict';

// Only public deployment settings belong here. The Gemini key stays on FastAPI.
const deployment = window.CVBOOST_CONFIG || {};
const staticFrontend = deployment.staticMode === true;
const apiBaseUrl = typeof deployment.apiBaseUrl === 'string' ? deployment.apiBaseUrl.replace(/\/+$/, '') : '';
const apiEndpoint = path => `${apiBaseUrl}${path}`;
let liveAnalysisAvailable = !staticFrontend;

const $ = (id) => document.getElementById(id);
const form = $('analysis-form');
const jobInput = $('job-description');
const fileInput = $('resume');
const tabs = [...document.querySelectorAll('[role="tab"]')];
let selectedFile = null;
let currentAnalysis = null;
let busy = false;
let showEvidence = false;
let inputsChanged = false;

const SAMPLE_JOB = `Data Analyst
We are looking for a Data Analyst to turn business data into clear insights.
Required skills: Python, SQL, data cleaning, data visualization, communication, and Power BI.
You will prepare datasets, analyze performance trends, build interactive dashboards, and present findings to stakeholders.
Preferred skills: Excel, Git, and dbt. You should enjoy collaborating with product and business teams.`;

// Build all AI-derived content with textContent, never interpolated HTML.
function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
function icon(name) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.classList.add('icon'); svg.setAttribute('aria-hidden', 'true');
  const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
  use.setAttribute('href', '#i-' + name); svg.append(use); return svg;
}
function errorMessage(message) {
  $('form-error').textContent = message;
  $('form-error').hidden = !message;
}
function updateCounter() { $('character-count').textContent = jobInput.value.length.toLocaleString(); }
function invalidateAnalysis() {
  if (!currentAnalysis) return;
  inputsChanged = true;
  $('result-badge').textContent = 'Inputs changed · process to update';
  $('result-badge').classList.add('demo');
  $('export-button').disabled = true;
}
function selectFile(file) {
  if (busy || !file) return;
  errorMessage('');
  const maxMB = Number(fileInput.dataset.maxMb);
  if (!file.name.toLowerCase().endsWith('.pdf')) return errorMessage('Choose a PDF resume.');
  if (!file.size) return errorMessage('This file is empty. Choose another PDF.');
  if (file.size > maxMB * 1024 * 1024) return errorMessage(`Your PDF must be no larger than ${maxMB} MB.`);
  selectedFile = file;
  $('file-name').textContent = file.name;
  $('file-size').textContent = `${(file.size / 1024).toFixed(0)} KB · Ready to analyze`;
  $('selected-file').hidden = false; $('drop-zone').hidden = true;
  invalidateAnalysis();
}
fileInput.addEventListener('change', () => selectFile(fileInput.files[0]));
$('remove-file').addEventListener('click', () => {
  if (busy) return;
  selectedFile = null; fileInput.value = '';
  $('selected-file').hidden = true; $('drop-zone').hidden = false;
  invalidateAnalysis(); fileInput.focus();
});
const dropZone = $('drop-zone');
['dragenter', 'dragover'].forEach(type => dropZone.addEventListener(type, event => {
  event.preventDefault(); if (!busy) dropZone.classList.add('is-dragover');
}));
['dragleave', 'drop'].forEach(type => dropZone.addEventListener(type, event => {
  event.preventDefault(); dropZone.classList.remove('is-dragover');
}));
dropZone.addEventListener('drop', event => {
  if (!busy && event.dataTransfer.files.length === 1) selectFile(event.dataTransfer.files[0]);
  else if (!busy) errorMessage('Please choose one PDF resume at a time.');
});
jobInput.addEventListener('input', () => { updateCounter(); invalidateAnalysis(); });
$('example-job-button').addEventListener('click', () => {
  if (busy) return;
  jobInput.value = SAMPLE_JOB; updateCounter(); invalidateAnalysis(); jobInput.focus();
});

function setBusy(value, label = 'Reading your PDF, comparing skills, and building your recommendations…') {
  busy = value;
  ['process-button', 'sample-button', 'empty-example', 'example-job-button', 'remove-file', 'consent', 'resume', 'job-description'].forEach(id => {
    if ($(id)) $(id).disabled = value;
  });
  $('process-button').disabled = value || !liveAnalysisAvailable;
  $('results-column').setAttribute('aria-busy', String(value));
  $('export-button').disabled = value || !currentAnalysis || inputsChanged;
  $('process-label').textContent = value ? 'Processing…' : 'Process';
  $('process-icon').classList.toggle('spin', value);
  $('process-status').textContent = value ? label : '';
}

async function readResponse(response) {
  let payload;
  try { payload = await response.json(); }
  catch { throw new Error('The server returned an unexpected response. Please try again.'); }
  if (!response.ok) throw new Error(payload.error?.message || 'The analysis could not be completed. Please try again.');
  return payload;
}
form.addEventListener('submit', async event => {
  event.preventDefault(); if (busy) return;
  errorMessage('');
  if (!liveAnalysisAvailable) return errorMessage('Connect a configured CVBoost Python backend to analyze your resume. You can explore the sample analysis now.');
  if (!selectedFile) { errorMessage('Upload your PDF resume first, or try the sample analysis.'); fileInput.focus(); return; }
  const job = jobInput.value.trim();
  if (job.length < 80 || job.length > Number(jobInput.maxLength)) {
    errorMessage(`Add a job description between 80 and ${jobInput.maxLength} characters.`); jobInput.focus(); return;
  }
  if (!$('consent').checked) { errorMessage('Please allow sending the extracted text to Google Gemini before processing.'); $('consent').focus(); return; }
  const body = new FormData();
  body.append('resume', selectedFile); body.append('job_description', job); body.append('consent', 'true');
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 240000);
  setBusy(true);
  try {
    const response = await fetch(apiEndpoint('/api/analyze'), { method: 'POST', body, signal: controller.signal });
    const analysis = await readResponse(response);
    renderAnalysis(analysis);
    $('process-status').textContent = 'Your analysis is ready.';
  } catch (error) {
    errorMessage(error.name === 'AbortError' ? 'Analysis timed out. Please try again after the server model finishes loading.' : error.message || 'Could not connect to the server.');
  } finally { clearTimeout(timer); setBusy(false); }
});

async function loadSample() {
  if (busy) return;
  errorMessage(''); setBusy(true, 'Opening a fictional, precomputed example. No resume is sent to AI.');
  try {
    const data = await readResponse(await fetch(staticFrontend ? '/data/demo.json' : apiEndpoint('/api/demo'), { cache: 'no-store' }));
    jobInput.value = SAMPLE_JOB; updateCounter(); renderAnalysis(data);
  } catch (error) { errorMessage(error.message); }
  finally { setBusy(false); }
}
['sample-button', 'empty-example'].forEach(id => { if ($(id)) $(id).addEventListener('click', loadSample); });

function showMetric(name, value, detail) {
  const target = $('metric-' + name); target.replaceChildren();
  if (value === null || value === undefined) target.textContent = 'N/A';
  else { target.append(document.createTextNode(Number(value).toFixed(1)), element('small', '', '%')); }
  $('bar-' + name).style.width = `${value == null ? 0 : Math.max(0, Math.min(100, value))}%`;
  $('detail-' + name).textContent = detail;
}

function renderSkills(skills) {
  const matched = skills.filter(skill => skill.status === 'matched');
  const missing = skills.filter(skill => skill.status === 'missing');
  $('matched-count').textContent = matched.length;
  $('gap-count').textContent = missing.length;
  const matchedContainer = $('matched-skills'); matchedContainer.replaceChildren();
  const categories = ['Programming Languages', 'Data Analysis', 'Databases', 'Tools', 'Soft Skills'];
  for (const category of categories) {
    const group = matched.filter(skill => skill.category === category);
    if (!group.length) continue;
    const section = element('section', 'skill-group');
    section.append(element('h4', '', category));
    const chips = element('div', 'skill-chips');
    const evidence = element('div', 'evidence-list'); evidence.hidden = !showEvidence;
    for (const skill of group) {
      const chip = element('span', 'skill-chip'); chip.append(icon('check'), document.createTextNode(skill.name)); chips.append(chip);
      const quote = element('p'); quote.append(element('strong', '', skill.name + ': '), document.createTextNode(skill.evidence)); evidence.append(quote);
    }
    section.append(chips, evidence); matchedContainer.append(section);
  }
  if (!matched.length) matchedContainer.append(element('p', 'panel-empty', 'No source-backed skill matches were identified. Make your relevant experience explicit in your resume.'));
  const missingContainer = $('missing-skills'); missingContainer.replaceChildren();
  for (const skill of [...missing].sort((a,b) => (a.priority === b.priority ? 0 : a.priority === 'required' ? -1 : 1))) {
    const row = element('div', 'gap-row'); const label = element('div');
    label.append(element('strong', '', skill.name), element('small', '', skill.category));
    row.append(label, element('span', 'priority-tag' + (skill.priority === 'preferred' ? ' preferred' : ''), skill.priority === 'required' ? 'Required' : 'Preferred'));
    missingContainer.append(row);
  }
  if (!missing.length) missingContainer.append(element('p', 'panel-empty', skills.length ? 'All extracted skill requirements have supporting resume evidence. Focus on strengthening your examples and outcomes.' : 'Add explicit skill requirements to your job description to see skill gaps.'));
}
$('evidence-button').addEventListener('click', () => {
  showEvidence = !showEvidence;
  $('evidence-button').setAttribute('aria-pressed', String(showEvidence));
  $('evidence-button').textContent = showEvidence ? 'Hide evidence' : 'Show evidence';
  document.querySelectorAll('.evidence-list').forEach(list => { list.hidden = !showEvidence; });
});

function renderResumeSection(name, title, entries) {
  const panel = $('panel-' + name); panel.replaceChildren(element('h3', '', title));
  if (!entries.length) { panel.append(element('p', 'panel-empty', 'No source-backed information was identified for this section.')); return; }
  for (const entry of entries) {
    const card = element('article', 'resume-entry');
    card.append(element('h4', '', entry.title));
    if (entry.subtitle) card.append(element('p', 'entry-subtitle', entry.subtitle));
    card.append(element('p', '', entry.detail), element('blockquote', '', 'Resume evidence: ' + entry.evidence));
    panel.append(card);
  }
}
function renderRecommendations(recommendations) {
  $('recommendation-narrative').textContent = recommendations.narrative;
  const plan = $('action-plan'); plan.replaceChildren();
  recommendations.action_plan.forEach((step, index) => {
    const card = element('article', 'action-step');
    const heading = element('div', 'step-overline');
    heading.append(element('span', '', String(index + 1).padStart(2, '0') + ' / ' + step.priority.toUpperCase()), element('span', '', step.horizon));
    card.append(heading, element('h4', '', step.skill), element('p', '', step.action), element('p', 'deliverable', 'Build: ' + step.deliverable)); plan.append(card);
  });
  const roles = $('related-roles'); roles.replaceChildren();
  for (const role of recommendations.related_roles) {
    const card = element('article', 'role-card'); card.append(icon('briefcase'), element('h4', '', role.title), element('p', '', role.reason)); roles.append(card);
  }
  $('roles-title').closest('section').hidden = !recommendations.related_roles.length;
}
function renderAnalysis(data) {
  currentAnalysis = data; inputsChanged = false;
  $('empty-state').hidden = true; $('analysis-results').hidden = false; $('result-context').hidden = false;
  const isDemo = data.metadata.mode === 'demo';
  $('result-badge').textContent = isDemo ? 'Sample analysis · fictional data' : 'Analysis complete';
  $('result-badge').classList.toggle('demo', isDemo);
  $('target-role').textContent = data.job_title;
  $('result-meta').textContent = isDemo ? 'Alex Morgan · precomputed example · no AI call' : `${data.metadata.filename} · ${data.metadata.pages} page${data.metadata.pages === 1 ? '' : 's'} · ${(data.metadata.elapsed_ms / 1000).toFixed(1)}s`;
  const scores = data.scores;
  showMetric('total', scores.total, 'Weighted overall alignment');
  showMetric('required', scores.required.score, scores.required.total ? `${scores.required.matched} of ${scores.required.total} skills evidenced` : 'No explicit required skills found');
  showMetric('preferred', scores.preferred.score, scores.preferred.total ? `${scores.preferred.matched} of ${scores.preferred.total} skills evidenced` : 'No explicit preferred skills found');
  showMetric('semantic', scores.semantic, isDemo ? 'Illustrative semantic score' : 'MiniLM + cosine similarity');
  renderSkills(data.skills);
  renderResumeSection('education', 'Education', data.education);
  renderResumeSection('experience', 'Experience', data.experience);
  renderResumeSection('achievements', 'Achievements', data.achievements);
  const profile = $('panel-profile'); profile.replaceChildren(element('h3', '', 'Profile'));
  profile.append(element('div', 'profile-name', data.profile.name || 'Name not identified'), element('p', 'profile-headline', data.profile.headline), element('p', 'profile-summary', data.profile.summary || 'No profile summary was identified.'));
  const target = element('article', 'resume-entry'); target.style.marginTop = '24px';
  target.append(element('h4', '', 'Target role context'), element('p', '', data.enriched_description)); profile.append(target);
  renderRecommendations(data.recommendations);
  const names = {required:'required skill coverage', preferred:'preferred skill coverage', semantic:'semantic similarity'};
  $('score-formula').textContent = 'Overall = ' + Object.entries(scores.weights).map(([key, value]) => `${(value * 100).toFixed(0)}% ${names[key]}`).join(' + ') + '. Components without explicit requirements are excluded and the remaining weights are normalized.';
  const notes = $('analysis-notes'); notes.replaceChildren();
  data.notes.forEach(note => notes.append(element('li', '', note)));
  $('export-button').disabled = false; activateTab('skills');
}

function activateTab(name, focus = false) {
  for (const tab of tabs) {
    const selected = tab.dataset.tab === name;
    tab.setAttribute('aria-selected', String(selected)); tab.tabIndex = selected ? 0 : -1;
    $('panel-' + tab.dataset.tab).hidden = !selected;
    if (selected && focus) tab.focus();
  }
}
tabs.forEach((tab, index) => {
  tab.addEventListener('click', () => activateTab(tab.dataset.tab));
  tab.addEventListener('keydown', event => {
    let next;
    if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
    if (event.key === 'ArrowLeft') next = (index - 1 + tabs.length) % tabs.length;
    if (event.key === 'Home') next = 0;
    if (event.key === 'End') next = tabs.length - 1;
    if (next !== undefined) { event.preventDefault(); activateTab(tabs[next].dataset.tab, true); }
  });
});

$('export-button').addEventListener('click', () => {
  if (!currentAnalysis || inputsChanged || busy) return;
  const blob = new Blob([JSON.stringify(currentAnalysis, null, 2)], {type:'application/json'});
  const url = URL.createObjectURL(blob); const anchor = document.createElement('a');
  anchor.href = url; anchor.download = `cvboost-${currentAnalysis.metadata.mode}-report.json`;
  document.body.append(anchor); anchor.click(); anchor.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
});
const howDialog = $('how-dialog');
$('how-button').addEventListener('click', () => howDialog.showModal());
$('close-how').addEventListener('click', () => howDialog.close());
howDialog.addEventListener('click', event => {
  const rect = howDialog.getBoundingClientRect();
  if (event.target === howDialog && (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom)) howDialog.close();
});

async function initialize() {
  if (staticFrontend && !apiBaseUrl) {
    $('server-light').classList.add('sample');
    $('server-status').textContent = 'Preview ready · sample analysis available';
    $('setup-notice').hidden = false;
    $('setup-notice').textContent = 'Preview mode: explore the fictional sample analysis. Connect a deployed CVBoost Python backend to analyze your own resume.';
    $('process-button').disabled = true;
    updateCounter();
    return;
  }
  try {
    const health = await readResponse(await fetch(apiEndpoint('/api/health'), {cache:'no-store'}));
    const ready = health.analysis_configured && health.parser_installed && health.encoder_installed;
    if (staticFrontend) liveAnalysisAvailable = Boolean(ready);
    $('server-light').classList.add(ready ? 'ready' : 'sample');
    $('server-status').textContent = ready ? 'Ready for your next move' : health.demo_enabled ? 'Sample analysis ready to explore' : 'Live analysis needs configuration';
    $('setup-notice').hidden = ready;
    if (health.analysis_configured && !ready) $('setup-notice').textContent = 'The server still needs the PDF and semantic model dependencies. Install requirements.txt to enable live analysis.';
  } catch {
    if (staticFrontend) liveAnalysisAvailable = false;
    $('server-status').textContent = 'Server connection unavailable';
    $('setup-notice').hidden = false; $('setup-notice').textContent = staticFrontend ? 'The configured backend could not be reached. Check its URL and allowed origins. The sample analysis is still available.' : 'Could not connect to the CVBoost API. Open this app through its FastAPI server and try refreshing.';
  }
  $('process-button').disabled = busy || !liveAnalysisAvailable;
  updateCounter();
}
initialize();
