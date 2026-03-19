import React from 'react';
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

// A shadcn-like utility to enforce style consistency
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
