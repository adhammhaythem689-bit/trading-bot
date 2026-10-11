import { useRef, useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import { OrbitControls, Text, Stars } from "@react-three/drei";
import { BUILDINGS, EMPLOYEES, employeePosition } from "./employees";
import { getGridTexture, seededRandom } from "./textures";
import { StandingPerson } from "./People";

function Windows({ height, width, depth, color, seed }) {
  const windows = useMemo(() => {
    const rand = seededRandom(seed);
    const rows = Math.max(2, Math.floor(height * 2.2));
    const out = [];
    for (let r = 0; r < rows; r++) {
      for (let side = 0; side < 4; side++) {
        for (let col = -1; col <= 1; col += 2) {
          if (rand() > 0.55) continue;
          const lit = rand() > 0.35;
          const y = (r + 0.5) * (height / rows) - height / 2;
          const c = col * 0.32;
          let pos, rot;
          if (side === 0) { pos = [c, y, depth / 2 + 0.01]; rot = [0, 0, 0]; }
          else if (side === 1) { pos = [c, y, -depth / 2 - 0.01]; rot = [0, Math.PI, 0]; }
          else if (side === 2) { pos = [width / 2 + 0.01, y, c]; rot = [0, Math.PI / 2, 0]; }
          else { pos = [-width / 2 - 0.01, y, c]; rot = [0, -Math.PI / 2, 0]; }
          out.push({ pos, rot, lit, key: `${r}-${side}-${col}` });
        }
      }
    }
    return out;
  }, [height, width, depth, seed]);

  // windows are laid out around the tower's center, so the group sits at the center
  return (
    <group position={[0, height / 2 + 0.2, 0]}>
      {windows.map((w) => (
        <mesh key={w.key} position={w.pos} rotation={w.rot}>
          <planeGeometry args={[0.2, 0.13]} />
          <meshStandardMaterial
            color={w.lit ? color : "#1f2937"}
            emissive={w.lit ? color : "#000000"}
            emissiveIntensity={w.lit ? 1.2 : 0}
            toneMapped={false}
          />
        </mesh>
      ))}
    </group>
  );
}

function Building({ building, onSelect, selected, busy }) {
  const planned = building.plannedOnly;
  const w = 1.4, d = 1.4, h = building.height;
  const beaconRef = useRef();

  useFrame((state) => {
    if (beaconRef.current) {
      const speed = busy ? 8 : 2;
      const pulse = 0.6 + Math.sin(state.clock.elapsedTime * speed) * 0.4;
      beaconRef.current.material.emissiveIntensity = planned ? 0.15 : pulse * (busy ? 2 : 1);
    }
  });

  const click = (e) => { e.stopPropagation(); onSelect(); };

  return (
    <group position={building.position}>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.015, 0]}>
        <ringGeometry args={[1.15, 1.3, 48]} />
        <meshBasicMaterial color={building.color} transparent opacity={planned ? 0.12 : busy ? 0.9 : 0.4} />
      </mesh>
      <mesh position={[0, 0.1, 0]} onClick={click}>
        <boxGeometry args={[w + 0.3, 0.2, d + 0.3]} />
        <meshStandardMaterial color="#1f2937" roughness={0.6} metalness={0.3} />
      </mesh>
      <mesh position={[0, h / 2 + 0.2, 0]} onClick={click} castShadow>
        <boxGeometry args={[w, h, d]} />
        <meshStandardMaterial
          color={planned ? "#1f2937" : "#2a3550"}
          emissive={selected ? building.color : "#000000"}
          emissiveIntensity={selected ? 0.3 : 0}
          roughness={0.5}
          metalness={0.15}
          opacity={planned ? 0.5 : 1}
          transparent={planned}
        />
      </mesh>
      <mesh position={[0, h + 0.45, 0]} onClick={click} castShadow>
        <boxGeometry args={[w * 0.65, 0.5, d * 0.65]} />
        <meshStandardMaterial color={planned ? "#1f2937" : "#334066"} roughness={0.4} metalness={0.2}
          opacity={planned ? 0.5 : 1} transparent={planned} />
      </mesh>
      {!planned && <Windows height={h} width={w} depth={d} color={building.color} seed={building.seed} />}
      {!planned && [[-w / 2, -d / 2], [w / 2, -d / 2], [-w / 2, d / 2], [w / 2, d / 2]].map(([x, z], i) => (
        <mesh key={i} position={[x, h / 2 + 0.2, z]}>
          <boxGeometry args={[0.04, h, 0.04]} />
          <meshStandardMaterial color={building.color} emissive={building.color} emissiveIntensity={0.8} toneMapped={false} />
        </mesh>
      ))}
      <mesh ref={beaconRef} position={[0, h + 0.8, 0]}>
        <sphereGeometry args={[0.08, 12, 12]} />
        <meshStandardMaterial color={building.color} emissive={building.color} emissiveIntensity={0.6} toneMapped={false} />
      </mesh>
      <Text position={[0, h + 1.15, 0]} fontSize={0.2} color="#e5e7eb" anchorX="center" anchorY="bottom"
        outlineWidth={0.012} outlineColor="#0b0e14">
        {building.name}
      </Text>
      {planned && (
        <Text position={[0, h + 0.95, 0]} fontSize={0.13} color="#9ca3af" anchorX="center">
          NOT IMPLEMENTED
        </Text>
      )}
    </group>
  );
}

// During a replay, a glowing packet carries the work from one employee to the next.
// The order is the real pipeline order from the run log.
function HandOffPacket({ from, to, stepKey, color }) {
  const ref = useRef();
  const startRef = useRef({ key: null, t: 0 });
  useFrame((state) => {
    if (!ref.current) return;
    if (startRef.current.key !== stepKey) startRef.current = { key: stepKey, t: state.clock.elapsedTime };
    const p = Math.min(1, (state.clock.elapsedTime - startRef.current.t) / 0.7);
    const ease = p * p * (3 - 2 * p);
    const a = from || to;
    ref.current.position.set(
      a[0] + (to[0] - a[0]) * ease,
      1.3 + Math.sin(ease * Math.PI) * 0.8,
      a[2] + (to[2] - a[2]) * ease,
    );
  });
  return (
    <mesh ref={ref}>
      <sphereGeometry args={[0.09, 16, 16]} />
      <meshStandardMaterial color={color} emissive={color} emissiveIntensity={2} toneMapped={false} />
      <pointLight color={color} intensity={1} distance={2.5} />
    </mesh>
  );
}

function Ground({ onClick }) {
  const texture = useMemo(() => getGridTexture(), []);
  return (
    <>
      <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow onClick={onClick}>
        <planeGeometry args={[34, 20]} />
        <meshStandardMaterial map={texture} color="#2a3550" roughness={0.9} />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.01, 0]}>
        <planeGeometry args={[20, 1.4]} />
        <meshStandardMaterial color="#141b2e" roughness={0.6} />
      </mesh>
      {[-5.25, -1.75, 1.75, 5.25].map((x) => (
        <mesh key={x} rotation={[-Math.PI / 2, 0, 0]} position={[x, 0.01, 0]}>
          <planeGeometry args={[0.8, 12]} />
          <meshStandardMaterial color="#141b2e" roughness={0.6} />
        </mesh>
      ))}
    </>
  );
}

export default function CityScene({ statuses, selection, onSelect, replayStep, previousReplayStep }) {
  const activeEmployeeId = replayStep ? replayStep.employee : null;
  const activeEmployee = EMPLOYEES.find((e) => e.id === activeEmployeeId);
  const previousEmployee = previousReplayStep ? EMPLOYEES.find((e) => e.id === previousReplayStep.employee) : null;

  return (
    <>
      <color attach="background" args={["#060810"]} />
      <fog attach="fog" args={["#060810", 20, 40]} />
      <hemisphereLight args={["#2d4a7a", "#0b0e14", 0.9]} />
      <ambientLight intensity={0.5} />
      <directionalLight position={[8, 14, 8]} intensity={1.6} color="#cfe8ff" castShadow />
      <Stars radius={50} depth={20} count={1500} factor={2} saturation={0} fade speed={0.3} />

      <Ground onClick={() => onSelect(null)} />

      {BUILDINGS.map((b) => (
        <Building
          key={b.id}
          building={b}
          selected={selection?.type === "building" && selection.id === b.id}
          busy={activeEmployee?.building === b.id}
          onSelect={() => onSelect({ type: "building", id: b.id })}
        />
      ))}

      {EMPLOYEES.map((e) => {
        const building = BUILDINGS.find((b) => b.id === e.building);
        return (
          <StandingPerson
            key={e.id}
            employee={e}
            color={building.color}
            status={statuses[e.id]}
            position={employeePosition(e)}
            selected={selection?.type === "employee" && selection.id === e.id}
            active={activeEmployeeId === e.id}
            onClick={() => onSelect({ type: "employee", id: e.id })}
          />
        );
      })}

      {activeEmployee && (
        <HandOffPacket
          stepKey={replayStep.step}
          from={previousEmployee ? employeePosition(previousEmployee) : null}
          to={employeePosition(activeEmployee)}
          color={BUILDINGS.find((b) => b.id === activeEmployee.building).color}
        />
      )}

      <OrbitControls minDistance={4} maxDistance={30} maxPolarAngle={Math.PI / 2.1} target={[0, 0.5, 0]} />
    </>
  );
}
