// frontend/src/lib/password-strength.ts
//
// Wraps zxcvbn-ts with our app's defaults so we don't need to repeat
// the boilerplate config in every component that wants password
// strength feedback.
//
// HOW ZXCVBN WORKS (mentally):
//   You give it a password. It checks the password against:
//     - Common-passwords dictionaries (in the lang packs)
//     - Repeated patterns ("aaaa", "1111", "abcabc")
//     - Keyboard walks ("qwerty", "qweasd")
//     - Personal info you optionally provide (name, email)
//   It returns a score from 0 (very weak) to 4 (very strong) + warnings.
//
// USAGE FROM A COMPONENT:
//   const result = scorePassword('myWeak123');
//   result.score        // 0..4
//   result.label        // 'Weak' | 'Fair' | 'Good' | 'Strong' | 'Excellent'
//   result.warning      // 'This is a top-100 common password' | null
//   result.suggestions  // ['Add another word', ...]

import { zxcvbn, zxcvbnOptions } from '@zxcvbn-ts/core';
import * as zxcvbnCommonPackage from '@zxcvbn-ts/language-common';
import * as zxcvbnEnPackage from '@zxcvbn-ts/language-en';

// ── One-time configuration ──
//
// We configure zxcvbn ONCE at module load (top-level code below). This
// avoids re-loading the dictionaries on every keystroke. Module-level
// config is evaluated once per app session.
zxcvbnOptions.setOptions({
  // The dictionaries used to detect common patterns and known passwords.
  // 'common' = top-passwords + repeated patterns (language-agnostic)
  // 'en' = English dictionaries (first names, last names, words)
  dictionary: {
    ...zxcvbnCommonPackage.dictionary,
    ...zxcvbnEnPackage.dictionary,
  },
  graphs: zxcvbnCommonPackage.adjacencyGraphs,
  translations: zxcvbnEnPackage.translations,
});


// ── Public API ──

export interface PasswordScore {
  /** 0..4 — zxcvbn's score where 4 is strongest. */
  score: 0 | 1 | 2 | 3 | 4;

  /** Human-readable label for the score. */
  label: 'Weak' | 'Fair' | 'Good' | 'Strong' | 'Excellent';

  /** A short warning shown to the user, or null if the password is fine. */
  warning: string | null;

  /** Up to 2 actionable suggestions ("Add another word"). */
  suggestions: string[];
}

const LABELS: PasswordScore['label'][] = [
  'Weak',
  'Fair',
  'Good',
  'Strong',
  'Excellent',
];

/**
 * Score a password.
 *
 * @param password The password to evaluate.
 * @param userInputs Optional list of user-specific strings (email, name)
 *   that should NOT appear in the password. Including these lets zxcvbn
 *   penalize "joeshmoe2024" if the user is named Joe Shmoe.
 */
export function scorePassword(
  password: string,
  userInputs: string[] = [],
): PasswordScore {
  // Empty password = score 0 (don't show the user a confusing label
  // before they've typed anything).
  if (!password) {
    return { score: 0, label: 'Weak', warning: null, suggestions: [] };
  }

  // Filter out empty strings from userInputs (zxcvbn dislikes them).
  const cleanInputs = userInputs.filter((s) => s && s.trim().length > 0);

  const result = zxcvbn(password, cleanInputs);

  return {
    score: result.score as PasswordScore['score'],
    label: LABELS[result.score],
    warning: result.feedback.warning || null,
    // Cap suggestions at 2 — more is overwhelming UX.
    suggestions: result.feedback.suggestions.slice(0, 2),
  };
}