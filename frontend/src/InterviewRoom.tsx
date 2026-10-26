import { useCallback, useEffect, useRef, useState } from "react";
import { Mic, MicOff, Volume2, ArrowRight, CheckCircle2, ShieldCheck, Sparkles, LoaderCircle } from "lucide-react";
import "./interview.css";

const API = (import.meta as any).env?.VITE_API_URL || "http://127.0.0.1:8000";
type InterviewData = { id:number; status:string; task_title:string; task_description?:string; project_name:string; intern_name:string; acceptance_criteria?:string[]; questions:{type:string;question:string;checks:string[]}[]; transcript:{question_index:number;question:string;answer:string}[]; report?:any };
export default function InterviewRoom(){
  const params = new URLSearchParams(window.location.search);
  const sessionId = Number(params.get("session_id") || 0);
  const joinToken = params.get("join_token") || "";
  const [data,setData] = useState<InterviewData|null>(null);
  const [index,setIndex] = useState(0);
  const [answer,setAnswer] = useState("");
  const [busy,setBusy] = useState(false);
  const [listening,setListening] = useState(false);
  const [speaking,setSpeaking] = useState(false);
  const [consent,setConsent] = useState(false);
  const [error,setError] = useState("");
  const [finished,setFinished] = useState<any>(null);
  const recognition = useRef<any>(null);
  const currentQuestion = data?.questions?.[index];
  const call = useCallback(async(path:string, init:RequestInit={})=>{
    const url = `${API}${path}${path.includes("?")?"&":"?"}join_token=${encodeURIComponent(joinToken)}`;
    const res=await fetch(url,{...init,headers:{"Content-Type":"application/json",...(init.headers||{})}});
    const body=await res.json().catch(()=>({detail:"Unexpected server response"}));
    if(!res.ok) throw new Error(body.detail||`Request failed (${res.status})`);
    return body;
  },[joinToken]);
  useEffect(()=>{ if(!sessionId||!joinToken){setError("This interview link is incomplete. Ask the project coordinator for a new link.");return;} call(`/interviews/${sessionId}/public`).then((d)=>{setData(d);setFinished(d.status==="COMPLETED"?d.report:null);setIndex(d.transcript?.length||0);}).catch(e=>setError(e.message)); },[sessionId,joinToken,call]);
  const speak = useCallback((text:string)=>{
    if(!("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const utterance=new SpeechSynthesisUtterance(text); utterance.lang="en-IN"; utterance.rate=0.96;
    utterance.onstart=()=>setSpeaking(true); utterance.onend=()=>setSpeaking(false); utterance.onerror=()=>setSpeaking(false);
    window.speechSynthesis.speak(utterance);
  },[]);
  useEffect(()=>{ if(currentQuestion && !finished){ speak(currentQuestion.question); } return ()=>{ if("speechSynthesis" in window) window.speechSynthesis.cancel(); }; },[index,currentQuestion?.question,finished,speak]);
  function startListening(){
    const w=window as any; const Recognition=w.SpeechRecognition||w.webkitSpeechRecognition;
    if(!Recognition){setError("Speech recognition is not supported in this browser. Type your answer below, or use current Chrome/Edge.");return;}
    setError(""); const rec=new Recognition(); recognition.current=rec; rec.lang="en-IN"; rec.continuous=true; rec.interimResults=true;
    rec.onresult=(event:any)=>{let text="";for(let i=0;i<event.results.length;i++) text+=event.results[i][0].transcript+" ";setAnswer(text.trim());};
    rec.onerror=(event:any)=>{setListening(false);if(event.error!=="no-speech")setError(`Microphone error: ${event.error}. You can type your answer instead.`);};
    rec.onend=()=>setListening(false); rec.start(); setListening(true);
  }
  function stopListening(){try{recognition.current?.stop();}catch{}setListening(false);}
  async function saveAnswerAndContinue(){
    if(!currentQuestion||!answer.trim()) {setError("Please answer the question before continuing.");return;}
    setBusy(true);setError("");stopListening();
    try{
      await call(`/interviews/${sessionId}/answer`,{method:"POST",body:JSON.stringify({question_index:index,question:currentQuestion.question,answer:answer.trim()})});
      const next=index+1;
      if(next>=data!.questions.length){
        if(!consent){setError("Please confirm the interview data notice before finishing.");setBusy(false);return;}
        const result=await call(`/interviews/${sessionId}/finish`,{method:"POST",body:JSON.stringify({consent_confirmed:true})});setFinished(result.report);setData(prev=>prev?{...prev,status:"COMPLETED"}:prev);
      } else {setIndex(next);setAnswer("");}
    }catch(e:any){setError(e.message||"Unable to save answer");}finally{setBusy(false);}
  }
  if(error&&!data) return <div className="interview-page"><div className="interview-card"><div className="ai-mark"><Sparkles/></div><h1>InternMind AI Interview</h1><p className="interview-error">{error}</p></div></div>;
  if(!data) return <div className="interview-page"><div className="interview-card"><LoaderCircle className="spin"/><h2>Preparing your interview room…</h2></div></div>;
  if(finished) return <div className="interview-page"><div className="interview-card result-card"><div className="ai-mark success"><CheckCircle2/></div><div className="interview-eyebrow">INTERVIEW COMPLETED</div><h1>Your interview report</h1><p>{data.task_title}</p><div className="score-circle"><strong>{finished.overall_score}</strong><span>/ 100</span></div><h3>{finished.recommendation?.replaceAll("_"," ")}</h3><p className="muted">Your answers have been saved and feedback has been emailed if email delivery is configured.</p><div className="report-list">{(finished.rubric_details||[]).map((r:any,i:number)=><div className="report-row" key={i}><div><strong>Question {i+1}</strong><p>{r.feedback}</p></div><span>{r.score}/100</span></div>)}</div><div className="privacy-note"><ShieldCheck size={17}/> This prototype uses explainable heuristic scoring. It is not a definitive judgement of your ability or proof of code correctness.</div></div></div>;
  return <div className="interview-page"><div className="interview-top"><div className="interview-brand"><span className="brand-mini"><Sparkles size={18}/></span> InternMind <b>AI</b></div><span className="secure-pill"><ShieldCheck size={14}/> Private interview room</span></div><div className="interview-layout"><section className="interview-card avatar-card"><div className="interview-eyebrow">AI TECHNICAL INTERVIEWER</div><div className={`avatar-stage ${speaking?"is-speaking":""} ${listening?"is-listening":""}`}><div className="avatar-glow"/><div className="avatar-halo"/><div className="avatar-head"><div className="avatar-hair"/><div className="avatar-face"><div className="avatar-brows"><i/><i/></div><div className="avatar-eyes"><i/><i/></div><div className="avatar-nose"/><div className="avatar-mouth"/></div><div className="avatar-neck"/><div className="avatar-body"/></div><div className="avatar-status"><span className="status-pulse"/>{speaking?"AI is speaking":listening?"Listening to you":"Ready to interview"}</div></div><h2>Hello, {data.intern_name.split(" ")[0]}.</h2><p>I’ll ask about your task, implementation, testing, and how you handled edge cases. Take your time and explain your reasoning.</p><button className="speak-again" onClick={()=>speak(currentQuestion?.question||"Welcome to your interview")}><Volume2 size={16}/> Repeat question</button></section><section className="interview-card question-card"><div className="question-progress"><span>QUESTION {Math.min(index+1,data.questions.length)} OF {data.questions.length}</span><div className="progress-track"><i style={{width:`${((index+1)/data.questions.length)*100}%`}}/></div></div><div className="task-context"><span>{data.project_name}</span><strong>{data.task_title}</strong>{data.acceptance_criteria?.length? <ul>{data.acceptance_criteria.slice(0,3).map((c,i)=><li key={i}>{c}</li>)}</ul>:null}</div><div className="question-prompt"><span className="question-type">{currentQuestion?.type?.replaceAll("_"," ")||"Question"}</span><h2>{currentQuestion?.question||"Interview complete"}</h2></div><label className="answer-label" htmlFor="answer">Your answer</label><textarea id="answer" value={answer} onChange={e=>setAnswer(e.target.value)} placeholder="Speak using the microphone or type your answer here…" rows={6}/><div className="answer-tools"><button className={`mic-button ${listening?"active":""}`} onClick={listening?stopListening:startListening}>{listening?<MicOff size={17}/>:<Mic size={17}/>} {listening?"Stop listening":"Answer by voice"}</button><span>{answer.trim().split(/\s+/).filter(Boolean).length} words</span></div>{error&&<div className="interview-error">{error}</div>}<label className="consent-row"><input type="checkbox" checked={consent} onChange={e=>setConsent(e.target.checked)}/><span>I understand this AI interview stores my written/transcribed answers for generating a feedback report. I can use text input if microphone speech recognition is unavailable.</span></label><button className="continue-button" disabled={busy||!answer.trim()} onClick={saveAnswerAndContinue}>{busy?<><LoaderCircle className="spin" size={17}/> Saving…</>:index===data.questions.length-1?"Finish interview":"Save answer & next question"}<ArrowRight size={17}/></button><p className="interview-footnote">Microphone permission is required for voice input. This browser room is not a Google Meet call; no raw audio recording is saved by this app.</p></section></div><footer className="interview-footer">INTERNMIND AI · TASK-BASED REVIEW · {data.status}</footer></div>;
}
