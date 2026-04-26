// frontend/src/components/auth/otp-input.tsx
//
// A 6-box one-time-password input with auto-advance, paste handling,
// and Backspace navigation. Polished UX users actually like.
//
// FEATURES:
//   - One <input> per digit, auto-focus advances on type
//   - Backspace on empty box jumps focus back
//   - Pasting a 6-digit code fills all boxes at once
//   - Only digits accepted (filtered on input)
//   - Calls onComplete(code) when all 6 digits are entered
//
// USAGE:
//   <OtpInput length={6} onComplete={(code) => verifyOtp(code)} />
//
// THE KEY TECHNIQUE:
//   We hold an array of refs (one per <input>), so we can imperatively
//   focus a different box from a keyboard event handler. This is the
//   ONE place in React where useRef-driven imperative DOM is the right
//   tool — useState would force a re-render on every focus change.

import { useRef, useState, type ClipboardEvent, type KeyboardEvent } from 'react';
import { cn } from '@/lib/utils';

interface OtpInputProps {
  /** How many digits the OTP has. Default 6. */
  length?: number;

  /** Called with the full OTP string the moment all boxes are filled. */
  onComplete: (otp: string) => void;

  /** When true, all boxes are disabled (e.g., during submit). */
  disabled?: boolean;

  /** Optional className passed through for layout customization. */
  className?: string;

  /**
   * If true, render a red border on every box (e.g., when the OTP is
   * rejected by the server). The parent toggles this; we just style.
   */
  hasError?: boolean;
}

export function OtpInput({
  length = 6,
  onComplete,
  disabled = false,
  className,
  hasError = false,
}: OtpInputProps) {
  // ── State: the digit in each box ──
  // Array of single-character strings. We keep them as strings (not
  // numbers) so that '' (empty) is distinguishable from '0'.
  const [values, setValues] = useState<string[]>(
    () => Array(length).fill(''),
  );

  // ── Refs: one DOM ref per <input> ──
  // We need imperative .focus() control on these. useRef stores them
  // without causing re-renders.
  const inputRefs = useRef<Array<HTMLInputElement | null>>([]);

  // ── Helper: write a value into box `index`, then advance focus ──
  function setBox(index: number, value: string) {
    // Take only the LAST character typed — handles the case where the
    // user types fast and the input register two chars before our
    // handler can fire.
    const digit = value.slice(-1);

    // Reject anything that isn't a digit.
    if (digit && !/\d/.test(digit)) return;

    const next = [...values];
    next[index] = digit;
    setValues(next);

    // Auto-advance focus if we filled this box and there's a next one.
    if (digit && index < length - 1) {
      inputRefs.current[index + 1]?.focus();
    }

    // If all boxes are now filled, fire onComplete.
    if (next.every((v) => v !== '') && next.join('').length === length) {
      onComplete(next.join(''));
    }
  }

  // ── Keyboard handler: Backspace navigation ──
  function handleKeyDown(index: number, e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Backspace' && !values[index] && index > 0) {
      // Box is empty + Backspace pressed → jump back and clear that box.
      e.preventDefault();
      const next = [...values];
      next[index - 1] = '';
      setValues(next);
      inputRefs.current[index - 1]?.focus();
    } else if (e.key === 'ArrowLeft' && index > 0) {
      e.preventDefault();
      inputRefs.current[index - 1]?.focus();
    } else if (e.key === 'ArrowRight' && index < length - 1) {
      e.preventDefault();
      inputRefs.current[index + 1]?.focus();
    }
  }

  // ── Paste handler: distribute digits across boxes ──
  function handlePaste(e: ClipboardEvent<HTMLInputElement>) {
    e.preventDefault();
    // Get the pasted text, keep only digits, take up to `length` chars.
    const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, length);
    if (!pasted) return;

    // Spread across boxes starting from index 0.
    const next = Array(length).fill('');
    for (let i = 0; i < pasted.length; i++) {
      next[i] = pasted[i];
    }
    setValues(next);

    // Focus the box AFTER the last filled one (or the last box).
    const focusIndex = Math.min(pasted.length, length - 1);
    inputRefs.current[focusIndex]?.focus();

    // If they pasted a complete code, fire onComplete.
    if (pasted.length === length) {
      onComplete(pasted);
    }
  }

  return (
    <div className={cn('flex gap-2 justify-center', className)}>
      {Array.from({ length }, (_, i) => (
        <input
          key={i}
          // Storing the ref into our array. The callback ref pattern.
          ref={(el) => { inputRefs.current[i] = el; }}
          type="text"
          // inputMode='numeric' = mobile keyboards show the number pad
          inputMode="numeric"
          // pattern restricts to digits (modern browsers honor this)
          pattern="\d*"
          // maxLength=1 = visually constrain. We also slice in the handler.
          maxLength={1}
          value={values[i]}
          onChange={(e) => setBox(i, e.target.value)}
          onKeyDown={(e) => handleKeyDown(i, e)}
          onPaste={handlePaste}
          disabled={disabled}
          // autoFocus on the FIRST box so users can type immediately
          autoFocus={i === 0}
          // ── Tailwind styling ──
          // h-14 w-12 = 56px tall, 48px wide. Big enough to feel solid.
          // text-center text-xl = digit centered, large
          // tracking-widest = wide letter spacing (looks more "code-like")
          // font-mono = use monospace font (numbers align)
          // hasError ring → red border. Otherwise normal teal focus ring.
          className={cn(
            'h-14 w-12 rounded-md border bg-background',
            'text-center text-xl font-mono tabular-nums tracking-widest',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2',
            'transition-colors',
            'disabled:cursor-not-allowed disabled:opacity-50',
            hasError
              ? 'border-destructive focus-visible:ring-destructive'
              : 'border-input focus-visible:ring-ring',
          )}
          aria-label={`OTP digit ${i + 1}`}
        />
      ))}
    </div>
  );
}