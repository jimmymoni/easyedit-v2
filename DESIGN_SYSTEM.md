# EasyEdit v2 Design System

**Version:** 1.0
**Last Updated:** October 2025
**Status:** Official Design Standard

---

## 🎯 Design Philosophy

**"Professional, Minimal, Dark Mode First"**

EasyEdit v2 is a professional video editing tool with a dark-first aesthetic inspired by DaVinci Resolve and modern SaaS applications. The design emphasizes clarity, efficiency, and brand identity through strategic use of orange accents on dark surfaces.

### Core Principles

1. **Dark Background, Light Cards** - Maximum contrast for readability
2. **Orange Brand Identity** - Consistent use of orange (#FF6B35) for all interactive elements
3. **Minimalist & Clean** - Remove unnecessary visual noise
4. **Professional** - Video editor-grade polish and attention to detail
5. **Consistent** - Every component follows the same patterns

---

## 🎨 Color Palette

### Background & Surfaces

```css
/* Main Background */
--background: #000000         /* Pure black - main app background */

/* Dark Surfaces */
--dark-surface: #181818       /* Dark cards/containers on black background */
--dark-border: #2A2A2A        /* Subtle borders for dark surfaces */

/* Light Surfaces */
--card: #FFFFFF               /* White cards on black background */
--card-border: hsl(0 0% 89.8%)   /* Light gray borders */
```

**Usage:**
- Use `#000000` black for main app background
- Use `#FFFFFF` white cards for primary content areas
- Use `#181818` dark surfaces for secondary containers (like progress indicators)
- Use `#2A2A2A` borders for dark surfaces

### Brand Colors

```css
/* Primary Orange - Brand Color */
--orange-400: #FF8854         /* Lighter orange variant */
--orange-500: #FF6B35         /* PRIMARY BRAND COLOR - use for all interactive elements */
--orange-600: #FF5722         /* Darker orange variant */

/* Orange Gradient (Completion States) */
background: linear-gradient(90deg, #FF6B35, #FF884F);
```

**Usage:**
- ✅ **Use orange for:** Sliders, progress bars, active states, toggles, buttons, links, icons
- ✅ **Primary orange:** `#FF6B35` for normal state
- ✅ **Gradient:** Use for completion/success states with warm glow
- ❌ **Never use blue** - Not part of brand identity

### Semantic Colors

```css
/* Success */
--success: #22c55e            /* Green - only for final success states */

/* Destructive */
--destructive: hsl(0 84.2% 60.2%)   /* Red - errors, delete actions */
```

**Usage:**
- ✅ Use green (#22c55e) ONLY for final completion/success messages
- ✅ For progress indicators, use orange gradient instead of green
- ✅ Use destructive red for errors and delete confirmations

### Text Colors

```css
/* Light Theme Text (on white cards) */
--foreground: hsl(0 0% 3.9%)        /* Near-black - primary text */
--muted-foreground: hsl(0 0% 45.1%) /* Gray - secondary text */

/* Dark Theme Text (on dark surfaces) */
--text-light: #EAEAEA              /* Light gray - primary text on dark */
--text-light-muted: rgba(234, 234, 234, 0.7)  /* Muted light text */
```

**Usage:**
- On white cards: Use `hsl(0 0% 3.9%)` for text
- On dark surfaces (#181818): Use `#EAEAEA` for text
- For descriptions/secondary text: Use 70% opacity variant

### Borders & Separators

```css
--border: hsl(0 0% 89.8%)           /* Standard light borders */
--border-80: hsla(0 0% 89.8% / 0.8) /* Softer borders */
--border-60: hsla(0 0% 89.8% / 0.6) /* Subtle dividers */

--dark-border: #2A2A2A              /* Dark surface borders */
```

---

## 📐 Spacing & Layout

### Padding Scale

```css
--spacing-xs: 4px     /* 0.25rem */
--spacing-sm: 8px     /* 0.5rem */
--spacing-md: 12px    /* 0.75rem */
--spacing-lg: 16px    /* 1rem */
--spacing-xl: 24px    /* 1.5rem */
--spacing-2xl: 32px   /* 2rem */
```

**Component Padding:**
- Small cards: `p-4` (16px)
- Medium cards: `p-6` (24px)
- Large cards: `p-8` (32px)

### Border Radius

```css
--radius-sm: 4px      /* Small elements */
--radius-md: 6px      /* Buttons, inputs */
--radius-lg: 8px      /* Cards (rounded-lg) */
--radius-xl: 12px     /* Large cards (rounded-xl) */
--radius-full: 9999px /* Pills, progress bars (rounded-full) */
```

**Usage:**
- Cards: `rounded-xl` (12px)
- Progress bars: `rounded-full`
- Buttons: `rounded-lg` (8px)

### Shadows

```css
/* Light Surfaces */
--shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05)
--shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1)
--shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1)

/* Orange Glow (for completion states) */
--shadow-orange-glow: 0 0 6px rgba(255, 107, 53, 0.5)
```

**Usage:**
- Default cards: `shadow-sm`
- Hover state: `shadow-md`
- Drag-active: `shadow-lg shadow-primary/20`
- Orange glow: Use for completed progress bars

---

## 🔤 Typography

### Font Families

```css
--font-sans: 'Inter', system-ui, -apple-system, sans-serif;
--font-mono: 'JetBrains Mono', Menlo, Monaco, Consolas, monospace;
```

**Usage:**
- All UI text: Inter (default)
- Code/technical: JetBrains Mono

### Font Sizes

```css
--text-xs: 12px      /* Badges, helper text */
--text-sm: 14px      /* Secondary text, descriptions */
--text-base: 16px    /* Body text */
--text-lg: 18px      /* Section headings */
--text-xl: 20px      /* Page titles */
--text-2xl: 24px     /* Hero headings */
--text-3xl: 30px     /* Major headings */
```

### Font Weights

```css
--font-normal: 400    /* Body text */
--font-medium: 500    /* Subtle emphasis */
--font-semibold: 600  /* Section headings */
--font-bold: 700      /* Major headings */
```

---

## 🎛️ Component Patterns

### White Cards (Primary Content)

```tsx
<div className="
  bg-card
  rounded-xl
  border border-border/80
  shadow-sm
  hover:shadow-md
  transition-shadow duration-200
  p-6
">
  {/* Content */}
</div>
```

**Features:**
- White background on black
- Subtle border with 80% opacity
- Shadow that intensifies on hover
- Smooth transition

### Dark Cards (Secondary Content)

```tsx
<div className="
  bg-[#181818]
  border border-[#2A2A2A]
  rounded-xl
  shadow-lg
  p-6
  transition-all duration-300
">
  {/* Content with text-[#EAEAEA] */}
</div>
```

**Features:**
- Dark surface (#181818)
- Subtle dark border (#2A2A2A)
- Light text (#EAEAEA)
- Used for progress, alerts, secondary info

### Progress Bars

```tsx
{/* Track */}
<div className="w-full h-3 bg-muted/20 rounded-full border border-[#2A2A2A]">

  {/* Fill (In Progress) */}
  <div
    className="h-full transition-all duration-300"
    style={{
      width: `${percentage}%`,
      background: '#FF6B35'  /* Orange - brand color */
    }}
  />

  {/* Fill (Completed) - Orange gradient with glow */}
  <div
    className="h-full transition-all duration-300 shadow-[0_0_6px_rgba(255,107,53,0.5)]"
    style={{
      width: '100%',
      background: 'linear-gradient(90deg, #FF6B35, #FF884F)'
    }}
  />
</div>
```

**Features:**
- Orange (#FF6B35) for in-progress
- Orange gradient + glow for completion (NOT green)
- Smooth transitions

### Upload Zones

```tsx
{/* Empty State */}
<div className="
  border-dashed
  border-muted-foreground/25
  hover:border-muted-foreground/50
  hover:bg-accent/30
  rounded-xl
  p-8
">

{/* With File */}
<div className="
  border-border
  bg-card
  hover:bg-accent/50
  shadow-sm
  hover:shadow-md
  rounded-xl
  p-4
">

{/* Drag Active */}
<div className="
  border-primary
  bg-primary/5
  shadow-lg
  shadow-primary/20
  rounded-xl
">
```

### Sliders (Orange Brand)

```tsx
<Slider
  className="flex-1"
  /* Slider automatically uses orange from design system */
/>
```

**Features:**
- Track: Muted gray
- Fill: Orange (#FF6B35)
- Thumb: Orange with hover state

### Switches (Orange Brand)

```tsx
<Switch
  checked={enabled}
  /* Switch automatically uses orange when ON */
/>
```

**Features:**
- Off: Gray/muted
- On: Orange (#FF6B35)

---

## ✨ Interactive States

### Hover States

```css
/* Cards */
.card:hover {
  box-shadow: var(--shadow-md);
  background: hsl(var(--accent) / 0.3-0.5);
}

/* Buttons */
.button:hover {
  opacity: 0.9;
}

/* Table Rows */
.table-row:hover {
  background: hsl(var(--accent) / 0.3);
}
```

### Active/Selected States

```css
/* Always use orange for active/selected */
.active {
  color: #FF6B35;
  border-color: #FF6B35;
}

/* Progress bars, sliders, toggles */
background: #FF6B35;
```

### Disabled States

```css
.disabled {
  opacity: 0.5;
  cursor: not-allowed;
  color: hsl(var(--muted-foreground));
}
```

---

## 📝 Usage Guidelines

### DO ✅

- ✅ Use orange (#FF6B35) for ALL interactive elements
- ✅ Use white cards on black backgrounds for primary content
- ✅ Use dark cards (#181818) for secondary/progress indicators
- ✅ Use `text-[#EAEAEA]` for text on dark surfaces
- ✅ Use orange gradient for completion states (not green)
- ✅ Use design system variables (bg-muted, border-border) not hardcoded colors
- ✅ Use subtle opacity variations for hover (/30, /50)
- ✅ Use `rounded-xl` (12px) for cards
- ✅ Use smooth transitions: `transition-all duration-300`

### DON'T ❌

- ❌ Don't use blue anywhere (not part of brand)
- ❌ Don't use green for progress bars (use orange gradient)
- ❌ Don't mix multiple accent colors (stick to orange)
- ❌ Don't use hardcoded gray values (use design system: muted, border)
- ❌ Don't use full opacity backgrounds on dark (use /30-/50)
- ❌ Don't use multiple shadow styles (stick to sm, md, lg)

---

## 🎨 Code Examples

### Example 1: Dark Progress Card

```tsx
<div className="w-full bg-[#181818] border border-[#2A2A2A] rounded-xl shadow-lg p-6">
  <h3 className="text-lg font-semibold text-[#EAEAEA]">
    Processing...
  </h3>
  <p className="text-sm text-[#EAEAEA]/70 mt-1">
    Please wait while we process your file
  </p>

  {/* Progress Bar */}
  <div className="mt-4 w-full h-3 bg-muted/20 rounded-full border border-[#2A2A2A]">
    <div
      className="h-full transition-all duration-300"
      style={{
        width: '60%',
        background: '#FF6B35'
      }}
    />
  </div>
</div>
```

### Example 2: White Content Card

```tsx
<div className="bg-card rounded-xl border border-border/80 shadow-sm hover:shadow-md transition-shadow p-6">
  <h3 className="text-lg font-semibold text-foreground">
    Upload Files
  </h3>
  <p className="text-sm text-muted-foreground mt-1">
    Drag and drop your audio and timeline files
  </p>
</div>
```

### Example 3: Orange Button

```tsx
<button className="
  bg-orange-500
  hover:bg-orange-600
  text-white
  font-medium
  px-6
  py-3
  rounded-lg
  transition-colors
  duration-200
">
  Process Timeline
</button>
```

---

## 🔧 Implementation Notes

### Tailwind Configuration

The design system is implemented using:
- Tailwind CSS utilities
- Custom color values via `bg-[#HEX]` syntax
- Design system variables from `index.css`
- Shadcn UI components (pre-styled with design system)

### Component Libraries

- **Shadcn UI:** Pre-built components following design system
- **Lucide Icons:** Icon library for consistent iconography
- **React Dropzone:** File upload with design system styling

### Browser Support

- Modern browsers (Chrome, Firefox, Safari, Edge)
- CSS Grid and Flexbox required
- CSS custom properties required

---

## 📚 Reference Components

See these components for correct implementation:

- **Dark Card:** `frontend/src/components/UploadProgress.tsx`
- **White Card:** `frontend/src/components/ProcessingOptionsTable.tsx`
- **Upload Zone:** `frontend/src/components/AudioUploadZone.tsx`
- **Sliders/Switches:** `frontend/src/components/ProcessingOptionsTable.tsx`

---

## 🎯 Brand Identity

**Project:** EasyEdit v2
**Tagline:** AI-Powered Timeline Editor
**Industry:** Video Editing / Post-Production
**Target:** Professional video editors, content creators
**Aesthetic:** Dark, minimal, professional, efficient
**Inspiration:** DaVinci Resolve meets modern SaaS

**Primary Brand Color:** Orange (#FF6B35)
**Visual Identity:** Dark backgrounds, high contrast, orange accents
**Feeling:** Professional, powerful, trustworthy, modern

---

**End of Design System v1.0**

*For questions or updates, refer to this document as the single source of truth for all design decisions.*
