import React from "react";

interface NexoraLogoProps {
  className?: string;
  size?: number;
}

export const NexoraLogo: React.FC<NexoraLogoProps> = ({ className = "", size = 32 }) => {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={`transition-all duration-300 hover:scale-105 ${className}`}
    >
      <defs>
        <linearGradient id="nexoraGrad1" x1="4" y1="4" x2="44" y2="44" gradientUnits="userSpaceOnUse">
          <stop stopColor="#00F0FF" />
          <stop offset="0.5" stopColor="#6366F1" />
          <stop offset="1" stopColor="#A855F7" />
        </linearGradient>
        <linearGradient id="nexoraGrad2" x1="44" y1="4" x2="4" y2="44" gradientUnits="userSpaceOnUse">
          <stop stopColor="#A855F7" />
          <stop offset="0.5" stopColor="#00F0FF" />
          <stop offset="1" stopColor="#3B82F6" />
        </linearGradient>
        <filter id="nexoraGlow" x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="3" result="blur" />
          <feComposite in="SourceGraphic" in2="blur" operator="over" />
        </filter>
      </defs>

      {/* Hexagonal Core Shield */}
      <polygon
        points="24,4 42,14 42,34 24,44 6,34 6,14"
        stroke="url(#nexoraGrad1)"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="rgba(10, 15, 29, 0.4)"
        filter="url(#nexoraGlow)"
      />

      {/* Futuristic Stylized 'N' Ribbon */}
      <path
        d="M16 34V14L32 34V14"
        stroke="url(#nexoraGrad2)"
        strokeWidth="3.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* Quantum Node Vertex Accent */}
      <circle cx="24" cy="24" r="2.5" fill="#00F0FF" />
      <circle cx="16" cy="14" r="2" fill="#00F0FF" />
      <circle cx="32" cy="34" r="2" fill="#A855F7" />
    </svg>
  );
};
