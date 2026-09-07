import {useState} from "react";

export default function FindingsList({findings=[]}){
  const [selected,setSelected]=useState(null);

  return (
    <div className="findings-panel">
      <h3>Findings ({findings.length})</h3>

      <div className="findings-list">
        {findings.map((item,index)=>(
          <button
            key={item.finding_id||index}
            className="finding-row"
            onClick={()=>setSelected(item)}
          >
            <span className={`severity-dot ${item.severity?.toLowerCase()}`}/>
            <div>
              <strong>{item.rule_id||item.error_type||"Finding"}</strong>
              <span>{item.error_type?.replaceAll("_"," ")}</span>
            </div>
            <span className={`badge ${item.severity?.toLowerCase()}`}>
              {item.severity||"—"}
            </span>
          </button>
        ))}
      </div>

      {selected&&(
        <div className="finding-detail">
          <h3>{selected.error_type}</h3>
          <p>{selected.message||selected.explanation}</p>

          {selected.feature_id&&(
            <div className="detail-row">
              <span>Feature</span>
              <strong>{selected.feature_id}</strong>
            </div>
          )}

          <div className="detail-row">
            <span>Severity</span>
            <strong>{selected.severity}</strong>
          </div>

          {selected.recommendation&&(
            <>
              <h4>Recommendation</h4>
              <p>{selected.recommendation}</p>
            </>
          )}
        </div>
      )}
    </div>
  );
}