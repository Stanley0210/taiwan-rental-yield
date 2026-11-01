# Fonts

`NotoSansTC.ttf` — Noto Sans TC (variable, weight axis), from
`google/fonts:ofl/notosanstc`, under the **SIL Open Font Licence 1.1** (`OFL.txt`,
included as the licence requires). It derives from Adobe's Source Han Sans —
the licence file carries Adobe's copyright and the reserved font name 'Source'.

It is here, and committed rather than downloaded on demand, because
`housing_report.py` **embeds** it in the PDF and a PDF that renders Chinese
depends on it. Two things make an OFL font the right choice over the alternatives:

- reportlab's built-in CID fonts (`UnicodeCIDFont('MSung-Light')`) are **not
  embedded**. On a viewer without the Adobe Asian font pack they render the
  *wrong glyphs* rather than none — 實價登錄 came out as 巋牝岫完. That looks like
  text, so nothing fails loudly.
- macOS system fonts (STHeiti, Songti) render correctly but may not be embedded
  in a document that gets redistributed. This one may.

**Do not subset it.** The report is generated from live registry data, so the
glyph set is not known in advance — a subset would silently drop a character in
some district or building name.
