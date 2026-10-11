import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { STATUS_COLORS } from "./utils";

const SKIN_TONES = ["#e8b998", "#c68863", "#8d5a3b", "#f1c9a5", "#a8714a"];
const HAIR = ["#2b2320", "#5a3b22", "#111111", "#7a5230", "#3a2a1e"];

function hashIndex(id, n) {
  let h = 0;
  for (const c of id) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return h % n;
}

export function StandingPerson({ employee, color, status, position, selected, active, onClick }) {
  const bodyRef = useRef();
  const orbRef = useRef();
  const phase = useMemo(() => hashIndex(employee.id, 100) / 10, [employee.id]);
  const skin = SKIN_TONES[hashIndex(employee.id, SKIN_TONES.length)];
  const hair = HAIR[hashIndex(employee.id + "h", HAIR.length)];
  const statusColor = STATUS_COLORS[status] || "#374151";

  useFrame((state) => {
    const t = state.clock.elapsedTime + phase;
    if (bodyRef.current) {
      // active = this employee's step is being replayed; otherwise a subtle ambient sway
      bodyRef.current.position.y = active ? Math.abs(Math.sin(t * 6)) * 0.08 : Math.sin(t * 1.5) * 0.01;
      bodyRef.current.rotation.y = active ? Math.sin(t * 3) * 0.3 : 0;
    }
    if (orbRef.current) {
      orbRef.current.material.emissiveIntensity = active ? 1.5 + Math.sin(t * 8) * 0.8 : 0.9;
    }
  });

  return (
    <group position={position} onClick={(e) => { e.stopPropagation(); onClick(); }}>
      <group ref={bodyRef}>
        <mesh position={[-0.06, 0.2, 0]}><boxGeometry args={[0.08, 0.4, 0.09]} /><meshStandardMaterial color="#1f2433" /></mesh>
        <mesh position={[0.06, 0.2, 0]}><boxGeometry args={[0.08, 0.4, 0.09]} /><meshStandardMaterial color="#1f2433" /></mesh>
        <mesh position={[0, 0.58, 0]}><boxGeometry args={[0.26, 0.36, 0.15]} /><meshStandardMaterial color={color} roughness={0.7} /></mesh>
        <mesh position={[-0.17, 0.56, 0]}><boxGeometry args={[0.07, 0.32, 0.08]} /><meshStandardMaterial color={color} roughness={0.7} /></mesh>
        <mesh position={[0.17, 0.56, 0]}><boxGeometry args={[0.07, 0.32, 0.08]} /><meshStandardMaterial color={color} roughness={0.7} /></mesh>
        <mesh position={[0, 0.88, 0]}><sphereGeometry args={[0.11, 16, 16]} /><meshStandardMaterial color={skin} roughness={0.8} /></mesh>
        <mesh position={[0, 0.94, -0.01]}><sphereGeometry args={[0.115, 16, 16, 0, Math.PI * 2, 0, Math.PI * 0.5]} /><meshStandardMaterial color={hair} roughness={0.9} /></mesh>
      </group>
      {/* status light above the head: green finished, gray nothing to do, red failed */}
      <mesh ref={orbRef} position={[0, 1.18, 0]}>
        <sphereGeometry args={[0.05, 12, 12]} />
        <meshStandardMaterial color={statusColor} emissive={statusColor} emissiveIntensity={0.9} toneMapped={false} />
      </mesh>
      {(selected || active) && (
        <mesh position={[0, 0.02, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[0.22, 0.29, 32]} />
          <meshBasicMaterial color={active ? color : "#ffffff"} />
        </mesh>
      )}
      {active && <pointLight position={[0, 1, 0.3]} color={color} intensity={1.2} distance={2} />}
    </group>
  );
}

export function SeatedPerson({ employee, color, status, onClick }) {
  const headRef = useRef();
  const skin = SKIN_TONES[hashIndex(employee.id, SKIN_TONES.length)];
  const hair = HAIR[hashIndex(employee.id + "h", HAIR.length)];
  const statusColor = STATUS_COLORS[status] || "#374151";
  const phase = useMemo(() => hashIndex(employee.id, 100) / 10, [employee.id]);

  useFrame((state) => {
    if (!headRef.current) return;
    const t = state.clock.elapsedTime + phase;
    headRef.current.rotation.y = Math.sin(t * 0.3) * 0.15;
    headRef.current.rotation.x = -0.05 + Math.sin(t * 0.5) * 0.03;
  });

  return (
    <group position={[0, 0, 0.08]} onClick={(e) => { e.stopPropagation(); onClick(); }}>
      <mesh position={[0, 0.45, 0.35]}><boxGeometry args={[0.42, 0.06, 0.42]} /><meshStandardMaterial color="#1f2937" roughness={0.6} /></mesh>
      <mesh position={[0, 0.75, 0.54]}><boxGeometry args={[0.42, 0.55, 0.06]} /><meshStandardMaterial color="#1f2937" roughness={0.6} /></mesh>
      <mesh position={[-0.18, 0.22, 0.35]}><cylinderGeometry args={[0.02, 0.02, 0.45, 6]} /><meshStandardMaterial color="#111827" /></mesh>
      <mesh position={[0.18, 0.22, 0.35]}><cylinderGeometry args={[0.02, 0.02, 0.45, 6]} /><meshStandardMaterial color="#111827" /></mesh>
      <mesh position={[0, 0.72, 0.32]}><boxGeometry args={[0.32, 0.4, 0.22]} /><meshStandardMaterial color={color} roughness={0.7} /></mesh>
      <mesh position={[-0.19, 0.62, 0.1]} rotation={[0.5, 0, 0]}><boxGeometry args={[0.08, 0.3, 0.08]} /><meshStandardMaterial color={color} /></mesh>
      <mesh position={[0.19, 0.62, 0.1]} rotation={[0.5, 0, 0]}><boxGeometry args={[0.08, 0.3, 0.08]} /><meshStandardMaterial color={color} /></mesh>
      <group ref={headRef} position={[0, 1.02, 0.3]}>
        <mesh><sphereGeometry args={[0.14, 16, 16]} /><meshStandardMaterial color={skin} roughness={0.8} /></mesh>
        <mesh position={[0, 0.06, 0.01]}><sphereGeometry args={[0.145, 16, 16, 0, Math.PI * 2, 0, Math.PI * 0.5]} /><meshStandardMaterial color={hair} roughness={0.9} /></mesh>
      </group>
      <mesh position={[0, 1.32, 0.3]}>
        <sphereGeometry args={[0.04, 12, 12]} />
        <meshStandardMaterial color={statusColor} emissive={statusColor} emissiveIntensity={1} toneMapped={false} />
      </mesh>
    </group>
  );
}
