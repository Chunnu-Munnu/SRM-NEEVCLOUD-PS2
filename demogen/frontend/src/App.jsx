import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import IntentInput from "./components/IntentInput";
import LoadingScreen from "./components/LoadingScreen";
import Navbar from "./components/Navbar";
import WalkthroughViewer from "./components/WalkthroughViewer";

const BACKEND_URL = "http://localhost:8000";
const AUTO_CAPTURE_INTERVAL_MS = 2500;
const MAX_RAW_CAPTURES = 24;

const loadingMessages = [
  "Understanding your intent...",
  "Planning navigation flow...",
  "Reviewing your full recording...",
  "Choosing the most relevant moments...",
  "Generating AI narration...",
  "Building your walkthrough...",
];

function App() {
  const [intent, setIntent] = useState("");
  const [persona, setPersona] = useState("developer");
  const [language, setLanguage] = useState("english");
  const [steps, setSteps] = useState([]);
  const [faqs, setFaqs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState(loadingMessages[0]);
  const [currentView, setCurrentView] = useState("input");
  const [error, setError] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [captureCount, setCaptureCount] = useState(0);
  const [plannedFlow, setPlannedFlow] = useState([]);
  const [currentCaptureIndex, setCurrentCaptureIndex] = useState(0);
  const [validationFeedback, setValidationFeedback] = useState(null);
  const [isValidating, setIsValidating] = useState(false);

  const messageIndex = useRef(0);
  const captureStreamRef = useRef(null);
  const captureVideoRef = useRef(null);
  const capturedFilesRef = useRef([]);
  const captureSequenceRef = useRef(0);
  const lastCaptureSignatureRef = useRef(null);

  const captureSupported =
    typeof navigator !== "undefined" && !!navigator.mediaDevices && !!navigator.mediaDevices.getDisplayMedia;

  useEffect(() => {
    if (!loading) {
      return undefined;
    }
    const timer = setInterval(() => {
      messageIndex.current = (messageIndex.current + 1) % loadingMessages.length;
      setLoadingMessage(loadingMessages[messageIndex.current]);
    }, 3000);
    return () => clearInterval(timer);
  }, [loading]);

  useEffect(() => {
    return () => {
      if (captureStreamRef.current) {
        captureStreamRef.current.getTracks().forEach((track) => track.stop());
      }
    };
  }, []);

  const beginLoading = () => {
    setError("");
    setLoading(true);
    setCurrentView("loading");
    messageIndex.current = 0;
    setLoadingMessage(loadingMessages[0]);
  };

  const finishWithResponse = async (response) => {
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: "Unexpected server error" }));
      throw new Error(err.detail || "Generation failed");
    }

    const data = await response.json();
    setSteps(data.steps || []);
    setFaqs(data.faqs || []);
    setCurrentView("walkthrough");
  };

  const generateDemo = async () => {
    try {
      beginLoading();
      const response = await fetch(`${BACKEND_URL}/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ intent, persona, language }),
      });
      await finishWithResponse(response);
    } catch (e) {
      setError(e.message || "Something went wrong while generating your demo.");
      setCurrentView("input");
    } finally {
      setLoading(false);
    }
  };

  const makeFrameSignature = (canvas) => {
    const thumb = document.createElement("canvas");
    const width = 24;
    const height = 16;
    thumb.width = width;
    thumb.height = height;
    const thumbCtx = thumb.getContext("2d");
    if (!thumbCtx) {
      return "";
    }
    thumbCtx.drawImage(canvas, 0, 0, width, height);
    const pixels = thumbCtx.getImageData(0, 0, width, height).data;
    const values = [];
    for (let i = 0; i < pixels.length; i += 16) {
      const gray = Math.round((pixels[i] + pixels[i + 1] + pixels[i + 2]) / 3);
      values.push(gray.toString(16).padStart(2, "0"));
    }
    return values.join("");
  };

  const signatureDistance = (a, b) => {
    if (!a || !b || a.length !== b.length) {
      return 999;
    }
    let diff = 0;
    let samples = 0;
    for (let index = 0; index < a.length; index += 2) {
      const first = parseInt(a.slice(index, index + 2), 16);
      const second = parseInt(b.slice(index, index + 2), 16);
      diff += Math.abs(first - second);
      samples += 1;
    }
    return samples ? diff / samples : 999;
  };

  const buildFrameSnapshot = async () => {
    const video = captureVideoRef.current;
    if (!video || video.videoWidth === 0 || video.videoHeight === 0) {
      throw new Error("Shared tab is not ready yet. Wait a second and try again.");
    }

    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const context = canvas.getContext("2d");
    if (!context) {
      throw new Error("Unable to access capture canvas.");
    }
    context.drawImage(video, 0, 0, canvas.width, canvas.height);

    const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
    if (!blob) {
      throw new Error("Failed to capture frame.");
    }

    const sequence = captureSequenceRef.current + 1;
    return {
      file: new File([blob], `${String(sequence).padStart(2, "0")}_recording_moment.png`, {
        type: "image/png",
      }),
      signature: makeFrameSignature(canvas),
    };
  };

  const recordSnapshot = useCallback(async (manual = false) => {
    if (!captureVideoRef.current || capturedFilesRef.current.length >= MAX_RAW_CAPTURES) {
      return;
    }

    const snapshot = await buildFrameSnapshot();
    const isDistinctEnough = manual || signatureDistance(snapshot.signature, lastCaptureSignatureRef.current) > 7;
    if (!isDistinctEnough) {
      return;
    }

    captureSequenceRef.current += 1;
    capturedFilesRef.current = [...capturedFilesRef.current, snapshot.file];
    lastCaptureSignatureRef.current = snapshot.signature;
    setCaptureCount(capturedFilesRef.current.length);
    if (plannedFlow.length) {
      const progress = Math.min(
        Math.round(((capturedFilesRef.current.length - 1) / Math.max(MAX_RAW_CAPTURES - 1, 1)) * Math.max(plannedFlow.length - 1, 0)),
        Math.max(plannedFlow.length - 1, 0)
      );
      setCurrentCaptureIndex(progress);
    }
    setValidationFeedback({
      step_number: capturedFilesRef.current.length,
      is_match: true,
      should_capture: true,
      confidence: 90,
      message: manual
        ? "Captured this moment manually. DemoGen will later review the whole recording and choose the most relevant steps."
        : "Recorded a distinct moment from your live flow. Keep navigating through NeevCloud.",
      recommended_action: "Continue naturally. DemoGen will decide the best final steps after you stop recording.",
      observed_elements: [],
    });
  }, [plannedFlow.length]);

  const stopCaptureTracks = useCallback(() => {
    if (captureStreamRef.current) {
      captureStreamRef.current.getTracks().forEach((track) => track.stop());
      captureStreamRef.current = null;
    }
    captureVideoRef.current = null;
    setIsRecording(false);
  }, []);

  const uploadCapturedFrames = useCallback(async () => {
    if (!capturedFilesRef.current.length) {
      throw new Error("No moments were recorded yet.");
    }

    beginLoading();
    const formData = new FormData();
    formData.append("intent", intent);
    formData.append("persona", persona);
    formData.append("language", language);
    capturedFilesRef.current.forEach((file) => formData.append("captures", file));

    const response = await fetch(`${BACKEND_URL}/generate/live-capture`, {
      method: "POST",
      body: formData,
    });
    await finishWithResponse(response);
  }, [intent, persona, language]);

  const stopLiveCapture = useCallback(async () => {
    try {
      stopCaptureTracks();
      await uploadCapturedFrames();
    } catch (e) {
      setError(e.message || "Failed to process your recording.");
      setCurrentView("input");
    } finally {
      setLoading(false);
      setPlannedFlow([]);
      setCurrentCaptureIndex(0);
      setValidationFeedback(null);
      setIsValidating(false);
    }
  }, [stopCaptureTracks, uploadCapturedFrames]);

  const startLiveCapture = async () => {
    if (!captureSupported) {
      setError("This browser does not support live tab capture.");
      return;
    }
    if (intent.trim().length <= 6) {
      setError("Add a clear prompt first, then start recording.");
      return;
    }

    try {
      setError("");
      capturedFilesRef.current = [];
      captureSequenceRef.current = 0;
      lastCaptureSignatureRef.current = null;
      setCaptureCount(0);
      setCurrentCaptureIndex(0);

      const planResponse = await fetch(`${BACKEND_URL}/plan-flow`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ intent, persona, language }),
      });
      if (!planResponse.ok) {
        const err = await planResponse.json().catch(() => ({ detail: "Unable to plan flow" }));
        throw new Error(err.detail || "Unable to plan flow");
      }
      const planData = await planResponse.json();
      setPlannedFlow((planData.steps || []).filter(Boolean));

      const stream = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: false });
      const video = document.createElement("video");
      video.srcObject = stream;
      video.muted = true;
      video.playsInline = true;

      await new Promise((resolve) => {
        video.onloadedmetadata = resolve;
      });
      await video.play();

      captureStreamRef.current = stream;
      captureVideoRef.current = video;
      setIsRecording(true);
      setValidationFeedback({
        step_number: 1,
        is_match: true,
        should_capture: true,
        confidence: 100,
        message: "Recording started. Just navigate through NeevCloud normally and DemoGen will capture the full flow in the background.",
        recommended_action: "When you're done, click Finish and DemoGen will choose the most relevant moments for the final demo.",
        observed_elements: [],
      });

      const [track] = stream.getVideoTracks();
      if (track) {
        track.addEventListener(
          "ended",
          () => {
            stopCaptureTracks();
          },
          { once: true }
        );
      }
    } catch (e) {
      setError(e.message || "Unable to start recording.");
      stopCaptureTracks();
      setPlannedFlow([]);
    }
  };

  const validateCurrentStep = async () => {
    setValidationFeedback({
      step_number: captureCount,
      is_match: true,
      should_capture: true,
      confidence: 100,
      message: "DemoGen is now using whole-session recording mode. It will decide what is relevant after you stop recording.",
      recommended_action: "Keep navigating, then press Finish when you’ve completed the NeevCloud flow.",
      observed_elements: [],
    });
  };

  const captureCurrentStep = async () => {
    try {
      await recordSnapshot(true);
    } catch (e) {
      setError(e.message || "Failed to capture the current moment.");
    }
  };

  useEffect(() => {
    if (!isRecording) {
      return undefined;
    }

    const timer = setInterval(() => {
      recordSnapshot(false).catch(() => {});
    }, AUTO_CAPTURE_INTERVAL_MS);

    return () => clearInterval(timer);
  }, [isRecording, recordSnapshot]);

  const retry = () => {
    setError("");
    setCurrentView("input");
  };

  const captureProgressLabel = useMemo(() => {
    if (!plannedFlow.length) {
      return `${captureCount} recorded moments`;
    }
    return `${captureCount} recorded moments across a ${plannedFlow.length}-step planned flow`;
  }, [captureCount, plannedFlow.length]);

  return (
    <div className="min-h-screen bg-bg">
      {currentView !== "loading" && <Navbar />}

      {currentView === "input" && (
        <div>
          <IntentInput
            intent={intent}
            setIntent={setIntent}
            persona={persona}
            setPersona={setPersona}
            language={language}
            setLanguage={setLanguage}
            onSubmit={generateDemo}
            onStartLiveCapture={startLiveCapture}
            onStopLiveCapture={stopLiveCapture}
            onCaptureCurrentStep={captureCurrentStep}
            onValidateCurrentStep={validateCurrentStep}
            isLoading={loading}
            isRecording={isRecording}
            isValidating={isValidating}
            captureCount={captureCount}
            captureProgressLabel={captureProgressLabel}
            captureSupported={captureSupported}
            plannedFlow={plannedFlow}
            currentCaptureIndex={currentCaptureIndex}
            validationFeedback={validationFeedback}
          />
          {error && (
            <div className="mx-auto -mt-6 max-w-4xl rounded-xl border border-red-400/50 bg-red-900/20 p-4 text-sm text-red-200">
              <p>{error}</p>
              <button className="mt-2 rounded-md border border-red-300/50 px-3 py-2" onClick={retry}>
                Retry
              </button>
            </div>
          )}
        </div>
      )}

      {currentView === "loading" && <LoadingScreen message={loadingMessage} />}

      {currentView === "walkthrough" && (
        <WalkthroughViewer intent={intent} steps={steps} faqs={faqs} onBack={() => setCurrentView("input")} />
      )}
    </div>
  );
}

export default App;
