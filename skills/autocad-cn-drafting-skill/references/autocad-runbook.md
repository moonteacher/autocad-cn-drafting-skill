# AutoCAD Operator Runbook

Use full AutoCAD on Windows or macOS. AutoCAD LT for Mac cannot run this
AutoLISP workflow.

1. Start a new blank metric drawing.
2. Confirm no production drawing is open.
3. Run `APPLOAD` and select `autocad-cn-drafting.lsp`.
4. Run `CADBUILD`.
5. Inspect wall joins, openings, furniture, room labels, dimensions, and the
   non-plot review layer.
6. Resolve every item in `space-analysis.md`.
7. Create or adjust a layout viewport. The generated alpha layout creates a
   border and title block but does not assume a machine-specific PC3/CTB.
8. Confirm the available Chinese font. Replace `txt.shx` only with a licensed
   project font.
9. Run `CADAUDIT`.
10. Save DWG, export ASCII DXF, and plot PDF.
11. Run `audit_dxf.py` on the exported DXF.
12. Have a qualified person review all final sheets.

The generated LISP avoids COM and ActiveX. It does not require a Windows-only
.NET plugin.
