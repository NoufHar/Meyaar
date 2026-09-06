import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import ChatAssistant from "./ChatAssistant";
import {
  MapContainer,
  TileLayer,
  GeoJSON,
  CircleMarker,
  Popup,
  useMap,
} from "react-leaflet";
import {
  Upload,
  MapPinned,
  FileText,
  Image as ImageIcon,
  MessageSquare,
  AlertTriangle,
  ShieldCheck,
  CheckCircle2,
  XCircle,
  ScanSearch,
  Send,
  Download,
  Database,
  FileCheck2,
  Clock3,
} from "lucide-react";
import "./App.css";

const API_URL = "http://127.0.0.1:8000";

function MapResizeFix({ trigger }) {
  const map = useMap();

  useEffect(() => {
    const fixMap = () => {
      setTimeout(() => {
        map.invalidateSize(true);
      }, 100);
    };

    fixMap();

    window.addEventListener("resize", fixMap);

    return () => {
      window.removeEventListener("resize", fixMap);
    };
  }, [map, trigger]);

  return null;
}

function App() {
  const [activeTab, setActiveTab] = useState("vector");

  // =========================================================
  // VECTOR STATE
  // =========================================================
  const [file, setFile] = useState(null);
  const [layerType, setLayerType] = useState("buildings");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [selectedError, setSelectedError] = useState(null);

  // =========================================================
  // REPORT STATE
  // =========================================================
  const [reportLoading, setReportLoading] = useState(false);
  const [reportStatus, setReportStatus] = useState(null);
  const [reportGeneratedAt, setReportGeneratedAt] = useState(null);

  // =========================================================
  // VISION STATE
  // =========================================================
  const [imageFile, setImageFile] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);
  const [visionResult, setVisionResult] = useState(null);
  const [visionLoading, setVisionLoading] = useState(false);

  // =========================================================
  // VECTOR VALUES
  // =========================================================
  const analyses = result?.analysis?.analyses || [];
  const mapData = result?.map_data || null;

  const errorIds = useMemo(() => {
    const ids = new Set();

    analyses.forEach((item) => {
      if (item.feature_id) {
        ids.add(String(item.feature_id));
      }

      (item.related_features || []).forEach((id) => {
        ids.add(String(id));
      });
    });

    return ids;
  }, [analyses]);

  const totalErrors = result?.validation?.total_errors || 0;
  const totalFeatures = result?.insertion?.inserted_rows || 0;

  const highErrors = analyses.filter(
    (item) => item.severity?.toLowerCase() === "high"
  ).length;

  const mediumErrors = analyses.filter(
    (item) => item.severity?.toLowerCase() === "medium"
  ).length;

  const lowErrors = analyses.filter(
    (item) => item.severity?.toLowerCase() === "low"
  ).length;

  const qualityScore =
    totalFeatures > 0
      ? Math.max(
          0,
          (1 - totalErrors / totalFeatures) * 100
        ).toFixed(1)
      : "—";

  const firstLocation =
    analyses.find((item) => item.location)?.location;

  const mapCenter = firstLocation
    ? [firstLocation.lat, firstLocation.lon]
    : [24.7136, 46.6753];

  // =========================================================
  // VECTOR ANALYSIS
  // =========================================================
  async function handleAnalyze() {
    if (!file) {
      alert("Choose a dataset first.");
      return;
    }

    try {
      setLoading(true);
      setResult(null);
      setSelectedError(null);
      setReportStatus(null);
      setReportGeneratedAt(null);

      const formData = new FormData();

      formData.append("file", file);
      formData.append("layer_type", layerType);

      const response = await axios.post(
        `${API_URL}/vectors/process`,
        formData,
        {
          timeout: 300000,
        }
      );

      setResult(response.data);

      const firstError =
        response.data?.analysis?.analyses?.[0];

      if (firstError) {
        setSelectedError(firstError);
      }
    } catch (error) {
      console.error("Analysis error:", error);

      alert(
        error?.response?.data?.detail ||
          "Could not analyze the dataset. Make sure FastAPI is running."
      );
    } finally {
      setLoading(false);
    }
  }

  // =========================================================
  // REPORT
  // =========================================================
  async function handleGenerateReport() {
    if (!result) {
      alert("Analyze a vector dataset first.");
      return;
    }

    try {
      setReportLoading(true);
      setReportStatus("generating");

      const response = await axios.post(
        `${API_URL}/reports/generate`,
        {
          dataset: result.insertion,
          validation: result.validation,
        },
        {
          responseType: "blob",
          timeout: 300000,
        }
      );

      const contentType =
        response.headers["content-type"] || "";

      // لو الباكند رجع PDF مباشرة
      if (contentType.includes("application/pdf")) {
        const blob = new Blob([response.data], {
          type: "application/pdf",
        });

        const url =
          window.URL.createObjectURL(blob);

        const link =
          document.createElement("a");

        link.href = url;
        link.download =
          "Meyaar_Quality_Report.pdf";

        document.body.appendChild(link);

        link.click();

        link.remove();

        window.URL.revokeObjectURL(url);
      }

      setReportStatus("success");
      setReportGeneratedAt(
        new Date().toLocaleString()
      );
    } catch (error) {
      console.error("Report error:", error);

      setReportStatus("error");

      alert(
        "Could not generate the report. Check FastAPI terminal."
      );
    } finally {
      setReportLoading(false);
    }
  }

  // =========================================================
  // MAP HELPERS
  // =========================================================
  function getFeatureId(feature) {
    return String(
      feature?.properties?.feature_id ||
        feature?.properties?.id ||
        feature?.properties?.["@id"] ||
        ""
    );
  }

  function featureStyle(feature) {
    const id = getFeatureId(feature);

    const isError =
      errorIds.has(id);

    return {
      color: isError
        ? "#ef4444"
        : "#00bfa6",

      weight: isError
        ? 4
        : 2,

      fillColor: isError
        ? "#ef4444"
        : "#00bfa6",

      fillOpacity: isError
        ? 0.75
        : 0.35,
    };
  }

  // =========================================================
  // VISION
  // =========================================================
  function handleImageChange(event) {
    const selected =
      event.target.files?.[0];

    if (!selected) {
      return;
    }

    setImageFile(selected);
    setVisionResult(null);

    const previewUrl =
      URL.createObjectURL(selected);

    setImagePreview(previewUrl);
  }

  async function handleVisionAnalyze() {
    if (!imageFile) {
      alert("Choose a map image first.");
      return;
    }

    try {
      setVisionLoading(true);
      setVisionResult(null);

      const formData =
        new FormData();

      formData.append(
        "file",
        imageFile
      );

      const response =
        await axios.post(
          `${API_URL}/images/analyze`,
          formData,
          {
            timeout: 300000,
          }
        );

      console.log(
        "VISION RESULT:",
        response.data
      );

      setVisionResult(
        response.data
      );
    } catch (error) {
      console.error(
        "Vision error:",
        error
      );

      alert(
        error?.response?.data?.detail ||
          "Could not analyze the map image. Make sure FastAPI and Moondream are running."
      );
    } finally {
      setVisionLoading(false);
    }
  }

  // =========================================================
  // MAIN LAYOUT
  // =========================================================
  return (
    <div className="app-shell">
      <aside className="sidebar">

        <div className="brand">
          <div className="brand-mark">
            م
          </div>

          <div>
            <h1>Meyaar</h1>

            <span>
              Geospatial Quality & Compliance
            </span>
          </div>
        </div>

        <nav className="nav">

          <button
            className={`nav-item ${
              activeTab === "vector"
                ? "active"
                : ""
            }`}
            onClick={() =>
              setActiveTab("vector")
            }
          >
            <MapPinned size={19} />

            Vector Dataset
          </button>

          <button
            className={`nav-item ${
              activeTab === "image"
                ? "active"
                : ""
            }`}
            onClick={() =>
              setActiveTab("image")
            }
          >
            <ImageIcon size={19} />

            Map Image
          </button>

          <button
            className={`nav-item ${
              activeTab === "reports"
                ? "active"
                : ""
            }`}
            onClick={() =>
              setActiveTab("reports")
            }
          >
            <FileText size={19} />

            Reports
          </button>

          <button
  className={`nav-item ${
    activeTab === "chat"
      ? "active"
      : ""
  }`}
  onClick={() =>
    setActiveTab("chat")
  }
>
  <MessageSquare size={19} />

  Chat Assistant
</button>

        </nav>

        <div className="sidebar-footer">
          <ShieldCheck size={18} />

          <span>
            Meyaar MVP
          </span>
        </div>

      </aside>

      <main className="main">

  {activeTab === "vector" && (
    <>
      <PageHeader
        eyebrow="MEYAAR PLATFORM"
        title="Vector Dataset Analysis"
        status="System Ready"
      />

      <VectorPage
        file={file}
        setFile={setFile}
        layerType={layerType}
        setLayerType={setLayerType}
        loading={loading}
        handleAnalyze={handleAnalyze}
        result={result}
        totalErrors={totalErrors}
        highErrors={highErrors}
        mediumErrors={mediumErrors}
        lowErrors={lowErrors}
        qualityScore={qualityScore}
        mapCenter={mapCenter}
        firstLocation={firstLocation}
        mapData={mapData}
        featureStyle={featureStyle}
        analyses={analyses}
        selectedError={selectedError}
        setSelectedError={setSelectedError}
        reportLoading={reportLoading}
        handleGenerateReport={handleGenerateReport}
      />
    </>
  )}

  {activeTab === "image" && (
    <>
      <PageHeader
        eyebrow="MEYAAR VISION"
        title="Map Image Analysis"
        status="Vision Ready"
      />

      <VisionPage
        imageFile={imageFile}
        imagePreview={imagePreview}
        handleImageChange={handleImageChange}
        visionLoading={visionLoading}
        handleVisionAnalyze={handleVisionAnalyze}
        visionResult={visionResult}
      />
    </>
  )}

  {activeTab === "reports" && (
    <>
      <PageHeader
        eyebrow="MEYAAR REPORTING"
        title="Quality Reports"
        status="Reporting Ready"
      />

      <ReportsPage
        result={result}
        analyses={analyses}
        totalErrors={totalErrors}
        totalFeatures={totalFeatures}
        highErrors={highErrors}
        mediumErrors={mediumErrors}
        lowErrors={lowErrors}
        qualityScore={qualityScore}
        reportLoading={reportLoading}
        reportStatus={reportStatus}
        reportGeneratedAt={reportGeneratedAt}
        handleGenerateReport={handleGenerateReport}
        setActiveTab={setActiveTab}
      />
    </>
  )}

  {activeTab === "chat" && (
    <>
      <PageHeader
        eyebrow="MEYAAR ASSISTANT"
        title="Chat Assistant"
        status="Assistant Ready"
      />

      <ChatAssistant
        result={result}
        analyses={analyses}
        visionResult={visionResult}
        qualityScore={qualityScore}
      />
    </>
  )}

</main>
    </div>
  );
}

// =============================================================
// HEADER
// =============================================================
function PageHeader({
  eyebrow,
  title,
  status,
}) {
  return (
    <header className="topbar">
      <div>
        <span className="eyebrow">
          {eyebrow}
        </span>

        <h2>
          {title}
        </h2>
      </div>

      <div className="status-pill">
        <span className="status-dot">
        </span>

        {status}
      </div>
    </header>
  );
}

// =============================================================
// VECTOR PAGE
// =============================================================
function VectorPage({
  file,
  setFile,
  layerType,
  setLayerType,
  loading,
  handleAnalyze,
  result,
  totalErrors,
  highErrors,
  mediumErrors,
  lowErrors,
  qualityScore,
  mapCenter,
  firstLocation,
  mapData,
  featureStyle,
  analyses,
  selectedError,
  setSelectedError,
  reportLoading,
  handleGenerateReport,
}) {
  return (
    <section className="content">

      <div className="intro-row">
        <div>
          <h3>
            Validate your geospatial dataset
          </h3>

          <p>
            Upload a vector dataset and Meyaar
            will insert, validate, detect and
            analyze spatial quality issues.
          </p>
        </div>

        <div className="formats">
          GeoJSON · Shapefile · GPKG
        </div>
      </div>

      <section className="upload-card">

        <div className="upload-left">

          <div className="upload-icon">
            <Upload size={25} />
          </div>

          <div>
            <h4>
              Upload Dataset
            </h4>

            <p>
              {file
                ? file.name
                : "Choose a geospatial vector file"}
            </p>
          </div>

        </div>

        <div className="upload-controls">

          <select
            value={layerType}
            onChange={(e) =>
              setLayerType(
                e.target.value
              )
            }
          >
            <option value="buildings">
              Buildings
            </option>

            <option value="roads">
              Roads
            </option>
          </select>

          <label className="file-button">

            Choose File

            <input
              type="file"
              accept=".geojson,.json,.zip,.gpkg"
              onChange={(e) =>
                setFile(
                  e.target.files?.[0] ||
                    null
                )
              }
            />

          </label>

          <button
            className="analyze-button"
            onClick={handleAnalyze}
            disabled={loading}
          >
            {loading
              ? "Analyzing..."
              : "Analyze Dataset"}
          </button>

        </div>

      </section>

      <section className="dataset-strip">

        <div>
          <span>
            Dataset
          </span>

          <strong>
            {result?.filename ||
              "No dataset analyzed"}
          </strong>
        </div>

        <div>
          <span>
            Layer
          </span>

          <strong>
            {result?.layer_name ||
              "—"}
          </strong>
        </div>

        <div>
          <span>
            Features
          </span>

          <strong>
            {result?.insertion
              ?.inserted_rows
              ?.toLocaleString?.() ||
              "—"}
          </strong>
        </div>

        <div>
          <span>
            Geometry
          </span>

          <strong>
            {result?.insertion
              ?.geometry_types
              ?.join(", ") ||
              "—"}
          </strong>
        </div>

        <div>
          <span>
            CRS
          </span>

          <strong>
            {result?.insertion?.crs ||
              "—"}
          </strong>
        </div>

      </section>

      <section className="kpi-grid">

        <KpiCard
          title="Total Errors"
          value={totalErrors}
          icon={
            <AlertTriangle
              size={22}
            />
          }
        />

        <KpiCard
          title="High"
          value={highErrors}
          icon={
            <AlertTriangle
              size={22}
            />
          }
        />

        <KpiCard
          title="Medium"
          value={mediumErrors}
          icon={
            <AlertTriangle
              size={22}
            />
          }
        />

        <KpiCard
          title="Low"
          value={lowErrors}
          icon={
            <AlertTriangle
              size={22}
            />
          }
        />

        <KpiCard
          title="Quality Score"
          value={`${qualityScore}${
            qualityScore !== "—"
              ? "%"
              : ""
          }`}
          icon={
            <ShieldCheck
              size={22}
            />
          }
        />

      </section>

      <section className="workspace-grid">

        <div className="panel map-panel">

          <div className="panel-header">

            <div>
              <span className="panel-kicker">
                SPATIAL VIEW
              </span>

              <h4>
                Interactive Map
              </h4>
            </div>

            <div className="map-legend">

              <span>
                <i className="legend valid">
                </i>

                Valid
              </span>

              <span>
                <i className="legend error">
                </i>

                Error
              </span>

            </div>

          </div>

          <div className="map-wrapper">

            <MapContainer
              key={`${mapCenter[0]}-${mapCenter[1]}`}
              center={mapCenter}
              zoom={
                firstLocation
                  ? 18
                  : 11
              }
              scrollWheelZoom
              className="map"
            >

              <MapResizeFix
                trigger={
                  result?.run_id
                }
              />

              <TileLayer
                attribution="&copy; OpenStreetMap contributors"
                url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
              />

              {mapData && (
                <GeoJSON
                  key={
                    result?.run_id ||
                    "map"
                  }
                  data={mapData}
                  style={
                    featureStyle
                  }
                />
              )}

              {analyses
                .filter(
                  (item) =>
                    item.location
                )
                .map(
                  (item, index) => (
                    <CircleMarker
                      key={`${item.feature_id}-${index}`}
                      center={[
                        item.location.lat,
                        item.location.lon,
                      ]}
                      radius={8}
                      pathOptions={{
                        color:
                          "#ffffff",
                        weight: 2,
                        fillColor:
                          "#ef4444",
                        fillOpacity: 1,
                      }}
                    >
                      <Popup>
                        <strong>
                          {item.rule_id ||
                            "Detected Error"}
                        </strong>

                        <br />

                        {
                          item.feature_id
                        }
                      </Popup>
                    </CircleMarker>
                  )
                )}

            </MapContainer>

            {!result && (
              <div className="map-empty">

                <MapPinned
                  size={34}
                />

                <strong>
                  No analysis yet
                </strong>

                <span>
                  Upload a dataset
                  to visualize the
                  results.
                </span>

              </div>
            )}

          </div>

        </div>

        <div className="right-column">

          <div className="panel errors-panel">

            <div className="panel-header">

              <div>
                <span className="panel-kicker">
                  VALIDATION RESULTS
                </span>

                <h4>
                  Detected Errors
                </h4>
              </div>

              <span className="count-badge">
                {analyses.length}
              </span>

            </div>

            <div className="error-table">

              {analyses.length ===
              0 ? (
                <div className="empty-state">
                  No detected errors
                  yet.
                </div>
              ) : (
                analyses.map(
                  (item, index) => (
                    <button
                      className={`error-row ${
                        selectedError ===
                        item
                          ? "selected"
                          : ""
                      }`}
                      key={`${
                        item.result_id ||
                        item.feature_id
                      }-${index}`}
                      onClick={() =>
                        setSelectedError(
                          item
                        )
                      }
                    >

                      <div>
                        <strong>
                          {item.rule_id ||
                            "Rule"}
                        </strong>

                        <span>
                          {
                            item.feature_id
                          }
                        </span>
                      </div>

                      <span
                        className={`severity ${
                          item.severity?.toLowerCase() ||
                          "medium"
                        }`}
                      >
                        {item.severity ||
                          "Unknown"}
                      </span>

                    </button>
                  )
                )
              )}

            </div>

          </div>

          <div className="panel detail-panel">

            <div className="panel-header">

              <div>
                <span className="panel-kicker">
                  AGENT ANALYSIS
                </span>

                <h4>
                  Error Details
                </h4>
              </div>

            </div>

            {!selectedError ? (
              <div className="empty-state">
                Select an error to view
                its analysis.
              </div>
            ) : (
              <div className="detail-content">

                <div className="detail-title">

                  <AlertTriangle
                    size={20}
                  />

                  <div>
                    <strong>
                      {selectedError.rule_id ||
                        "Detected Issue"}
                    </strong>

                    <span>
                      {
                        selectedError.feature_id
                      }
                    </span>
                  </div>

                </div>

                <DetailBlock
                  title="Explanation"
                  text={
                    selectedError.explanation
                  }
                />

                <DetailBlock
                  title="Cause"
                  text={
                    selectedError.cause
                  }
                />

                <DetailBlock
                  title="Recommendation"
                  text={
                    selectedError.recommendation
                  }
                />

                <div className="detail-meta">

                  <span>
                    Status:
                    <strong>
                      {" "}
                      {selectedError.status ||
                        "confirmed"}
                    </strong>
                  </span>

                  <span>
                    Model:
                    <strong>
                      {" "}
                      {selectedError.agent_model ||
                        "—"}
                    </strong>
                  </span>

                </div>

              </div>
            )}

          </div>

          <button
            className="report-button"
            onClick={
              handleGenerateReport
            }
            disabled={
              !result ||
              reportLoading
            }
          >
            <FileText size={19} />

            {reportLoading
              ? "Generating Report..."
              : "Generate Quality Report"}
          </button>

        </div>

      </section>

    </section>
  );
}

// =============================================================
// VISION PAGE
// =============================================================
function VisionPage({
  imageFile,
  imagePreview,
  handleImageChange,
  visionLoading,
  handleVisionAnalyze,
  visionResult,
}) {
  const elements =
    visionResult?.elements || [];

  const issues =
    visionResult?.issues || [];

  const findElement =
    (name) =>
      elements.find(
        (item) =>
          String(item.element)
            .toLowerCase()
            .replaceAll(" ", "_") ===
          name
      );

  const titleElement =
    findElement("title");

  const legendElement =
    findElement("legend");

  const scaleElement =
    findElement("scale");

  const northArrowElement =
    findElement("north_arrow");

  return (
    <section className="content">

      <div className="intro-row">

        <div>
          <h3>
            Inspect cartographic map elements
          </h3>

          <p>
            Upload a map image and Meyaar
            Vision will inspect the presence
            of required map elements.
          </p>
        </div>

        <div className="formats">
          PNG · JPG · JPEG
        </div>

      </div>

      <section className="vision-layout">

        <div className="vision-left">

          <div className="panel vision-upload-panel">

            <div className="panel-header">

              <div>
                <span className="panel-kicker">
                  MAP INPUT
                </span>

                <h4>
                  Upload Map Image
                </h4>
              </div>

              <ScanSearch
                size={22}
              />

            </div>

            <label className="vision-dropzone">

              {imagePreview ? (
                <img
                  src={
                    imagePreview
                  }
                  alt="Map preview"
                  className="vision-preview"
                />
              ) : (
                <div className="vision-placeholder">

                  <ImageIcon
                    size={45}
                  />

                  <strong>
                    Choose a map
                    image
                  </strong>

                  <span>
                    JPG, JPEG or
                    PNG
                  </span>

                </div>
              )}

              <input
                type="file"
                accept=".png,.jpg,.jpeg,image/png,image/jpeg"
                onChange={
                  handleImageChange
                }
              />

            </label>

            {imageFile && (
              <div className="vision-file-name">

                <ImageIcon
                  size={17}
                />

                <span>
                  {imageFile.name}
                </span>

              </div>
            )}

            <button
              className="vision-analyze-button"
              onClick={
                handleVisionAnalyze
              }
              disabled={
                visionLoading ||
                !imageFile
              }
            >
              <ScanSearch
                size={19}
              />

              {visionLoading
                ? "Analyzing with Moondream..."
                : "Analyze Map Image"}
            </button>

          </div>

        </div>

        <div className="vision-right">

          <div className="panel">

            <div className="panel-header">

              <div>
                <span className="panel-kicker">
                  VISION RESULTS
                </span>

                <h4>
                  Cartographic Elements
                </h4>
              </div>

              {visionResult && (
                <span className="count-badge">
                  {
                    elements.filter(
                      (item) =>
                        item.present
                    ).length
                  }
                  /{elements.length}
                </span>
              )}

            </div>

            {!visionResult ? (
              <div className="vision-empty-state">

                <ScanSearch
                  size={34}
                />

                <strong>
                  No image analyzed
                  yet
                </strong>

                <span>
                  Meyaar currently
                  checks Title,
                  Legend, Scale and
                  North Arrow.
                </span>

              </div>
            ) : (
              <>

                <div className="vision-element-grid">

                  <VisionElementCard
                    title="Title"
                    item={
                      titleElement
                    }
                  />

                  <VisionElementCard
                    title="Legend"
                    item={
                      legendElement
                    }
                  />

                  <VisionElementCard
                    title="Scale"
                    item={
                      scaleElement
                    }
                  />

                  <VisionElementCard
                    title="North Arrow"
                    item={
                      northArrowElement
                    }
                  />

                </div>

                <div className="vision-findings">

                  <div className="vision-findings-header">

                    <div>
                      <span className="panel-kicker">
                        DETECTED FINDINGS
                      </span>

                      <h4>
                        Visual Quality Issues
                      </h4>
                    </div>

                    <span className="count-badge">
                      {issues.length}
                    </span>

                  </div>

                  {issues.length ===
                  0 ? (
                    <div className="vision-success">

                      <CheckCircle2
                        size={23}
                      />

                      <div>
                        <strong>
                          No missing
                          elements
                          detected
                        </strong>

                        <span>
                          All
                          cartographic
                          elements in
                          the current
                          Vision scope
                          were found.
                        </span>
                      </div>

                    </div>
                  ) : (
                    <div className="vision-issue-list">

                      {issues.map(
                        (
                          issue,
                          index
                        ) => (
                          <div
                            className="vision-issue"
                            key={`${issue.error_type}-${index}`}
                          >
                            <XCircle
                              size={20}
                            />

                            <div>
                              <strong>
                                {String(
                                  issue.error_type ||
                                    "Vision Issue"
                                )
                                  .replaceAll(
                                    "_",
                                    " "
                                  )
                                  .replace(
                                    /\b\w/g,
                                    (
                                      c
                                    ) =>
                                      c.toUpperCase()
                                  )}
                              </strong>

                              <span>
                                {issue.message ||
                                  "A required cartographic element was not detected."}
                              </span>
                            </div>

                          </div>
                        )
                      )}

                    </div>
                  )}

                </div>

              </>
            )}

          </div>

        </div>

      </section>

    </section>
  );
}

// =============================================================
// REPORTS PAGE
// =============================================================
function ReportsPage({
  result,
  analyses,
  totalErrors,
  totalFeatures,
  highErrors,
  mediumErrors,
  lowErrors,
  qualityScore,
  reportLoading,
  reportStatus,
  reportGeneratedAt,
  handleGenerateReport,
  setActiveTab,
}) {
  if (!result) {
    return (
      <section className="content">

        <div className="intro-row">
          <div>
            <h3>
              Quality assessment reports
            </h3>

            <p>
              Generate a PDF quality report
              from the latest vector
              validation run.
            </p>
          </div>
        </div>

        <div className="reports-empty">

          <div className="reports-empty-icon">
            <FileText
              size={34}
            />
          </div>

          <h3>
            No vector analysis available
          </h3>

          <p>
            Analyze a vector dataset first
            before generating the quality
            report.
          </p>

          <button
            className="report-primary-button"
            onClick={() =>
              setActiveTab("vector")
            }
          >
            <MapPinned
              size={18}
            />

            Go to Vector Dataset
          </button>

        </div>

      </section>
    );
  }

  return (
    <section className="content">

      <div className="intro-row">

        <div>
          <h3>
            Quality assessment report
          </h3>

          <p>
            Review the latest validation
            summary and generate the final
            Meyaar report.
          </p>
        </div>

        <div className="formats">
          PDF · Arabic Audio · Telegram
        </div>

      </div>

      <section className="report-summary-grid">

        <div className="report-summary-main">

          <div className="panel report-dataset-card">

            <div className="panel-header">

              <div>
                <span className="panel-kicker">
                  CURRENT DATASET
                </span>

                <h4>
                  Assessment Source
                </h4>
              </div>

              <Database
                size={22}
              />

            </div>

            <div className="report-dataset-info">

              <ReportInfoRow
                label="Dataset"
                value={
                  result?.filename ||
                  "—"
                }
              />

              <ReportInfoRow
                label="Layer"
                value={
                  result?.layer_name ||
                  "—"
                }
              />

              <ReportInfoRow
                label="Features"
                value={
                  totalFeatures
                    ?.toLocaleString?.() ||
                  "—"
                }
              />

              <ReportInfoRow
                label="Geometry"
                value={
                  result?.insertion
                    ?.geometry_types
                    ?.join(", ") ||
                  "—"
                }
              />

              <ReportInfoRow
                label="CRS"
                value={
                  result?.insertion
                    ?.crs ||
                  "—"
                }
              />

            </div>

          </div>

          <div className="panel report-findings-card">

            <div className="panel-header">

              <div>
                <span className="panel-kicker">
                  VALIDATION SUMMARY
                </span>

                <h4>
                  Detected Findings
                </h4>
              </div>

              <span className="count-badge">
                {totalErrors}
              </span>

            </div>

            {analyses.length === 0 ? (
              <div className="report-no-findings">

                <CheckCircle2
                  size={23}
                />

                <div>
                  <strong>
                    No analyzed findings
                  </strong>

                  <span>
                    No validation
                    findings were
                    returned for this
                    run.
                  </span>
                </div>

              </div>
            ) : (
              <div className="report-finding-list">

                {analyses.map(
                  (
                    item,
                    index
                  ) => (
                    <div
                      className="report-finding-row"
                      key={`${item.feature_id}-${index}`}
                    >

                      <div className="report-finding-left">

                        <AlertTriangle
                          size={18}
                        />

                        <div>
                          <strong>
                            {item.rule_id ||
                              "Finding"}
                          </strong>

                          <span>
                            {
                              item.feature_id
                            }
                          </span>
                        </div>

                      </div>

                      <span
                        className={`severity ${
                          item.severity?.toLowerCase() ||
                          "medium"
                        }`}
                      >
                        {item.severity ||
                          "Unknown"}
                      </span>

                    </div>
                  )
                )}

              </div>
            )}

          </div>

        </div>

        <div className="report-summary-side">

          <div className="panel report-score-card">

            <span className="panel-kicker">
              QUALITY SUMMARY
            </span>

            <div className="report-score-value">
              {qualityScore}
              {qualityScore !== "—"
                ? "%"
                : ""}
            </div>

            <span className="report-score-label">
              Quality Score
            </span>

            <div className="report-mini-stats">

              <ReportMiniStat
                label="High"
                value={highErrors}
              />

              <ReportMiniStat
                label="Medium"
                value={mediumErrors}
              />

              <ReportMiniStat
                label="Low"
                value={lowErrors}
              />

            </div>

          </div>

          <div className="panel report-action-card">

            <div className="report-action-icon">
              <FileCheck2
                size={28}
              />
            </div>

            <h4>
              Generate Meyaar Report
            </h4>

            <p>
              Creates the quality report
              from the latest validation
              result.
            </p>

            <div className="report-output-list">

              <div>
                <FileText
                  size={17}
                />

                PDF Quality Report
              </div>

              <div>
                <Download
                  size={17}
                />

                Arabic Audio Summary
              </div>

              <div>
                <Send
                  size={17}
                />

                Telegram Delivery
              </div>

            </div>

            <button
              className="report-primary-button"
              onClick={
                handleGenerateReport
              }
              disabled={
                reportLoading
              }
            >

              {reportLoading ? (
                <>
                  <Clock3
                    size={18}
                  />

                  Generating...
                </>
              ) : (
                <>
                  <Send
                    size={18}
                  />

                  Generate & Send Report
                </>
              )}

            </button>

            {reportStatus ===
              "success" && (
              <div className="report-status-success">

                <CheckCircle2
                  size={18}
                />

                <div>
                  <strong>
                    Report generated
                    successfully
                  </strong>

                  {reportGeneratedAt && (
                    <span>
                      {
                        reportGeneratedAt
                      }
                    </span>
                  )}
                </div>

              </div>
            )}

            {reportStatus ===
              "error" && (
              <div className="report-status-error">

                <XCircle
                  size={18}
                />

                <span>
                  Report generation
                  failed.
                </span>

              </div>
            )}

          </div>

        </div>

      </section>

    </section>
  );
}

// =============================================================
// SMALL COMPONENTS
// =============================================================
function VisionElementCard({
  title,
  item,
}) {
  const present =
    item?.present;

  return (
    <div
      className={`vision-element-card ${
        !item
          ? "unknown"
          : present
          ? "present"
          : "missing"
      }`}
    >

      <div className="vision-element-icon">

        {!item ? (
          <ScanSearch
            size={25}
          />
        ) : present ? (
          <CheckCircle2
            size={25}
          />
        ) : (
          <XCircle
            size={25}
          />
        )}

      </div>

      <div>
        <span>
          {title}
        </span>

        <strong>
          {!item
            ? "Unknown"
            : present
            ? "Present"
            : "Missing"}
        </strong>
      </div>

    </div>
  );
}

function KpiCard({
  title,
  value,
  icon,
}) {
  return (
    <div className="kpi-card">

      <div className="kpi-icon">
        {icon}
      </div>

      <div>
        <span>
          {title}
        </span>

        <strong>
          {value}
        </strong>
      </div>

    </div>
  );
}

function DetailBlock({
  title,
  text,
}) {
  return (
    <div className="detail-block">

      <span>
        {title}
      </span>

      <p>
        {text ||
          "No information available."}
      </p>

    </div>
  );
}

function ReportInfoRow({
  label,
  value,
}) {
  return (
    <div className="report-info-row">

      <span>
        {label}
      </span>

      <strong>
        {value}
      </strong>

    </div>
  );
}

function ReportMiniStat({
  label,
  value,
}) {
  return (
    <div className="report-mini-stat">

      <strong>
        {value}
      </strong>

      <span>
        {label}
      </span>

    </div>
  );
}

export default App;