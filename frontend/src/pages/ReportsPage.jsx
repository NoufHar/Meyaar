import {Download,FileText,Mail,Volume2} from "lucide-react";
import {api} from "../api";

export default function ReportsPage({analysis}){
  async function download(type){
    if(!analysis?.analysis_id&&!analysis?.id){
      return alert("No saved analysis selected.");
    }

    const id=analysis.analysis_id||analysis.id;

    try{
      const response=await api.get(`/analyses/${id}/${type}`,{
        responseType:"blob",
      });

      const url=URL.createObjectURL(response.data);
      const link=document.createElement("a");

      link.href=url;
      link.download=type==="report"
        ? `${analysis.filename}_report.pdf`
        : `${analysis.filename}_summary.mp3`;

      link.click();
      URL.revokeObjectURL(url);
    }catch{
      alert(`${type} is not available.`);
    }
  }

  return (
    <div className="page">
      <header className="page-header">
        <span className="eyebrow">REPORTING</span>
        <h1>Inspection Report</h1>
        <p>Quality evidence and generated analysis outputs.</p>
      </header>

      {!analysis ? (
        <div className="empty-state">Select or run an analysis first.</div>
      ):(
        <div className="report-grid">
          <div className="panel report-main">
            <FileText size={34}/>
            <h2>{analysis.filename}</h2>
            <p>{analysis.findings?.length??analysis.total_findings??0} findings</p>

            <button
              className="button primary"
              onClick={()=>download("report")}
            >
              <Download size={17}/>
              Download PDF
            </button>
          </div>

          <div className="panel report-action" onClick={()=>download("audio")}>
            <Volume2/>
            <div>
              <strong>Arabic Audio Summary</strong>
              <span>Download MP3 summary</span>
            </div>
          </div>

          <div className="panel report-action">
            <Mail/>
            <div>
              <strong>Email Delivery</strong>
              <span>
                {analysis.email_status==="failed"
                  ?"Email delivery failed"
                  :"Report and audio sent to your email"}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}