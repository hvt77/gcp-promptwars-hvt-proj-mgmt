# UI & UX Layout Specification

## Design System
- **Theme:** Enterprise Dark Slate (`bg-slate-900`, `text-slate-100`, accent `blue-600`).
- **Layout:** Responsive sidebar navigation or tabbed header using Alpine.js (`x-data="{ tab: 'pipeline' }"`).
- **Widgets:** 
  - Summary KPI cards at top (Total Pipeline Value, Active Project Health, Total Billable Hours, Outstanding Invoices).
  - Data tables with clean borders and status badges (Green/Amber/Red pills).
  - Modal or inline forms for creating records without page reloads.