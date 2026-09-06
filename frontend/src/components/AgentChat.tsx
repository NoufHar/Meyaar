"use client";

import { useState } from "react";
import { useLanguage } from "@/components/LanguageProvider";
import { getAuthToken } from "@/lib/api";

interface AgentChatProps { runId: string; embedded?: boolean; }
interface ChatMessage { role: "user" | "assistant"; text: string; }

type SpeechRecognitionEventLike = { results: ArrayLike<{ 0: { transcript: string } }> };
type SpeechRecognitionLike = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: (() => void) | null;
  start: () => void;
};
type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

export default function AgentChat({ runId, embedded = false }: AgentChatProps) {
  const { language, t } = useLanguage();
  const [isOpen, setIsOpen] = useState(embedded);
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [downloadingAudio, setDownloadingAudio] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  function speechSegments(text: string) {
    const tokens = text.match(/[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]+|[A-Za-z]+|[^\u0600-\u06FFA-Za-z]+/g) ?? [text];
    const segments: Array<{ text: string; language: "ar" | "en" }> = [];
    let activeLanguage: "ar" | "en" = /[\u0600-\u06FF]/.test(text) ? "ar" : "en";

    for (const token of tokens) {
      const language = /[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]/.test(token)
        ? "ar"
        : /[A-Za-z]/.test(token)
          ? "en"
          : activeLanguage;
      const previous = segments.at(-1);
      if (previous?.language === language) previous.text += token;
      else segments.push({ text: token, language });
      activeLanguage = language;
    }

    return segments.filter((segment) => segment.text.trim());
  }

  function speak(text: string) {
    window.speechSynthesis.cancel();
    const voices = window.speechSynthesis.getVoices();

    for (const segment of speechSegments(text)) {
      const utterance = new SpeechSynthesisUtterance(segment.text);
      utterance.lang = segment.language === "ar" ? "ar-SA" : "en-US";
      utterance.rate = segment.language === "ar" ? 0.92 : 0.96;
      const matchingVoice = voices.find((voice) =>
        voice.lang.toLowerCase().startsWith(segment.language),
      );
      if (matchingVoice) utterance.voice = matchingVoice;
      window.speechSynthesis.speak(utterance);
    }
  }

  function listen() {
    const browserWindow = window as typeof window & {
      SpeechRecognition?: SpeechRecognitionConstructor;
      webkitSpeechRecognition?: SpeechRecognitionConstructor;
    };
    const Recognition = browserWindow.SpeechRecognition ?? browserWindow.webkitSpeechRecognition;
    if (!Recognition) {
      setError("Voice input is not supported by this browser.");
      return;
    }
    const recognition = new Recognition();
    recognition.lang = language === "ar" ? "ar-SA" : "en-US";
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.onresult = (event) => setQuestion(event.results[0][0].transcript);
    recognition.onerror = () => setError("Voice input could not be captured.");
    recognition.start();
  }

  function downloadExplanation(text: string, index: number) {
    const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `meyaar-agent-explanation-${index + 1}.txt`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  async function downloadAudio(text: string, index: number) {
    setError(null);
    setDownloadingAudio(index);
    try {
      const response = await fetch("/backend/voice/synthesize", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${getAuthToken() ?? ""}` },
        body: JSON.stringify({ text, voice: "lulwa" }),
      });
      if (!response.ok) {
        const responseText = await response.text();
        let message = responseText || "Audio download failed.";
        try {
          const body = JSON.parse(responseText) as { detail?: string };
          message = body.detail ?? message;
        } catch {
          // The server may return plain text for an unexpected internal error.
        }
        throw new Error(message);
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `meyaar-agent-explanation-${index + 1}.wav`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Audio download failed.");
    } finally {
      setDownloadingAudio(null);
    }
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const text = question.trim();
    if (!text || loading) return;
    setMessages((current) => [...current, { role: "user", text }]);
    setQuestion("");
    setError(null);
    setLoading(true);
    try {
      const response = await fetch(`/backend/api/validation/${runId}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${getAuthToken() ?? ""}` },
        body: JSON.stringify({ question: text }),
      });
      const body = await response.json() as { answer?: string; detail?: string };
      if (!response.ok) throw new Error(body.detail ?? "Agent request failed.");
      setMessages((current) => [...current, { role: "assistant", text: body.answer ?? "No answer returned." }]);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Agent request failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={embedded ? "w-full" : "fixed bottom-6 right-6 z-[3000] flex flex-col items-end gap-3 rtl:left-6 rtl:right-auto rtl:items-start"}>
    {isOpen && (
    <section className={`flex flex-col overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-xl ${embedded ? 'min-h-[620px] w-full' : 'max-h-[75vh] w-[min(420px,calc(100vw-2rem))]'}`}>
      <div className="border-b border-slate-200 px-6 py-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.18em] text-blue-600">{t("AI assistant")}</p>
            <h2 className="mt-2 text-xl font-bold">{t("Ask about this analysis")}</h2>
          </div>
          {!embedded && <button type="button" onClick={() => setIsOpen(false)} aria-label="Close assistant" className="rounded-full bg-slate-100 px-3 py-1.5 text-lg hover:bg-slate-200">×</button>}
        </div>
        <p className="mt-2 text-sm text-slate-500">{t("Answers are grounded in the current validation run. Voice input and playback use your browser.")}</p>
      </div>
      <div className={`${embedded ? 'min-h-0 flex-1' : 'max-h-80'} space-y-3 overflow-y-auto p-5`} aria-live="polite">
        {messages.length === 0 && <p className="rounded-xl bg-slate-50 p-4 text-sm text-slate-500">{t("Try: “Which errors should I fix first?”")}</p>}
        {messages.map((message, index) => (
          <div key={`${message.role}-${index}`} className={`rounded-2xl p-4 text-sm ${message.role === 'user' ? 'ml-12 bg-blue-600 text-white' : 'mr-12 bg-slate-100 text-slate-800'}`}>
            <p>{message.text}</p>
            {message.role === "assistant" && <div className="mt-3 flex flex-wrap gap-3 text-xs font-bold text-blue-700">
              <button type="button" onClick={() => speak(message.text)}>🔊 {t("Listen")}</button>
              <button type="button" onClick={() => downloadExplanation(message.text, index)}>↓ {t("Download explanation")}</button>
              <button type="button" disabled={downloadingAudio === index} onClick={() => downloadAudio(message.text, index)} className="disabled:opacity-50">↓ {downloadingAudio === index ? t("Preparing audio...") : t("Download audio")}</button>
            </div>}
          </div>
        ))}
      </div>
      <form onSubmit={submit} className="border-t border-slate-200 p-5">
        <div className="flex gap-2">
          <input value={question} onChange={(event) => setQuestion(event.target.value)} maxLength={2000} placeholder={t("Ask a question about the detected errors...")} className="min-w-0 flex-1 rounded-xl border border-slate-300 px-4 py-3 text-sm outline-none focus:border-blue-500" />
          <button type="button" onClick={listen} title="Voice input" className="rounded-xl border border-slate-300 px-4 hover:bg-slate-50">🎙️</button>
          <button type="submit" disabled={loading || !question.trim()} className="rounded-xl bg-blue-600 px-5 text-sm font-bold text-white disabled:bg-slate-400">{loading ? t("Asking...") : t("Send")}</button>
        </div>
        {error && <p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}
      </form>
    </section>
    )}

    {!embedded && <button
      type="button"
      onClick={() => setIsOpen((value) => !value)}
      aria-label={isOpen ? "Close AI assistant" : "Open AI assistant"}
      aria-expanded={isOpen}
      className="flex size-14 items-center justify-center rounded-full border border-blue-400 bg-blue-600 text-white shadow-[0_10px_30px_rgba(37,99,235,0.35)] ring-4 ring-white transition hover:scale-105 hover:bg-blue-700"
    >
      <svg
        viewBox="0 0 24 24"
        aria-hidden="true"
        className="size-7"
        fill="currentColor"
      >
        <path d="M12 3.25c-5.05 0-9 3.57-9 8.12 0 2.2.94 4.2 2.58 5.67l-.77 3.18a.45.45 0 0 0 .56.53l3.63-1.1c.95.28 1.96.42 3 .42 5.05 0 9-3.57 9-8.12S17.05 3.25 12 3.25Z" />
      </svg>
    </button>}
    </div>
  );
}
