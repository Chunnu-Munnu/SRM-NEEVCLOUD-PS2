const StepCard = ({ step, index, selected, onClick, backendBase }) => {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`min-w-[190px] rounded-lg border p-2 text-left transition ${
        selected ? "border-teal bg-teal/10" : "border-slate-700 bg-[#0f1a2a] hover:border-teal/40"
      }`}
    >
      <img
        src={`${backendBase}${step.screenshot_url}`}
        alt={`Step ${index + 1}`}
        className="h-24 w-full rounded-md object-cover"
      />
      <p className="mt-2 text-xs text-slate-300">Step {index + 1}</p>
      <p className="line-clamp-2 text-xs text-slate-400">{step.page_title}</p>
    </button>
  );
};

export default StepCard;
