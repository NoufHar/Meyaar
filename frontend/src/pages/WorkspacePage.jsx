import MetricCard from "../components/MetricCard";
import FindingsList from "../components/FindingsList";
import MapPanel from "../components/MapPanel";

export default function WorkspacePage({analysis,setPage}){
  if(!analysis){
    return <div className="page empty-state">Start an inspection first.</div>;
  }

  const findings=analysis.findings||[];

  const count=severity=>
    findings.filter(
      item=>item.severity?.toLowerCase()===severity
    ).length;

  return (
    <div className="page">
      <header className="page-header row">
        <div>
          <span className="eyebrow">INSPECTION RESULTS</span>
          <h1>{analysis.filename}</h1>
          <p>
            {analysis.input_type==="vector"
              ? `${analysis.layer_type||"Vector"} dataset`
              : "Map Image"}
          </p>
        </div>

        <button
          className="button primary"
          onClick={()=>setPage("reports")}
        >
          View Report
        </button>
      </header>

      <div className="metrics">
        <MetricCard value={count("high")} label="High Severity" tone="high"/>
        <MetricCard value={count("medium")} label="Medium Severity" tone="medium"/>
        <MetricCard value={count("low")} label="Low Severity" tone="low"/>
        <MetricCard value={findings.length} label="Total Findings"/>
      </div>

      <section className="workspace-grid">
        <div className="map-panel">
          {analysis.input_type==="image" ? (
            analysis.preview
              ? <img className="inspection-image" src={analysis.preview}/>
              : <div className="empty-state">Image preview unavailable.</div>
          ):(
            <MapPanel data={analysis.visualization}/>
          )}
        </div>

        <FindingsList findings={findings}/>
      </section>
    </div>
  );
}