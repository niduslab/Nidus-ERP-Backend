// frontend/src/components/auth/password-strength-meter.tsx
//
// A small visual indicator for password strength.
// Shows a 4-segment bar that fills up as the password gets stronger,
// plus a label and (optional) warning/suggestion text.
//
// USAGE:
//   <PasswordStrengthMeter password={form.watch('password')} userInputs={[email, fullName]} />
//
// DESIGN:
//   ┌──────────────────┐
//   │ ▰▰▱▱▱▱▱▱  Fair  │   ← 2 of 4 segments filled, "Fair" label
//   │ Add another word │   ← optional suggestion under the bar
//   └──────────────────┘

import { useMemo } from 'react';
import { scorePassword } from '@/lib/password-strength';
import { cn } from '@/lib/utils';

interface PasswordStrengthMeterProps {
  /** The current password value (typically from form.watch('password')) */
  password: string;

  /**
   * Optional context strings (email, name) that the password should NOT
   * resemble. Helps zxcvbn flag "myname2024"-style passwords.
   */
  userInputs?: string[];
}

// ── Color mapping for each score level ──
// We use semantic Tailwind classes that respect dark mode automatically.
const SEGMENT_COLORS: Record<number, string> = {
  0: 'bg-destructive',         // Weak       (red)
  1: 'bg-destructive/70',      // Fair       (lighter red)
  2: 'bg-warning',             // Good       (amber)
  3: 'bg-success/80',          // Strong     (green)
  4: 'bg-success',             // Excellent  (deep green)
};

const TEXT_COLORS: Record<number, string> = {
  0: 'text-destructive',
  1: 'text-destructive',
  2: 'text-warning',
  3: 'text-success',
  4: 'text-success',
};

export function PasswordStrengthMeter({
  password,
  userInputs = [],
}: PasswordStrengthMeterProps) {
  // useMemo prevents re-running zxcvbn on every parent re-render unless
  // the password or userInputs actually changed. zxcvbn isn't slow, but
  // good habit to memoize work that depends on user input.
  const result = useMemo(
    () => scorePassword(password, userInputs),
    // Stringify userInputs so the array reference identity doesn't trigger.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [password, userInputs.join('|')],
  );

  // Don't render anything if the password is empty — avoids visual clutter
  // before the user has started typing.
  if (!password) return null;

  return (
    <div className="space-y-1.5">
      {/* ── The 4-segment bar ── */}
      {/* Each segment is filled if the score is >= its index + 1. */}
      <div className="flex gap-1">
        {[0, 1, 2, 3].map((i) => (
          <div
            key={i}
            className={cn(
              'h-1.5 flex-1 rounded-full transition-colors',
              // If the score covers this segment, color it. Otherwise grey.
              result.score > i ? SEGMENT_COLORS[result.score] : 'bg-muted',
            )}
          />
        ))}
      </div>

      {/* ── Label + optional warning/suggestion ── */}
      <div className="flex items-baseline justify-between gap-2 text-xs">
        <span className={cn('font-medium', TEXT_COLORS[result.score])}>
          {result.label}
        </span>
        {/* Show warning OR the first suggestion (priority: warning) */}
        {result.warning ? (
          <span className="text-muted-foreground truncate">
            {result.warning}
          </span>
        ) : result.suggestions[0] ? (
          <span className="text-muted-foreground truncate">
            {result.suggestions[0]}
          </span>
        ) : null}
      </div>
    </div>
  );
}