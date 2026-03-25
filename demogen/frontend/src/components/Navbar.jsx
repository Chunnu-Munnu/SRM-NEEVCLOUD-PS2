const Navbar = () => {
  return (
    <header className="border-b border-teal/20 bg-[#0a121d]/80 backdrop-blur-md">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="h-8 w-8 rounded-md border border-teal/60 bg-gradient-to-br from-teal/30 to-transparent" />
          <div>
            <h1 className="text-lg font-semibold text-tealSoft">DemoGen</h1>
            <p className="text-xs text-slate-300">AI-powered walkthrough builder</p>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Navbar;
