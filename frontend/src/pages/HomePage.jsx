import {useEffect,useState} from "react";
import {FileText,MapPinned,Upload} from "lucide-react";
import {api} from "../api";

export default function HomePage({user,setPage,onOpen}){
  const [analyses,setAnalyses]=useState([]);

  useEffect(()=>{
    api.get("/analyses")
      .then(({data})=>setAnalyses(data))
      .catch(()=>setAnalyses([]));
  },[]);

  return (
    <div className="page">
      <section className="welcome-banner">
        <div>
          <span className="eyebrow">MEYAAR WORKSPACE</span>
          <h1>Welcome, {user?.name?.split(" ")[0]}</h1>
          <p>From geospatial data to trusted results.</p>
        </div>
      </section>

      <div className="quick-grid">
        <button className="action-card" onClick={()=>setPage("inspection")}>
          <Upload/>
          <strong>New Inspection</strong>
          <span>Inspect Vector data or Map Images</span>
        </button>

        <button className="action-card" onClick={()=>setPage("workspace")}>
          <MapPinned/>
          <strong>Workspace</strong>
          <span>Review current findings</span>
        </button>

        <button className="action-card" onClick={()=>setPage("reports")}>
          <FileText/>
          <strong>Reports</strong>
          <span>Access inspection outputs</span>
        </button>
      </div>

      <section className="panel history-panel">
        <div className="section-title">
          <h2>Recent Analyses</h2>
        </div>

        {!analyses.length ? (
          <div className="empty-state">No analyses yet.</div>
        ):(
          <div className="history-list">
            {analyses.slice(0,8).map(item=>(
              <button
                key={item.id}
                className="history-row"
                onClick={()=>onOpen(item.id)}
              >
                <div>
                  <strong>{item.filename}</strong>
                  <span>
                    {item.input_type} · {item.layer_type||"Map Image"}
                  </span>
                </div>

                <strong>{item.total_findings} findings</strong>
              </button>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}