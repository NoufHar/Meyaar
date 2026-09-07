const steps=[
  ["1","Ingestion","Preparing data"],
  ["2","Validation","Running checks"],
  ["3","Analysis","Explaining findings"],
  ["4","Compliance","Checking standards"],
  ["5","Report","Preparing results"],
];

export default function InspectionProgress({filename}){
  return (
    <div className="page">
      <header className="page-header">
        <h1>Inspection in Progress</h1>
        <p>Meyaar is analyzing your data.</p>
      </header>

      <div className="progress-steps">
        {steps.map(([n,title,text],i)=>(
          <div
            key={title}
            className={`progress-step ${i<2?"done":i===2?"running":""}`}
          >
            <span>{i<2?"✓":n}</span>
            <strong>{title}</strong>
            <small>{text}</small>
          </div>
        ))}
      </div>

      <div className="panel progress-panel">
        <h3>Live Activity</h3>
        <p>✓ File uploaded successfully</p>
        <p>✓ Detecting input type</p>
        <p>✓ Preparing {filename}</p>
        <p className="active-line">● Running validation...</p>
      </div>
    </div>
  );
}