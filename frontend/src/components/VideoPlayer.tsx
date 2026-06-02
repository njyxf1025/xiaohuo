import { Download } from "lucide-react";

import { cn } from "../lib/utils";

export interface VideoPlayerProps {
  src: string;
  downloadName?: string;
  poster?: string;
  className?: string;
}

export default function VideoPlayer({
  src,
  downloadName = "singing-digital-human.mp4",
  className,
}: VideoPlayerProps) {
  return (
    <div className={cn("card space-y-3", className)}>
      <div className="overflow-hidden rounded-xl bg-black ring-1 ring-slate-800">
        <video
          src={src}
          controls
          playsInline
          className="aspect-video w-full"
          preload="metadata"
        />
      </div>
      <div className="flex items-center justify-end">
        <a
          href={src}
          download={downloadName}
          className="btn-primary"
          target="_blank"
          rel="noreferrer"
        >
          <Download className="h-4 w-4" />
          下载视频
        </a>
      </div>
    </div>
  );
}
