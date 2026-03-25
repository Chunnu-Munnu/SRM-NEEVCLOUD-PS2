const ExportPanel = ({ onExportPDF, onCreateLink, shareUrl }) => {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <button
        type="button"
        onClick={onExportPDF}
        className="rounded-md border border-slate-600 bg-[#101d2f] px-3 py-2 text-xs text-slate-100 hover:border-teal/60"
      >
        Export PDF
      </button>
      <button
        type="button"
        onClick={onCreateLink}
        className="rounded-md border border-teal/50 bg-teal/10 px-3 py-2 text-xs text-tealSoft hover:bg-teal/20"
      >
        Create Share Link
      </button>
      {shareUrl && (
        <a href={shareUrl} target="_blank" rel="noreferrer" className="text-xs text-tealSoft underline">
          Open shared demo
        </a>
      )}
    </div>
  );
};

export default ExportPanel;
