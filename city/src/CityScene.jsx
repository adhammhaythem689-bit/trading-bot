import { useRef, useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import { OrbitControls, Text } from "@react-three/drei";
import { DEPARTMENTS } from "./departments";

function Building({ dept, onSelect, selected }) {
  const planned = dept.plannedOnly;
  return (
    <group position={dept.position}>
      <mesh
        position={[0, 0.75, 0]}
        onClick={(e) => { e.stopPropagation(); onSelect(dept.id); }}
        castShadow
      >
        <boxGeometry args={[1.6, 1.5, 1.6]} />
        <meshStandardMaterial
          color={dept.color}
          emissive={selected ? dept.color : "#000000"}
          emissiveIntensity={selected ? 0.5 : 0}
          opacity={planned ? 0.35 : 1}
          transparent={planned}
        />
      </mesh>
      <Text position={[0, 1.7, 0]} fontSize={0.22} color="#e5e7eb" anchorX="center" anchorY="bottom">
        {dept.name}
      </Text>
      {planned && (
        <Text position={[0, 1.4, 0.85]} fontSize={0.14} color="#9ca3af" anchorX="center">
          NOT IMPLEMENTED
        </Text>
      )}
    </group>
  );
}

function Bot({ dept, onSelect, selected, status }) {
  const ref = useRef();
  const phase = useMemo(() => Math.random() * Math.PI * 2, []);
  const isActive = status === "running" || status === "complete";

  useFrame((state) => {
    if (!ref.current) return;
    const t = state.clock.elapsedTime + phase;
    // idle bob -- explicitly ambient, not representing computation progress
    ref.current.position.y = 0.55 + Math.sin(t * 2) * 0.04;
    if (isActive) ref.current.rotation.y = Math.sin(t * 0.6) * 0.4;
  });

  const bodyColor = status === "halted" ? "#ef4444" : status === "idle" ? "#6b7280" : dept.color;

  return (
    <group position={[dept.position[0], 0, dept.position[2] + 1.3]}>
      <mesh
        ref={ref}
        onClick={(e) => { e.stopPropagation(); onSelect(dept.id); }}
      >
        <capsuleGeometry args={[0.18, 0.35, 4, 8]} />
        <meshStandardMaterial color={bodyColor} emissive={selected ? "#ffffff" : "#000000"} emissiveIntensity={selected ? 0.3 : 0} />
      </mesh>
      {selected && (
        <mesh position={[0, 0.05, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[0.35, 0.42, 32]} />
          <meshBasicMaterial color="#ffffff" />
        </mesh>
      )}
    </group>
  );
}

export default function CityScene({ cityData, selectedId, onSelect }) {
  const departments = cityData ? cityData.departments : {};

  return (
    <>
      <color attach="background" args={["#0b0e14"]} />
      <ambientLight intensity={0.5} />
      <directionalLight position={[8, 12, 6]} intensity={1.1} castShadow />
      <pointLight position={[0, 4, 0]} intensity={0.3} color="#38bdf8" />

      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0]} receiveShadow onClick={() => onSelect(null)}>
        <planeGeometry args={[30, 20]} />
        <meshStandardMaterial color="#111827" />
      </mesh>

      {/* simple road grid, purely cosmetic */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.01, -1]}>
        <planeGeometry args={[18, 1.2]} />
        <meshStandardMaterial color="#1f2937" />
      </mesh>

      {DEPARTMENTS.map((dept) => {
        const deptData = departments[dept.id] || { status: "idle" };
        return (
          <group key={dept.id}>
            <Building dept={dept} onSelect={onSelect} selected={selectedId === dept.id} />
            <Bot dept={dept} onSelect={onSelect} selected={selectedId === dept.id} status={deptData.status} />
          </group>
        );
      })}

      <OrbitControls
        minDistance={4}
        maxDistance={22}
        maxPolarAngle={Math.PI / 2.1}
        target={[0, 0.5, 0]}
      />
    </>
  );
}
