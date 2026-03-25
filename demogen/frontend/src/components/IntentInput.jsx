import { useMemo } from "react";

const personaOptions = [
  {
    value: "new user",
    title: "New User",
    description: "Friendly, guided explanations\nfor first-time platform users",
  },
  {
    value: "developer",
    title: "Developer",
    description: "Technical walkthroughs with\nAPI and automation context",
  },
  {
    value: "enterprise admin",
    title: "Enterprise Admin",
    description: "Governance, billing, and\nteam access best practices",
  },
];

const languageOptions = ["english", "hindi", "tamil", "kannada"];

const IconShape = ({ selected }) => (
  <svg viewBox="0 0 100 100" className="h-8 w-8">
    <rect x="12" y="12" width="76" height="76" rx="16" className={selected ? "fill-teal/45" : "fill-slate-700"} />
    <circle cx="50" cy="50" r="18" className={selected ? "fill-tealSoft" : "fill-slate-300"} />
  </svg>
);

const IntentInput = ({
  intent,
  setIntent,
  persona,
  setPersona,
  language,
  setLanguage,
  onSubmit,
  onStartLiveCapture,
  onStopLiveCapture,
  onCaptureCurrentStep,
  onValidateCurrentStep,
  isLoading,
  isRecording,
  isValidating,
  captureCount,
  captureProgressLabel,
  captureSupported,
  plannedFlow,
  currentCaptureIndex,
  validationFeedback,
}) => {
  const canSubmit = useMemo(() => intent.trim().length > 6 && !isLoading, [intent, isLoading]);
  const safeStepIndex = plannedFlow.length ? Math.min(currentCaptureIndex, plannedFlow.length - 1) : 0;
  const currentPlan = plannedFlow[safeStepIndex] || null;

  return (
    <div className="grid-bg min-h-screen bg-bg px-4 py-8 text-slate-100">
      <div className="mx-auto max-w-5xl rounded-2xl border border-teal/25 bg-[#0a111b]/80 p-6 shadow-neon sm:p-10">
        <h1 className="text-center text-4xl font-semibold text-tealSoft">DemoGen</h1>
        <p className="mt-3 text-center text-lg text-slate-300">Turn intent into interactive demos - instantly</p>

        <div className="mt-8">
          <textarea
            className="h-40 w-full rounded-xl border border-teal/30 bg-[#0d1725] p-4 text-base text-slate-100 outline-none transition focus:border-teal focus:shadow-neon"
            placeholder={"Show me how to launch a GPU instance for ML training on NeevCloud\nCreate an API key and secure it for backend use\nWalk me through adding SSH keys and connecting to an instance"}
            value={intent}
            onChange={(e) => setIntent(e.target.value)}
          />
        </div>

        <div className="mt-7 grid gap-3 sm:grid-cols-3">
          {personaOptions.map((option) => {
            const selected = persona === option.value;
            return (
              <button
                type="button"
                key={option.value}
                onClick={() => setPersona(option.value)}
                className={`rounded-xl border p-4 text-left transition ${
                  selected ? "border-teal bg-teal/10" : "border-slate-700 bg-[#0e1a2a]/80 hover:border-teal/50"
                }`}
              >
                <div className="mb-3">
                  <IconShape selected={selected} />
                </div>
                <h3 className="font-semibold text-white">{option.title}</h3>
                <p className="mt-1 whitespace-pre-line text-sm text-slate-300">{option.description}</p>
              </button>
            );
          })}
        </div>

        <div className="mt-6 flex flex-wrap items-center gap-2">
          {languageOptions.map((lang) => (
            <button
              key={lang}
              type="button"
              onClick={() => setLanguage(lang)}
              className={`rounded-full border px-4 py-2 text-sm font-medium capitalize transition ${
                language === lang
                  ? "border-teal bg-teal text-[#05201b]"
                  : "border-slate-600 bg-[#112033] text-slate-200 hover:border-teal/60"
              }`}
            >
              {lang}
            </button>
          ))}
        </div>

        <div className="mt-8 grid gap-3 sm:grid-cols-2">
          <button
            type="button"
            onClick={onSubmit}
            disabled={!canSubmit || isRecording}
            className={`shimmer flex w-full items-center justify-center gap-3 rounded-xl px-5 py-4 text-base font-semibold text-white transition ${
              canSubmit && !isRecording ? "opacity-100" : "cursor-not-allowed opacity-50"
            }`}
          >
            {isLoading && <span className="h-5 w-5 animate-spin rounded-full border-2 border-white/35 border-t-white" />}
            Generate Demo
          </button>

          {!isRecording ? (
            <button
              type="button"
              onClick={onStartLiveCapture}
              disabled={!canSubmit || !captureSupported || isLoading}
              className={`rounded-xl border px-5 py-4 text-base font-semibold transition ${
                canSubmit && captureSupported && !isLoading
                  ? "border-teal bg-[#102332] text-tealSoft hover:bg-[#143046]"
                  : "cursor-not-allowed border-slate-700 bg-[#0f1724] text-slate-500"
              }`}
            >
              Start Recording
            </button>
          ) : (
            <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
              <button
                type="button"
                onClick={onCaptureCurrentStep}
                className="rounded-xl border border-teal bg-[#102332] px-4 py-4 text-sm font-semibold text-tealSoft transition hover:bg-[#143046]"
              >
                Capture Extra Moment
              </button>
              <button
                type="button"
                onClick={onStopLiveCapture}
                disabled={isLoading}
                className="rounded-xl border border-red-400/50 bg-red-900/20 px-4 py-4 text-sm font-semibold text-red-100 transition hover:bg-red-900/35"
              >
                Finish Recording
              </button>
            </div>
          )}
        </div>

        <div className="mt-6 grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="rounded-xl border border-slate-700 bg-[#0d1725] p-4 text-sm text-slate-300">
            <p className="font-medium text-slate-100">Whole-Session Capture Mode</p>
            <p className="mt-1">
              DemoGen now records the full NeevCloud flow in the background, then reviews the entire session afterward to choose the most relevant moments for the final walkthrough.
            </p>
            <p className="mt-2 text-xs text-slate-400">
              {isRecording
                ? `Recording is active. ${captureProgressLabel || `${captureCount} moments recorded`}`
                : captureSupported
                ? "Your browser supports tab/window sharing."
                : "This browser does not support screen capture APIs."}
            </p>
          </div>

          <div className="rounded-xl border border-slate-700 bg-[#0d1725] p-4 text-sm text-slate-300">
            <p className="font-medium text-slate-100">Planned NeevCloud Flow</p>
            {currentPlan ? (
              <div className="mt-2">
                <p className="text-xs uppercase tracking-[0.18em] text-tealSoft">
                  Likely focus around step {safeStepIndex + 1} of {plannedFlow.length}
                </p>
                <p className="mt-2 text-base font-semibold text-white">{currentPlan.action || "Follow the next planned step"}</p>
                <p className="mt-2 text-sm text-slate-300">
                  {currentPlan.step_purpose || "Navigate naturally through the NeevCloud flow. DemoGen will select the best parts afterward."}
                </p>
              </div>
            ) : (
              <p className="mt-2 text-sm text-slate-400">Start recording to generate the planned NeevCloud journey.</p>
            )}
          </div>
        </div>

        {validationFeedback && (
          <div className="mt-6 rounded-xl border border-teal/30 bg-[#0f1724] p-4 text-sm text-slate-200">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="font-medium text-tealSoft">Recording Status</p>
              <span className="rounded-full border border-white/15 px-3 py-1 text-xs">{captureCount} moments stored</span>
            </div>
            <p className="mt-2">{validationFeedback.message}</p>
            {validationFeedback.recommended_action && <p className="mt-2 text-xs text-slate-300">Next: {validationFeedback.recommended_action}</p>}
          </div>
        )}

        {plannedFlow.length > 0 && (
          <div className="mt-6 rounded-xl border border-slate-700 bg-[#0d1725] p-4">
            <p className="text-sm font-medium text-slate-100">Planned Flow</p>
            <div className="mt-3 grid gap-2">
              {plannedFlow.map((step, idx) => {
                const isCurrent = idx === safeStepIndex;
                return (
                  <div
                    key={`${step.url || step.action || "step"}-${idx}`}
                    className={`rounded-lg border px-4 py-3 text-sm ${
                      isCurrent ? "border-teal bg-teal/10" : "border-slate-700 bg-[#0f1724]"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <p className="font-medium text-white">{idx + 1}. {step.action || "Planned step"}</p>
                      <span className="text-xs text-slate-400">Planned</span>
                    </div>
                    <p className="mt-1 text-slate-300">{step.step_purpose || "DemoGen will map recorded moments to this part of the NeevCloud flow."}</p>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default IntentInput;
