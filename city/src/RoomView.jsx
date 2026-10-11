import { useMemo, useState } from "react";
import { Canvas } from "@react-three/fiber";
import { OrbitControls, Text } from "@react-three/drei";
import { BUILDINGS, employeesIn } from "./employees";
import { SeatedPerson } from "./People";
import { drawStepScreen, drawBacktestScreen, drawEmptyRoomScreen } from "./screens";
import { employeeSteps } from "./utils";
import { EmployeePanel } from "./Panels";

const DESK_SPACING = 1.4;

function Desk({ x, employee, color, status, screen, onSelect }) {
  return (
    <group position={[x, 0, 0]}>
      <mesh position={[0, 0.78, -0.15]}>
        <boxGeometry args={[0.95, 0.05, 0.5]} />
        <meshStandardMaterial color="#1a2030" roughness={0.5} metalness={0.2} />
      </mesh>
      <mesh position={[-0.42, 0.4, -0.15]}><boxGeometry args={[0.05, 0.78, 0.45]} /><meshStandardMaterial color="#13161f" /></mesh>
      <mesh position={[0.42, 0.4, -0.15]}><boxGeometry args={[0.05, 0.78, 0.45]} /><meshStandardMaterial color="#13161f" /></mesh>

      <group position={[0, 1.0, -0.2]} onClick={(e) => { e.stopPropagation(); onSelect?.(); }}>
        <mesh><boxGeometry args={[0.7, 0.46, 0.03]} /><meshStandardMaterial color="#111318" roughness={0.4} /></mesh>
        <mesh position={[0, 0, 0.018]}>
          <planeGeometry args={[0.64, 0.4]} />
          <meshBasicMaterial map={screen} toneMapped={false} />
        </mesh>
        <mesh position={[0, -0.28, 0]}><boxGeometry args={[0.05, 0.12, 0.05]} /><meshStandardMaterial color="#1f2937" /></mesh>
        <mesh position={[0, -0.36, 0]}><boxGeometry args={[0.24, 0.03, 0.14]} /><meshStandardMaterial color="#1f2937" /></mesh>
        <pointLight position={[0, 0, 0.35]} color={color} intensity={0.5} distance={1.5} />
      </group>

      {employee && <SeatedPerson employee={employee} color={color} status={status} onClick={onSelect} />}
      {employee && (
        <Text position={[0, 1.55, -0.2]} fontSize={0.07} color="#e5e7eb" anchorX="center">
          {employee.title}
        </Text>
      )}
    </group>
  );
}

function Room({ building, staff, runs, snapshot, statuses, onSelectEmployee }) {
  const color = building.color;
  const deskCount = Math.max(1, staff.length);
  const width = deskCount * DESK_SPACING + 1.6;

  const screens = useMemo(() => {
    if (staff.length === 0) return [drawEmptyRoomScreen(building.note)];
    return staff.map((e) =>
      e.run === "manual"
        ? drawBacktestScreen(e, snapshot?.departments?.backtesting, color)
        : drawStepScreen(e, employeeSteps(runs[e.run], e.id), statuses[e.id], color),
    );
  }, [staff, runs, snapshot, statuses, color, building.note]);

  return (
    <group>
      <mesh rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[width, 4]} />
        <meshStandardMaterial color="#1e2535" roughness={0.8} />
      </mesh>
      <mesh position={[0, 1.3, -1.2]}><boxGeometry args={[width, 2.6, 0.08]} /><meshStandardMaterial color="#1b2233" roughness={0.9} /></mesh>
      <mesh position={[-width / 2, 1.3, 0]}><boxGeometry args={[0.08, 2.6, 4]} /><meshStandardMaterial color="#161c2b" roughness={0.9} /></mesh>
      <mesh position={[width / 2, 1.3, 0]}><boxGeometry args={[0.08, 2.6, 4]} /><meshStandardMaterial color="#161c2b" roughness={0.9} /></mesh>
      <mesh position={[0, 2.4, -1.15]}>
        <boxGeometry args={[width - 0.4, 0.03, 0.02]} />
        <meshStandardMaterial color={color} emissive={color} emissiveIntensity={1} toneMapped={false} />
      </mesh>
      <Text position={[0, 2.15, -1.1]} fontSize={0.14} color="#e5e7eb" anchorX="center">{building.name}</Text>

      {staff.length === 0 ? (
        <Desk x={0} color={color} screen={screens[0]} />
      ) : (
        staff.map((e, i) => (
          <Desk
            key={e.id}
            x={(i - (staff.length - 1) / 2) * DESK_SPACING}
            employee={e}
            color={color}
            status={statuses[e.id]}
            screen={screens[i]}
            onSelect={() => onSelectEmployee(e.id)}
          />
        ))
      )}

      <hemisphereLight args={["#3b5683", "#0b0e14", 1.1]} />
      <ambientLight intensity={0.6} />
      <directionalLight position={[2, 3, 2]} intensity={1.2} color="#dde8ff" />
      <pointLight position={[0, 2.2, 0.5]} intensity={1.2} color="#dde8ff" distance={6} />
    </group>
  );
}

export default function RoomView({ buildingId, runs, snapshot, statuses, onBack }) {
  const building = BUILDINGS.find((b) => b.id === buildingId);
  const staff = useMemo(() => employeesIn(buildingId), [buildingId]);
  const [selectedEmployee, setSelectedEmployee] = useState(null);
  if (!building) return null;

  const spread = Math.max(1, staff.length) * DESK_SPACING;

  return (
    <div style={{ position: "absolute", inset: 0, zIndex: 20, background: "#060810" }}>
      <button
        onClick={onBack}
        style={{
          position: "absolute", top: 16, left: 16, zIndex: 21, background: "#1f2937", color: "#e5e7eb",
          border: "1px solid #374151", borderRadius: 8, padding: "8px 16px", fontSize: 13, cursor: "pointer",
          fontFamily: "system-ui, sans-serif",
        }}
      >
        ← Back to city
      </button>
      <div style={{
        position: "absolute", bottom: 16, left: 16, zIndex: 21, color: "#6b7280", fontSize: 11,
        fontFamily: "system-ui, sans-serif", maxWidth: 420,
      }}>
        Each monitor shows what that employee did in their latest real run. Click a person or a monitor for
        the full details. Drag to look around, scroll to zoom.
      </div>
      <Canvas camera={{ position: [spread * 0.55 + 0.6, 1.7, spread * 0.6 + 1.9], fov: 42 }}>
        <color attach="background" args={["#060810"]} />
        <fog attach="fog" args={["#060810", 5, 11]} />
        <Room building={building} staff={staff} runs={runs} snapshot={snapshot} statuses={statuses}
          onSelectEmployee={setSelectedEmployee} />
        <OrbitControls minDistance={1} maxDistance={6} target={[0, 0.95, -0.15]} maxPolarAngle={Math.PI / 1.9} />
      </Canvas>
      {selectedEmployee && (
        <EmployeePanel employeeId={selectedEmployee} runs={runs} snapshot={snapshot} onClose={() => setSelectedEmployee(null)} />
      )}
    </div>
  );
}
