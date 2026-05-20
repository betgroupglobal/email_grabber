"use client";

import { Suspense } from "react";
import { UnifiedOperationsHub } from "@/components/operations/UnifiedOperationsHub";

function OperationsFallback() {
  return (
    <div className="flex min-h-[50vh] items-center justify-center text-slate-400">
      Loading autonomous operations…
    </div>
  );
}

export default function OperationsPage() {
  return (
    <Suspense fallback={<OperationsFallback />}>
      <UnifiedOperationsHub />
    </Suspense>
  );
}
