import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { Text } from "@react-three/drei";
import { SCREEN_DRAWERS } from "./screenTextures";

function Employee({ color, status }) {
  const headRef = useRef();
  useFrame((state) => {
    if (!headRef.current) return;
    const t = state.clock.elapsedTime;
    // small idle head movement, looking at the monitor, occasionally glancing away
    headRef.current.rotation.y = Math.sin(t * 0.3) * 0.15;
    headRef.current.rotation.x = -0.05 + Math.sin(t * 0.5) * 0.03;
  });
  const skin = "#e8b998";
  const shirt = status === "halted" ? "#7f1d1d" : "#273349";

  return (
    <group position={[0, 0, 0.08]}>
      {/* chair */}
      <mesh position={[0, 0.45, 0.35]}>
        <boxGeometry args={[0.42, 0.06, 0.42]} />
        <meshStandardMaterial color="#1f2937" roughness={0.6} />
      </mesh>
      <mesh position={[0, 0.75, 0.54]}>
        <boxGeometry args={[0.42, 0.55, 0.06]} />
        <meshStandardMaterial color="#1f2937" roughness={0.6} />
      </mesh>
      <mesh position={[-0.18, 0.25, 0.35]}><cylinderGeometry args={[0.02, 0.02, 0.45, 6]} /><meshStandardMaterial color="#111827" /></mesh>
      <mesh position={[0.18, 0.25, 0.35]}><cylinderGeometry args={[0.02, 0.02, 0.45, 6]} /><meshStandardMaterial color="#111827" /></mesh>

      {/* torso, sitting */}
      <mesh position={[0, 0.72, 0.32]}>
        <boxGeometry args={[0.32, 0.4, 0.22]} />
        <meshStandardMaterial color={shirt} roughness={0.7} />
      </mesh>

      {/* arms toward desk */}
      <mesh position={[-0.19, 0.62, 0.1]} rotation={[0.5, 0, 0]}><boxGeometry args={[0.08, 0.3, 0.08]} /><meshStandardMaterial color={shirt} /></mesh>
      <mesh position={[0.19, 0.62, 0.1]} rotation={[0.5, 0, 0]}><boxGeometry args={[0.08, 0.3, 0.08]} /><meshStandardMaterial color={shirt} /></mesh>

      {/* head */}
      <group ref={headRef} position={[0, 1.02, 0.3]}>
        <mesh><sphereGeometry args={[0.14, 16, 16]} /><meshStandardMaterial color={skin} roughness={0.8} /></mesh>
        <mesh position={[0, 0.1, -0.02]}><sphereGeometry args={[0.145, 16, 16, 0, Math.PI * 2, 0, Math.PI * 0.55]} /><meshStandardMaterial color="#2b2320" roughness={0.9} /></mesh>
      </group>

      {/* desk accent glow under hands, ties the employee to their department color */}
      <pointLight position={[0, 0.9, 0.1]} color={color} intensity={0.35} distance={1.2} />
    </group>
  );
}

function Monitor({ texture, color }) {
  return (
    <group position={[0, 0.95, -0.15]}>
      <mesh><boxGeometry args={[0.62, 0.42, 0.03]} /><meshStandardMaterial color="#111318" roughness={0.4} /></mesh>
      <mesh position={[0, 0, 0.018]}>
        <planeGeometry args={[0.56, 0.36]} />
        <meshBasicMaterial map={texture} toneMapped={false} />
      </mesh>
      <mesh position={[0, -0.26, 0]}><boxGeometry args={[0.05, 0.12, 0.05]} /><meshStandardMaterial color="#1f2937" /></mesh>
      <mesh position={[0, -0.33, 0]}><boxGeometry args={[0.24, 0.03, 0.14]} /><meshStandardMaterial color="#1f2937" /></mesh>
      <pointLight position={[0, 0, 0.3]} color={color} intensity={0.5} distance={1.5} />
    </group>
  );
}

export default function Room({ dept, data }) {
  const color = dept.color;
  const drawer = SCREEN_DRAWERS[dept.id];
  const texture = useMemo(() => drawer(data, color), [drawer, data, color]);

  return (
    <group>
      {/* floor */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0]} receiveShadow>
        <planeGeometry args={[4, 4]} />
        <meshStandardMaterial color="#1e2535" roughness={0.8} />
      </mesh>
      {/* back + side walls */}
      <mesh position={[0, 1.2, -1.2]}>
        <boxGeometry args={[4, 2.4, 0.08]} />
        <meshStandardMaterial color="#1b2233" roughness={0.9} />
      </mesh>
      <mesh position={[-2, 1.2, 0]}>
        <boxGeometry args={[0.08, 2.4, 4]} />
        <meshStandardMaterial color="#161c2b" roughness={0.9} />
      </mesh>
      <mesh position={[2, 1.2, 0]}>
        <boxGeometry args={[0.08, 2.4, 4]} />
        <meshStandardMaterial color="#161c2b" roughness={0.9} />
      </mesh>

      {/* wall accent strip, department color */}
      <mesh position={[0, 2.2, -1.16]}>
        <boxGeometry args={[3.6, 0.03, 0.02]} />
        <meshStandardMaterial color={color} emissive={color} emissiveIntensity={1} toneMapped={false} />
      </mesh>

      {/* desk */}
      <mesh position={[0, 0.78, -0.15]}>
        <boxGeometry args={[0.9, 0.05, 0.5]} />
        <meshStandardMaterial color="#1a2030" roughness={0.5} metalness={0.2} />
      </mesh>
      <mesh position={[-0.4, 0.4, -0.15]}><boxGeometry args={[0.05, 0.78, 0.45]} /><meshStandardMaterial color="#13161f" /></mesh>
      <mesh position={[0.4, 0.4, -0.15]}><boxGeometry args={[0.05, 0.78, 0.45]} /><meshStandardMaterial color="#13161f" /></mesh>

      <Monitor texture={texture} color={color} />
      <Employee color={color} status={data.status} />

      <Text position={[0, 2.05, -1.1]} fontSize={0.12} color="#e5e7eb" anchorX="center">
        {dept.name}
      </Text>
      <Text position={[0, 1.88, -1.1]} fontSize={0.07} color="#9ca3af" anchorX="center">
        {dept.role}
      </Text>

      <hemisphereLight args={["#3b5683", "#0b0e14", 1.1]} />
      <ambientLight intensity={0.6} />
      <directionalLight position={[2, 3, 2]} intensity={1.2} color="#dde8ff" />
      <pointLight position={[0, 2.2, 0.5]} intensity={1.2} color="#dde8ff" distance={5} />
      <pointLight position={[0, 1, -1]} intensity={0.6} color={color} distance={3} />
    </group>
  );
}
