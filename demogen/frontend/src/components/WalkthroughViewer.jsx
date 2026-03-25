import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import APIPanel from "./APIPanel";
import ExportPanel from "./ExportPanel";
import FAQPanel from "./FAQPanel";
import HighlightOverlay from "./HighlightOverlay";
import StepCard from "./StepCard";

const BACKEND_BASE = "http://localhost:8000";
const AUTO_PLAY_MS = 4200;
const LANGUAGE_CODES = {
  english: "en-US",
  hindi: "hi-IN",
  tamil: "ta-IN",
  kannada: "kn-IN",
};

const WalkthroughViewer = ({ intent, steps, faqs, onBack }) => {
  const [localizedSteps, setLocalizedSteps] = useState(steps);
  const [currentStep, setCurrentStep] = useState(0);
  const [selectedLanguage, setSelectedLanguage] = useState("english");
  const [activeTab, setActiveTab] = useState("narration");
  const [voiceOn, setVoiceOn] = useState(false);
  const [shareUrl, setShareUrl] = useState("");
  const [autoPlay, setAutoPlay] = useState(false);
  const [voices, setVoices] = useState([]);
  const [translationLoading, setTranslationLoading] = useState(false);
  const [translationError, setTranslationError] = useState("");

  const utteranceRef = useRef(null);
  const autoAdvanceTimeoutRef = useRef(null);

  useEffect(() => {
    setLocalizedSteps(steps);
  }, [steps]);

  useEffect(() => {
    const updateVoices = () => {
      setVoices(window.speechSynthesis?.getVoices?.() || []);
    };

    updateVoices();
    window.speechSynthesis?.addEventListener?.("voiceschanged", updateVoices);
    return () => {
      window.speechSynthesis?.removeEventListener?.("voiceschanged", updateVoices);
    };
  }, []);

  useEffect(() => {
    return () => {
      window.speechSynthesis.cancel();
      if (autoAdvanceTimeoutRef.current) {
        clearTimeout(autoAdvanceTimeoutRef.current);
      }
    };
  }, []);

  const step = localizedSteps[currentStep] || null;
  const stepHasTargetTranslation = !!step?.language_narrations?.[selectedLanguage]?.trim();

  const narration = useMemo(() => {
    if (!step) return "";
    return step.language_narrations?.[selectedLanguage] || step.language_narrations?.english || step.narration;
  }, [step, selectedLanguage]);

  const goToNextStep = useCallback(() => {
    setCurrentStep((value) => {
      if (value >= localizedSteps.length - 1) {
        setAutoPlay(false);
        return value;
      }
      return value + 1;
    });
  }, [localizedSteps.length]);

  const pickVoice = useCallback(
    (languageKey) => {
      if (!voices.length) {
        return null;
      }
      const targetCode = LANGUAGE_CODES[languageKey] || "en-US";
      const prefix = targetCode.split("-")[0].toLowerCase();
      return (
        voices.find((voice) => voice.lang?.toLowerCase() === targetCode.toLowerCase()) ||
        voices.find((voice) => voice.lang?.toLowerCase().startsWith(prefix)) ||
        voices.find((voice) => voice.lang?.toLowerCase().startsWith("en")) ||
        null
      );
    },
    [voices]
  );

  const ensureTranslation = useCallback(async (stepIndex, languageKey) => {
    if (languageKey === "english") {
      return;
    }

    const targetStep = localizedSteps[stepIndex];
    const existing = targetStep?.language_narrations?.[languageKey];
    const sourceText = targetStep?.language_narrations?.english || targetStep?.narration || "";
    if (!targetStep || existing?.trim() || !sourceText.trim()) {
      return;
    }

    try {
      setTranslationLoading(true);
      setTranslationError("");
      const response = await fetch(`${BACKEND_BASE}/translate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: sourceText, target_language: languageKey }),
      });
      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: "Unable to translate narration" }));
        throw new Error(err.detail || "Unable to translate narration");
      }
      const data = await response.json();
      setLocalizedSteps((current) =>
        current.map((item, index) =>
          index === stepIndex
            ? {
                ...item,
                language_narrations: {
                  ...(item.language_narrations || {}),
                  [languageKey]: data.translated_text || sourceText,
                },
              }
            : item
        )
      );
    } catch (error) {
      setTranslationError(error.message || "Unable to load translation right now.");
    } finally {
      setTranslationLoading(false);
    }
  }, [localizedSteps]);

  useEffect(() => {
    if (!step || selectedLanguage === "english") {
      return;
    }
    ensureTranslation(currentStep, selectedLanguage);
  }, [currentStep, ensureTranslation, selectedLanguage, step]);

  useEffect(() => {
    window.speechSynthesis.cancel();
    if (autoAdvanceTimeoutRef.current) {
      clearTimeout(autoAdvanceTimeoutRef.current);
      autoAdvanceTimeoutRef.current = null;
    }

    if (!narration) {
      return;
    }

    const shouldWaitForTranslation = selectedLanguage !== "english" && !stepHasTargetTranslation;
    if (shouldWaitForTranslation) {
      return;
    }

    if (voiceOn) {
      const utterance = new SpeechSynthesisUtterance(narration);
      utteranceRef.current = utterance;
      const targetLanguage = LANGUAGE_CODES[selectedLanguage] || "en-US";
      utterance.lang = targetLanguage;
      utterance.rate = 1;
      utterance.pitch = 1;
      const preferredVoice = pickVoice(selectedLanguage);
      if (preferredVoice) {
        utterance.voice = preferredVoice;
        utterance.lang = preferredVoice.lang || targetLanguage;
      }
      utterance.onend = () => {
        if (autoPlay) {
          goToNextStep();
        }
      };
      window.speechSynthesis.speak(utterance);
      return () => {
        utterance.onend = null;
        window.speechSynthesis.cancel();
      };
    }

    if (autoPlay) {
      autoAdvanceTimeoutRef.current = setTimeout(() => {
        goToNextStep();
      }, AUTO_PLAY_MS);
    }

    return () => {
      if (autoAdvanceTimeoutRef.current) {
        clearTimeout(autoAdvanceTimeoutRef.current);
        autoAdvanceTimeoutRef.current = null;
      }
    };
  }, [autoPlay, currentStep, goToNextStep, narration, pickVoice, selectedLanguage, stepHasTargetTranslation, voiceOn]);

  const nextStep = () => setCurrentStep((s) => Math.min(s + 1, localizedSteps.length - 1));
  const prevStep = () => setCurrentStep((s) => Math.max(s - 1, 0));
  const hasValidUrl = typeof step?.url === "string" && step.url.startsWith("http");

  const exportPDF = async () => {
    const res = await fetch(`${BACKEND_BASE}/export/pdf`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ steps: localizedSteps, intent }),
    });
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "demogen_export.pdf";
    a.click();
    window.URL.revokeObjectURL(url);
  };

  const createShareLink = async () => {
    const res = await fetch(`${BACKEND_BASE}/export/link`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ steps: localizedSteps, intent }),
    });
    const data = await res.json();
    setShareUrl(data.share_url);
  };

  if (!step) {
    return (
      <div className="p-8 text-slate-200">
        <p>No steps available.</p>
        <button className="mt-3 rounded-md border border-slate-600 px-3 py-2" onClick={onBack}>
          Back
        </button>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col bg-bg text-slate-100">
      <div className="flex items-center justify-between border-b border-slate-700 px-4 py-3">
        <button className="rounded-md border border-slate-600 px-3 py-2 text-sm" onClick={onBack}>
          Back
        </button>
        <p className="max-w-[75%] truncate text-sm text-slate-300">{intent}</p>
      </div>

      <div className="grid flex-1 grid-cols-1 lg:grid-cols-[65%_35%]">
        <div className="relative border-b border-slate-700 lg:border-b-0 lg:border-r">
          <img src={`${BACKEND_BASE}${step.screenshot_url}`} alt={step.page_title} className="h-full w-full object-contain bg-[#060b13]" />
          <HighlightOverlay highlight={step.highlight} elementDescription={step.element_description} animated={autoPlay} />
        </div>

        <div className="flex flex-col gap-4 p-4">
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm text-tealSoft">
              Step {currentStep + 1} of {localizedSteps.length}
            </p>
            <button
              className={`rounded-full border px-3 py-1 text-xs ${autoPlay ? "border-teal bg-teal text-[#07231f]" : "border-slate-600"}`}
              onClick={() => setAutoPlay((value) => !value)}
            >
              {autoPlay ? "Pause Demo" : "Play Demo"}
            </button>
          </div>

          <p className="text-lg leading-relaxed text-slate-100">{narration}</p>

          <div className="flex flex-wrap gap-2">
            {["english", "hindi", "tamil", "kannada"].map((lang) => (
              <button
                key={lang}
                className={`rounded-full border px-3 py-1 text-xs capitalize ${
                  selectedLanguage === lang ? "border-teal bg-teal text-[#04201c]" : "border-slate-600"
                }`}
                onClick={() => setSelectedLanguage(lang)}
              >
                {lang}
              </button>
            ))}
          </div>

          {(translationLoading || translationError) && (
            <div className="rounded-lg border border-slate-700 bg-[#0f1724] px-3 py-2 text-xs text-slate-300">
              {translationLoading ? `Translating this step into ${selectedLanguage}...` : translationError}
            </div>
          )}

          <div className="flex gap-2">
            <button
              className={`rounded-md px-3 py-2 text-sm ${activeTab === "narration" ? "bg-teal text-[#07231f]" : "bg-[#132235]"}`}
              onClick={() => setActiveTab("narration")}
            >
              Narration
            </button>
            <button
              className={`rounded-md px-3 py-2 text-sm ${activeTab === "api" ? "bg-teal text-[#07231f]" : "bg-[#132235]"}`}
              onClick={() => setActiveTab("api")}
            >
              API & Code
            </button>
          </div>

          {activeTab === "narration" ? (
            <div className="rounded-xl border border-slate-700 bg-[#0f1827] p-4 text-sm text-slate-300">
              <p className="font-medium text-slate-100">{step.page_title}</p>
              <p className="mt-2">{narration}</p>
              {hasValidUrl ? (
                <a href={step.url} target="_blank" rel="noreferrer" className="mt-3 inline-block text-xs text-tealSoft underline">
                  {step.url}
                </a>
              ) : (
                <p className="mt-3 text-xs text-slate-500">Live capture mode: URL omitted to avoid showing incorrect links.</p>
              )}
            </div>
          ) : (
            <APIPanel apiCall={step.api_call} codeSnippet={step.code_snippet} />
          )}

          <ExportPanel onExportPDF={exportPDF} onCreateLink={createShareLink} shareUrl={shareUrl} />
        </div>
      </div>

      <div className="border-t border-slate-700 px-4 py-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <button className="rounded-md border border-slate-600 px-3 py-2 text-sm" onClick={prevStep} disabled={currentStep === 0}>
            Previous
          </button>

          <div className="flex items-center gap-2">
            {localizedSteps.map((_, idx) => (
              <button
                key={`dot-${idx}`}
                className={`h-3 w-3 rounded-full border ${
                  idx < currentStep
                    ? "border-teal bg-teal"
                    : idx === currentStep
                    ? "animate-pulse border-teal bg-teal/50"
                    : "border-slate-500"
                }`}
                onClick={() => setCurrentStep(idx)}
              />
            ))}
          </div>

          <div className="flex items-center gap-2">
            <button
              className={`rounded-md border px-3 py-2 text-sm ${voiceOn ? "border-teal bg-teal/10" : "border-slate-600"}`}
              onClick={() => setVoiceOn((v) => !v)}
            >
              {voiceOn ? "Voice On" : "Voice Off"}
            </button>
            <button
              className="rounded-md border border-slate-600 px-3 py-2 text-sm"
              onClick={nextStep}
              disabled={currentStep === localizedSteps.length - 1}
            >
              Next
            </button>
          </div>
        </div>

        <div className="mt-4 flex gap-3 overflow-x-auto pb-2">
          {localizedSteps.map((s, idx) => (
            <StepCard
              key={`${s.step_number}-${idx}`}
              step={s}
              index={idx}
              selected={idx === currentStep}
              onClick={() => setCurrentStep(idx)}
              backendBase={BACKEND_BASE}
            />
          ))}
        </div>

        <FAQPanel faqs={faqs} />
      </div>
    </div>
  );
};

export default WalkthroughViewer;
