interface HeaderProps {
  backendOnline: boolean | null;
}


export default function Header({
  backendOnline,
}: HeaderProps) {
  const statusText =
    backendOnline === null
      ? "Checking backend"
      : backendOnline
        ? "Backend online"
        : "Backend offline";

  const statusColor =
    backendOnline === null
      ? "bg-amber-400"
      : backendOnline
        ? "bg-emerald-500"
        : "bg-red-500";

  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-4 lg:px-8">
        <div className="flex items-center gap-3">
          <div className="flex size-11 items-center justify-center rounded-2xl bg-blue-600 text-lg font-black text-white shadow-sm">
            M
          </div>

          <div>
            <p className="text-lg font-bold text-slate-950">
              MEYAAR
            </p>

            <p className="text-xs text-slate-500">
              Geospatial validation platform
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-2">
          <span
            className={`size-2.5 rounded-full ${statusColor}`}
          />

          <span className="text-xs font-semibold text-slate-600">
            {statusText}
          </span>
        </div>
      </div>
    </header>
  );
}
