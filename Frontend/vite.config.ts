// frontend/vite.config.ts
//
// Vite build configuration.
// Most projects don't need to touch this much — but we add ONE thing:
// the `@/` path alias, which lets us write:
//   import { Button } from '@/components/ui/button';
// instead of:
//   import { Button } from '../../../components/ui/button';
//
// The alias must be configured in TWO places:
//   1. Here (for Vite's bundler at build/dev time)
//   2. In tsconfig.json (so TypeScript / VS Code understand it too)

import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    // Dev server port. Default is 5173. Change if it clashes with another
    // service on your machine (Django runs on 8000, no conflict).
    port: 5173,

    // Auto-open the browser when `npm run dev` starts.
    open: true,
  },
});