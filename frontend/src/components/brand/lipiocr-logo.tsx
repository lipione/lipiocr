"use client";

import { useId } from "react";

type LipiOcrLogoProps = {
  className?: string;
  label?: string;
  markClassName?: string;
  showWordmark?: boolean;
  size?: "sm" | "md" | "lg";
  tone?: "full" | "light";
};

const sizeMap = {
  sm: {
    mark: "h-9 w-9",
    wordmark: "h-7 w-[116px]",
    gap: "gap-2.5",
  },
  md: {
    mark: "h-11 w-11",
    wordmark: "h-8 w-[140px]",
    gap: "gap-3",
  },
  lg: {
    mark: "h-14 w-14",
    wordmark: "h-10 w-[176px]",
    gap: "gap-4",
  },
};

export function LipiOcrLogo({
  className = "",
  label = "LipiOCR",
  markClassName = "",
  showWordmark = true,
  size = "md",
  tone = "full",
}: LipiOcrLogoProps) {
  const sizing = sizeMap[size];
  return (
    <span className={`inline-flex items-center ${sizing.gap} ${className}`} aria-label={label} role="img">
      <LipiOcrMark className={`${sizing.mark} ${markClassName}`} />
      {showWordmark ? <LipiOcrWordmark className={sizing.wordmark} tone={tone} /> : null}
    </span>
  );
}

export function LipiOcrMark({ className = "" }: { className?: string }) {
  const id = useId().replace(/:/g, "");
  const faceId = `${id}-lipi-mark-face`;
  const edgeId = `${id}-lipi-mark-edge`;
  const shadowId = `${id}-lipi-mark-shadow`;

  return (
    <svg aria-hidden="true" className={className} viewBox="0 0 96 96">
      <defs>
        <linearGradient id={faceId} x1="24" x2="72" y1="15" y2="82" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#5EEAD4" />
          <stop offset="0.5" stopColor="#13B8B9" />
          <stop offset="1" stopColor="#087A8F" />
        </linearGradient>
        <linearGradient id={edgeId} x1="28" x2="63" y1="63" y2="86" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#0F766E" />
          <stop offset="1" stopColor="#075985" />
        </linearGradient>
        <filter id={shadowId} x="-20%" y="-20%" width="140%" height="150%">
          <feDropShadow dx="0" dy="8" floodColor="#0F766E" floodOpacity="0.22" stdDeviation="7" />
        </filter>
      </defs>
      <g fill="none" stroke="#0EA5A8" strokeLinecap="round" strokeWidth="5.5">
        <path d="M16 26v-9c0-3 2-5 5-5h10" />
        <path d="M65 12h10c3 0 5 2 5 5v9" />
        <path d="M80 70v9c0 3-2 5-5 5H65" />
        <path d="M31 84H21c-3 0-5-2-5-5v-9" />
      </g>
      <g filter={`url(#${shadowId})`}>
        <path d="M32 19 64 38v38H32V19Z" fill={`url(#${faceId})`} />
        <path d="M32 76h32L49 86H24l8-10Z" fill={`url(#${edgeId})`} />
        <path d="M64 38H50a5 5 0 0 1-5-5V19l19 19Z" fill="#0E9FB2" />
        <path d="M46 42h18v31H34V30h12v12Z" fill="#F8FAFC" />
        <rect fill="#0E9FB2" height="5" rx="2" width="16" x="52" y="48" />
        <rect fill="#0E9FB2" height="5" rx="2" width="26" x="42" y="59" />
        <rect fill="#0E9FB2" height="5" rx="2" width="26" x="42" y="70" />
      </g>
    </svg>
  );
}

export function LipiOcrWordmark({ className = "", tone = "full" }: { className?: string; tone?: "full" | "light" }) {
  const dark = tone === "light" ? "#FFFFFF" : "#0B1933";
  const teal = tone === "light" ? "#67E8F9" : "#0EA5A8";
  return (
    <svg aria-hidden="true" className={className} viewBox="0 0 285 64">
      <text
        fill={dark}
        fontFamily="Plus Jakarta Sans, Inter, ui-sans-serif, system-ui, sans-serif"
        fontSize="50"
        fontWeight="500"
        letterSpacing="0"
        x="0"
        y="50"
      >
        Lipi
      </text>
      <text
        fill={teal}
        fontFamily="Plus Jakarta Sans, Inter, ui-sans-serif, system-ui, sans-serif"
        fontSize="50"
        fontWeight="500"
        letterSpacing="0"
        x="113"
        y="50"
      >
        OCR
      </text>
    </svg>
  );
}
