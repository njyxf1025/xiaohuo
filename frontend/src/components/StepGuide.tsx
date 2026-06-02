import { Check } from "lucide-react";

import { cn } from "../lib/utils";

export interface StepGuideProps {
  current: 1 | 2 | 3 | 4;
}

const STEPS = [
  { id: 1, label: "上传音乐" },
  { id: 2, label: "选择高潮" },
  { id: 3, label: "选择形象" },
  { id: 4, label: "生成视频" },
];

export default function StepGuide({ current }: StepGuideProps) {
  return (
    <ol className="card flex w-full flex-col gap-3 sm:flex-row sm:items-center sm:gap-0">
      {STEPS.map((step, idx) => {
        const done = step.id < current;
        const active = step.id === current;
        return (
          <li
            key={step.id}
            className={cn(
              "flex flex-1 items-center gap-3",
              idx !== STEPS.length - 1 && "sm:pr-3",
            )}
          >
            <div
              className={cn(
                "flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-sm font-semibold transition",
                done && "bg-emerald-500/20 text-emerald-300 ring-1 ring-emerald-500/40",
                active && "bg-brand-500 text-white shadow-glow",
                !done && !active && "bg-slate-800 text-slate-400",
              )}
            >
              {done ? <Check className="h-4 w-4" /> : step.id}
            </div>
            <div className="min-w-0 flex-1">
              <p
                className={cn(
                  "text-sm font-semibold",
                  active ? "text-white" : done ? "text-emerald-200" : "text-slate-400",
                )}
              >
                {step.label}
              </p>
              <p className="text-[11px] text-slate-500">步骤 {step.id} / 4</p>
            </div>
            {idx !== STEPS.length - 1 && (
              <div
                className={cn(
                  "mx-3 hidden h-px flex-1 sm:block",
                  done ? "bg-emerald-500/40" : "bg-slate-800",
                )}
              />
            )}
          </li>
        );
      })}
    </ol>
  );
}
