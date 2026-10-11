import { Canvas } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import Room from "./Room";
import { DEPARTMENTS } from "./departments";

export default function RoomView({ deptId, cityData, onBack }) {
  const dept = DEPARTMENTS.find((d) => d.id === deptId);
  const data = (cityData && cityData.departments[deptId]) || { status: "idle" };
  if (!dept) return null;

  return (
    <div style={{ position: "absolute", inset: 0, zIndex: 20, background: "#060810" }}>
      <button
        onClick={onBack}
        style={{
          position: "absolute", top: 16, left: 16, zIndex: 21,
          background: "#1f2937", color: "#e5e7eb", border: "1px solid #374151",
          borderRadius: 8, padding: "8px 16px", fontSize: 13, cursor: "pointer",
          fontFamily: "system-ui, sans-serif",
        }}
      >
        ← Back to city
      </button>
      <div style={{
        position: "absolute", bottom: 16, left: 16, zIndex: 21, color: "#6b7280",
        fontSize: 11, fontFamily: "system-ui, sans-serif", maxWidth: 400,
      }}>
        Workstation view. The monitor renders this department's real, current data.
        Drag to look around, scroll to zoom.
      </div>
      {/* over-the-shoulder 3/4 view: employee in the foreground, monitor readable behind */}
      <Canvas shadows camera={{ position: [1.5, 1.65, 2.3], fov: 42 }}>
        <color attach="background" args={["#060810"]} />
        <fog attach="fog" args={["#060810", 4, 9]} />
        <Room dept={dept} data={data} />
        <OrbitControls
          minDistance={1.0}
          maxDistance={4}
          target={[0, 0.95, -0.15]}
          maxPolarAngle={Math.PI / 1.9}
        />
      </Canvas>
    </div>
  );
}
