"use client";

export function RealityPause({
  reasons,
  onClose,
}: {
  reasons: string[];
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-950/90 backdrop-blur-sm">
      <div className="flex min-h-full items-center justify-center p-4">
        <div className="w-full max-w-md rounded-2xl border border-amber-500/40 bg-slate-900 p-6 shadow-2xl">
          <h2 className="text-xl font-semibold text-amber-400">
            ⚠️ Pause before continuing
          </h2>
          <p className="mt-2 text-sm text-slate-300">
            This interaction shows several patterns associated with financial
            scams.
          </p>

          <ul className="mt-4 space-y-1 text-sm text-slate-200">
            {reasons.map((r) => (
              <li key={r}>• {r}</li>
            ))}
          </ul>

          <p className="mt-4 text-sm font-medium text-slate-100">
            Verify through your bank&apos;s official app before continuing.
          </p>

          <div className="mt-6 flex flex-col gap-2">
            <button
              onClick={onClose}
              className="rounded-lg bg-emerald-600 py-2 font-medium hover:bg-emerald-500"
            >
              Verify Safely
            </button>
            <button
              onClick={onClose}
              className="rounded-lg bg-slate-700 py-2 hover:bg-slate-600"
            >
              I&apos;m Not Sure
            </button>
            <button
              onClick={onClose}
              className="rounded-lg py-2 text-sm text-slate-400 hover:text-slate-200"
            >
              Continue Anyway
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}