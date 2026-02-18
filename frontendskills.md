# EntropyShield Frontend Engineering Standards
**Role:** Senior Frontend Engineer | **Stack:** React 19 + Vite + Tailwind v4

A living guide to building the "Palantir meets Linear" aesthetic for EntropyShield's compliance platform.

---

## 1. Visual Language: "Futuristic Enterprise"
*The aesthetic is dark, trustworthy, and high-precision.*

### Core Palette (Tailwind v4)
* **Backgrounds:** Deep Slate/Gray is the baseline. Avoid pure black.
    * *Base:* `bg-slate-950`
    * *Surface:* `bg-slate-900` or `bg-slate-800/50`
* **Glassmorphism (The "Card" Standard):**
    * Use for all major containers (Summary Cards, Upload Zones).
    * *Class:* `bg-white/5 backdrop-blur-lg border border-white/10 shadow-2xl`
    * *Hover:* `hover:bg-white/10 hover:border-white/20 transition-all duration-300`
* **Accents & Status:**
    * *Primary Action:* `text-sky-400` (Electric Blue)
    * *Success/Verified:* `text-emerald-400` (Neon Green)
    * *Alert/Violation:* `text-rose-500` (Signal Red)
    * *Warning/Tampered:* `text-amber-400` (Caution Orange)

### Typography & Readability
* **Font:** Inter or JetBrains Mono (for code/data).
* **Hierarchy:**
    * Headers: `font-bold tracking-tight text-white`
    * Subtext: `text-slate-400 text-sm`
    * Data Values: `font-mono text-sky-300` (implies precision)

---

## 2. React 19 & Architecture
*Performance, simplicity, and type safety.*

### Component Structure
Avoid "prop drilling." Keep state as close to where it's used as possible.
* **`components/ui/`**: Reusable atoms (Buttons, Badges, Cards).
* **`components/dashboard/`**: Feature-specific blocks (ViolationFeed, SummaryMetrics).
* **`components/upload/`**: The complex "Brain" components (DropZone, TamperToggle).

### State Management
* **Local State:** Use `useState` for simple UI toggles (e.g., Modal open/close).
* **Global Context:** Use `React Context` *only* for:
    * User Authentication state.
    * Global Preferences (e.g., Toggle "Forensic Mode").
    * Toast Notification Queue.
* **Server State:** For API data (`/api/compliance/run`), use custom hooks (e.g., `useComplianceData`) that wrap `fetch`. *Keep it lightweight—no Redux.*

### The "Scanner" Pattern (Async UI)
For the Policy Uploader & Tamper Check:
1.  **Idle:** Standard Glassmorphism card.
2.  **Loading ("Scanning..."):**
    * Use a pulsing animation: `animate-pulse` or a custom CSS scanline effect.
    * Lock the UI: `pointer-events-none opacity-80`.
3.  **Result:**
    * *Verified:* `border-emerald-500/50` + Emerald Badge.
    * *Tampered:* `border-red-500/50` + Red Alert Modal.

---

## 3. Tailwind v4 Best Practices
*Utility-first, maintainable, and composable.*

### Conditional Classes
Use `clsx` or `tailwind-merge` to handle dynamic states without messy template literals.
```tsx
// Bad
className={`p-4 border ${isError ? 'border-red-500' : 'border-gray-500'}`}

// Good
import { cn } from '@/lib/utils';
className={cn("p-4 border transition-colors", 
  isError ? "border-red-500 bg-red-500/10" : "border-white/10 hover:border-white/20"
)}