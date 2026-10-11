export function isSnapshotStale(generatedAt, staleMinutes, now = Date.now()) {
  if (!generatedAt) return false;
  const ageMs = now - new Date(generatedAt).getTime();
  return ageMs > staleMinutes * 60 * 1000;
}
