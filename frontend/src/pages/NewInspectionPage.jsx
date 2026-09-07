import {useState} from "react";
import {Upload} from "lucide-react";
import {api} from "../api";
import InspectionProgress from "../components/InspectionProgress";

const imageExtensions=["png","jpg","jpeg","tif","tiff"];

export default function NewInspectionPage({onComplete}){
  const [file,setFile]=useState(null);
  const [layerType,setLayerType]=useState("");
  const [loading,setLoading]=useState(false);

  async function inspect(){
    if(!file) return alert("Choose a file first.");

    const form=new FormData();
    form.append("file",file);
    if(layerType) form.append("layer_type",layerType);

    try{
      setLoading(true);

      const ext=file.name.split(".").pop().toLowerCase();
      const preview=imageExtensions.includes(ext)
        ? URL.createObjectURL(file)
        : null;

      const {data}=await api.post("/inspect",form);

      onComplete({...data,preview});
    }catch(error){
      alert(error.response?.data?.detail||"Inspection failed.");
    }finally{
      setLoading(false);
    }
  }

  if(loading){
    return <InspectionProgress filename={file?.name}/>;
  }

  return (
    <div className="page">
      <header className="page-header">
        <span className="eyebrow">NEW INSPECTION</span>
        <h1>Upload Your Data</h1>
        <p>
          Upload Vector data or a Map Image.
          Meyaar will automatically route it to the correct validation pipeline.
        </p>
      </header>

      <label className="upload-zone">
        <Upload size={42}/>
        <strong>{file?.name||"Choose a geospatial file"}</strong>
        <span>GeoJSON, Shapefile, GPKG, CSV, PNG or JPG</span>

        <input
          hidden
          type="file"
          accept=".geojson,.json,.gpkg,.csv,.parquet,.zip,.png,.jpg,.jpeg,.tif,.tiff"
          onChange={e=>setFile(e.target.files?.[0]||null)}
        />
      </label>

      <div className="field">
        <label>Vector layer type</label>
        <select value={layerType} onChange={e=>setLayerType(e.target.value)}>
          <option value="">Auto Detect</option>
          <option value="buildings">Buildings</option>
          <option value="roads">Roads</option>
        </select>
      </div>

      <button className="button primary inspect-button" onClick={inspect}>
        Start Inspection
      </button>
    </div>
  );
}