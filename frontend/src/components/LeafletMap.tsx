"use client";

import { useEffect, useMemo, useState } from "react";

import { geoJSON, popup } from "leaflet";
import type {
  FeatureCollection,
  GeoJsonProperties,
  Geometry,
} from "geojson";
import {
  GeoJSON,
  MapContainer,
  TileLayer,
  useMap,
  useMapEvents,
} from "react-leaflet";

import type {
  ValidationError,
} from "@/types/analysis";


interface LeafletMapProps {
  errors: ValidationError[];
  selectedErrorId: string | null;
  layerData?: FeatureCollection;
  showLayer: boolean;
  showErrors: boolean;
  resetKey: number;
}


interface ErrorProperties {
  resultId: string;
  featureId: string;
  errorType: string;
  severity: string;
  details: string;
}


function colorForSeverity(severity: string) {
  const colors: Record<string, string> = {
    critical: "#991b1b",
    high: "#dc2626",
    medium: "#f59e0b",
    low: "#2563eb",
    warning: "#f59e0b",
  };

  return colors[severity.toLowerCase()] ?? "#7c3aed";
}


function escapeHtml(value: string) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}


function FitToErrors({
  data,
  resetKey,
}: {
  data: FeatureCollection;
  resetKey: number;
}) {
  const map = useMap();

  useEffect(() => {
    if (data.features.length === 0) {
      return;
    }

    const bounds = geoJSON(data).getBounds();

    if (bounds.isValid()) {
      map.fitBounds(bounds.pad(0.15));
    }
  }, [data, map, resetKey]);

  return null;
}


function ZoomTracker({
  onZoomChange,
}: {
  onZoomChange: (zoom: number) => void;
}) {
  const map = useMapEvents({
    zoom: () => onZoomChange(map.getZoom()),
    zoomend: () => onZoomChange(map.getZoom()),
  });

  useEffect(() => {
    onZoomChange(map.getZoom());
  }, [map, onZoomChange]);

  return null;
}


function FocusSelectedError({
  data,
  selectedErrorId,
}: {
  data: FeatureCollection<Geometry, ErrorProperties>;
  selectedErrorId: string | null;
}) {
  const map = useMap();

  useEffect(() => {
    if (!selectedErrorId) {
      return;
    }

    const feature = data.features.find(
      (item) =>
        item.properties.resultId ===
        selectedErrorId,
    );

    if (!feature) {
      return;
    }

    const bounds = geoJSON(feature).getBounds();

    if (!bounds.isValid()) {
      return;
    }

    const properties = feature.properties;
    const target = bounds.getCenter();
    const popupContent = `
        <div style="min-width: 220px">
          <strong>${escapeHtml(properties.errorType)}</strong>
          <p><b>Feature:</b> ${escapeHtml(properties.featureId)}</p>
          <p><b>Severity:</b> ${escapeHtml(properties.severity)}</p>
          <p>${escapeHtml(properties.details)}</p>
        </div>
      `;

    map.closePopup();

    // Three cinematic stages: city, neighborhood, then the exact error.
    map.flyTo(target, 9, {
      animate: true,
      duration: 1,
    });

    const neighborhoodTimer = window.setTimeout(() => {
      map.flyTo(target, 13, {
        animate: true,
        duration: 3,
      });
    }, 1000);

    const errorTimer = window.setTimeout(() => {
      map.flyTo(target, 17, {
        animate: true,
        duration: 3,
      });
    }, 4000);

    const popupTimer = window.setTimeout(() => {
      popup({ maxWidth: 320 })
        .setLatLng(target)
        .setContent(popupContent)
        .openOn(map);
    }, 7000);

    return () => {
      window.clearTimeout(neighborhoodTimer);
      window.clearTimeout(errorTimer);
      window.clearTimeout(popupTimer);
    };
  }, [data, map, selectedErrorId]);

  return null;
}


export default function LeafletMap({
  errors,
  selectedErrorId,
  layerData,
  showLayer,
  showErrors,
  resetKey,
}: LeafletMapProps) {
  const [currentZoom, setCurrentZoom] = useState(6);
  const data = useMemo<FeatureCollection<
    Geometry,
    ErrorProperties
  >>(() => ({
    type: "FeatureCollection",
    features: errors
      .filter(
        (error) => error.geometry != null,
      )
      .map((error) => ({
        type: "Feature",
        geometry: error.geometry as Geometry,
        properties: {
          resultId: String(error.result_id),
          featureId: error.feature_id,
          errorType: error.error_type,
          severity: error.severity,
          details: error.details,
        },
      })),
  }), [errors]);

  return (
    <MapContainer
      center={[24.7136, 46.6753]}
      zoom={6}
      scrollWheelZoom
      className="h-full min-h-[420px] w-full"
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      <ZoomTracker onZoomChange={setCurrentZoom} />

      {showLayer && currentZoom >= 11 && layerData && layerData.features.length > 0 && (
        <GeoJSON
          key={`layer-${JSON.stringify(layerData).length}`}
          data={layerData}
          style={{
            color: "#64748b",
            fillColor: "#cbd5e1",
            weight: 0.8,
            opacity: 0.35,
            fillOpacity: 0.06,
          }}
        />
      )}

      {showErrors && data.features.length > 0 && (
        <GeoJSON
          key={`errors-outline-v4-${selectedErrorId ?? "none"}-${currentZoom}-${data.features.length}`}
          data={data}
          style={(feature) => {
            const isSelected =
              selectedErrorId != null &&
              String(
                feature?.properties?.resultId,
              ) === selectedErrorId;

            const color = colorForSeverity(
              String(
                feature?.properties?.severity ??
                  "unknown",
              ),
            );
            const isArriving = currentZoom >= 16;

            return {
              fill: false,
              color: isSelected ? "#dc2626" : color,
              weight: isSelected
                ? isArriving
                  ? 4
                  : 1.5
                : 2,
              opacity: !isArriving
                ? 0
                : isSelected
                  ? 0.72
                  : 0.24,
              dashArray: isSelected ? undefined : "4 6",
            };
          }}
          onEachFeature={(feature, layer) => {
            const properties = (
              feature.properties ?? {}
            ) as GeoJsonProperties &
              Partial<ErrorProperties>;

            layer.bindPopup(`
              <div style="min-width: 220px">
                <strong>${escapeHtml(
                  properties.errorType ??
                    "Detected error",
                )}</strong>
                <p><b>Severity:</b> ${escapeHtml(
                  properties.severity ?? "unknown",
                )}</p>
                <p><b>Feature:</b> ${escapeHtml(
                  properties.featureId ?? "unknown",
                )}</p>
                <p>${escapeHtml(
                  properties.details ?? "",
                )}</p>
              </div>
            `);
          }}
        />
      )}

      <FitToErrors
        data={
          showLayer && layerData?.features.length
            ? layerData
            : data
        }
        resetKey={resetKey}
      />

      <FocusSelectedError
        data={data}
        selectedErrorId={selectedErrorId}
      />
    </MapContainer>
  );
}
