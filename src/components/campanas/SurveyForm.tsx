'use client';
import {useEffect,useState} from 'react';
import Image from 'next/image';
import {fetchFromApi} from '@/lib/api';
import type {SurveyDraft} from '@/modules/campanas/service';
type Survey = {questionnaire:SurveyDraft;is_test:boolean;submitted:boolean};
export function SurveyForm({token}:{token:string}) {
 const [survey,setSurvey]=useState<Survey|null>(null);
 const [answers,setAnswers]=useState<Record<string,string|string[]>>({});
 const [error,setError]=useState('');
 const [busy,setBusy]=useState(false);
 const [saved,setSaved]=useState(false);
 useEffect(()=>{let active=true;fetchFromApi<Survey>(`/encuestas/${encodeURIComponent(token)}`).then(s=>{if(active){setSurvey(s);setSaved(s.submitted);}}).catch(e=>{if(active)setError(e.message);});return()=>{active=false;};},[token]);
 async function submit(event:React.FormEvent) {
  event.preventDefault();setBusy(true);setError('');
  try {await fetchFromApi(`/encuestas/${encodeURIComponent(token)}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({answers})});setSaved(true);}
  catch(e){setError(e instanceof Error?e.message:'No se pudo guardar.');}finally{setBusy(false);}
 }
 return <div role="region" aria-label="Cuestionario TAIICO" tabIndex={0} className="h-full max-h-dvh min-h-0 flex-1 overflow-y-auto overscroll-contain bg-[#34587C] px-4 py-6 [scrollbar-gutter:stable] sm:px-8 sm:py-12"><div className="mx-auto max-w-2xl overflow-hidden rounded-2xl border border-white/20 bg-white shadow-2xl shadow-[#07385B]/30">
 <header className="flex flex-col items-center gap-4 border-b-4 border-[#00ADD3] bg-[#07385B] px-6 py-7 text-center sm:flex-row sm:px-10 sm:text-left">
   <Image src="/logo.png" alt="TAIICO Life Advisors" width={512} height={512} priority unoptimized className="h-24 w-24 shrink-0 sm:h-28 sm:w-28" />
   <div><p className="mt-2 text-2xl font-semibold text-white">{survey?.questionnaire.header_title || 'Tu opinión cuenta'}</p><p className="mt-1 text-sm text-white/80">{survey?.questionnaire.header_description || 'Construyamos juntos herramientas para tu operación.'}</p></div>
 </header>
 <div className="p-6 sm:p-10">
 {survey?.is_test&&<p className="mt-3 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">Prueba interna. Tu respuesta no se incluirá en los resultados de los agentes.</p>}
 {error&&<p role="alert" className="my-4 rounded bg-red-50 p-3 text-red-700">{error.replace('API Error: ','')}</p>}
 {!survey&&!error&&<p className="mt-4">Cargando encuesta…</p>}
 {saved?<div role="status" className="mt-6"><h1 className="text-2xl font-bold text-[#07385B]">{survey?.questionnaire.success_title || '¡Gracias por compartir tu opinión!'}</h1><p className="mt-3 text-slate-600">{survey?.questionnaire.success_description || 'Tu respuesta quedó guardada.'}</p></div>:survey&&<form onSubmit={submit}>
 <h1 className="mt-4 text-2xl font-bold text-[#07385B]">{survey.questionnaire.title}</h1><p className="mt-3 text-slate-600">{survey.questionnaire.description}</p>
 <div className="my-8 space-y-8">{survey.questionnaire.questions.map((q,i)=><fieldset key={q.id} disabled={busy}><legend className="mb-3 font-semibold leading-6 text-[#07385B]">{i+1}. {q.label} {!q.required&&<span className="font-normal">(opcional)</span>}</legend>
 {q.format==='phone'?<input type="tel" autoComplete="tel" aria-label={q.label} maxLength={q.max_length} required={q.required} value={String(answers[q.id]||'')} onChange={e=>setAnswers({...answers,[q.id]:e.target.value})} className="w-full rounded-lg border border-slate-300 p-3 text-slate-900"/>:q.type==='text'?<textarea aria-label={q.label} maxLength={q.max_length} required={q.required} value={String(answers[q.id]||'')} onChange={e=>setAnswers({...answers,[q.id]:e.target.value})} rows={4} className="w-full rounded-lg border border-slate-300 p-3 text-slate-900 outline-none transition focus:border-[#007B9A] focus:ring-2 focus:ring-[#00ADD3]/25"/>:q.options?.map(option=>{
 const chosen=Array.isArray(answers[q.id])?answers[q.id] as string[]:[];
 const isChosen=q.type==='multiple'?chosen.includes(option):answers[q.id]===option;
 return <label key={option} className={`mb-2 flex cursor-pointer items-start gap-3 rounded-lg border p-3 text-slate-800 transition focus-within:ring-2 focus-within:ring-[#00ADD3]/40 ${isChosen?'border-[#007B9A] bg-[#EAF8FC]':'border-slate-200 bg-white hover:border-[#007B9A] hover:bg-[#F3FAFD]'}`}><input className="mt-1 h-4 w-4 shrink-0 accent-[#07385B]" type={q.type==='multiple'?'checkbox':'radio'} name={q.id} required={q.type==='single'&&q.required} checked={q.type==='multiple'?chosen.includes(option):answers[q.id]===option} onChange={()=>{
 if(q.type==='single'){setAnswers({...answers,[q.id]:option});return;}
 const next=chosen.includes(option)?chosen.filter(v=>v!==option):option===q.exclusive_option?[option]:[...chosen.filter(v=>v!==q.exclusive_option),option];
 if(next.length>(q.max_choices||3)){setError('Elige hasta tres prioridades.');return;}setError('');setAnswers({...answers,[q.id]:next});
 }}/>{option}</label>;
 })}</fieldset>)}</div>{survey.questionnaire.privacy_url&&<p className="mb-5 text-sm"><a className="underline" href={survey.questionnaire.privacy_url} target="_blank" rel="noreferrer">Aviso de privacidad</a></p>}<button disabled={busy} className="w-full rounded-lg bg-[#07385B] p-3 font-semibold text-white transition hover:bg-[#34587C] focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#007B9A] disabled:cursor-wait disabled:opacity-50">{busy?'Guardando…':'Enviar respuesta'}</button></form>}
 </div>
 <footer className="border-t border-[#DCEAF1] bg-[#F3F8FB] px-6 py-4 text-center text-xs font-medium text-[#34587C]">TAIICO Life Advisors · Gracias por ayudarnos a mejorar.</footer>
 </div></div>;
}
