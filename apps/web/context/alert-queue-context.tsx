"use client";

import { createContext } from "react";

export const AlertQueueContext = createContext<{
  setIsInTurn: (v: boolean) => void;
} | null>(null);
