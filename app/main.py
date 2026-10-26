import os, csv, io, smtplib, secrets
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from email.message import EmailMessage
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import create_engine, String, Text, DateTime, Boolean, ForeignKey, Integer, JSON, select, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker, Session
from jose import jwt, JWTError
from passlib.context import CryptContext

load_dotenv()
APP_NAME = os.getenv("APP_NAME", "InternMind AI")
SECRET = os.getenv("SECRET_KEY", "dev-secret-change-this")
DB_URL = os.getenv("DATABASE_URL", "sqlite:///./internmind.db")
TOKEN_MINUTES = int(os.getenv("TOKEN_EXPIRE_MINUTES", "480"))
connect_args = {"check_same_thread": False} if DB_URL.startswith("sqlite") else {}
engine = create_engine(DB_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer = HTTPBearer(auto_error=False)

class Base(DeclarativeBase): pass
def utcnow(): return datetime.now(timezone.utc)
class User(Base):
    __tablename__="users"
    id: Mapped[int]=mapped_column(primary_key=True)
    name: Mapped[str]=mapped_column(String(160))
    email: Mapped[str]=mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str]=mapped_column(String(255), default="")
    role: Mapped[str]=mapped_column(String(20), default="intern")
    skills: Mapped[list]=mapped_column(JSON, default=list)
    active: Mapped[bool]=mapped_column(Boolean, default=True)
class Project(Base):
    __tablename__="projects"
    id: Mapped[int]=mapped_column(primary_key=True)
    name: Mapped[str]=mapped_column(String(200))
    client_name: Mapped[str]=mapped_column(String(200), default="")
    description: Mapped[str]=mapped_column(Text, default="")
    created_by: Mapped[int]=mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=utcnow)
class Requirement(Base):
    __tablename__="requirements"
    id: Mapped[int]=mapped_column(primary_key=True)
    project_id: Mapped[int]=mapped_column(ForeignKey("projects.id"), index=True)
    code: Mapped[str]=mapped_column(String(30))
    description: Mapped[str]=mapped_column(Text)
    acceptance_evidence: Mapped[str]=mapped_column(Text, default="")
class Task(Base):
    __tablename__="tasks"
    id: Mapped[int]=mapped_column(primary_key=True)
    project_id: Mapped[int]=mapped_column(ForeignKey("projects.id"), index=True)
    title: Mapped[str]=mapped_column(String(250))
    description: Mapped[str]=mapped_column(Text)
    acceptance_criteria: Mapped[list]=mapped_column(JSON, default=list)
    requirement_codes: Mapped[list]=mapped_column(JSON, default=list)
    status: Mapped[str]=mapped_column(String(30), default="READY")
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=utcnow)
class Dependency(Base):
    __tablename__="dependencies"
    id: Mapped[int]=mapped_column(primary_key=True)
    task_id: Mapped[int]=mapped_column(ForeignKey("tasks.id"))
    depends_on_id: Mapped[int]=mapped_column(ForeignKey("tasks.id"))
class Assignment(Base):
    __tablename__="assignments"
    id: Mapped[int]=mapped_column(primary_key=True)
    task_id: Mapped[int]=mapped_column(ForeignKey("tasks.id"), unique=True)
    intern_id: Mapped[int]=mapped_column(ForeignKey("users.id"), index=True)
    assigned_by: Mapped[int]=mapped_column(ForeignKey("users.id"))
    due_at: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    status: Mapped[str]=mapped_column(String(30), default="ASSIGNED")
class Submission(Base):
    __tablename__="submissions"
    id: Mapped[int]=mapped_column(primary_key=True)
    task_id: Mapped[int]=mapped_column(ForeignKey("tasks.id"), index=True)
    intern_id: Mapped[int]=mapped_column(ForeignKey("users.id"), index=True)
    version: Mapped[int]=mapped_column(Integer)
    repository_url: Mapped[str]=mapped_column(String(1000), default="")
    notes: Mapped[str]=mapped_column(Text, default="")
    evidence: Mapped[dict]=mapped_column(JSON, default=dict)
    submitted_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=utcnow)
class QARun(Base):
    __tablename__="qa_runs"
    id: Mapped[int]=mapped_column(primary_key=True)
    submission_id: Mapped[int]=mapped_column(ForeignKey("submissions.id"))
    report: Mapped[dict]=mapped_column(JSON, default=dict)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=utcnow)
class Review(Base):
    __tablename__="reviews"
    id: Mapped[int]=mapped_column(primary_key=True)
    submission_id: Mapped[int]=mapped_column(ForeignKey("submissions.id"))
    reviewer_id: Mapped[int]=mapped_column(ForeignKey("users.id"))
    decision: Mapped[str]=mapped_column(String(30))
    feedback: Mapped[str]=mapped_column(Text, default="")
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=utcnow)
class Correction(Base):
    __tablename__="corrections"
    id: Mapped[int]=mapped_column(primary_key=True)
    review_id: Mapped[int]=mapped_column(ForeignKey("reviews.id"))
    cycle_number: Mapped[int]=mapped_column(Integer)
    correction_deadline: Mapped[datetime|None]=mapped_column(DateTime(timezone=True), nullable=True)
    next_review_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True), nullable=True)
    timezone_name: Mapped[str]=mapped_column(String(80), default="Asia/Kolkata")
    meet_url: Mapped[str]=mapped_column(String(1000), default="")
    status: Mapped[str]=mapped_column(String(30), default="AWAITING_SCHEDULE")
class Notice(Base):
    __tablename__="notices"
    id: Mapped[int]=mapped_column(primary_key=True)
    recipient: Mapped[str]=mapped_column(String(255))
    subject: Mapped[str]=mapped_column(String(255))
    body: Mapped[str]=mapped_column(Text)
    status: Mapped[str]=mapped_column(String(20), default="PENDING")
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=utcnow)
class Audit(Base):
    __tablename__="audit"
    id: Mapped[int]=mapped_column(primary_key=True)
    actor_id: Mapped[int]=mapped_column(ForeignKey("users.id"))
    entity: Mapped[str]=mapped_column(String(80))
    entity_id: Mapped[int]=mapped_column(Integer)
    action: Mapped[str]=mapped_column(String(100))
    details: Mapped[dict]=mapped_column(JSON, default=dict)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=utcnow)

class InterviewSession(Base):
    __tablename__="interview_sessions"
    id: Mapped[int]=mapped_column(primary_key=True)
    task_id: Mapped[int]=mapped_column(ForeignKey("tasks.id"), index=True)
    intern_id: Mapped[int]=mapped_column(ForeignKey("users.id"), index=True)
    submission_id: Mapped[int|None]=mapped_column(ForeignKey("submissions.id"), nullable=True)
    join_token: Mapped[str]=mapped_column(String(120), unique=True, index=True)
    status: Mapped[str]=mapped_column(String(30), default="PREPARED")
    questions: Mapped[list]=mapped_column(JSON, default=list)
    transcript: Mapped[list]=mapped_column(JSON, default=list)
    report: Mapped[dict]=mapped_column(JSON, default=dict)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True), nullable=True)

Base.metadata.create_all(engine)
app=FastAPI(title=APP_NAME, version="1.0.0", description="Intern task allocation, evidence QA, review and correction workflow MVP")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in os.getenv("FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if x.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def db_dep():
    db=SessionLocal()
    try: yield db
    finally: db.close()
def audit(db,user,entity,eid,action,details=None):
    db.add(Audit(actor_id=user.id, entity=entity, entity_id=eid, action=action, details=details or {}))
def email(db,to,subject,body):
    n=Notice(recipient=to,subject=subject,body=body,status="LOGGED")
    host=os.getenv("SMTP_HOST",""); smtp_user=os.getenv("SMTP_USER",""); smtp_pass=os.getenv("SMTP_PASSWORD",""); sender=os.getenv("SMTP_FROM",smtp_user)
    try:
        if host and smtp_user and smtp_pass and sender:
            msg=EmailMessage(); msg["From"]=sender; msg["To"]=to; msg["Subject"]=subject; msg.set_content(body)
            with smtplib.SMTP(host,int(os.getenv("SMTP_PORT","587")),timeout=15) as s:
                s.starttls(); s.login(smtp_user,smtp_pass); s.send_message(msg)
            n.status="SENT"
        else: print(f"\\n[EMAIL PREVIEW] To={to} Subject={subject}\\n{body}\\n")
    except Exception as e:
        n.status="FAILED"; print("Email failed:", str(e))
    db.add(n)
def actor(creds: HTTPAuthorizationCredentials=Depends(bearer), db: Session=Depends(db_dep)):
    if not creds: raise HTTPException(401,"Bearer token required")
    try: payload=jwt.decode(creds.credentials,SECRET,algorithms=["HS256"]); uid=int(payload["sub"])
    except (JWTError,ValueError,KeyError): raise HTTPException(401,"Invalid/expired token")
    u=db.get(User,uid)
    if not u or not u.active: raise HTTPException(401,"Inactive/missing user")
    return u
def roles(*allowed):
    def check(u: User=Depends(actor)):
        if u.role not in allowed: raise HTTPException(403,"Insufficient role")
        return u
    return check
def seed():
    with SessionLocal() as db:
        if not db.scalar(select(User.id).limit(1)):
            db.add(User(name=os.getenv("ADMIN_NAME","Project Admin"),email=os.getenv("ADMIN_EMAIL","admin@example.com").lower(),
                        password_hash=pwd.hash(os.getenv("ADMIN_PASSWORD","ChangeThisPassword123!")),role="admin"))
            db.commit()
seed()

class Login(BaseModel): email: EmailStr; password: str
class ProjectIn(BaseModel): name: str=Field(min_length=2); client_name: str=""; description: str=""
class RequirementIn(BaseModel): code: str; description: str; acceptance_evidence: str=""
class TaskIn(BaseModel):
    title: str
    description: str
    acceptance_criteria: list[str]=[]
    requirement_codes: list[str]=[]
    depends_on_task_ids: list[int]=[]
class AssignIn(BaseModel):
    intern_id: int
    due_at: datetime
    review_at: datetime | None = None
    meet_url: str = ""
class SubmitIn(BaseModel): repository_url: str=""; notes: str=""; evidence: dict={}
class ReviewIn(BaseModel): decision: str; feedback: str=""; rubric: dict={}
class ScheduleIn(BaseModel):
    correction_deadline: datetime
    next_review_at: datetime
    timezone_name: str="Asia/Kolkata"
    meet_url: str=""

@app.get("/")
def home(): return {"app":APP_NAME,"docs":"/docs","status":"ready"}
@app.get("/health")
def health(): return {"status":"ok"}
@app.post("/auth/login")
def login(data: Login, db: Session=Depends(db_dep)):
    u=db.scalar(select(User).where(User.email==data.email.lower()))
    if not u or not pwd.verify(data.password,u.password_hash): raise HTTPException(401,"Incorrect email/password")
    token=jwt.encode({"sub":str(u.id),"exp":utcnow()+timedelta(minutes=TOKEN_MINUTES)},SECRET,algorithm="HS256")
    return {"access_token":token,"token_type":"bearer","role":u.role,"user_id":u.id}

@app.post("/projects")
def create_project(x: ProjectIn, db: Session=Depends(db_dep), u: User=Depends(roles("admin","mentor"))):
    p=Project(name=x.name,client_name=x.client_name,description=x.description,created_by=u.id); db.add(p); db.flush()
    audit(db,u,"project",p.id,"created",{"name":p.name}); db.commit()
    return {"id":p.id,"name":p.name}
@app.get("/projects")
def list_projects(db: Session=Depends(db_dep), u: User=Depends(actor)):
    return [{"id":p.id,"name":p.name,"client_name":p.client_name,"description":p.description} for p in db.scalars(select(Project)).all()]
@app.get("/projects/{pid}/interns")
def list_project_interns(pid: int, db: Session=Depends(db_dep), u: User=Depends(roles("admin","mentor"))):
    if not db.get(Project,pid): raise HTTPException(404,"Project not found")
    people=db.scalars(select(User).where(User.role=="intern", User.active==True).order_by(User.name)).all()
    return [{"id":p.id,"name":p.name,"email":p.email,"skills":p.skills or []} for p in people]

@app.get("/projects/{pid}/submissions")
def list_project_submissions(pid: int, db: Session=Depends(db_dep), u: User=Depends(roles("admin","mentor"))):
    if not db.get(Project,pid): raise HTTPException(404,"Project not found")
    tasks=db.scalars(select(Task).where(Task.project_id==pid)).all()
    out=[]
    for t in tasks:
        submissions=db.scalars(select(Submission).where(Submission.task_id==t.id).order_by(Submission.version.desc())).all()
        for s in submissions:
            person=db.get(User,s.intern_id)
            latest_qa=db.scalar(select(QARun).where(QARun.submission_id==s.id).order_by(QARun.id.desc()))
            out.append({"id":s.id,"task_id":t.id,"task_title":t.title,"intern_id":s.intern_id,
                        "intern_name":person.name if person else "Unknown","version":s.version,
                        "repository_url":s.repository_url,"notes":s.notes,"evidence":s.evidence or {},
                        "submitted_at":s.submitted_at.isoformat(),"qa_report":latest_qa.report if latest_qa else None})
    return out

@app.post("/projects/{pid}/requirements")
def add_requirement(pid: int, x: RequirementIn, db: Session=Depends(db_dep), u: User=Depends(roles("admin","mentor"))):
    if not db.get(Project,pid): raise HTTPException(404,"Project not found")
    code=x.code.upper()
    if db.scalar(select(Requirement.id).where(Requirement.project_id==pid,Requirement.code==code)): raise HTTPException(409,"Requirement code already exists")
    r=Requirement(project_id=pid,code=code,description=x.description,acceptance_evidence=x.acceptance_evidence); db.add(r); db.flush()
    audit(db,u,"requirement",r.id,"created",{"code":code}); db.commit()
    return {"id":r.id,"code":r.code}
@app.post("/projects/{pid}/interns/import")
async def import_interns(pid: int, file: UploadFile=File(...), db: Session=Depends(db_dep), u: User=Depends(roles("admin","mentor"))):
    if not db.get(Project,pid): raise HTTPException(404,"Project not found")
    if not file.filename.lower().endswith(".csv"): raise HTTPException(400,"Upload CSV")
    raw=await file.read()
    if len(raw)>2_000_000: raise HTTPException(413,"CSV too large")
    try: rows=csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    except UnicodeDecodeError: raise HTTPException(400,"CSV must be UTF-8")
    if not {"name","email"}.issubset(set(rows.fieldnames or [])): raise HTTPException(400,"CSV columns required: name,email; optional skills")
    created=[]; skipped=[]
    for row in rows:
        name=(row.get("name") or "").strip(); em=(row.get("email") or "").strip().lower()
        if not name or not em: skipped.append({"email":em,"reason":"missing name/email"}); continue
        if db.scalar(select(User.id).where(User.email==em)): skipped.append({"email":em,"reason":"email exists"}); continue
        skills=[s.strip() for s in (row.get("skills") or "").split(";") if s.strip()]
        person=User(name=name,email=em,role="intern",skills=skills,password_hash=""); db.add(person); db.flush()
        created.append({"id":person.id,"name":name,"email":em})
    audit(db,u,"project",pid,"interns_imported",{"created":len(created),"skipped":len(skipped)}); db.commit()
    return {"created":created,"skipped":skipped,"note":"Add a secure invitation/password activation flow before production."}
@app.get("/projects/{pid}/tasks")
def list_tasks(pid: int, db: Session=Depends(db_dep), u: User=Depends(actor)):
    result=[]
    for t in db.scalars(select(Task).where(Task.project_id==pid)).all():
        a=db.scalar(select(Assignment).where(Assignment.task_id==t.id))
        result.append({"id":t.id,"title":t.title,"description":t.description,"status":t.status,"acceptance_criteria":t.acceptance_criteria,
                       "requirement_codes":t.requirement_codes,"assigned_intern_id":a.intern_id if a else None,"due_at":a.due_at.isoformat() if a else None})
    return result
@app.post("/projects/{pid}/tasks")
def create_task(pid: int, x: TaskIn, db: Session=Depends(db_dep), u: User=Depends(roles("admin","mentor"))):
    if not db.get(Project,pid): raise HTTPException(404,"Project not found")
    reqs=db.scalars(select(Requirement).where(Requirement.project_id==pid)).all(); known={r.code for r in reqs}
    codes=[c.upper() for c in x.requirement_codes]
    if set(codes)-known: raise HTTPException(400,{"unknown_requirement_codes":sorted(set(codes)-known)})
    t=Task(project_id=pid,title=x.title,description=x.description,acceptance_criteria=x.acceptance_criteria,requirement_codes=codes,status="READY")
    db.add(t); db.flush()
    for did in x.depends_on_task_ids:
        d=db.get(Task,did)
        if not d or d.project_id!=pid or d.id==t.id: db.rollback(); raise HTTPException(400,f"Invalid dependency task id {did}")
        db.add(Dependency(task_id=t.id,depends_on_id=did))
    audit(db,u,"task",t.id,"created",{"requirements":codes}); db.commit()
    return {"id":t.id,"title":t.title,"requirement_dna":{"linked":codes,"coverage_mapped":len(codes)}}
@app.post("/tasks/{tid}/assign")
def assign(tid: int, x: AssignIn, db: Session=Depends(db_dep), u: User=Depends(roles("admin","mentor"))):
    t=db.get(Task,tid); person=db.get(User,x.intern_id)
    if not t: raise HTTPException(404,"Task not found")
    if not person or person.role!="intern": raise HTTPException(400,"intern_id must be an intern")
    if db.scalar(select(Assignment.id).where(Assignment.task_id==tid)): raise HTTPException(409,"Task already assigned")
    for d in db.scalars(select(Dependency).where(Dependency.task_id==tid)).all():
        prior=db.get(Task,d.depends_on_id)
        if not prior or prior.status!="APPROVED": raise HTTPException(409,f"Dependency {d.depends_on_id} not approved")
    a=Assignment(task_id=tid,intern_id=person.id,assigned_by=u.id,due_at=x.due_at,status="IN_PROGRESS"); db.add(a); t.status="ASSIGNED"; db.flush()
    p=db.get(Project,t.project_id)
    if x.meet_url and not x.meet_url.startswith("https://"): raise HTTPException(400,"Meet URL must use HTTPS")
    body=(f"Hi {person.name},\nProject: {p.name}\nTask ID: TASK-{t.id:04d}\nTask: {t.title}\n\nInstructions:\n{t.description}\n\n"
          + "Acceptance criteria:\n- " + "\n- ".join(t.acceptance_criteria or ["See task description"])
          + f"\n\nRequirement codes: {', '.join(t.requirement_codes) or 'Not mapped'}\nSubmission deadline: {x.due_at.isoformat()}"
          + f"\nReview meeting: {x.review_at.isoformat() if x.review_at else 'To be confirmed by mentor'}"
          + f"\nGoogle Meet: {x.meet_url or 'To be shared by mentor'}\nSubmission endpoint: /tasks/{t.id}/submit"
          + "\nPlease bring your deliverables and evidence to the review.")
    email(db,person.email,f"[InternMind] Task assigned: {t.title}",body); audit(db,u,"assignment",a.id,"assigned",{"task_id":tid,"intern_id":person.id}); db.commit()
    return {"assignment_id":a.id,"task_id":tid,"email":"sent or logged"}
@app.get("/me/tasks")
def my_tasks(db: Session=Depends(db_dep), u: User=Depends(actor)):
    out=[]
    for a in db.scalars(select(Assignment).where(Assignment.intern_id==u.id)).all():
        t=db.get(Task,a.task_id)
        out.append({"task_id":t.id,"title":t.title,"description":t.description,"acceptance_criteria":t.acceptance_criteria,"requirement_codes":t.requirement_codes,"status":a.status,"due_at":a.due_at.isoformat()})
    return out
@app.post("/tasks/{tid}/submit")
def submit(tid: int, x: SubmitIn, db: Session=Depends(db_dep), u: User=Depends(actor)):
    t=db.get(Task,tid)
    if not t: raise HTTPException(404,"Task not found")
    a=db.scalar(select(Assignment).where(Assignment.task_id==tid,Assignment.intern_id==u.id))
    if u.role not in ("admin","mentor") and not a: raise HTTPException(403,"Not assigned to this task")
    if not x.repository_url and not x.notes and not x.evidence: raise HTTPException(400,"Provide repository_url, notes or evidence")
    ver=(db.scalar(select(func.max(Submission.version)).where(Submission.task_id==tid,Submission.intern_id==u.id)) or 0)+1
    s=Submission(task_id=tid,intern_id=u.id,version=ver,repository_url=x.repository_url,notes=x.notes,evidence=x.evidence); db.add(s); t.status="SUBMITTED"
    if a: a.status="SUBMITTED"
    db.flush(); audit(db,u,"submission",s.id,"submitted",{"task_id":tid,"version":ver}); db.commit()
    return {"submission_id":s.id,"version":ver,"status":"SUBMITTED"}
@app.post("/submissions/{sid}/qa")
def qa(sid: int, db: Session=Depends(db_dep), u: User=Depends(roles("admin","mentor"))):
    s=db.get(Submission,sid)
    if not s: raise HTTPException(404,"Submission not found")
    t=db.get(Task,s.task_id); reqs=db.scalars(select(Requirement).where(Requirement.project_id==t.project_id)).all()
    report={"overall":"REVIEW_REQUIRED","checks":[],"unmapped_requirement_codes":sorted(set(t.requirement_codes)-{r.code for r in reqs}),
            "repo_url_present":bool(s.repository_url),"notes_present":bool(s.notes.strip()),"evidence_keys":list(s.evidence.keys()),
            "safety_note":"No submitted code was executed. Mentor makes final decision."}
    for i,c in enumerate(t.acceptance_criteria or [],1):
        report["checks"].append({"id":f"AC-{i:03}","criterion":c,"status":"NEEDS_HUMAN_CHECK","reason":"Semantic/code correctness needs real tests and mentor review."})
    if not s.repository_url and not s.notes and not s.evidence: report["checks"].append({"id":"EVIDENCE-001","status":"MISSING","criterion":"Submission evidence"})
    for r in reqs:
        if r.code in t.requirement_codes and r.acceptance_evidence:
            report["checks"].append({"id":r.code,"criterion":r.acceptance_evidence,"status":"PROVIDED" if r.code in s.evidence else "MISSING"})
    q=QARun(submission_id=sid,report=report); t.status="REVIEW_PENDING"; db.add(q); db.flush(); audit(db,u,"qa",q.id,"completed",{"submission_id":sid}); db.commit()
    return {"qa_run_id":q.id,"report":report}
@app.post("/submissions/{sid}/review")
def review(sid: int, x: ReviewIn, db: Session=Depends(db_dep), u: User=Depends(roles("admin","mentor"))):
    s=db.get(Submission,sid)
    if not s: raise HTTPException(404,"Submission not found")
    decision=x.decision.upper()
    if decision not in ("APPROVED","CORRECTION_REQUIRED"): raise HTTPException(400,"decision must be APPROVED or CORRECTION_REQUIRED")
    if decision=="CORRECTION_REQUIRED" and not x.feedback.strip(): raise HTTPException(400,"Feedback required")
    t=db.get(Task,s.task_id); a=db.scalar(select(Assignment).where(Assignment.task_id==t.id,Assignment.intern_id==s.intern_id)); person=db.get(User,s.intern_id)
    r=Review(submission_id=sid,reviewer_id=u.id,decision=decision,feedback=x.feedback); db.add(r); db.flush()
    cycle=None
    if decision=="APPROVED":
        t.status="APPROVED"
        if a: a.status="APPROVED"
        email(db,person.email,f"[InternMind] Approved: {t.title}",f"Your task #{t.id} ({t.title}) is approved.\\n{x.feedback}")
    else:
        t.status="CORRECTION_REQUIRED"
        if a: a.status="CORRECTION_REQUIRED"
        n=(db.scalar(select(func.max(Correction.cycle_number).join(Review).where(Review.submission_id==sid)) or 0)+1)
        cycle=Correction(review_id=r.id,cycle_number=n,status="AWAITING_SCHEDULE"); db.add(cycle); db.flush()
        email(db,person.email,f"[InternMind] Corrections required: {t.title}",f"Task #{t.id} needs correction.\\nFeedback:\\n{x.feedback}\\nA new review time and Meet link will be emailed after the mentor confirms them.")
    audit(db,u,"review",r.id,"decision_recorded",{"decision":decision,"submission_id":sid}); db.commit()
    return {"review_id":r.id,"decision":decision,"correction_cycle_id":cycle.id if cycle else None}
@app.post("/correction-cycles/{cid}/schedule")
def schedule(cid: int, x: ScheduleIn, db: Session=Depends(db_dep), u: User=Depends(roles("admin","mentor"))):
    c=db.get(Correction,cid)
    if not c: raise HTTPException(404,"Correction cycle not found")
    if x.correction_deadline >= x.next_review_at: raise HTTPException(400,"Correction deadline must precede review time")
    if x.meet_url and not x.meet_url.startswith("https://"): raise HTTPException(400,"Meet URL must use HTTPS")
    r=db.get(Review,c.review_id); s=db.get(Submission,r.submission_id); t=db.get(Task,s.task_id); person=db.get(User,s.intern_id)
    c.correction_deadline=x.correction_deadline; c.next_review_at=x.next_review_at; c.timezone_name=x.timezone_name; c.meet_url=x.meet_url
    c.status="SCHEDULED" if x.meet_url else "TIME_SET_LINK_PENDING"
    body=f"Task #{t.id}: {t.title}\\nFeedback:\\n{r.feedback}\\nCorrection deadline: {x.correction_deadline.isoformat()}\\nNext review: {x.next_review_at.isoformat()} ({x.timezone_name})\\nMeet link: {x.meet_url or 'Not confirmed; mentor must provide it.'}"
    email(db,person.email,f"[InternMind] Correction review scheduled: {t.title}",body); audit(db,u,"correction",c.id,"schedule_updated",{"status":c.status}); db.commit()
    return {"correction_cycle_id":c.id,"status":c.status,"email":"sent or logged"}
@app.get("/projects/{pid}/agent-intelligence")
def agent_intelligence(pid: int, db: Session=Depends(db_dep), u: User=Depends(roles("admin","mentor"))):
    """Explainable multi-agent analysis over recorded project data; no code execution or external LLM required."""
    project=db.get(Project,pid)
    if not project: raise HTTPException(404,"Project not found")
    tasks=db.scalars(select(Task).where(Task.project_id==pid).order_by(Task.id)).all()
    requirements=db.scalars(select(Requirement).where(Requirement.project_id==pid)).all()
    task_ids={t.id for t in tasks}; req_codes={r.code for r in requirements}
    assignments={a.task_id:a for a in db.scalars(select(Assignment).where(Assignment.task_id.in_(task_ids))).all()} if task_ids else {}
    deps=db.scalars(select(Dependency).where(Dependency.task_id.in_(task_ids))).all() if task_ids else []
    submissions=[]
    for t in tasks:
        submissions += db.scalars(select(Submission).where(Submission.task_id==t.id).order_by(Submission.version.desc())).all()
    agents=[]; actions=[]; risk_count=0; evidence_gap_count=0; escalation_count=0
    # Agent 1: Requirement DNA / traceability
    findings=[]
    for t in tasks:
        missing=sorted(set(t.requirement_codes or [])-req_codes)
        if not (t.requirement_codes or []): findings.append({"severity":"MEDIUM","task_id":t.id,"message":"Task is not linked to a requirement code; requirement coverage is hard to prove."})
        if missing: findings.append({"severity":"HIGH","task_id":t.id,"message":"Unknown requirement code(s): "+", ".join(missing)})
    agents.append({"name":"Requirement DNA Agent","purpose":"Checks whether each task is traceable to known project requirements.","findings":findings})
    risk_count += sum(1 for f in findings if f["severity"] in ("HIGH","MEDIUM"))
    if findings: actions.append("Map each task to valid requirement codes and define observable acceptance evidence.")
    # Agent 2: Dependency / delivery risk
    findings=[]
    for d in deps:
        prior=db.get(Task,d.depends_on_id); child=db.get(Task,d.task_id)
        if prior and child and prior.status!="APPROVED":
            findings.append({"severity":"HIGH","task_id":child.id,"message":f"Blocked by Task #{prior.id} ({prior.status}); downstream work may be delayed."})
    for t in tasks:
        a=assignments.get(t.id)
        if not a and t.status in ("READY","CREATED"):
            findings.append({"severity":"MEDIUM","task_id":t.id,"message":"Task is not assigned; deadline risk is unknown."})
        if a and a.due_at:
            due=a.due_at
            if due.tzinfo is None: due=due.replace(tzinfo=timezone.utc)
            if due < utcnow() and t.status not in ("APPROVED",):
                findings.append({"severity":"HIGH","task_id":t.id,"message":"Task deadline has passed and task is not approved."})
    agents.append({"name":"Dependency & Delivery Risk Agent","purpose":"Finds blocked downstream tasks, unassigned work and overdue tasks.","findings":findings})
    risk_count += sum(1 for f in findings if f["severity"] in ("HIGH","MEDIUM"))
    if findings: actions.append("Review blocked and overdue tasks first; update dependencies and agree a recovery deadline with the intern.")
    # Agent 3: integration contract sentinel, using task metadata only
    findings=[]
    integration_terms=("api","endpoint","schema","database","integration","contract","payload","auth")
    for t in tasks:
        text_blob=(t.title+" "+t.description).lower()
        if any(term in text_blob for term in integration_terms) and not (t.acceptance_criteria or []):
            findings.append({"severity":"MEDIUM","task_id":t.id,"message":"Integration-related task has no acceptance criteria; request API/schema examples and error cases."})
    agents.append({"name":"Integration Contract Sentinel","purpose":"Flags integration-related tasks that lack explicit acceptance criteria. It does not inspect repository code.","findings":findings})
    risk_count += len(findings)
    if findings: actions.append("Publish a shared contract for affected modules: endpoint, request/response schema, error cases and versioning.")
    # Agent 4: evidence/review triage
    findings=[]
    latest_by_task={}
    for sub in submissions:
        if sub.task_id not in latest_by_task or sub.version > latest_by_task[sub.task_id].version: latest_by_task[sub.task_id]=sub
    for t in tasks:
        if t.status in ("SUBMITTED","REVIEW_PENDING","CORRECTION_REQUIRED"):
            sub=latest_by_task.get(t.id)
            if not sub:
                findings.append({"severity":"HIGH","task_id":t.id,"message":"Task is awaiting review but no submission record was found."}); evidence_gap_count+=1
            else:
                gaps=[]
                if not sub.repository_url: gaps.append("repository link")
                if not sub.notes.strip(): gaps.append("submission notes")
                if not (sub.evidence or {}): gaps.append("evidence bundle")
                if gaps:
                    findings.append({"severity":"MEDIUM","task_id":t.id,"message":"Submission is missing: "+", ".join(gaps)+"."}); evidence_gap_count+=1
    agents.append({"name":"Proof-Carrying Review Agent","purpose":"Checks for basic submission evidence presence before mentor review; it does not claim code correctness.","findings":findings})
    if findings: actions.append("Ask interns to attach repository/source links, concise change notes and acceptance evidence before the review meeting.")
    # Agent 5: disagreement/uncertainty escalation guard
    findings=[]
    for sub in submissions:
        qa=db.scalar(select(QARun).where(QARun.submission_id==sub.id).order_by(QARun.id.desc()))
        if not qa:
            findings.append({"severity":"INFO","task_id":sub.task_id,"message":f"Submission #{sub.id} has no QA report yet; run evidence QA before mentor decision."})
        elif qa.report.get("overall") in ("REVIEW_REQUIRED","UNCERTAIN","CONFLICT"):
            findings.append({"severity":"HIGH","task_id":sub.task_id,"message":f"Submission #{sub.id} needs human verification; automated evidence checks are not a final pass/fail decision."})
    agents.append({"name":"Self-Doubt & Human Escalation Agent","purpose":"Routes uncertain or unchecked submissions to a mentor instead of making an unsupported autonomous approval.","findings":findings})
    escalation_count=len(findings)
    if findings: actions.append("Mentor: inspect each flagged submission and record the final decision. Do not treat metadata checks as proof of correctness.")
    dependency_count=len(deps)
    result={"project_id":pid,"project_name":project.name,"generated_at":utcnow().isoformat(),"mode":"explainable_rules_no_external_llm","summary":{"task_count":len(tasks),"requirement_count":len(requirements),"dependency_count":dependency_count,"risk_count":risk_count,"evidence_gap_count":evidence_gap_count,"human_escalation_count":escalation_count},"agents":agents,"recommended_actions":actions or ["No rule-based warning found. Continue normal evidence collection and mentor reviews."],"limitations":["This analysis uses stored project metadata and submission records only.","It does not execute submitted code, scan private repositories, or create Google Meet events.","AI/rule outputs are recommendations; final review decisions remain with an authorized mentor."]}
    audit(db,u,"project",pid,"agent_intelligence_run",{"risk_count":risk_count,"evidence_gap_count":evidence_gap_count,"human_escalation_count":escalation_count})
    db.commit()
    return result

@app.get("/dashboard")
def dashboard(db: Session=Depends(db_dep), u: User=Depends(roles("admin","mentor"))):
    statuses=["READY","ASSIGNED","SUBMITTED","REVIEW_PENDING","CORRECTION_REQUIRED","APPROVED"]
    return {"intern_count":db.scalar(select(func.count(User.id)).where(User.role=="intern")) or 0,
            "project_count":db.scalar(select(func.count(Project.id))) or 0,"task_count":db.scalar(select(func.count(Task.id))) or 0,
            "submission_count":db.scalar(select(func.count(Submission.id))) or 0,
            "task_status_counts":{s:db.scalar(select(func.count(Task.id)).where(Task.status==s)) or 0 for s in statuses}}
@app.get("/audit")
def audit_log(limit: int=100, db: Session=Depends(db_dep), u: User=Depends(roles("admin","mentor"))):
    rows=db.scalars(select(Audit).order_by(Audit.id.desc()).limit(min(max(limit,1),500))).all()
    return [{"id":r.id,"actor_id":r.actor_id,"entity":r.entity,"entity_id":r.entity_id,"action":r.action,"details":r.details,"created_at":r.created_at.isoformat()} for r in rows]


# --- Autonomous AI interview endpoints (browser speech + deterministic evidence rubric MVP) ---
class InterviewPrepareIn(BaseModel):
    task_id: int
    intern_id: int
    submission_id: int | None = None
    frontend_url: str = "http://localhost:5173"

class InterviewAnswerIn(BaseModel):
    question_index: int
    question: str
    answer: str = Field(max_length=12000)

class InterviewFinishIn(BaseModel):
    consent_confirmed: bool = False


def build_interview_questions(task: Task, submission: Submission | None):
    criteria = task.acceptance_criteria or []
    questions = [
        {"type":"overview", "question":f"Please explain your approach to the task: {task.title}. What did you build and why?", "checks":["approach","task"]},
        {"type":"requirements", "question":f"How does your solution satisfy this task's requirements: {task.description[:500]}?", "checks":["requirements","solution"]},
        {"type":"testing", "question":"How did you test your work? Please describe one test, its expected result, and the actual result.", "checks":["test","result"]},
        {"type":"edge_cases", "question":"What is one edge case or failure scenario, and how does your solution handle it?", "checks":["error","edge","handle"]},
        {"type":"reflection", "question":"If you had another hour, what would you improve, and how would you verify that improvement?", "checks":["improve","verify"]},
    ]
    if criteria:
        questions[1]["question"] += " Acceptance criteria include: " + "; ".join(criteria[:5])
    if submission:
        context = []
        if submission.repository_url: context.append("Repository: " + submission.repository_url)
        if submission.notes: context.append("Submission notes: " + submission.notes[:500])
        questions[0]["question"] += " Your submitted work: " + (" | ".join(context) if context else "submission on record")
    return questions

@app.post("/interviews/prepare")
def prepare_interview(x: InterviewPrepareIn, db: Session=Depends(db_dep), u: User=Depends(roles("admin","mentor"))):
    task=db.get(Task,x.task_id); person=db.get(User,x.intern_id)
    if not task: raise HTTPException(404,"Task not found")
    if not person or person.role!="intern": raise HTTPException(400,"intern_id must identify an intern")
    assignment=db.scalar(select(Assignment).where(Assignment.task_id==task.id, Assignment.intern_id==person.id))
    if not assignment: raise HTTPException(409,"Assign this task to the intern before preparing the interview")
    submission=None
    if x.submission_id:
        submission=db.get(Submission,x.submission_id)
        if not submission or submission.task_id!=task.id or submission.intern_id!=person.id: raise HTTPException(400,"Submission does not match this task and intern")
    token=secrets.token_urlsafe(32)
    session=InterviewSession(task_id=task.id,intern_id=person.id,submission_id=submission.id if submission else None,join_token=token,
                             questions=build_interview_questions(task,submission),status="PREPARED")
    db.add(session); db.flush()
    base=x.frontend_url.rstrip("/")
    join_url=f"{base}/interview?session_id={session.id}&join_token={token}"
    project=db.get(Project,task.project_id)
    body=(f"Hi {person.name},\n\nYour AI avatar review interview is ready.\nProject: {project.name if project else 'Internship project'}\nTask: TASK-{task.id:04d} — {task.title}\n\nJoin the secure InternMind interview room: {join_url}\n\nThe AI interviewer will ask task-specific questions, listen to your answers and generate a feedback report. This prototype uses your browser's speech features. Confirm consent before recording/processing any interview data.\n\nPlease use Chrome or Edge and allow microphone access. The room link is private; do not share it.")
    email(db,person.email,f"[InternMind AI] Review interview: {task.title}",body)
    audit(db,u,"interview",session.id,"prepared",{"task_id":task.id,"intern_id":person.id,"submission_id":submission.id if submission else None})
    db.commit()
    return {"id":session.id,"status":session.status,"task_id":task.id,"intern_id":person.id,"intern_name":person.name,"intern_email":person.email,"task_title":task.title,"join_url":join_url,"email":"sent or logged","question_count":len(session.questions),"meeting_mode":"InternMind browser room; not a Google Meet participant bot"}

@app.get("/projects/{pid}/interviews")
def list_interviews(pid:int, db:Session=Depends(db_dep), u:User=Depends(roles("admin","mentor"))):
    if not db.get(Project,pid): raise HTTPException(404,"Project not found")
    tasks=db.scalars(select(Task).where(Task.project_id==pid)).all(); task_map={t.id:t for t in tasks}
    sessions=db.scalars(select(InterviewSession).where(InterviewSession.task_id.in_(list(task_map) or [-1])).order_by(InterviewSession.id.desc())).all()
    out=[]
    for s in sessions:
        person=db.get(User,s.intern_id); t=task_map.get(s.task_id)
        out.append({"id":s.id,"task_id":s.task_id,"task_title":t.title if t else "Unknown task","intern_id":s.intern_id,"intern_name":person.name if person else "Unknown","status":s.status,"created_at":s.created_at.isoformat(),"report":s.report or {}})
    return out

@app.get("/interviews/{iid}/public")
def public_interview(iid:int, join_token:str, db:Session=Depends(db_dep)):
    s=db.get(InterviewSession,iid)
    if not s or not secrets.compare_digest(s.join_token,join_token): raise HTTPException(404,"Interview link is invalid or expired")
    task=db.get(Task,s.task_id); person=db.get(User,s.intern_id); project=db.get(Project,task.project_id) if task else None
    if s.status=="COMPLETED":
        return {"id":s.id,"status":s.status,"task_title":task.title if task else "Task","intern_name":person.name if person else "Intern","project_name":project.name if project else "Project","questions":s.questions,"transcript":s.transcript,"report":s.report}
    return {"id":s.id,"status":s.status,"task_title":task.title if task else "Task","task_description":task.description if task else "","acceptance_criteria":task.acceptance_criteria or [] if task else [],"intern_name":person.name if person else "Intern","project_name":project.name if project else "Project","questions":s.questions,"transcript":s.transcript or [],"report":s.report or {},"recording_notice":"No audio recording is saved by this endpoint. Transcript answers are stored for the review report."}

@app.post("/interviews/{iid}/answer")
def save_interview_answer(iid:int, join_token:str, x:InterviewAnswerIn, db:Session=Depends(db_dep)):
    s=db.get(InterviewSession,iid)
    if not s or not secrets.compare_digest(s.join_token,join_token): raise HTTPException(404,"Interview link is invalid")
    if s.status=="COMPLETED": raise HTTPException(409,"Interview is already completed")
    if x.question_index<0 or x.question_index>=len(s.questions): raise HTTPException(400,"Invalid question index")
    if not x.answer.strip(): raise HTTPException(400,"Answer cannot be empty")
    rows=list(s.transcript or [])
    rows=[r for r in rows if r.get("question_index")!=x.question_index]
    rows.append({"question_index":x.question_index,"question":x.question,"answer":x.answer.strip(),"answered_at":utcnow().isoformat()})
    rows.sort(key=lambda r:r["question_index"])
    s.transcript=rows; s.status="IN_PROGRESS"; db.commit()
    return {"saved":True,"answered_count":len(rows),"total_questions":len(s.questions)}

def evaluate_with_local_llm(task: Task | None, questions: list, transcript: list, submission: Submission | None = None):
    """Optional local Ollama semantic evaluation; returns None when not configured/available."""
    base=os.getenv("OLLAMA_BASE_URL","").strip().rstrip("/")
    model=os.getenv("OLLAMA_MODEL","").strip()
    if not base or not model: return None
    import json as _json
    from urllib.request import Request, urlopen
    from urllib.error import URLError, HTTPError
    prompt={"task":{"title":task.title if task else "Task","description":task.description if task else "","acceptance_criteria":task.acceptance_criteria or [] if task else []},"questions":questions,"answers":transcript,"submission":{"repository_url":submission.repository_url if submission else "","notes":submission.notes if submission else "","evidence":submission.evidence or {} if submission else {}}}
    instruction=("Evaluate a technical internship task submission and interview fairly. Use only supplied task requirements, answer transcript, repository URL, notes, and evidence. You cannot browse or execute the repository; do not claim you inspected source code or ran tests. Do not infer from accent, identity, appearance, emotion, or fluency. Score technical understanding and submission evidence only. Return JSON exactly with keys overall_score (integer 0-100), recommendation (PASS_CANDIDATE or CORRECTIONS_REQUIRED), rubric_details (array, one per question, each with question, score 0-100, status ANSWERED or NOT_ANSWERED, feedback, evidence_quote), and limitations (array of strings). Passing recommendation requires specific technical answers, repository URL, implementation notes, and concrete evidence; if evidence is missing or vague, choose CORRECTIONS_REQUIRED. This is an advisory prototype evaluation.")
    body=_json.dumps({"model":model,"stream":False,"format":"json","messages":[{"role":"system","content":instruction},{"role":"user","content":_json.dumps(prompt,ensure_ascii=False)}]}).encode()
    try:
        req=Request(base+"/api/chat",data=body,headers={"Content-Type":"application/json"},method="POST")
        with urlopen(req,timeout=60) as response: data=_json.loads(response.read().decode())
        result=_json.loads(data.get("message",{}).get("content","{}"))
        score=max(0,min(100,int(result.get("overall_score",0))))
        details=result.get("rubric_details",[])
        if not isinstance(details,list) or len(details)!=len(questions): return None
        result["overall_score"]=score
        result["recommendation"]="AUTO_APPROVED" if score>=70 and all(d.get("status")=="ANSWERED" for d in details) else "CORRECTIONS_REQUIRED"
        result["evaluation_engine"]="ollama_local_llm"
        result["limitations"]=(result.get("limitations") or [])+["Local LLM evaluation can be wrong; validate against objective task tests and submission evidence."]
        return result
    except Exception as exc:
        print("Local Ollama evaluation unavailable; using deterministic fallback:",str(exc))
        return None

@app.post("/interviews/{iid}/finish")
def finish_interview(iid:int, join_token:str, x:InterviewFinishIn, db:Session=Depends(db_dep)):
    s=db.get(InterviewSession,iid)
    if not s or not secrets.compare_digest(s.join_token,join_token): raise HTTPException(404,"Interview link is invalid")
    if not x.consent_confirmed: raise HTTPException(400,"Participant must confirm the interview data notice before finishing")
    if s.status=="COMPLETED": return {"status":s.status,"report":s.report}
    task=db.get(Task,s.task_id); person=db.get(User,s.intern_id)
    if os.getenv("AUTONOMOUS_MODE", "false").lower() == "true":
        submitted = db.scalar(select(Submission.id).where(Submission.task_id==s.task_id, Submission.intern_id==s.intern_id, Submission.submitted_at>=s.created_at).order_by(Submission.version.desc()))
        if not submitted:
            raise HTTPException(409, "Submit the task deliverables before completing the autonomous review interview.")
        s.submission_id = submitted
    answers={r["question_index"]:r for r in (s.transcript or [])}
    details=[]; total=0
    for i,q in enumerate(s.questions):
        ans=answers.get(i,{}).get("answer","")
        words=[w.strip(".,!?():;\"'").lower() for w in ans.split() if len(w.strip(".,!?():;\"'"))>3]
        meaningful=len(words)
        evidence_terms=[t.lower() for t in (q.get("checks") or [])]
        matched=[t for t in evidence_terms if t in ans.lower()]
        length_score=min(60,meaningful*5)
        relevance_score=min(40,len(matched)*20)
        score=length_score+relevance_score if ans else 0
        score=min(100,score); total+=score
        details.append({"question":q["question"],"answer":ans,"score":score,"evidence_terms_matched":matched,"status":"ANSWERED" if ans else "NOT_ANSWERED","feedback":"Add concrete examples and test evidence." if score<60 else "Answer contains useful detail; compare with the submitted implementation and test results."})
    avg=round(total/max(1,len(s.questions)))
    answered=len(answers)
    # This is an explainable heuristic baseline, not a semantic LLM assessment.
    decision="AUTO_APPROVED" if avg>=70 and answered==len(s.questions) else "CORRECTIONS_REQUIRED"
    report={"overall_score":avg,"answered_count":answered,"question_count":len(s.questions),"recommendation":decision,"rubric_details":details,"evaluation_engine":"deterministic_fallback","limitations":["Prototype scoring is a deterministic heuristic, not a semantic LLM judgement.","The interview does not prove authorship or code correctness; use test results and submission evidence too.","This session runs in the InternMind browser room; it does not place an avatar inside Google Meet."],"generated_at":utcnow().isoformat()}
    latest_submission=db.scalar(select(Submission).where(Submission.task_id==s.task_id,Submission.intern_id==s.intern_id,Submission.submitted_at>=s.created_at).order_by(Submission.version.desc()))
    submission_review={"repository_url_present":bool(latest_submission and latest_submission.repository_url.strip()),"notes_present":bool(latest_submission and latest_submission.notes.strip()),"evidence_keys":list((latest_submission.evidence or {}).keys()) if latest_submission else [],"review_scope":"Metadata/evidence only; repository source code is not executed or independently verified by this MVP."}
    submission_evidence_ok=bool(latest_submission and latest_submission.repository_url.strip() and latest_submission.notes.strip() and (latest_submission.evidence or {}))
    semantic=evaluate_with_local_llm(task,s.questions,s.transcript or [],latest_submission)
    if semantic:
        semantic.update({"answered_count":answered,"question_count":len(s.questions),"generated_at":utcnow().isoformat()})
        report=semantic
    avg=int(report.get("overall_score",avg)); decision=str(report.get("recommendation",decision))
    report["submission_review"]=submission_review
    if os.getenv("AUTONOMOUS_MODE", "false").lower()=="true" and not submission_evidence_ok:
        decision="CORRECTIONS_REQUIRED"
        report["recommendation"]=decision
        report.setdefault("limitations",[]).append("Automatic approval requires a repository URL, implementation notes, and at least one concrete evidence field.")
        report["submission_review"]["decision_gate"]="CORRECTIONS_REQUIRED: repository URL, notes, or evidence is missing"
    s.report=report; s.status="COMPLETED"; s.completed_at=utcnow()
    if task:
        task.status="APPROVED" if report.get("recommendation")=="AUTO_APPROVED" else "CORRECTION_REQUIRED"
        assignment=db.scalar(select(Assignment).where(Assignment.task_id==task.id,Assignment.intern_id==s.intern_id))
        if assignment: assignment.status=task.status
        # Automatically allocate successor tasks that explicitly depend on this approved task.
        # This avoids assigning arbitrary unrelated tasks to an intern.
        if task.status=="APPROVED":
            successor_ids=[d.task_id for d in db.scalars(select(Dependency).where(Dependency.depends_on_id==task.id)).all()]
            admin_user=db.scalar(select(User).where(User.role=="admin").order_by(User.id).limit(1))
            people=db.scalars(select(User).where(User.role=="intern",User.active==True)).all()
            for successor_id in successor_ids:
                successor=db.get(Task,successor_id)
                if not successor or successor.status not in ("READY","CORRECTION_REQUIRED"):
                    continue
                if db.scalar(select(Assignment.id).where(Assignment.task_id==successor.id)):
                    continue
                prereqs=db.scalars(select(Dependency).where(Dependency.task_id==successor.id)).all()
                if any((db.get(Task,d.depends_on_id) is None or db.get(Task,d.depends_on_id).status!="APPROVED") for d in prereqs):
                    continue
                # Explainable workload + keyword skill matching; choose the least-loaded eligible intern.
                task_words=set((successor.title+" "+successor.description).lower().replace("/"," ").replace(","," ").split())
                ranked=[]
                for candidate in people:
                    active_count=db.scalar(select(func.count(Assignment.id)).where(Assignment.intern_id==candidate.id,Assignment.status.in_(["ASSIGNED","IN_PROGRESS","SUBMITTED","REVIEW_PENDING","CORRECTION_REQUIRED"]))) or 0
                    skill_words=set(" ".join(candidate.skills or []).lower().replace(","," ").split())
                    match=len(task_words & skill_words)
                    ranked.append((active_count,-match,candidate.id,candidate))
                if not ranked: break
                # Keep a task chain with the intern who just passed the prerequisite.
                # This gives each intern a continuous learning path instead of handing
                # their next task to a random colleague.
                chosen=person if person and person.role=="intern" and person.active else sorted(ranked,key=lambda z:(z[0],z[1],z[2]))[0][3]
                assigned_by=(admin_user.id if admin_user else person.id if person else chosen.id)
                due=utcnow()+timedelta(days=7)
                new_assignment=Assignment(task_id=successor.id,intern_id=chosen.id,assigned_by=assigned_by,due_at=due,status="ASSIGNED")
                db.add(new_assignment); successor.status="ASSIGNED"
                proj=db.get(Project,successor.project_id)
                review_start=(due.astimezone(ZoneInfo("Asia/Kolkata"))+timedelta(days=1)).replace(hour=10,minute=0,second=0,microsecond=0)
                token2=secrets.token_urlsafe(32)
                next_session=InterviewSession(task_id=successor.id,intern_id=chosen.id,submission_id=None,join_token=token2,status="SCHEDULED",questions=build_interview_questions(successor,None),transcript=[],report={})
                db.add(next_session); db.flush()
                public_url=os.getenv("APP_PUBLIC_URL","http://localhost:5173").rstrip("/")
                ai_room=f"{public_url}/interview?session_id={next_session.id}&join_token={token2}"
                submission_url=f"{public_url}/task-submit.html?task_id={successor.id}&join_token={token2}"
                meet_url=""
                try:
                    from app.google_calendar import create_meet_event
                    meet_url=create_meet_event(summary=f"InternMind AI task review — {chosen.name} — TASK-{successor.id:04d}",description=f"Project: {proj.name if proj else 'Project'}\nTask: {successor.title}\nAI interview room: {ai_room}",attendee_email=chosen.email,start_at=review_start,end_at=review_start+timedelta(minutes=30),timezone_name="Asia/Kolkata") or ""
                except Exception as exc: print("Google Meet creation failed:",str(exc))
                email(db,chosen.email,f"[InternMind AI] Next task assigned: {successor.title}",f"Hi {chosen.name},\n\nYour previous task was approved automatically.\nProject: {proj.name if proj else 'Project'}\nTask ID: TASK-{successor.id:04d}\nTask: {successor.title}\nInstructions: {successor.description}\nAcceptance criteria: "+"; ".join(successor.acceptance_criteria or [])+f"\nDeadline: {due.astimezone(ZoneInfo('Asia/Kolkata')).isoformat()}\nReview date/time: {review_start.isoformat()} (Asia/Kolkata)\nGoogle Meet: {meet_url or 'Not created; configure Google Calendar OAuth.'}\nSubmit your work: {submission_url}\nAI interview room: {ai_room}\n\nThis task was assigned automatically after your prior task passed review.")
    correction_details=""
    correction_submission_id=(s.submission_id or (db.scalar(select(Submission.id).where(Submission.task_id==s.task_id,Submission.intern_id==s.intern_id,Submission.submitted_at>=s.created_at).order_by(Submission.version.desc())) if person and task else None))
    if person and task and decision!="AUTO_APPROVED" and correction_submission_id:
        # Fully automatic correction cycle: persist the decision, generate a fresh
        # submission/interview token, schedule a new review and notify the intern.
        admin_user=db.scalar(select(User).where(User.role=="admin").order_by(User.id).limit(1))
        if admin_user:
            review_row=Review(submission_id=correction_submission_id,reviewer_id=admin_user.id,decision="CORRECTION_REQUIRED",feedback="\n".join(d.get("feedback","") for d in details))
            db.add(review_row); db.flush()
            cycle_no=(db.scalar(select(func.max(Correction.cycle_number).join(Review).where(Review.submission_id==review_row.submission_id)) or 0)+1)
            correction_deadline=utcnow()+timedelta(days=3)
            review_start=(correction_deadline.astimezone(ZoneInfo("Asia/Kolkata"))+timedelta(days=1)).replace(hour=10,minute=0,second=0,microsecond=0)
            correction=Correction(review_id=review_row.id,cycle_number=cycle_no,correction_deadline=correction_deadline,next_review_at=review_start,timezone_name="Asia/Kolkata",status="SCHEDULED")
            db.add(correction); db.flush()
            new_token=secrets.token_urlsafe(32)
            new_session=InterviewSession(task_id=task.id,intern_id=person.id,submission_id=None,join_token=new_token,status="SCHEDULED",questions=build_interview_questions(task,None),transcript=[],report={})
            db.add(new_session); db.flush()
            public_url=os.getenv("APP_PUBLIC_URL","http://localhost:5173").rstrip("/")
            submit_url=f"{public_url}/task-submit.html?task_id={task.id}&join_token={new_token}"
            interview_url=f"{public_url}/interview?session_id={new_session.id}&join_token={new_token}"
            meet_url=""
            try:
                from app.google_calendar import create_meet_event
                proj=db.get(Project,task.project_id)
                meet_url=create_meet_event(summary=f"InternMind AI correction review — {person.name} — TASK-{task.id:04d}",description=f"Project: {proj.name if proj else 'Project'}\nTask: {task.title}\nCorrection deadline: {correction_deadline.isoformat()}\nAI interview room: {interview_url}",attendee_email=person.email,start_at=review_start,end_at=review_start+timedelta(minutes=30),timezone_name="Asia/Kolkata") or ""
            except Exception as exc: print("Google Meet correction review creation failed:",str(exc))
            correction_details=(f"\n\nCORRECTION REQUIRED\nCorrection deadline: {correction_deadline.isoformat()}\nNext review: {review_start.isoformat()} (Asia/Kolkata)\nGoogle Meet: {meet_url or 'Not created; configure Google Calendar OAuth.'}\nResubmit here: {submit_url}\nAI interview room: {interview_url}\nPlease correct the feedback items above and resubmit. The system will re-review automatically.")
    if person:
        body=(f"Hi {person.name},\n\nYour AI interview report for task TASK-{task.id if task else s.task_id:04d} is ready.\nScore: {avg}/100\nRecommendation: {decision}\n\n"+"\n".join([f"Q{i+1}: {d['status']} — {d['feedback']}" for i,d in enumerate(details)])+"\n\nThis prototype report is a heuristic and should be considered alongside task evidence and test results."+correction_details)
        email(db,person.email,"[InternMind AI] Interview feedback",body)
    audit(db,person or db.get(User,1),"interview",s.id,"completed",{"score":report.get("overall_score",avg),"recommendation":report.get("recommendation",decision)})
    db.commit()
    return {"status":s.status,"report":report}



@app.post("/autonomous/tasks/{tid}/submit")
def autonomous_public_submit(tid:int, join_token:str, x:SubmitIn, db:Session=Depends(db_dep)):
    """Student submission endpoint protected by the unique invite token; no account login required."""
    session=db.scalar(select(InterviewSession).where(InterviewSession.task_id==tid,InterviewSession.join_token==join_token).order_by(InterviewSession.id.desc()))
    if not session or not secrets.compare_digest(session.join_token,join_token): raise HTTPException(404,"Submission link is invalid.")
    if session.status=="COMPLETED": raise HTTPException(409,"This review cycle is complete; use the latest task email for the next task.")
    if session.created_at and (utcnow()-session.created_at.replace(tzinfo=timezone.utc if session.created_at.tzinfo is None else session.created_at.tzinfo)).days>45:
        raise HTTPException(410,"This submission link expired. Request a new task invitation.")
    if not x.repository_url and not x.notes and not x.evidence: raise HTTPException(400,"Provide a GitHub/repository URL, notes, or evidence.")
    task=db.get(Task,tid)
    if not task: raise HTTPException(404,"Task not found.")
    ver=(db.scalar(select(func.max(Submission.version)).where(Submission.task_id==tid,Submission.intern_id==session.intern_id)) or 0)+1
    submission=Submission(task_id=tid,intern_id=session.intern_id,version=ver,repository_url=x.repository_url,notes=x.notes,evidence=x.evidence)
    db.add(submission); task.status="SUBMITTED"
    assignment=db.scalar(select(Assignment).where(Assignment.task_id==tid,Assignment.intern_id==session.intern_id))
    if assignment: assignment.status="SUBMITTED"
    session.submission_id=submission.id if submission.id else None
    session.status="SUBMISSION_RECEIVED"
    db.flush(); session.submission_id=submission.id
    email(db,session and db.get(User,session.intern_id).email,"[InternMind AI] Submission received",f"We received your submission for TASK-{tid:04d}: {task.title}. Your AI review interview is scheduled using the link in your task email.\nSubmission version: {ver}")
    db.commit()
    return {"status":"SUBMITTED","task_id":tid,"submission_id":submission.id,"version":ver,"interview_url":f"{os.getenv('APP_PUBLIC_URL','http://localhost:5173').rstrip('/')}/interview?session_id={session.id}&join_token={join_token}"}


# Background reminder agent. It never creates duplicate reminders for the same
# task/recipient within 24 hours. SMTP must be configured for real delivery.
def run_reminder_agent():
    now=utcnow()
    with SessionLocal() as db:
        active=db.scalars(select(Assignment).where(Assignment.status.in_(["ASSIGNED","IN_PROGRESS","CORRECTION_REQUIRED"]))).all()
        for a in active:
            task=db.get(Task,a.task_id); person=db.get(User,a.intern_id)
            if not task or not person: continue
            due=a.due_at
            if due and due.tzinfo is None: due=due.replace(tzinfo=timezone.utc)
            if not due: continue
            upcoming=now < due <= now+timedelta(hours=24)
            overdue=due < now
            if not upcoming and not overdue: continue
            kind="deadline reminder" if upcoming else "overdue task reminder"
            subject=f"[InternMind AI] {kind.title()}: {task.title}"
            recent=db.scalar(select(Notice.id).where(Notice.recipient==person.email,Notice.subject==subject,Notice.created_at>=now-timedelta(hours=24)).limit(1))
            if recent: continue
            body=(f"Hi {person.name},\\n\\nThis is an automatic {kind} for TASK-{task.id:04d}: {task.title}.\\n"
                  f"Deadline: {due.astimezone(ZoneInfo('Asia/Kolkata')).isoformat()} (Asia/Kolkata).\\n"
                  f"Current task status: {a.status}.\\nPlease open your latest InternMind task email for submission and interview links.")
            email(db,person.email,subject,body)
        db.commit()

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    _reminder_scheduler=BackgroundScheduler(daemon=True)
    @app.on_event("startup")
    def start_reminder_scheduler():
        if os.getenv("REMINDER_AGENT_ENABLED","true").lower()=="true" and not _reminder_scheduler.running:
            _reminder_scheduler.add_job(run_reminder_agent,"interval",hours=1,id="internmind_reminder_agent",replace_existing=True)
            _reminder_scheduler.start()
    @app.on_event("shutdown")
    def stop_reminder_scheduler():
        if _reminder_scheduler.running: _reminder_scheduler.shutdown(wait=False)
except ImportError:
    print("APScheduler unavailable; background reminders disabled. Install requirements.txt.")


# ---------------- AUTONOMOUS MODE ----------------
# Student details are the only routine input. This endpoint creates/reuses the
# project, imports candidates, creates a three-stage task chain per intern,
# assigns stage 1, schedules a Google Calendar/Meet event when configured,
# creates a private AI interview room, and emails the student.
from pathlib import Path as _Path

class AutonomousStatusOut(BaseModel):
    enabled: bool
    smtp_configured: bool
    google_calendar_configured: bool
    public_url: str
    notes: list[str]

@app.get("/autonomous/status", response_model=AutonomousStatusOut)
def autonomous_status():
    smtp_ok=all(os.getenv(k,"").strip() for k in ("SMTP_HOST","SMTP_USER","SMTP_PASSWORD","SMTP_FROM"))
    creds=os.getenv("GOOGLE_CALENDAR_CREDENTIALS","credentials.json")
    token=os.getenv("GOOGLE_CALENDAR_TOKEN","token.json")
    calendar_ok=os.path.exists(creds) and os.path.exists(token) and os.getenv("GOOGLE_CALENDAR_ENABLED","false").lower()=="true"
    notes=[]
    if not smtp_ok: notes.append("SMTP is not fully configured; emails will be previewed, not delivered.")
    if not calendar_ok: notes.append("Google Calendar OAuth is not configured; real Meet links cannot be created yet.")
    notes.append("The AI voice interview room runs in the InternMind website. Google Calendar API can create a Meet event, but it does not place an AI bot inside a standard Meet call.")
    return {"enabled":os.getenv("AUTONOMOUS_MODE","false").lower()=="true","smtp_configured":smtp_ok,"google_calendar_configured":calendar_ok,"public_url":os.getenv("APP_PUBLIC_URL","http://localhost:5173"),"notes":notes}

@app.post("/autonomous/enroll-csv")
async def autonomous_enroll_csv(file: UploadFile=File(...), db: Session=Depends(db_dep), u: User=Depends(roles("admin","mentor"))):
    """One upload starts the workflow: candidates -> unique task chain -> email -> scheduled review."""
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(400,"Upload a CSV with name,email,skills columns.")
    raw=await file.read()
    if len(raw)>2_000_000: raise HTTPException(413,"CSV too large (max 2 MB).")
    try: rows=list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
    except UnicodeDecodeError: raise HTTPException(400,"CSV must be UTF-8.")
    if not rows or not {"name","email"}.issubset(set(rows[0].keys())):
        raise HTTPException(400,"CSV headers must include name,email; skills is optional.")

    project_name=os.getenv("AUTONOMOUS_PROJECT_NAME","Thozhil Autonomous Internship Project")
    project=db.scalar(select(Project).where(Project.name==project_name).order_by(Project.id).limit(1))
    if not project:
        project=Project(name=project_name,client_name="Thozhil",description="Autonomous multi-agent internship project",created_by=u.id)
        db.add(project); db.flush()

    bank=[]
    bank_path=_Path(__file__).resolve().parent.parent/"data"/"tasks_assignments.csv"
    if bank_path.exists():
        try:
            with bank_path.open("r",encoding="utf-8-sig",newline="") as f: bank=list(csv.DictReader(f))
        except Exception as exc: print("Could not read task bank:",exc)
    if not bank:
        bank=[{"title":"Project implementation work package","description":"Implement the assigned module, add tests, document setup and provide a public or accessible repository URL.","acceptance_criteria":"Working implementation; tests; README; demo evidence"}]

    from app.google_calendar import create_meet_event
    public_url=os.getenv("APP_PUBLIC_URL","http://localhost:5173").rstrip("/")
    created=[]; skipped=[]
    now=utcnow()
    for index,row in enumerate(rows):
        name=(row.get("name") or "").strip(); em=(row.get("email") or "").strip().lower()
        if not name or not em:
            skipped.append({"email":em,"reason":"missing name/email"}); continue
        if em.endswith("@example.com") or em.endswith("@example.org"):
            skipped.append({"email":em,"reason":"reserved demo email domain; replace with a real authorized student address before autonomous notifications"}); continue
        if "@" not in em or "." not in em.rsplit("@",1)[-1]:
            skipped.append({"email":em,"reason":"invalid email address"}); continue
        person=db.scalar(select(User).where(User.email==em))
        if person and person.role!="intern":
            skipped.append({"email":em,"reason":"email belongs to a non-intern account"}); continue
        if not person:
            skills=[v.strip() for v in (row.get("skills") or "").replace(",",";").split(";") if v.strip()]
            person=User(name=name,email=em,role="intern",skills=skills,password_hash="")
            db.add(person); db.flush()
        else:
            # Update details without overwriting an existing skill list with blanks.
            person.name=name
            skills=[v.strip() for v in (row.get("skills") or "").replace(",",";").split(";") if v.strip()]
            if skills: person.skills=skills

        existing_active=db.scalar(select(Assignment.id).join(Task,Assignment.task_id==Task.id).where(Assignment.intern_id==person.id,Task.project_id==project.id,Assignment.status.in_(["ASSIGNED","IN_PROGRESS","SUBMITTED","REVIEW_PENDING","CORRECTION_REQUIRED"])))
        if existing_active:
            skipped.append({"email":em,"reason":"already has an active task in this autonomous project"}); continue

        template=bank[len(created) % len(bank)]
        base_title=(template.get("title") or f"Unique Work Package {index+1}").strip()
        description=(template.get("description") or "Complete the assigned work package.").strip()
        raw_criteria=(template.get("acceptance_criteria") or "Working implementation; tests; README; demo evidence").strip()
        criteria=[c.strip().strip(". ") for c in raw_criteria.replace(";","\n").splitlines() if c.strip()]
        if not criteria: criteria=["Working implementation","Tests and validation evidence","README and setup instructions"]
        due=now+timedelta(days=7)
        review_start=(due.astimezone(ZoneInfo("Asia/Kolkata"))+timedelta(days=1)).replace(hour=10,minute=0,second=0,microsecond=0)
        # Three task stages; only stage 1 is assigned immediately. Later stages
        # become eligible after the prior stage's AI interview passes.
        tasks=[]
        stages=[(base_title,description,criteria),(f"{base_title} — automated tests and quality",description+"\nStage 2: strengthen test coverage, handle edge cases, and fix defects discovered in review.",criteria+["Edge cases covered","Test results documented"]),(f"{base_title} — integration and release evidence",description+"\nStage 3: integrate the module, update documentation, and provide release/demo evidence.",criteria+["Integration evidence provided","Final README and demo evidence included"])]
        for stage_no,(title,desc,ac) in enumerate(stages,1):
            task=Task(project_id=project.id,title=title,description=desc,acceptance_criteria=ac,requirement_codes=[],status="READY")
            db.add(task); db.flush(); tasks.append(task)
            if stage_no>1: db.add(Dependency(task_id=task.id,depends_on_id=tasks[stage_no-2].id))
        first=tasks[0]
        assignment=Assignment(task_id=first.id,intern_id=person.id,assigned_by=u.id,due_at=due,status="ASSIGNED")
        db.add(assignment); first.status="ASSIGNED"; db.flush()
        # Build the private interview room now so its URL can be included in the invite.
        token=secrets.token_urlsafe(32)
        questions=build_interview_questions(first,None)
        session=InterviewSession(task_id=first.id,intern_id=person.id,submission_id=None,join_token=token,status="SCHEDULED",questions=questions,transcript=[],report={})
        db.add(session); db.flush()
        ai_room=f"{public_url}/interview?session_id={session.id}&join_token={token}"
        submission_url=f"{public_url}/task-submit.html?task_id={first.id}&join_token={token}"
        meet_url=""
        try:
            meet_url=create_meet_event(
                summary=f"InternMind AI task review — {name} — TASK-{first.id:04d}",
                description=f"Project: {project.name}\nTask: {first.title}\nSubmission deadline: {due.isoformat()}\nAI interview room: {ai_room}",
                attendee_email=em, start_at=review_start, end_at=review_start+timedelta(minutes=30),
                timezone_name="Asia/Kolkata") or ""
        except Exception as exc:
            print("Google Meet creation failed:",str(exc))
        body=(f"Hi {name},\n\nWelcome to {project.name}. Your task has been assigned automatically.\n\n"
              f"Task ID: TASK-{first.id:04d}\nTask: {first.title}\n\nInstructions:\n{first.description}\n\n"
              f"Acceptance criteria:\n- "+"\n- ".join(first.acceptance_criteria or [])+
              f"\n\nSubmission deadline: {due.astimezone(ZoneInfo("Asia/Kolkata")).isoformat()}\nReview date/time: {review_start.astimezone(ZoneInfo("Asia/Kolkata")).isoformat()} (Asia/Kolkata)\n"
              f"Google Meet: {meet_url or 'Not created: configure Google Calendar OAuth to enable automatic Meet creation.'}\n"
              f"Submit your work here: {submission_url}\nAI interview room: {ai_room}\n\nSubmit your GitHub repository URL, notes, and evidence before the review."
              )
        email(db,person.email,f"[InternMind AI] Task assigned: {first.title}",body)
        created.append({"intern_id":person.id,"name":name,"email":em,"task_id":first.id,"task_title":first.title,"due_at":due.isoformat(),"review_at":review_start.isoformat(),"meet_url":meet_url or None,"ai_interview_url":ai_room,"next_stage_task_ids":[tasks[1].id,tasks[2].id]})
    audit(db,u,"project",project.id,"autonomous_enrollment",{"created":len(created),"skipped":len(skipped)})
    db.commit()
    return {"project_id":project.id,"project_name":project.name,"autonomous_mode":os.getenv("AUTONOMOUS_MODE","false").lower()=="true","created":created,"skipped":skipped,"email_note":"Check notice statuses and backend logs. SENT means SMTP accepted the message; it does not guarantee inbox delivery.","google_meet_note":"A real Meet link is returned only when Google Calendar OAuth is configured. Calendar-created Meet links do not automatically put the AI voice avatar inside Google Meet; the AI interview currently runs in the InternMind browser room."}
