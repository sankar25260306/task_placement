import { useEffect, useMemo, useState, type FormEvent, type ChangeEvent } from "react";
import InterviewRoom from "./InterviewRoom";
import AIInterviewAdmin from "./AIInterviewAdmin";
import {
  Activity, ArrowDownToLine, ArrowRight, Bell, Check, CheckCircle2,
  ChevronDown, CircleHelp, ClipboardCheck, Clock3, FileText, FolderKanban,
  LayoutDashboard, LogOut, Plus, RefreshCw, Search, Send, Settings2,
  ShieldCheck, Sparkles, Users, Workflow, X, BrainCircuit, GitBranch, AlertTriangle, ShieldAlert, Video
} from "lucide-react";

const API = (import.meta as any).env?.VITE_API_URL || "http://127.0.0.1:8000";

type Project = { id: number; name: string; client_name: string; description: string };
type Intern = { id: number; name: string; email: string; skills: string[] };
type Task = { id: number; title: string; description: string; status: string; acceptance_criteria: string[]; requirement_codes: string[]; assigned_intern_id: number | null; due_at: string | null };
type Submission = { id: number; task_id: number; task_title: string; intern_id: number; intern_name: string; version: number; repository_url: string; notes: string; evidence: Record<string, unknown>; submitted_at: string; qa_report: any };
type Dashboard = { intern_count: number; project_count: number; task_count: number; submission_count: number; task_status_counts: Record<string, number> };

async function request(path: string, token: string, init: RequestInit = {}) {
  const headers = new Headers(init.headers || {});
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (!(init.body instanceof FormData) && init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const response = await fetch(`${API}${path}`, { ...init, headers });
  const raw = await response.text();
  let data: any = null;
  try { data = raw ? JSON.parse(raw) : null; } catch { data = raw; }
  if (!response.ok) {
    const detail = typeof data?.detail === "string" ? data.detail : data?.detail ? JSON.stringify(data.detail) : raw || response.statusText;
    throw new Error(`${response.status}: ${detail}`);
  }
  return data;
}

const statusClass = (status: string) => status.toLowerCase().replaceAll("_", "-");
function App() {
  const [token, setToken] = useState(localStorage.getItem("internmind_token") || "");
  const [role, setRole] = useState(localStorage.getItem("internmind_role") || "");
  const [email, setEmail] = useState("admin@example.com");
  const [password, setPassword] = useState("ChangeThisPassword123!");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [page, setPage] = useState("Overview");
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState<number | "">("");
  const [tasks, setTasks] = useState<Task[]>([]);
  const [interns, setInterns] = useState<Intern[]>([]);
  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [agentReport, setAgentReport] = useState<any>(null);
  const [query, setQuery] = useState("");
  const [showProject, setShowProject] = useState(false);
  const [projectForm, setProjectForm] = useState({ name: "", client_name: "Thozhil", description: "" });
  const [reqForm, setReqForm] = useState({ code: "", description: "", acceptance_evidence: "" });
  const [taskForm, setTaskForm] = useState({ title: "", description: "", criteria: "", requirements: "" });
  const [assignForm, setAssignForm] = useState({ taskId: "", internId: "", dueAt: "", reviewAt: "", meetUrl: "" });
  const [reviewForm, setReviewForm] = useState({ submissionId: "", decision: "CORRECTION_REQUIRED", feedback: "" });

  async function loadCore(currentToken = token) {
    const [dash, proj] = await Promise.all([
      request("/dashboard", currentToken),
      request("/projects", currentToken)
    ]);
    setDashboard(dash); setProjects(proj);
    const selected = projectId || (proj[0]?.id ?? "");
    if (selected !== "") {
      setProjectId(selected as number);
      await loadProject(selected as number, currentToken);
    } else {
      setTasks([]); setInterns([]); setSubmissions([]);
    }
  }
  async function loadProject(id: number, currentToken = token) {
    const [taskRows, internRows, submissionRows] = await Promise.all([
      request(`/projects/${id}/tasks`, currentToken),
      request(`/projects/${id}/interns`, currentToken),
      request(`/projects/${id}/submissions`, currentToken)
    ]);
    setTasks(taskRows); setInterns(internRows); setSubmissions(submissionRows);
  }
  useEffect(() => {
    if (!token) return;
    loadCore().catch(e => { setError(e.message); if (String(e.message).startsWith("401")) logout(); });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);
  const selectedProject = projects.find(p => p.id === projectId);
  const filteredTasks = useMemo(() => tasks.filter(t => `${t.title} ${t.description} ${t.status}`.toLowerCase().includes(query.toLowerCase())), [tasks, query]);

  function logout() {
    localStorage.removeItem("internmind_token"); localStorage.removeItem("internmind_role");
    setToken(""); setRole(""); setDashboard(null); setProjects([]); setProjectId(""); setTasks([]); setInterns([]); setSubmissions([]);
  }
  async function run(action: () => Promise<void>) {
    setBusy(true); setError(""); setNotice("");
    try { await action(); } catch (e: any) { setError(e?.message || "Something went wrong"); }
    finally { setBusy(false); }
  }
  async function login(e: FormEvent) {
    e.preventDefault();
    await run(async () => {
      const result = await request("/auth/login", "", { method: "POST", body: JSON.stringify({ email, password }) });
      localStorage.setItem("internmind_token", result.access_token); localStorage.setItem("internmind_role", result.role);
      setRole(result.role); setToken(result.access_token); setNotice("Signed in successfully.");
    });
  }
  async function createProject(e: FormEvent) {
    e.preventDefault();
    await run(async () => {
      const created = await request("/projects", token, { method: "POST", body: JSON.stringify(projectForm) });
      setShowProject(false); setProjectForm({ name: "", client_name: "Thozhil", description: "" });
      await loadCore(); setProjectId(created.id); await loadProject(created.id); setNotice("Project created.");
    });
  }
  async function addRequirement(e: FormEvent) {
    e.preventDefault();
    if (projectId === "") return;
    await run(async () => {
      await request(`/projects/${projectId}/requirements`, token, { method: "POST", body: JSON.stringify(reqForm) });
      setReqForm({ code: "", description: "", acceptance_evidence: "" }); setNotice("Requirement added. You can link its code to a task.");
    });
  }
  async function importCsv(e: ChangeEvent<HTMLInputElement>) {
    const file = e.currentTarget.files?.[0];
    if (!file || projectId === "") return;
    await run(async () => {
      const body = new FormData(); body.append("file", file);
      const result = await request(`/projects/${projectId}/interns/import`, token, { method: "POST", body });
      await loadProject(Number(projectId));
      setNotice(`Import finished: ${result.created.length} created, ${result.skipped.length} skipped.`);
      e.currentTarget.value = "";
    });
  }
  async function createTask(e: FormEvent) {
    e.preventDefault();
    if (projectId === "") return;
    await run(async () => {
      const payload = {
        title: taskForm.title, description: taskForm.description,
        acceptance_criteria: taskForm.criteria.split("\n").map(s => s.trim()).filter(Boolean),
        requirement_codes: taskForm.requirements.split(",").map(s => s.trim().toUpperCase()).filter(Boolean),
        depends_on_task_ids: []
      };
      await request(`/projects/${projectId}/tasks`, token, { method: "POST", body: JSON.stringify(payload) });
      setTaskForm({ title: "", description: "", criteria: "", requirements: "" });
      await loadProject(Number(projectId)); await loadCore(); setNotice("Task created and requirement traceability recorded.");
    });
  }
  async function assignTask(e: FormEvent) {
    e.preventDefault();
    await run(async () => {
      if (!assignForm.taskId || !assignForm.internId || !assignForm.dueAt) throw new Error("Choose a task, intern and deadline.");
      await request(`/tasks/${assignForm.taskId}/assign`, token, {
        method: "POST", body: JSON.stringify({ intern_id: Number(assignForm.internId), due_at: new Date(assignForm.dueAt).toISOString(), review_at: assignForm.reviewAt ? new Date(assignForm.reviewAt).toISOString() : null, meet_url: assignForm.meetUrl.trim() })
      });
      setAssignForm({ taskId: "", internId: "", dueAt: "", reviewAt: "", meetUrl: "" });
      await loadProject(Number(projectId)); await loadCore(); setNotice("Task assigned. Email is sent if SMTP is configured; otherwise it is logged in the backend terminal.");
    });
  }
  async function loadAgentIntelligence() {
    if (projectId === "") throw new Error("Select a project first.");
    const result = await request(`/projects/${projectId}/agent-intelligence`, token);
    setAgentReport(result);
  }
  async function runQa(id: number) {
    await run(async () => {
      const result = await request(`/submissions/${id}/qa`, token, { method: "POST" });
      await loadProject(Number(projectId)); setNotice(`Evidence QA complete: ${result.report.overall}. Mentor review is still required.`);
    });
  }
  async function reviewSubmission(e: FormEvent) {
    e.preventDefault();
    await run(async () => {
      const result = await request(`/submissions/${reviewForm.submissionId}/review`, token, {
        method: "POST", body: JSON.stringify({ decision: reviewForm.decision, feedback: reviewForm.feedback })
      });
      setReviewForm({ submissionId: "", decision: "CORRECTION_REQUIRED", feedback: "" });
      await loadProject(Number(projectId)); await loadCore();
      setNotice(result.decision === "APPROVED" ? "Submission approved." : `Correction requested. Correction cycle #${result.correction_cycle_id} created.`);
    });
  }

  if (window.location.pathname.startsWith("/interview")) return <InterviewRoom />;

  if (!token) return <div className="login-shell">
    <div className="login-art">
      <div className="brand"><span className="brand-mark"><Sparkles size={20}/></span><span>InternMind<span className="brand-ai"> AI</span></span></div>
      <div className="login-copy"><div className="eyebrow light"><span className="pulse"></span> AUTONOMOUS INTERNSHIP OPERATIONS</div><h1>Turn every task into <em>measurable progress.</em></h1><p>One workspace to allocate work, connect requirements, review evidence and keep every intern moving forward.</p>
        <div className="login-features"><div><ShieldCheck size={18}/> Requirement traceability</div><div><Workflow size={18}/> Task allocation workflows</div><div><ClipboardCheck size={18}/> Evidence-first review</div></div>
      </div>
      <div className="login-foot">INTERNMIND AI · PROJECT OPERATIONS PLATFORM</div>
    </div>
    <div className="login-panel"><form className="login-form" onSubmit={login}>
      <div className="mobile-brand"><span className="brand-mark"><Sparkles size={18}/></span> InternMind AI</div>
      <div className="eyebrow">WELCOME BACK</div><h2>Sign in to workspace</h2><p className="muted">Use the admin email and password from your backend `.env` file.</p>
      {error && <div className="alert error"><X size={16}/>{error}</div>}
      <label>Email address<input type="email" value={email} onChange={e=>setEmail(e.target.value)} required autoComplete="username"/></label>
      <label>Password<input type="password" value={password} onChange={e=>setPassword(e.target.value)} required autoComplete="current-password"/></label>
      <button className="primary wide" disabled={busy}>{busy ? "Signing in…" : "Sign in"} <ArrowRight size={17}/></button>
      <div className="login-tip"><CircleHelp size={16}/><span>Default starter login, if unchanged: <b>admin@example.com</b> / <b>ChangeThisPassword123!</b></span></div>
    </form><div className="secure-note"><ShieldCheck size={15}/> Protected with token-based authentication</div></div>
  </div>;

  const nav = [
    { label: "WORKSPACE", items: [{ name: "Overview", icon: LayoutDashboard }, { name: "Projects", icon: FolderKanban }, { name: "Task board", icon: ClipboardCheck }, { name: "Interns", icon: Users }, { name: "Reviews", icon: ShieldCheck }, { name: "Agent Intelligence", icon: BrainCircuit }, { name: "AI Interviews", icon: Video }] },
    { label: "SYSTEM", items: [{ name: "Activity log", icon: Activity }] }
  ];
  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><span className="brand-mark"><Sparkles size={20}/></span><span>InternMind<span className="brand-ai"> AI</span></span></div>
      <div className="workspace-pill"><div className="workspace-icon">T</div><div><strong>Thozhil workspace</strong><small>Internship operations</small></div><ChevronDown size={15}/></div>
      <nav>{nav.map(group=><div className="nav-group" key={group.label}><div className="nav-label">{group.label}</div>{group.items.map(item=><button key={item.name} className={`nav-item ${page===item.name?"active":""}`} onClick={()=>setPage(item.name)}><item.icon size={18}/><span>{item.name}</span>{item.name==="Reviews"&&submissions.length>0&&<span className="nav-count">{submissions.length}</span>}</button>)}</div>)}</nav>
      <div className="sidebar-bottom"><div className="help-card"><div className="help-icon"><CircleHelp size={17}/></div><strong>Need a hand?</strong><p>Set up your first project and task workflow.</p><button onClick={()=>setPage("Projects")}>Open setup guide <ArrowRight size={14}/></button></div><div className="user-row"><div className="avatar">A</div><div className="user-info"><strong>Project Admin</strong><small>{role || "admin"}</small></div><button className="icon-btn" title="Sign out" onClick={logout}><LogOut size={17}/></button></div></div>
    </aside>
    <main className="main-area">
      <header className="topbar"><div className="breadcrumb">Workspace <span>/</span> <b>{page}</b></div><div className="top-actions"><div className="api-status"><span></span> API connected</div><button className="icon-btn" onClick={()=>run(async()=>{await loadCore();setNotice("Data refreshed.");})} title="Refresh"><RefreshCw size={17}/></button><button className="icon-btn notification" title="Notifications"><Bell size={17}/><i></i></button><div className="top-avatar">A</div></div></header>
      <div className="page-content">
        {error && <div className="alert error"><X size={16}/><span>{error}</span><button className="alert-close" onClick={()=>setError("")}><X size={14}/></button></div>}
        {notice && <div className="alert success"><CheckCircle2 size={17}/><span>{notice}</span><button className="alert-close" onClick={()=>setNotice("")}><X size={14}/></button></div>}
        {page==="Overview" && <><div className="page-heading"><div><div className="eyebrow">MONDAY, OCTOBER 26 · OPERATIONS</div><h1>Good work starts with clarity.</h1><p>Here’s the current pulse of your internship workspace.</p></div><button className="primary" onClick={()=>setShowProject(true)}><Plus size={17}/> New project</button></div>
          <div className="welcome-banner"><div className="banner-orb"><Sparkles size={24}/></div><div><div className="banner-kicker">YOUR WORKSPACE, IN SYNC</div><h2>Every task has a purpose. Every review has evidence.</h2><p>Start with a project, map requirements, then assign clear tasks to each intern.</p></div><div className="banner-art"><div className="orbit orbit-one"></div><div className="orbit orbit-two"></div><div className="banner-core"><Workflow size={28}/></div></div></div>
          <div className="section-title"><div><h3>Workspace overview</h3><p>Live totals from your backend database</p></div><span className="live-label"><span></span> LIVE DATA</span></div>
          <div className="stats-grid">
            <Stat icon={<FolderKanban size={19}/>} label="Projects" value={dashboard?.project_count ?? "—"} hint="Active workspaces" tone="violet"/>
            <Stat icon={<Users size={19}/>} label="Interns" value={dashboard?.intern_count ?? "—"} hint="Imported profiles" tone="blue"/>
            <Stat icon={<ClipboardCheck size={19}/>} label="Tasks" value={dashboard?.task_count ?? "—"} hint="Tracked deliverables" tone="orange"/>
            <Stat icon={<FileText size={19}/>} label="Submissions" value={dashboard?.submission_count ?? "—"} hint="Evidence received" tone="green"/>
          </div>
          <div className="content-grid"><section className="panel project-panel"><div className="panel-head"><div><h3>Projects</h3><p>Choose a project to manage its workflow</p></div><button className="text-button" onClick={()=>setPage("Projects")}>View all <ArrowRight size={14}/></button></div>
            {projects.length===0?<Empty icon={<FolderKanban size={22}/>} title="No projects yet" text="Create your first project to start organizing requirements and tasks." action="Create project" onAction={()=>setShowProject(true)}/>:<div className="project-list">{projects.slice(0,4).map(p=><button className={`project-row ${projectId===p.id?"selected":""}`} key={p.id} onClick={()=>{setProjectId(p.id);loadProject(p.id).catch(e=>setError(e.message));setPage("Task board");}}><div className="project-symbol"><FolderKanban size={18}/></div><div className="project-meta"><strong>{p.name}</strong><small>{p.client_name||"No client"} · Project #{p.id}</small></div><ArrowRight size={16}/></button>)}</div>}
          </section><section className="panel status-panel"><div className="panel-head"><div><h3>Task status</h3><p>Where work stands right now</p></div><span className="soft-tag">ALL TASKS</span></div><div className="status-list">{["READY","ASSIGNED","SUBMITTED","REVIEW_PENDING","CORRECTION_REQUIRED","APPROVED"].map((s,i)=><div className="status-line" key={s}><span className={`status-dot dot-${i}`}></span><span>{s.replaceAll("_"," ")}</span><strong>{dashboard?.task_status_counts?.[s] ?? 0}</strong></div>)}</div></section></div>
        </>}
        {page==="Projects" && <><PageHeading title="Projects" subtitle="Create and manage the projects your interns contribute to." action={<button className="primary" onClick={()=>setShowProject(true)}><Plus size={17}/> New project</button>}/><div className="project-cards">{projects.map(p=><div className="panel project-card" key={p.id}><div className="project-card-top"><div className="project-symbol large"><FolderKanban size={21}/></div><span className="soft-tag">PROJECT #{p.id}</span></div><h3>{p.name}</h3><p>{p.description||"No project description added yet."}</p><div className="project-client"><span>Client</span><b>{p.client_name||"—"}</b></div><button className="secondary wide" onClick={()=>{setProjectId(p.id);loadProject(p.id).catch(e=>setError(e.message));setPage("Task board");}}>Manage project <ArrowRight size={16}/></button></div>)}
          {projects.length===0&&<Empty icon={<FolderKanban size={22}/>} title="Your first project starts here" text="Create a project to begin tracking requirements and tasks." action="Create project" onAction={()=>setShowProject(true)}/>}</div></>}
        {page==="Task board" && <><PageHeading title="Task board" subtitle={selectedProject?`Manage work for ${selectedProject.name}.`:"Select or create a project to start."} action={<button className="primary" onClick={()=>setPage("Projects")}><FolderKanban size={16}/> Choose project</button>}/>
          <div className="toolbar"><div className="project-select"><FolderKanban size={17}/><select value={projectId} onChange={e=>{const id=Number(e.target.value);setProjectId(id);run(()=>loadProject(id));}}><option value="">Select project</option>{projects.map(p=><option value={p.id} key={p.id}>{p.name}</option>)}</select><ChevronDown size={14}/></div><div className="search-box"><Search size={16}/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search tasks…"/></div></div>
          {projectId!==""&&<><section className="panel form-panel requirement-panel"><div className="panel-head"><div><h3>Map a requirement</h3><p>Create a traceable requirement before linking it to a task.</p></div><span className="step-badge">REQ</span></div><form onSubmit={addRequirement} className="stack-form requirement-form"><label>Requirement code<input value={reqForm.code} onChange={e=>setReqForm({...reqForm,code:e.target.value})} required placeholder="e.g. REQ-01"/></label><label>Requirement description<textarea value={reqForm.description} onChange={e=>setReqForm({...reqForm,description:e.target.value})} required rows={2} placeholder="What must the project satisfy?"/></label><label>Evidence needed <small>What should prove the requirement?</small><input value={reqForm.acceptance_evidence} onChange={e=>setReqForm({...reqForm,acceptance_evidence:e.target.value})} placeholder="e.g. screenshot, test result, report"/></label><button className="secondary wide" disabled={busy}><Plus size={16}/> Add requirement</button></form></section><div className="workflow-grid"><section className="panel form-panel"><div className="panel-head"><div><h3>Create a task</h3><p>Define clear outcomes before assigning.</p></div><span className="step-badge">01</span></div><form onSubmit={createTask} className="stack-form"><label>Task title<input value={taskForm.title} onChange={e=>setTaskForm({...taskForm,title:e.target.value})} required placeholder="e.g. Build intern dashboard"/></label><label>Description<textarea value={taskForm.description} onChange={e=>setTaskForm({...taskForm,description:e.target.value})} required rows={3} placeholder="Explain scope and expected output…"/></label><label>Acceptance criteria <small>One criterion per line</small><textarea value={taskForm.criteria} onChange={e=>setTaskForm({...taskForm,criteria:e.target.value})} rows={3} placeholder={"Dashboard loads on mobile\nAPI errors are displayed clearly"}/></label><label>Requirement codes <small>Comma separated, e.g. REQ-01, REQ-02</small><input value={taskForm.requirements} onChange={e=>setTaskForm({...taskForm,requirements:e.target.value})} placeholder="REQ-01, REQ-02"/></label><button className="primary wide" disabled={busy}><Plus size={16}/> Create task</button></form></section>
            <section className="panel form-panel"><div className="panel-head"><div><h3>Assign to an intern</h3><p>Choose a task owner and deadline.</p></div><span className="step-badge">02</span></div><form onSubmit={assignTask} className="stack-form"><label>Unassigned task<select required value={assignForm.taskId} onChange={e=>setAssignForm({...assignForm,taskId:e.target.value})}><option value="">Select task</option>{tasks.filter(t=>!t.assigned_intern_id).map(t=><option key={t.id} value={t.id}>#{t.id} · {t.title}</option>)}</select></label><label>Intern<select required value={assignForm.internId} onChange={e=>setAssignForm({...assignForm,internId:e.target.value})}><option value="">Select intern</option>{interns.map(i=><option key={i.id} value={i.id}>{i.name} · {i.email}</option>)}</select></label><label>Submission deadline<input type="datetime-local" required value={assignForm.dueAt} onChange={e=>setAssignForm({...assignForm,dueAt:e.target.value})}/></label><label>Review meeting date & time<input type="datetime-local" value={assignForm.reviewAt} onChange={e=>setAssignForm({...assignForm,reviewAt:e.target.value})}/><small>Optional. Included in the task email when set.</small></label><label>Google Meet link<input type="url" placeholder="https://meet.google.com/..." value={assignForm.meetUrl} onChange={e=>setAssignForm({...assignForm,meetUrl:e.target.value})}/><small>Create the meeting in Google Calendar first, then paste its link.</small></label><div className="info-note"><Bell size={16}/><span>Task email is sent when SMTP is configured. Otherwise, an email preview is printed in the backend terminal.</span></div><button className="primary wide" disabled={busy||interns.length===0||tasks.every(t=>!!t.assigned_intern_id)}><Send size={16}/> Assign task</button>{interns.length===0&&<small className="warning-text">Import intern profiles first using the Interns page.</small>}</form></section></div></>}
          <section className="panel task-table-panel"><div className="panel-head"><div><h3>Tasks {selectedProject&&<span className="inline-muted">· {selectedProject.name}</span>}</h3><p>{filteredTasks.length} task(s) in this project</p></div><button className="icon-btn" onClick={()=>projectId!==""&&run(()=>loadProject(Number(projectId)))} title="Refresh tasks"><RefreshCw size={16}/></button></div><div className="table-wrap"><table><thead><tr><th>Task</th><th>Requirement DNA</th><th>Assignee</th><th>Deadline</th><th>Status</th></tr></thead><tbody>{filteredTasks.map(t=><tr key={t.id}><td><div className="task-title"><span className="task-id">#{t.id}</span><div><strong>{t.title}</strong><small>{t.description}</small></div></div></td><td>{t.requirement_codes?.length?<div className="chips">{t.requirement_codes.map(c=><span key={c}>{c}</span>)}</div>:<span className="muted">Not linked</span>}</td><td>{interns.find(i=>i.id===t.assigned_intern_id)?.name||"Unassigned"}</td><td>{t.due_at?new Date(t.due_at).toLocaleString():"—"}</td><td><span className={`status-pill ${statusClass(t.status)}`}>{t.status.replaceAll("_"," ")}</span></td></tr>)}</tbody></table>{filteredTasks.length===0&&<div className="empty-table">No tasks match this view yet.</div>}</div></section>
        </>}
        {page==="Interns" && <><PageHeading title="Intern directory" subtitle="Import intern profiles from a CSV and assign work to them."/><div className="import-layout"><section className="panel import-panel"><div className="upload-icon"><ArrowDownToLine size={22}/></div><h3>Import interns</h3><p>Upload a CSV with <code>name,email</code> columns and optional <code>skills</code>. Separate multiple skills with semicolons.</p><div className="csv-example"><span>name</span><span>email</span><span>skills</span><b>Alex</b><b>alex@example.com</b><b>Python; SQL</b></div><a className="download-link" href="/interns_template.csv" download><ArrowDownToLine size={15}/> Download CSV template</a><label className="file-button">Choose CSV file<input type="file" accept=".csv,text/csv" onChange={e=>importCsv(e)} disabled={projectId===""||busy}/></label>{projectId===""&&<small className="warning-text">Select a project first.</small>}</section><section className="panel directory-panel"><div className="panel-head"><div><h3>Interns</h3><p>{interns.length} profiles available to assign</p></div><span className="soft-tag">{selectedProject?.name||"No project selected"}</span></div><div className="table-wrap"><table><thead><tr><th>Name</th><th>Email</th><th>Skills</th></tr></thead><tbody>{interns.map(i=><tr key={i.id}><td><div className="person-cell"><div className="avatar">{i.name.slice(0,1).toUpperCase()}</div><strong>{i.name}</strong></div></td><td>{i.email}</td><td><div className="chips">{i.skills?.length?i.skills.map(s=><span key={s}>{s}</span>):<span className="muted">Not provided</span>}</div></td></tr>)}</tbody></table>{interns.length===0&&<div className="empty-table">No intern profiles yet. Import a CSV to begin.</div>}</div></section></div></>}
        {page==="Reviews" && <><PageHeading title="Submission reviews" subtitle="Run evidence checks, then record the mentor's final decision."/><div className="review-notice"><ShieldCheck size={20}/><div><strong>Human-in-the-loop review</strong><p>Automated QA checks submission metadata and evidence presence only. It does not execute submitted code or prove correctness. A mentor must make the final decision.</p></div></div><div className="panel task-table-panel"><div className="panel-head"><div><h3>Submissions</h3><p>Choose a submission to run QA or review.</p></div><button className="icon-btn" onClick={()=>projectId!==""&&run(()=>loadProject(Number(projectId)))}><RefreshCw size={16}/></button></div><div className="table-wrap"><table><thead><tr><th>Submission</th><th>Intern</th><th>Submitted</th><th>QA status</th><th>Actions</th></tr></thead><tbody>{submissions.map(s=><tr key={s.id}><td><div><strong>#{s.id} · {s.task_title}</strong><small>Version {s.version} · Task #{s.task_id}</small>{s.repository_url&&<a href={s.repository_url} target="_blank" rel="noreferrer">{s.repository_url}</a>}</div></td><td>{s.intern_name}</td><td>{new Date(s.submitted_at).toLocaleString()}</td><td>{s.qa_report?<span className="status-pill review-pending">{s.qa_report.overall||"QA complete"}</span>:<span className="muted">Not run</span>}</td><td><div className="row-actions"><button className="small-button" onClick={()=>runQa(s.id)} disabled={busy}>Run QA</button><button className="small-button dark" onClick={()=>setReviewForm({...reviewForm,submissionId:String(s.id)})}>Review</button></div></td></tr>)}</tbody></table>{submissions.length===0&&<div className="empty-table">No submissions yet. Intern submission login activation is not included in this MVP; submissions can currently be created through the API.</div>}</div></div>
          <section className="panel review-form-panel"><div className="panel-head"><div><h3>Record review decision</h3><p>Use a correction request when work needs changes.</p></div></div><form className="review-form" onSubmit={reviewSubmission}><label>Submission ID<input type="number" min="1" required value={reviewForm.submissionId} onChange={e=>setReviewForm({...reviewForm,submissionId:e.target.value})} placeholder="e.g. 12"/></label><label>Decision<select value={reviewForm.decision} onChange={e=>setReviewForm({...reviewForm,decision:e.target.value})}><option value="CORRECTION_REQUIRED">Correction required</option><option value="APPROVED">Approved</option></select></label><label className="feedback-field">Feedback / mentor notes<textarea required={reviewForm.decision==="CORRECTION_REQUIRED"} value={reviewForm.feedback} onChange={e=>setReviewForm({...reviewForm,feedback:e.target.value})} rows={2} placeholder="Explain what to change or add approval notes…"/></label><button className="primary" disabled={busy}><Check size={16}/> Save decision</button></form></section>
        </>}
        {page==="Agent Intelligence" && <><PageHeading title="Multi-agent project intelligence" subtitle="Five specialist agents inspect delivery risk, requirement traceability, dependencies, integration contracts and review evidence." action={<button className="primary" disabled={busy||projectId===""} onClick={()=>run(async()=>{await loadAgentIntelligence();setNotice("Agent analysis completed.");})}><BrainCircuit size={17}/> Run agent analysis</button>}/>
          <div className="review-notice"><BrainCircuit size={20}/><div><strong>Explainable multi-agent orchestration</strong><p>These agents use project database signals and transparent rules. They do not pretend to execute code or read private repositories. Human mentor approval remains required.</p></div></div>
          {!agentReport ? <section className="panel empty-state"><div className="empty-icon"><BrainCircuit size={24}/></div><h3>Ready to analyze this project</h3><p>Select a project from Task board or Projects, then run the agent analysis.</p></section> : <><div className="stats-grid"><Stat icon={<AlertTriangle size={19}/>} label="Risk signals" value={agentReport.summary?.risk_count ?? 0} hint="Needs attention" tone="orange"/><Stat icon={<GitBranch size={19}/>} label="Dependency links" value={agentReport.summary?.dependency_count ?? 0} hint="Connected tasks" tone="blue"/><Stat icon={<ShieldCheck size={19}/>} label="Evidence gaps" value={agentReport.summary?.evidence_gap_count ?? 0} hint="Submission checks" tone="violet"/><Stat icon={<ShieldAlert size={19}/>} label="Human escalations" value={agentReport.summary?.human_escalation_count ?? 0} hint="Mentor review needed" tone="green"/></div>
          <div className="project-cards">{(agentReport.agents||[]).map((agent:any)=><section className="panel project-card" key={agent.name}><div className="project-card-top"><div className="project-symbol large"><BrainCircuit size={21}/></div><span className={`status-pill ${agent.findings?.length?"correction-required":"approved"}`}>{agent.findings?.length ? `${agent.findings.length} finding(s)` : "No signal"}</span></div><h3>{agent.name}</h3><p>{agent.purpose}</p>{agent.findings?.length ? <ul>{agent.findings.map((f:any,i:number)=><li key={i}><strong>{f.severity}</strong> — {f.message}{f.task_id ? ` (Task #${f.task_id})` : ""}</li>)}</ul> : <p className="muted">No rule-based findings from the available project data.</p>}</section>)}</div>
          <section className="panel task-table-panel"><div className="panel-head"><div><h3>Recommended actions</h3><p>Prioritized next steps from the orchestrator.</p></div></div>{agentReport.recommended_actions?.length ? <ol>{agentReport.recommended_actions.map((a:any,i:number)=><li key={i}>{a}</li>)}</ol> : <p className="empty-table">No additional action generated.</p>}</section></>}
        </>}
        {page==="AI Interviews" && <AIInterviewAdmin token={token} projectId={projectId} tasks={tasks} interns={interns} submissions={submissions} />}
        {page==="Activity log" && <ActivityLog token={token} />}
      </div>
    </main>
    {showProject&&<div className="modal-backdrop" onMouseDown={e=>{if(e.target===e.currentTarget)setShowProject(false);}}><form className="modal" onSubmit={createProject}><div className="modal-head"><div><div className="eyebrow">WORKSPACE SETUP</div><h2>Create a project</h2><p>Give your intern team a shared goal and scope.</p></div><button type="button" className="icon-btn" onClick={()=>setShowProject(false)}><X size={18}/></button></div><label>Project name<input required minLength={2} value={projectForm.name} onChange={e=>setProjectForm({...projectForm,name:e.target.value})} placeholder="e.g. InternMind AI Platform"/></label><label>Client name<input value={projectForm.client_name} onChange={e=>setProjectForm({...projectForm,client_name:e.target.value})} placeholder="e.g. Thozhil"/></label><label>Description<textarea value={projectForm.description} onChange={e=>setProjectForm({...projectForm,description:e.target.value})} rows={3} placeholder="What will this project deliver?"/></label><div className="modal-actions"><button type="button" className="secondary" onClick={()=>setShowProject(false)}>Cancel</button><button className="primary" disabled={busy}><Plus size={16}/> Create project</button></div></form></div>}
  </div>;
}

function Stat({icon,label,value,hint,tone}:{icon:React.ReactNode;label:string;value:string|number;hint:string;tone:string}) {
  return <div className="stat-card"><div className={`stat-icon ${tone}`}>{icon}</div><div className="stat-label">{label}</div><div className="stat-value">{value}</div><div className="stat-hint">{hint}</div></div>;
}
function PageHeading({title,subtitle,action}:{title:string;subtitle:string;action?:React.ReactNode}) {
  return <div className="page-heading"><div><h1>{title}</h1><p>{subtitle}</p></div>{action}</div>;
}
function Empty({icon,title,text,action,onAction}:{icon:React.ReactNode;title:string;text:string;action:string;onAction:()=>void}) {
  return <div className="empty-state"><div className="empty-icon">{icon}</div><h3>{title}</h3><p>{text}</p><button className="secondary" onClick={onAction}>{action} <ArrowRight size={15}/></button></div>;
}
function ActivityLog({token}:{token:string}) {
  const [rows,setRows] = useState<any[]>([]);
  const [error,setError] = useState("");
  useEffect(()=>{request("/audit",token).then(setRows).catch(e=>setError(e.message));},[token]);
  return <><PageHeading title="Activity log" subtitle="A simple audit trail of project and review actions."/><div className="panel task-table-panel"><div className="panel-head"><div><h3>Recent activity</h3><p>Latest recorded events</p></div></div>{error&&<div className="alert error">{error}</div>}<div className="activity-list">{rows.map(r=><div className="activity-row" key={r.id}><div className="activity-icon"><Activity size={16}/></div><div><strong>{r.action.replaceAll("_"," ")}</strong><p>{r.entity} #{r.entity_id} · {JSON.stringify(r.details)}</p><small>{new Date(r.created_at).toLocaleString()}</small></div></div>)}{rows.length===0&&!error&&<div className="empty-table">No activity recorded yet.</div>}</div></div></>;
}
export default App;
