import { Clock } from "lucide-react";

export default function HistoryPage() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 px-4">
      <Clock className="h-10 w-10 text-muted-foreground/40" />
      <h1 className="text-lg font-semibold">Session History</h1>
      <p className="text-sm text-muted-foreground">Coming soon</p>
    </div>
  );
}
