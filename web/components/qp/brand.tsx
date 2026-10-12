import { cn } from "@/lib/utils";

export function Mark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={cn("size-7", className)} aria-hidden>
      <circle cx="16" cy="16" r="14.5" fill="#fff" stroke="#111827" strokeWidth="2.2" /><circle cx="16" cy="16" r="10" fill="none" stroke="#111827" strokeWidth="1.4" />
      <path d="M7 21 C 11 21, 12 11, 16 11 S 21 21, 25 21" fill="none" stroke="#0B2545" strokeWidth="2.2" strokeLinecap="round" />
      <path d="M7 11 C 11 11, 12 21, 16 21 S 21 11, 25 11" fill="none" stroke="#B7791F" strokeWidth="2.2" strokeLinecap="round" opacity="0.9" />
    </svg>
  );
}

export function Logo({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <Mark />
      <span className="serif text-[20px] font-semibold tracking-tight text-foreground">QuantPair</span>
    </span>
  );
}
