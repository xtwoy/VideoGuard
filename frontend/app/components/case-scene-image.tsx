import { ImageIcon } from "lucide-react";

/** Presentation assets are separate from observation/evidence records. */
export type CaseSceneImage = {
  id: string;
  src: string | null;
  alt: string;
  caption: string;
};

export type CaseIllustrations = {
  overview: CaseSceneImage[];
  revisionPlans: Record<string, CaseSceneImage[]>;
};

export function CaseSceneImage({
  image,
  placement = "context",
}: {
  image: CaseSceneImage;
  placement?: "context" | "issue";
}) {
  return (
    <figure className={`vg-scene-image vg-scene-image--${placement}`}>
      <div className="vg-scene-image-frame">
        {image.src ? (
          <img src={image.src} alt={image.alt} width={1280} height={720} />
        ) : (
          <div className="vg-scene-image-empty">
            <ImageIcon size={27} strokeWidth={1.3} aria-hidden />
            <strong>待补场景图</strong>
            <span>{image.alt}</span>
          </div>
        )}
      </div>
      <figcaption>
        <span className="vg-scene-image-label">
          {placement === "issue" ? "问题画面" : "场景画面"}
          <span>场景配图</span>
        </span>
        <p>{image.caption}</p>
      </figcaption>
    </figure>
  );
}
