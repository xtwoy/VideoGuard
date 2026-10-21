import manifest from "../../public/case-images/manifest.json";
import type { CaseIllustrations, CaseSceneImage } from "../components/case-scene-image";

export function illustrationsForCase(caseId: string): CaseIllustrations | undefined {
  const cases: Record<string, { overview: string[]; revisionPlans: Record<string, string[]> }> = manifest.cases;
  const assets: Record<string, CaseSceneImage> = manifest.assets;
  const selected = cases[caseId];
  if (!selected) return undefined;
  const resolve = (ids: string[]) => ids.map((id) => assets[id]).filter(Boolean);
  return {
    overview: resolve(selected.overview),
    revisionPlans: Object.fromEntries(
      Object.entries(selected.revisionPlans).map(([id, images]) => [id, resolve(images)]),
    ),
  };
}
