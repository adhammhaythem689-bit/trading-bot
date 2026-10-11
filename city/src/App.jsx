import { useEffect, useState } from "react";
import { Canvas } from "@react-three/fiber";
import CityScene from "./CityScene";
import Inspector from "./Inspector";
import RoomView from "./RoomView";
import { DEPARTMENTS } from "./departments";
import { isSnapshotStale } from "./utils";

const STALE_MINUTES = 90; // if the snapshot is older than this, flag it rather than pretend it's current

function useCityData() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch("/city_data.json")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(setData)
      .catch((e) => setError(e.message));
  }, []);

  return { data, error };
}

export default function App() {
  const { data, error } = useCityData();
  const [selectedId, setSelectedId] = useState(null);
  const [roomId, setRoomId] = useState(null);

  const isStale = data && isSnapshotStale(data.generated_at, STALE_MINUTES);

  return (
    <div style={{ position: "relative", width: "100vw", height: "100vh", background: "#0b0e14" }}>
      <div style={{
        position: "absolute", top: 16, left: 16, zIndex: 10, display: "flex", gap: 8, alignItems: "center",
      }}>
        <div style={{
          background: data ? (data.mode === "demo" ? "#7c2d12" : "#064e3b") : "#374151",
          color: "#fff", padding: "4px 12px", borderRadius: 999, fontSize: 12, fontWeight: 700,
        }}>
          {data ? (data.mode === "demo" ? "DEMO DATA" : "REAL DATA") : "LOADING..."}
        </div>
        {isStale && (
          <div style={{ background: "#78350f", color: "#fde68a", padding: "4px 12px", borderRadius: 999, fontSize: 12 }}>
            ⚠ Stale snapshot (&gt;{STALE_MINUTES}m old)
          </div>
        )}
        {error && (
          <div style={{ background: "#7f1d1d", color: "#fecaca", padding: "4px 12px", borderRadius: 999, fontSize: 12 }}>
            Data connection failed: {error}
          </div>
        )}
        {data && (
          <div style={{ color: "#9ca3af", fontSize: 11 }}>
            Last synced: {new Date(data.generated_at).toLocaleString()}
          </div>
        )}
      </div>

      <div style={{
        position: "absolute", bottom: 16, left: 16, zIndex: 10, color: "#6b7280", fontSize: 11, maxWidth: 420,
      }}>
        Click a building or bot to inspect it. Data is a snapshot from the last run of
        export_city_data.py (re-run it, then refresh, to update). This visualization is
        read-only and cannot affect the live trading bot.
      </div>

      <Canvas shadows camera={{ position: [10, 9, 12], fov: 45 }}>
        <CityScene cityData={data} selectedId={selectedId} onSelect={setSelectedId} />
      </Canvas>

      <Inspector selectedId={selectedId} cityData={data} onClose={() => setSelectedId(null)} onEnterRoom={setRoomId} />

      {roomId && <RoomView deptId={roomId} cityData={data} onBack={() => setRoomId(null)} />}
    </div>
  );
}
