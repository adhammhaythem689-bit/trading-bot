import { useRef, useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import { OrbitControls, Text, Stars } from "@react-three/drei";
import * as THREE from "three";
import { DEPARTMENTS } from "./departments";
import { getGridTexture, seededRandom } from "./textures";

function Windows({ height, width, depth, color, seed }) {
  const rand = useMemo(() => seededRandom(seed), [seed]);
  const rows = Math.max(2, Math.floor(height * 2.2));
  const windows = useMemo(() => {
    const out = [];
    for (let r = 0; r < rows; r++) {
      for (let side = 0; side < 4; side++) {
        if (rand() > 0.45) continue; // sparse, not every cell lit
        const lit = rand() > 0.3;
        const y = (r + 0.5) * (height / rows) - height / 2 + 0.15;
        let pos, rot;
        if (side === 0) { pos = [0, y, depth / 2 + 0.01]; rot = [0, 0, 0]; }
        else if (side === 1) { pos = [0, y, -depth / 2 - 0.01]; rot = [0, Math.PI, 0]; }
        else if (side === 2) { pos = [width / 2 + 0.01, y, 0]; rot = [0, Math.PI / 2, 0]; }
        else { pos = [-width / 2 - 0.01, y, 0]; rot = [0, -Math.PI / 2, 0]; }
        out.push({ pos, rot, lit, key: `${r}-${side}` });
      }
    }
    return out;
  }, [rows, height, width, depth, rand]);

  return (
    <group>
      {windows.map((w) => (
        <mesh key={w.key} position={w.pos} rotation={w.rot}>
          <planeGeometry args={[0.18, 0.12]} />
          <meshStandardMaterial
            color={w.lit ? color : "#1f2937"}
            emissive={w.lit ? color : "#000000"}
            emissiveIntensity={w.lit ? 1.4 : 0}
            toneMapped={false}
          />
        </mesh>
      ))}
    </group>
  );
}

function Building({ dept, onSelect, selected }) {
  const planned = dept.plannedOnly;
  const w = 1.4, d = 1.4, h = dept.height;
  const beaconRef = useRef();

  useFrame((state) => {
    if (beaconRef.current) {
      const pulse = 0.6 + Math.sin(state.clock.elapsedTime * 2) * 0.4;
      beaconRef.current.material.emissiveIntensity = planned ? 0.15 : pulse;
    }
  });

  return (
    <group position={dept.position}>
      {/* glowing footprint ring */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.015, 0]}>
        <ringGeometry args={[1.15, 1.3, 48]} />
        <meshBasicMaterial color={dept.color} transparent opacity={planned ? 0.15 : 0.45} />
      </mesh>

      {/* foundation platform */}
      <mesh position={[0, 0.1, 0]} onClick={(e) => { e.stopPropagation(); onSelect(dept.id); }}>
        <boxGeometry args={[w + 0.3, 0.2, d + 0.3]} />
        <meshStandardMaterial color="#1f2937" roughness={0.6} metalness={0.3} />
      </mesh>

      {/* main tower */}
      <mesh
        position={[0, h / 2 + 0.2, 0]}
        onClick={(e) => { e.stopPropagation(); onSelect(dept.id); }}
        castShadow
      >
        <boxGeometry args={[w, h, d]} />
        <meshStandardMaterial
          color={planned ? "#1f2937" : "#2a3550"}
          emissive={selected ? dept.color : "#000000"}
          emissiveIntensity={selected ? 0.35 : 0}
          roughness={0.5}
          metalness={0.15}
          opacity={planned ? 0.55 : 1}
          transparent={planned}
        />
      </mesh>

      {/* upper setback tier, gives the tower a more designed silhouette */}
      <mesh position={[0, h + 0.5, 0]} castShadow>
        <boxGeometry args={[w * 0.65, 0.5, d * 0.65]} />
        <meshStandardMaterial
          color={planned ? "#1f2937" : "#334066"}
          roughness={0.4}
          metalness={0.2}
          opacity={planned ? 0.55 : 1}
          transparent={planned}
        />
      </mesh>

      {!planned && <Windows height={h} width={w} depth={d} color={dept.color} seed={dept.seed} />}

      {/* vertical accent edge lights */}
      {!planned && [[-w / 2, -d / 2], [w / 2, -d / 2], [-w / 2, d / 2], [w / 2, d / 2]].map(([x, z], i) => (
        <mesh key={i} position={[x, h / 2 + 0.2, z]}>
          <boxGeometry args={[0.04, h, 0.04]} />
          <meshStandardMaterial color={dept.color} emissive={dept.color} emissiveIntensity={0.8} toneMapped={false} />
        </mesh>
      ))}

      {/* rooftop beacon */}
      <mesh ref={beaconRef} position={[0, h + 0.85, 0]}>
        <sphereGeometry args={[0.08, 12, 12]} />
        <meshStandardMaterial color={dept.color} emissive={dept.color} emissiveIntensity={0.6} toneMapped={false} />
      </mesh>

      <Text position={[0, h + 1.25, 0]} fontSize={0.2} color="#e5e7eb" anchorX="center" anchorY="bottom" outlineWidth={0.012} outlineColor="#0b0e14">
        {dept.name}
      </Text>
      {planned && (
        <Text position={[0, h + 1.0, 0]} fontSize={0.13} color="#9ca3af" anchorX="center">
          NOT IMPLEMENTED
        </Text>
      )}
    </group>
  );
}

function Bot({ dept, onSelect, selected, status }) {
  const groupRef = useRef();
  const visorRef = useRef();
  const phase = useMemo(() => Math.random() * Math.PI * 2, []);
  const isActive = status === "running" || status === "complete";
  const isHalted = status === "halted";

  useFrame((state) => {
    if (!groupRef.current) return;
    const t = state.clock.elapsedTime + phase;
    groupRef.current.position.y = Math.sin(t * 2) * 0.03;
    if (isActive) groupRef.current.rotation.y = Math.sin(t * 0.6) * 0.5;
    if (visorRef.current) {
      const blink = isHalted ? 0.5 + Math.sin(t * 6) * 0.5 : 0.9;
      visorRef.current.material.emissiveIntensity = blink * 1.5;
    }
  });

  const bodyColor = status === "idle" || status === "not_implemented" ? "#374151" : "#1a2234";
  const accentColor = isHalted ? "#ef4444" : dept.color;

  return (
    <group position={[dept.position[0], 0, dept.position[2] + 1.3]}>
      <group ref={groupRef} position={[0, 0.5, 0]} onClick={(e) => { e.stopPropagation(); onSelect(dept.id); }}>
        {/* legs */}
        <mesh position={[-0.08, -0.32, 0]}><boxGeometry args={[0.07, 0.25, 0.07]} /><meshStandardMaterial color={bodyColor} metalness={0.2} roughness={0.5} /></mesh>
        <mesh position={[0.08, -0.32, 0]}><boxGeometry args={[0.07, 0.25, 0.07]} /><meshStandardMaterial color={bodyColor} metalness={0.2} roughness={0.5} /></mesh>

        {/* torso */}
        <mesh position={[0, -0.05, 0]}>
          <boxGeometry args={[0.26, 0.32, 0.18]} />
          <meshStandardMaterial color={bodyColor} metalness={0.25} roughness={0.4} />
        </mesh>
        <mesh position={[0, -0.05, 0.091]}>
          <boxGeometry args={[0.14, 0.14, 0.01]} />
          <meshStandardMaterial color={accentColor} emissive={accentColor} emissiveIntensity={0.7} toneMapped={false} />
        </mesh>

        {/* head */}
        <mesh position={[0, 0.2, 0]}>
          <boxGeometry args={[0.17, 0.15, 0.15]} />
          <meshStandardMaterial color={bodyColor} metalness={0.25} roughness={0.35} />
        </mesh>
        <mesh ref={visorRef} position={[0, 0.2, 0.076]}>
          <boxGeometry args={[0.12, 0.04, 0.01]} />
          <meshStandardMaterial color={accentColor} emissive={accentColor} emissiveIntensity={1.2} toneMapped={false} />
        </mesh>

        {/* antenna */}
        <mesh position={[0, 0.32, 0]}>
          <cylinderGeometry args={[0.008, 0.008, 0.1, 6]} />
          <meshStandardMaterial color="#6b7280" metalness={0.8} />
        </mesh>
        <mesh position={[0, 0.38, 0]}>
          <sphereGeometry args={[0.018, 8, 8]} />
          <meshStandardMaterial color={accentColor} emissive={accentColor} emissiveIntensity={1} toneMapped={false} />
        </mesh>
      </group>

      <pointLight position={[0, 0.5, 0]} color={accentColor} intensity={selected ? 0.8 : 0.25} distance={2} />

      {selected && (
        <mesh position={[0, 0.02, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[0.32, 0.4, 32]} />
          <meshBasicMaterial color="#ffffff" />
        </mesh>
      )}
    </group>
  );
}

function Ground() {
  const texture = useMemo(() => getGridTexture(), []);
  return (
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0]} receiveShadow>
      <planeGeometry args={[30, 20]} />
      <meshStandardMaterial map={texture} color="#2a3550" roughness={0.9} />
    </mesh>
  );
}

export default function CityScene({ cityData, selectedId, onSelect }) {
  const departments = cityData ? cityData.departments : {};

  return (
    <>
      <color attach="background" args={["#060810"]} />
      <fog attach="fog" args={["#060810", 16, 32]} />
      <hemisphereLight args={["#2d4a7a", "#0b0e14", 0.9]} />
      <ambientLight intensity={0.5} />
      <directionalLight position={[8, 12, 6]} intensity={1.6} color="#cfe8ff" castShadow />
      <pointLight position={[0, 5, -1]} intensity={0.6} color="#38bdf8" />
      <Stars radius={40} depth={20} count={1200} factor={2} saturation={0} fade speed={0.3} />

      <Ground />
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.005, 0]} onClick={() => onSelect(null)}>
        <planeGeometry args={[30, 20]} />
        <meshBasicMaterial transparent opacity={0} />
      </mesh>

      {/* road */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.01, -1]}>
        <planeGeometry args={[18, 1.2]} />
        <meshStandardMaterial color="#141b2e" roughness={0.6} />
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
