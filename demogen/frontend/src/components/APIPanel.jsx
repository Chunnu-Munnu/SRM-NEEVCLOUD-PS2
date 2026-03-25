const APIPanel = ({ apiCall, codeSnippet }) => {
  const copyCode = async () => {
    if (!codeSnippet) {
      return;
    }
    await navigator.clipboard.writeText(codeSnippet);
  };

  return (
    <div className="rounded-xl border border-slate-700 bg-[#0f1928] p-4">
      <h4 className="text-sm font-semibold text-slate-200">API Mapping</h4>
      <div className="mt-2 inline-flex rounded-full border border-teal/50 bg-teal/10 px-3 py-1 text-xs text-tealSoft">
        {apiCall || "No direct API call identified for this step"}
      </div>

      <div className="mt-4 flex items-center justify-between">
        <h5 className="text-sm font-semibold text-slate-200">Code Snippet</h5>
        <button
          type="button"
          onClick={copyCode}
          className="rounded-md border border-slate-600 px-3 py-1 text-xs text-slate-200 hover:border-teal/50"
        >
          Copy
        </button>
      </div>
      <pre className="mt-2 max-h-60 overflow-auto rounded-md bg-[#070d16] p-3 text-xs text-slate-200">
        <code>{codeSnippet || "No code snippet available for this step."}</code>
      </pre>
    </div>
  );
};

export default APIPanel;
