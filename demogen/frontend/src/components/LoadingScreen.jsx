const LoadingScreen = ({ message }) => {
  return (
    <div className="grid-bg fixed inset-0 z-50 flex flex-col items-center justify-center bg-bg">
      <div className="mb-4 flex items-center gap-3">
        <div className="h-10 w-10 rounded-xl border border-teal/50 bg-gradient-to-br from-teal/40 to-transparent" />
        <h2 className="text-3xl font-bold tracking-wide text-tealSoft">DemoGen</h2>
      </div>
      <div className="progress-ring" />
      <p className="mt-8 text-lg text-slate-100 animate-messagefade">{message}</p>
      <p className="mt-3 text-sm text-slate-400">This takes about 30-45 seconds</p>
    </div>
  );
};

export default LoadingScreen;
