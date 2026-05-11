import type { CriticSchema } from "@/lib/types";

interface CriticFeedbackProps {
  critic: CriticSchema;
}

export default function CriticFeedback({ critic }: CriticFeedbackProps) {
  if (critic?.score == null && !critic?.suggestion) return null;

  return (
    <div className="mt-1.5 rounded-md border bg-secondary/40 px-3 py-2">
      <div className="flex items-center gap-2 text-xs">
        {critic.score != null && (
          <span className="font-medium text-muted-foreground">
            Score: {critic.score} out of 5
          </span>
        )}
      </div>
      {critic.suggestion && (
        <p className="mt-1 text-xs text-muted-foreground">
          {critic.suggestion}
        </p>
      )}
    </div>
  );
}
