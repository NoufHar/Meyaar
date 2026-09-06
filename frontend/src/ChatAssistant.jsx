import { useMemo, useState } from "react";
import {
  Bot,
  Send,
  User,
  Sparkles,
  AlertTriangle,
  MapPinned,
  Image as ImageIcon,
  ShieldCheck,
} from "lucide-react";

function ChatAssistant({
  result,
  analyses = [],
  visionResult,
  qualityScore,
}) {
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      text:
        "Hi, I’m Meyaar Assistant. I can explain the current vector validation and map-image results.",
    },
  ]);

  const [input, setInput] = useState("");

  const visionElements = visionResult?.elements || [];
  const visionIssues = visionResult?.issues || [];

  const suggestedPrompts = useMemo(
    () => [
      "Summarize the current analysis",
      "What errors were detected?",
      "What should I fix?",
      "What is the quality score?",
      "Summarize the vision results",
    ],
    []
  );

  function normalize(text) {
    return String(text || "")
      .toLowerCase()
      .trim();
  }

  function getDatasetSummary() {
    if (!result) {
      return "No vector dataset has been analyzed yet.";
    }

    const dataset =
      result?.filename || "Unknown dataset";

    const layer =
      result?.layer_name || "Unknown layer";

    const features =
      result?.insertion?.inserted_rows ?? "Unknown";

    const geometry =
      result?.insertion?.geometry_types?.join(", ") ||
      "Unknown";

    const crs =
      result?.insertion?.crs || "Unknown";

    const errors =
      result?.validation?.total_errors ??
      analyses.length;

    const score =
      qualityScore !== "—"
        ? `${qualityScore}%`
        : "not available";

    return (
      `The current dataset is ${dataset}. ` +
      `Layer: ${layer}. ` +
      `Features: ${features}. ` +
      `Geometry: ${geometry}. ` +
      `CRS: ${crs}. ` +
      `Detected errors: ${errors}. ` +
      `Quality Score: ${score}.`
    );
  }

  function getErrorsSummary() {
    if (!result) {
      return (
        "Analyze a vector dataset first so I can " +
        "explain its validation results."
      );
    }

    if (analyses.length === 0) {
      return (
        "No analyzed validation findings were " +
        "returned for the current dataset."
      );
    }

    return analyses
      .map((item, index) => {
        const related =
          item.related_features?.length > 0
            ? ` Related features: ${item.related_features.join(
                ", "
              )}.`
            : "";

        return (
          `${index + 1}. ${item.rule_id || "Rule"} — ` +
          `${item.error_type || "Detected issue"} on feature ` +
          `${item.feature_id || "unknown"}. ` +
          `Severity: ${item.severity || "unknown"}.` +
          related
        );
      })
      .join("\n");
  }

  function getRecommendations() {
    if (!result) {
      return "There is no vector analysis available yet.";
    }

    if (analyses.length === 0) {
      return (
        "There are currently no analyzed findings " +
        "that require a recommendation."
      );
    }

    return analyses
      .map(
        (item, index) =>
          `${index + 1}. ${item.rule_id || "Finding"} — ` +
          `${
            item.recommendation ||
            "No recommendation was returned."
          }`
      )
      .join("\n");
  }

  function getCauses() {
    if (!result) {
      return "There is no vector analysis available yet.";
    }

    if (analyses.length === 0) {
      return "No analyzed findings are available.";
    }

    return analyses
      .map(
        (item, index) =>
          `${index + 1}. ${item.rule_id || "Finding"} — ` +
          `${item.cause || "No cause was returned."}`
      )
      .join("\n");
  }

  function getVisionSummary() {
    if (!visionResult) {
      return (
        "No map image has been analyzed yet. " +
        "Open Map Image and run the Vision analysis first."
      );
    }

    if (visionElements.length === 0) {
      return (
        "The Vision analysis did not return " +
        "element results."
      );
    }

    const elementText = visionElements
      .map((item) => {
        const name = String(
          item.element || "element"
        )
          .replaceAll("_", " ")
          .replace(/\b\w/g, (c) =>
            c.toUpperCase()
          );

        return `${name}: ${
          item.present ? "Present" : "Missing"
        }`;
      })
      .join(", ");

    if (visionIssues.length === 0) {
      return (
        `${elementText}. ` +
        "No missing cartographic elements were detected " +
        "within the current Vision scope."
      );
    }

    const issuesText = visionIssues
      .map((issue) =>
        String(
          issue.error_type || "Vision issue"
        ).replaceAll("_", " ")
      )
      .join(", ");

    return (
      `${elementText}. ` +
      `Detected Vision findings: ${issuesText}.`
    );
  }

  function getHighestSeverity() {
    if (analyses.length === 0) {
      return "No analyzed errors are available.";
    }

    const priority = {
      critical: 4,
      high: 3,
      medium: 2,
      low: 1,
    };

    const sorted = [...analyses].sort(
      (a, b) =>
        (priority[
          String(b.severity || "").toLowerCase()
        ] || 0) -
        (priority[
          String(a.severity || "").toLowerCase()
        ] || 0)
    );

    const top = sorted[0];

    return (
      `The highest-priority finding is ` +
      `${top.rule_id || "the detected issue"} ` +
      `on feature ${top.feature_id || "unknown"}, ` +
      `with severity ${top.severity || "unknown"}. ` +
      `${
        top.recommendation
          ? `Recommendation: ${top.recommendation}`
          : ""
      }`
    );
  }

  function getQualityScore() {
    if (!result) {
      return (
        "Analyze a vector dataset first to calculate " +
        "the current Quality Score."
      );
    }

    return (
      `The current demo Quality Score is ${
        qualityScore !== "—"
          ? `${qualityScore}%`
          : "not available"
      }. ` +
      "This is a simple MVP quality indicator based on " +
      "detected errors versus feature count. It is not " +
      "an official GeoSA compliance score."
    );
  }

  function getFeatureCount() {
    if (!result) {
      return "No vector dataset has been analyzed yet.";
    }

    const count =
      result?.insertion?.inserted_rows;

    if (count === undefined || count === null) {
      return "The feature count is not available.";
    }

    return `The current dataset contains ${count} features.`;
  }

  function getCRS() {
    if (!result) {
      return "No vector dataset has been analyzed yet.";
    }

    return `The current dataset CRS is ${
      result?.insertion?.crs || "unknown"
    }.`;
  }

  function generateAnswer(question) {
    const q = normalize(question);

    if (
      q.includes("summary") ||
      q.includes("summarize") ||
      q.includes("ملخص") ||
      q.includes("لخص")
    ) {
      if (
        q.includes("vision") ||
        q.includes("image") ||
        q.includes("صورة")
      ) {
        return getVisionSummary();
      }

      return (
        `${getDatasetSummary()}\n\n` +
        `${getErrorsSummary()}`
      );
    }

    if (
      q.includes("error") ||
      q.includes("errors") ||
      q.includes("issue") ||
      q.includes("اخطاء") ||
      q.includes("أخطاء") ||
      q.includes("خطأ")
    ) {
      return getErrorsSummary();
    }

    if (
      q.includes("fix") ||
      q.includes("recommend") ||
      q.includes("recommendation") ||
      q.includes("اصلح") ||
      q.includes("أصلح") ||
      q.includes("توصية") ||
      q.includes("التوصيات")
    ) {
      return getRecommendations();
    }

    if (
      q.includes("cause") ||
      q.includes("reason") ||
      q.includes("سبب") ||
      q.includes("ليش")
    ) {
      return getCauses();
    }

    if (
      q.includes("highest") ||
      q.includes("priority") ||
      q.includes("important") ||
      q.includes("اهم") ||
      q.includes("أهم") ||
      q.includes("اخطر") ||
      q.includes("أخطر")
    ) {
      return getHighestSeverity();
    }

    if (
      q.includes("quality") ||
      q.includes("score") ||
      q.includes("جودة")
    ) {
      return getQualityScore();
    }

    if (
      q.includes("feature") ||
      q.includes("features") ||
      q.includes("عدد العناصر")
    ) {
      return getFeatureCount();
    }

    if (
      q.includes("crs") ||
      q.includes("coordinate") ||
      q.includes("نظام الاحداثيات") ||
      q.includes("نظام الإحداثيات") ||
      q.includes("الإحداثيات")
    ) {
      return getCRS();
    }

    if (
      q.includes("dataset") ||
      q.includes("layer") ||
      q.includes("بيانات") ||
      q.includes("طبقة")
    ) {
      return getDatasetSummary();
    }

    if (
      q.includes("vision") ||
      q.includes("image") ||
      q.includes("title") ||
      q.includes("legend") ||
      q.includes("scale") ||
      q.includes("north arrow") ||
      q.includes("صورة") ||
      q.includes("خريطة")
    ) {
      return getVisionSummary();
    }

    if (
      q.includes("what can you do") ||
      q.includes("help") ||
      q.includes("وش تسوي") ||
      q.includes("وش تقدر")
    ) {
      return (
        "I can explain the current Meyaar results, including:\n" +
        "• Dataset information\n" +
        "• Detected vector errors\n" +
        "• Error causes and recommendations\n" +
        "• Quality Score\n" +
        "• Feature count and CRS\n" +
        "• Map-image Vision findings\n\n" +
        "I only use results already produced by Meyaar " +
        "and do not invent spatial findings."
      );
    }

    return (
      "I can currently answer questions about the analysis " +
      "already produced by Meyaar. Try asking: " +
      "“What errors were detected?”, “What should I fix?”, " +
      "“What is the quality score?”, or " +
      "“Summarize the vision results.”"
    );
  }

  function sendMessage(text = input) {
    const question =
      String(text || "").trim();

    if (!question) {
      return;
    }

    const answer =
      generateAnswer(question);

    setMessages((previous) => [
      ...previous,
      {
        role: "user",
        text: question,
      },
      {
        role: "assistant",
        text: answer,
      },
    ]);

    setInput("");
  }

  function handleKeyDown(event) {
    if (
      event.key === "Enter" &&
      !event.shiftKey
    ) {
      event.preventDefault();
      sendMessage();
    }
  }

  return (
    <section className="content">
      <div className="intro-row">
        <div>
          <h3>
            Ask Meyaar about your results
          </h3>

          <p>
            The assistant explains the validation
            and Vision results already produced
            in this session.
          </p>
        </div>

        <div className="formats">
          Vector · Vision · Analysis
        </div>
      </div>

      <section className="chat-layout">
        <div className="chat-main panel">
          <div className="chat-header">
            <div className="chat-bot-avatar">
              <Bot size={24} />
            </div>

            <div>
              <h4>Meyaar Assistant</h4>

              <span>
                Context-aware result assistant
              </span>
            </div>

            <div className="chat-online">
              <span></span>
              Ready
            </div>
          </div>

          <div className="chat-messages">
            {messages.map(
              (message, index) => (
                <div
                  key={index}
                  className={`chat-message-row ${message.role}`}
                >
                  <div className="chat-message-avatar">
                    {message.role ===
                    "assistant" ? (
                      <Bot size={18} />
                    ) : (
                      <User size={18} />
                    )}
                  </div>

                  <div className="chat-message-content">
                    <span className="chat-message-name">
                      {message.role ===
                      "assistant"
                        ? "Meyaar"
                        : "You"}
                    </span>

                    <div className="chat-bubble">
                      {message.text
                        .split("\n")
                        .map(
                          (
                            line,
                            lineIndex
                          ) => (
                            <p
                              key={
                                lineIndex
                              }
                            >
                              {line ||
                                "\u00A0"}
                            </p>
                          )
                        )}
                    </div>
                  </div>
                </div>
              )
            )}
          </div>

          <div className="chat-input-area">
            <textarea
              value={input}
              onChange={(event) =>
                setInput(
                  event.target.value
                )
              }
              onKeyDown={
                handleKeyDown
              }
              placeholder="Ask about the current Meyaar analysis..."
              rows={1}
            />

            <button
              className="chat-send-button"
              onClick={() =>
                sendMessage()
              }
              disabled={!input.trim()}
            >
              <Send size={19} />
            </button>
          </div>
        </div>

        <div className="chat-side-column">
          <div className="panel chat-context-card">
            <div className="chat-side-title">
              <Sparkles size={19} />

              <div>
                <span className="panel-kicker">
                  CURRENT CONTEXT
                </span>

                <h4>
                  Available Results
                </h4>
              </div>
            </div>

            <div className="chat-context-list">
              <ContextStatus
                icon={
                  <MapPinned
                    size={18}
                  />
                }
                title="Vector Analysis"
                available={Boolean(
                  result
                )}
                text={
                  result
                    ? `${
                        result?.insertion
                          ?.inserted_rows ??
                        0
                      } features · ${
                        result?.validation
                          ?.total_errors ??
                        0
                      } errors`
                    : "No dataset analyzed"
                }
              />

              <ContextStatus
                icon={
                  <AlertTriangle
                    size={18}
                  />
                }
                title="Agent Analysis"
                available={
                  analyses.length > 0
                }
                text={
                  analyses.length > 0
                    ? `${analyses.length} analyzed finding(s)`
                    : "No analyzed findings"
                }
              />

              <ContextStatus
                icon={
                  <ImageIcon
                    size={18}
                  />
                }
                title="Vision Analysis"
                available={Boolean(
                  visionResult
                )}
                text={
                  visionResult
                    ? `${visionElements.filter(
                        (item) =>
                          item.present
                      ).length}/${
                        visionElements.length
                      } elements present`
                    : "No image analyzed"
                }
              />
            </div>
          </div>

          <div className="panel chat-suggestions-card">
            <span className="panel-kicker">
              SUGGESTED QUESTIONS
            </span>

            <h4>Try asking</h4>

            <div className="chat-suggestion-list">
              {suggestedPrompts.map(
                (prompt) => (
                  <button
                    key={prompt}
                    onClick={() =>
                      sendMessage(
                        prompt
                      )
                    }
                  >
                    {prompt}
                  </button>
                )
              )}
            </div>
          </div>

          <div className="chat-truth-note">
            <ShieldCheck size={18} />

            <p>
              Meyaar Assistant explains existing
              results. Spatial detection remains
              the responsibility of the
              deterministic validation engine.
            </p>
          </div>
        </div>
      </section>
    </section>
  );
}

function ContextStatus({
  icon,
  title,
  text,
  available,
}) {
  return (
    <div className="chat-context-item">
      <div
        className={`chat-context-icon ${
          available
            ? "available"
            : "unavailable"
        }`}
      >
        {icon}
      </div>

      <div>
        <strong>{title}</strong>
        <span>{text}</span>
      </div>

      <span
        className={`chat-context-dot ${
          available
            ? "available"
            : ""
        }`}
      ></span>
    </div>
  );
}

export default ChatAssistant;