import {useEffect} from "react";
import L from "leaflet";
import {GeoJSON,MapContainer,TileLayer,useMap} from "react-leaflet";

function FitBounds({data}){
  const map=useMap();

  useEffect(()=>{
    if(!data) return;

    const bounds=L.geoJSON(data).getBounds();
    if(bounds.isValid()){
      map.fitBounds(bounds,{padding:[25,25]});
    }
  },[data,map]);

  return null;
}

export default function MapPanel({data}){
  if(!data){
    return <div className="empty-state">Map preview is not available.</div>;
  }

  return (
    <MapContainer center={[24.7136,46.6753]} zoom={10} className="leaflet-map">
      <TileLayer
        attribution="&copy; OpenStreetMap"
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <GeoJSON data={data}/>
      <FitBounds data={data}/>
    </MapContainer>
  );
}