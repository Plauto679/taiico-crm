export default function Loading() {
  return (
    <div className="flex h-full min-h-0 flex-col gap-5 overflow-hidden p-4 pt-16 sm:p-8" role="status" aria-live="polite">
      <div className="h-9 w-56 animate-pulse rounded-lg bg-white/25" />
      <div className="h-28 flex-none animate-pulse rounded-2xl bg-white/90 shadow-sm">
        <div className="flex h-full items-center gap-4 px-5">
          <div className="h-11 w-11 rounded-xl bg-slate-200" />
          <div className="space-y-3">
            <div className="h-4 w-52 rounded bg-slate-200" />
            <div className="h-3 w-72 max-w-[60vw] rounded bg-slate-100" />
          </div>
        </div>
      </div>
      <div className="min-h-0 flex-1 animate-pulse overflow-hidden rounded-2xl bg-white shadow-sm">
        <div className="flex gap-5 border-b bg-slate-50 px-5 py-5">
          {["w-32", "w-44", "w-36", "w-40"].map((width) => <div key={width} className={`h-9 ${width} rounded bg-slate-200`} />)}
        </div>
        <div className="space-y-4 p-5">
          {Array.from({ length: 7 }, (_, index) => <div key={index} className="h-10 rounded bg-slate-100" />)}
        </div>
      </div>
      <span className="sr-only">Cargando módulo…</span>
    </div>
  );
}
