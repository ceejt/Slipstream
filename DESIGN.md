# DESIGN.md

Design system for the SlipStream prediction reports (`reports/*.html`, rendered by `src/f1pred/report.py`).

The look follows the Formula 1 race page (`formula1.com/en/racing/2026/united-states`). Values marked **observed** were read from that page's CSS on 2026-10-25. Values marked **decision** are SlipStream's own choices where the F1 page gives no rule.

Race reports stay one self-contained HTML file: no images, no icons, and no JavaScript of our own. The index page is the one exception: it has two small inline scripts (open a linked race, and the intro in section 7) and can load an optional car image and engine sound from `reports/assets/`. The only external requests allowed are the web font link and the Vercel Web Analytics script (`/_vercel/insights/script.js`), which is served by the host and counts visits without cookies.

## 1. Branding identity

**Name:** SlipStream. The brand is a plain text wordmark. Colors and type style are the only things borrowed from the F1 page.

**Design principle: a timing screen, not a dashboard.**
The page should read like a live timing tower: dense, flat, tabular, and fast to scan. The following rules keep it from looking like a generic generated page:

1. **Data first.** The page opens with the result and the table, not with a hero or a summary paragraph.
2. **Red is a signal.** F1 red marks probability (the bar) and one accent per section. It is never a background wash, a button color, or decoration.
3. **Flat.** No drop shadows, no gradients, no glassy cards. Surfaces are separated by tone and 1px rules. (observed: the F1 CSS has no soft shadows.)
4. **Uppercase labels, mixed-case values.** Labels and column heads are small uppercase. Names and numbers are large and bold.
5. **One type voice for numbers.** Every number (positions, grid, percentages) uses the same bold face and aligns in columns.
6. **Team color as identity.** Podium cards are a full block of the team's dark card color, as on formula1.com/en/drivers, and table rows carry a thin team stripe. There are no accent stripes on cards. This replaces the gold, silver and bronze medals, which read as generic.
7. **No filler.** If a block does not show a result or explain one, remove it.

## 2. Theme

Two themes. **Decision:** dark is the default because it matches the F1 timing look. The report switches to light when the viewer's system asks for it.

```css
:root { /* dark (default) */ }
@media (prefers-color-scheme: light) { :root { /* light */ } }
```

Both palettes are given in section 3. No theme toggle button is needed.

Elevation is tone, not shadow. Surfaces from lowest to highest:

| Layer | Dark | Light |
|---|---|---|
| Page background | `--bg` | `--bg` |
| Card / table surface | `--surface` | `--surface` |
| Rule / divider | `--rule` | `--rule` |

## 3. Colors

All colors are 6-digit hex.

### Brand
| Token | Hex | Use | Source |
|---|---|---|---|
| `--red` | `#E10600` | Probability bar fill, key accent, hit/active marker | observed (the most used non-neutral on the page) |
| `--red-deep` | `#CA0500` | Red text on light backgrounds, pressed state | observed |
| `--red-tint-light` | `#F6B4B2` | Soft red on dark backgrounds | observed (accent hot red 20, dark variant is `#710E10`) |
| `--purple` | `#5300A6` | Reserved for "best" markers, such as the top probability | observed (sector purple) |

### Neutrals (observed, F1 surface scale)
| Token | Dark | Light |
|---|---|---|
| `--bg` | `#15151E` | `#F7F4F1` |
| `--surface` | `#26262B` | `#FFFFFF` |
| `--surface-2` | `#303037` | `#E0DEDC` |
| `--rule` | `#47464C` | `#CDCDCD` |
| `--text` | `#FFFFFF` | `#15151E` |
| `--text-2` | `#F7F4F1` | `#15151E` |
| `--muted` | `#AAAAAA` | `#606066` |

Notes:
- `--bg` in dark mode is not pure black. F1's page background is `#15151E`, a deep navy-black. Pure `#000000` is used only for the page's heaviest overlays, so do not use it as the background.
- The light background is a warm off-white (`#F7F4F1`), not `#FFFFFF`. White is for cards.
- **Documented exception:** the Impeccable detector flags `#F7F4F1` as a "cream palette" default. It is F1's own light neutral (`surface-neutral-3`), taken from their CSS to follow their branding, so it stays. It only applies in light mode.

### Team colors (stripe on podium cards and table rows)
Read from the team-logo background colors on `formula1.com/en/results/2026/team` on 2026-10-25. **Decision:** a team not listed gets a hollow stripe (1px `--muted` outline, no fill) so it reads as "no color on file", not as a styled grey. Add new teams only after checking the value on formula1.com.

| Team | Hex |
|---|---|
| Mercedes | `#27F4D2` |
| Red Bull | `#3671C6` |
| Ferrari | `#E8002D` |
| McLaren | `#FF8000` |
| Aston Martin | `#229971` |
| Racing Bulls | `#6692FF` |
| Alpine | `#00A1E8` |
| Audi | `#FF2D00` |
| Cadillac | `#AAAAAD` |
| Williams | `#1868DB` |
| Haas | `#DEE1E2` |

Haas and Cadillac are near white and grey, so every stripe carries a 1px `--rule` inset outline to stay visible on both themes.

### Podium card colors
Each F1 driver card uses a darkened shade of the team color so white text stays readable. Read from `formula1.com/en/drivers` (`--f1-accessible-colour`) on 2026-10-25. Card text is always `#FFFFFF`, in both themes.

| Team | Card color | White text contrast |
|---|---|---|
| Alpine | `#004E70` | 9.0:1 |
| Aston Martin | `#0F4331` | 11.2:1 |
| Audi | `#751500` | 11.3:1 |
| Cadillac | `#58585B` | 7.1:1 |
| Ferrari | `#5C0012` | 14.4:1 |
| Haas | `#667175` | 5.0:1 |
| McLaren | `#804000` | 7.9:1 |
| Mercedes | `#067E6A` | 5.0:1 |
| Racing Bulls | `#0038C2` | 9.0:1 |
| Red Bull | `#142948` | 14.6:1 |
| Williams | `#082145` | 16.0:1 |

A team with no color on file gets a neutral card (`--surface-2`, theme text color). Use solid white for all card text. Opacity tricks drop the lighter cards (Mercedes, Haas) under 4.5:1.
Match team names with a lookup table in `report.py` (for example `"Red Bull"` and `"Red Bull Racing"` map to the same value). Unknown names get the hollow stripe, so a new constructor never breaks the page.

### CSS tokens
```css
:root {
  --red: #E10600; --red-deep: #CA0500; --purple: #5300A6;
  --bg: #15151E; --surface: #26262B; --surface-2: #303037; --rule: #47464C;
  --text: #FFFFFF; --text-2: #F7F4F1; --muted: #AAAAAA;
}
@media (prefers-color-scheme: light) {
  :root {
    --bg: #F7F4F1; --surface: #FFFFFF; --surface-2: #E0DEDC; --rule: #CDCDCD;
    --text: #15151E; --text-2: #15151E; --muted: #606066;
  }
}
```

### Color rules
- Red text on dark backgrounds is only for large text (24px and up). For small red text use `--red-tint-light`.
- Red text on light backgrounds uses `--red-deep` for small sizes.
- Never use green. In this report red means "model probability", and a second signal color would dilute it.
- Hits and misses in a backtest use words ("HIT", "MISS"), not green and red.

## 4. Typography

### What F1 uses (observed)
| Role | F1 font | Notes |
|---|---|---|
| Display (headings, big numbers) | Formula1 (weights 400, 500, 900, plus 400 italic) | Proprietary |
| Wide display | Formula1Wide (500) | Proprietary |
| Tabular numerals | Formula1Digits (400) | Proprietary |
| Body | Titillium Web (300 to 700, with italics) | Open source (SIL OFL) |
| Technical data (times, gaps) | KH Interference F1 (400, 700) | Proprietary |

### What SlipStream can use
The Formula1 and KH Interference fonts are licensed to F1 and are not free to embed or link. Do not copy their font files. **Titillium Web is the one F1 font that is open source, and it is the same face F1 uses for body text.**

| Role | Stack | Weight |
|---|---|---|
| Display | `"Formula1", "Titillium Web", system-ui, sans-serif` | 900, uppercase |
| Body | `"Titillium Web", system-ui, sans-serif` | 400, 600, 700 |
| Numbers | `"Titillium Web", system-ui, sans-serif` | 700, with `font-variant-numeric: tabular-nums` |

The first name in the display stack only renders for viewers who have Formula1 installed. Everyone else sees Titillium Web Black, which is close in weight and tone but not identical. Accept this: matching exactly would mean using a font we cannot license.

Load the open font with one link in `<head>`:
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Titillium+Web:wght@400;600;700;900&display=swap" rel="stylesheet">
```
If a report must work offline, embed the four weights as base64 `@font-face` instead (about 100 KB). The fallback stack keeps the page readable if the font fails to load.

### Type scale (observed sizes and line heights, F1 `typography-module`)
| Style | Size / line height | Weight | Font | Use here |
|---|---|---|---|---|
| `display-4xl` | 48px / 52px | 900 | Display | Podium position (P1) |
| `display-3xl` | 40px / 44px | 900 | Display | Page title (mobile: `display-2xl`) |
| `display-2xl` | 32px / 38px | 900 | Display | Driver code on podium cards |
| `display-xl` | 24px / 28px | 900 | Display | Section heading |
| `display-l` | 20px / 24px | 500 | Display | Sub heading |
| `display-m` | 16px / 22px | 500 | Display | Table driver code |
| `display-s` | 12px / 16px | 500 | Display | Labels (uppercase) |
| `body-m` | 17px / 28px | 400 | Body | Note text |
| `body-s-compact` | 16px / 20px | 600 | Body | Team name |
| `body-xs` | 14px / 16px | 600 | Body | Table cells |
| `body-2xs` | 12px / 16px | 600 | Body | Reasons, footnotes |
| `technical-xl` | 24px / 24px | 700 | Numbers | Podium probability |
| `technical-s` | 14px / 14px | 700 | Numbers | Table numbers |

### Rules
- Letter spacing is `0` everywhere, except uppercase labels at `0.5px`. (observed: 544 uses of `0`, 24 of `.5px`.)
- Page title, column heads and labels are uppercase. Driver codes are always uppercase (VER, ANT).
- Left align text. Right align numbers in tables so decimals line up.
- Use at most two weights on one screen region.

## 5. Spacing

F1's CSS is built on a Tailwind-style 4px grid. **Decision:** use the same scale.

| Token | px | Use |
|---|---|---|
| `--s1` | 4 | Gap between stripe and text |
| `--s2` | 8 | Inline gaps, chip padding |
| `--s3` | 12 | Cell padding (vertical) |
| `--s4` | 16 | Cell padding (horizontal), mobile page margin |
| `--s6` | 24 | Card padding, tablet page margin |
| `--s8` | 32 | Section gap, desktop page margin |
| `--s12` | 48 | Gap between page blocks |

### Breakpoints (observed)
| Name | Width | Change |
|---|---|---|
| Mobile | below 735px | Podium is one column, table hides the Team column |
| Tablet | 735px and up | Podium is three columns |
| Desktop | 1069px and up | Page margin grows to 32px |
| Wide | 1696px and up | Content stays centered; no further growth |

### Layout
- **Content width:** max 973px, centered (observed content column width).
- **Border radius (observed values):** `0` for the page and table, `4px` for the probability bar and tags, `8px` for podium cards. Avoid a single radius on everything; it is the main reason pages look generated.
- **Rules:** 1px `--rule` lines between table rows. No borders around cards. Cards are separated by tone.
- **Row height:** 44px minimum in the table.

## 6. Components

### 6.1 Page header
```
SLIPSTREAM                                   <- wordmark bar, display black, 1px rule below; links to the GitHub repo
UNITED STATES GRAND PRIX                     <- h1, display, uppercase
[UPCOMING]  Round 18, 2026  ·  Trained on 87 earlier races  ·  Made 2026-10-25 17:46 UTC
Raw model output, not calibrated. Has not yet beaten a grid-order baseline (82 races
through 2026 round 17). Grid is the qualifying order, so penalties are not included.
```
- Race pages have a "Back to all races" button on the right of the wordmark bar. It is a plain text link in a 1px outlined, 4px-radius box that links to `index.html`. The index page has no such button. There is no arrow glyph or icon.
- No eyebrow above the title. The round and year sit in the meta line.
- The tag is a 4px-radius box with a 1px border. `UPCOMING` uses the red tint (dark) or deep red (light). `SCORED` (a pre-race prediction with its result added) and `BACKTEST` use `--muted`. A scored page also shows when the result was added in the meta line.
- The claim sentence is body text (16px, regular), not a footnote. Its baseline sentence is generated from `data/evaluation.json` (written by `evaluate`) and stored in each prediction at the time it is made. It says "Has beaten" only when the model beats the grid logistic on Brier score and log loss and the grid order on top-3 overlap. Otherwise it says "Has not yet beaten". If no evaluation exists, the sentence is left out.
- Backtest only: a summary line follows ("2 of 3 picks finished on the podium. On the podium but not picked: HAM (2nd).").

### 6.2 Podium (three cards)
Section label: "Highest podium probability". The pattern follows the F1 driver card: a full block of the team's card color, 8px radius, 16px padding, white text, 256px minimum height on desktop.

- `Pick 1`, `Pick 2`, `Pick 3`: small uppercase label. These are not predicted finishing positions.
- Name: first name in regular weight (20px) above the surname in bold (32px, 28px on phones), as on F1's cards. The names come from `results.csv`; if a name is missing, the driver code is shown as the surname.
- Team and grid: "Red Bull · starts 2nd", 14px semibold
- Probability: 36px bold, one decimal ("84.4%"), with "podium probability" beneath. It sits at the bottom of the card so the three cards line up.
- Backtest only: an outcome line with a bordered marker (`HIT` solid, `MISS` dashed, both in the card's text color) and the result ("Finished 3rd", "Did not finish")
- Reasons: three plain-language lines, strongest first ("Starts 2nd", "Retires in 14% of races"), each with a "+" or "-" sign
- No stripe, border, shadow or gradient on the card. Not used from F1's card: the diagonal pattern image, the driver number image, the country flag, and the side gradient (all image assets).
- Phones: two columns inside the card (names left, probability right), so three picks stay compact

### 6.3 Probability bar (keep from the current design)
The existing bar stays. Only the tokens change.

```css
.bar { height: 8px; background: var(--surface-2); border-radius: 4px; min-width: 48px; }  /* 80px from 735px up */
.bar i { display: block; height: 100%; background: var(--red); border-radius: 4px; }
```
- Always show the number next to the bar. The bar alone does not meet the 3:1 contrast target on the dark track (see section 8).
- Do not put a label inside the bar.

### 6.4 Results table
- Header row: `display-s`, uppercase, `--muted`, bottom rule 1px `--rule`.
- Columns: Rank (by probability), Driver (with a 4px team stripe element), Team, Grid, Podium probability (bar and value together).
- Backtest adds one Finished column. Only the three picks get a marker beside the result: `HIT` if they finished in the top 3, otherwise `MISS`. A retirement reads `DNF`, and a missing result reads `n/a`.
- Row hover: background `--surface-2`, `0.15s`. No zebra stripes.
- Numbers: `technical-s`, right aligned, tabular figures.

### 6.5 Footer
Regular weight, 14px, `--muted`, max 68 characters wide. It explains how to read the page: "Probabilities are independent for each driver, so they do not add up to 100%. Reasons are the three features that moved a pick's score most, strongest first." The caveats about calibration and penalties are in the claim sentence at the top, not here.

### 6.6 Credit line
`Made by ceejt`, below a 1px `--rule` line at the very end of the page. "ceejt" links to `https://ceejt-portfolio.vercel.app/` (opens in a new tab, `rel="noopener noreferrer"`).

The link is the one decorative element on the page, by request: a reflective chrome finish made from banded text color (`--chrome-lo` and `--chrome-hi`, 105 degree bands every 18px), a 1px edge highlight, 17px bold. Bands stay within contrast on each theme (dark: `#8A8A92` to `#FFFFFF`; light: `#15151E` to `#5A5A62`, both at least 4.5:1 on the page background). It keeps a visible underline, so it reads as a link even where `background-clip: text` is unsupported. In that case the link falls back to the plain bold text color.

On hover or keyboard focus the bands shift by half a band over 0.8 seconds, once. Nothing loops. This is a documented exception to "animate only width, background-color, color" and to the flat rule.

### 6.7 "How it works" section
A reading section at the bottom of every report and of the index page, above the credit line. It is the one place with running prose, so it follows reading rules instead of the data-table rules.

- Heading: the same small uppercase label as other sections ("How it works"). Sub-headings are 20px bold body text, in plain sentence case, not uppercase.
- Text: 16px on 24px, regular weight, at most 68 characters wide. One short list (what the model looks at). No images, diagrams or icons.
- Content, in order: what the model looks at; how it turns facts into a percentage; why each pick has reasons; how it is checked; what it does not know.
- Voice: plain and direct, no formulas. Terms are explained the first time they appear (podium, walk-forward testing, Brier score, log loss, SHAP).
- The comparison table (first three on the grid, a formula on grid position, the SlipStream model) is built from the saved `data/evaluation.json`, so its numbers and the verdict sentence under it cannot drift from the evaluation. With no saved evaluation, the table and verdict are left out and the rest still shows.
- When the model changes (new features, a DNF model, weather), the text in `_method_html` must change with it. The tests check that the section and its table render, not that the prose is still true.

## 7. Animations

Keep motion small. It supports reading; it does not decorate.

| Where | What | Duration | Easing |
|---|---|---|---|
| Probability bars | Width grows from 0 to its value on load, one row after another (30ms offset per row) | 300ms | `cubic-bezier(0.4, 0, 0.2, 1)` |
| Table row hover | Background fades in | 150ms | `cubic-bezier(0.4, 0, 0.2, 1)` |
| Links | Color change | 150ms | same |
| Credit link | Chrome bands shift half a band on hover or focus, once | 800ms | `cubic-bezier(0.4, 0, 0.2, 1)` |

Durations and easing are observed on the F1 page (`.3s`, `.15s`, `cubic-bezier(.4,0,.2,1)`).

**Intro (decision, index page only).** A full-screen overlay with the wordmark, a cartoon car on a dashed road line, and a Skip button. After 0.8s the car drives left to right in 1.7s with smoke puffs behind it, then the overlay fades out in 300ms. The optional engine sound is tried when the car starts and stays silent if the browser blocks it (browsers usually allow sound only after a click). It shows once per browser session (`sessionStorage`), never with reduced motion or a `#race` link, and Escape or Skip ends it. While it shows, the page behind is `inert`. This is the one deliberate exception to the rules below.

Rules:
- No page-load fades, parallax, or looping animation, except the index intro above.
- Animate only `width`, `background-color`, `color`. Never animate layout.
- The F1 page has no reduced-motion rule. **SlipStream must add one:**

```css
@media (prefers-reduced-motion: reduce) {
  * { transition: none !important; animation: none !important; }
}
```
The bars then render at their final width at once.

## 8. Accessibility

Target: WCAG 2.2 level AA. Contrast ratios below were computed from the hex values in section 3.

### Contrast
| Pair | Ratio | Result |
|---|---|---|
| `#FFFFFF` on `#15151E` (text, dark) | 18.1:1 | Pass |
| `#AAAAAA` on `#15151E` (muted, dark) | 7.8:1 | Pass |
| `#AAAAAA` on `#26262B` (muted on card, dark) | 6.5:1 | Pass |
| `#15151E` on `#F7F4F1` (text, light) | 16.6:1 | Pass |
| `#606066` on `#F7F4F1` (muted, light) | 5.7:1 | Pass |
| `#FFFFFF` on `#E10600` (white on red) | 5.0:1 | Pass |
| `#FFFFFF` on team card colors (section 3) | 5.0:1 to 16.0:1 | Pass, lowest are Mercedes and Haas |
| `#E10600` on `#F7F4F1` (red text, light) | 4.5:1 | Pass, borderline |
| `#CA0500` on `#F7F4F1` (deep red text, light) | 5.4:1 | Pass |
| `#E10600` on `#15151E` (red text, dark) | 3.7:1 | Large text only |
| `#E10600` on `#303037` (bar fill on dark track) | 2.6:1 | Fails the 3:1 graphic target |
| `#E10600` on `#E0DEDC` (bar fill on light track) | 3.7:1 | Pass |
| `#AAAAAA` on `#F7F4F1` | 2.1:1 | Fail. Never use dark-mode muted on light |

Consequences:
- The bar's meaning must not depend on color or contrast. The percentage is always printed beside it.
- Do not use the dark `--muted` value on light backgrounds. The tokens in section 3 already swap it.
- Small red text on dark backgrounds uses `--red-tint-light`.

### Rules
1. **Language and structure.** `<html lang="en">`, one `<h1>`, section headings in order, a real `<table>` with `<th scope="col">` for the data table.
2. **Not by color alone.** Hit and miss use the words HIT and MISS. Team color stripes are decoration; the team name is always written.
3. **Bars.** Mark the bar container `role="img"` with `aria-label="84 percent podium probability"`, or make it `aria-hidden="true"` since the number is next to it. Use the second option to avoid reading the value twice.
4. **Focus.** There are no interactive elements today, but if links are added, use F1's focus style: `outline: 2px solid var(--text); outline-offset: 2px;` (observed: `2px solid` with offset `2px`, in the highest-contrast neutral).
5. **Text size.** Body text is never below 12px, and tables use 14px. Layout must work at 200% zoom without horizontal scrolling.
6. **Motion.** Respect `prefers-reduced-motion` (section 7).
7. **Touch targets.** Rows are 44px high. Any future link or button needs at least 44 by 44px.
8. **Escaping.** All event names and driver names go through `html.escape` (the current code already does this and `test_predict.py` covers it).

## 9. Status of `report.py`

Implemented in `src/f1pred/report.py`: F1-style podium cards with driver names, the credit line, the methodology section, an index page, tokens and both themes, Titillium Web, team stripes with a hollow fallback, the header and claim sentence, "Pick" labels, backtest outcome lines and summary, the merged probability column, plain-language reasons, focus and selection styles, reduced motion, and tests in `tests/test_predict.py`.

Not done: folding the many sub-1% rows, a reasons view for drivers outside the top three, and an index page listing past reports.

## 10. Sources

- F1 race page CSS, read 2026-10-25: custom properties (`--f1rd-colour-*`), `typography-module` classes, `@font-face` declarations, breakpoints at 735px, 1069px and 1696px, transitions of `.15s` and `.3s`, and the `2px` focus outline.
- Contrast ratios: computed from the hex values with the WCAG relative luminance formula.
- Fonts: Titillium Web is licensed under the SIL Open Font License 1.1. Formula1, Formula1Wide, Formula1Digits and KH Interference F1 are proprietary to Formula 1 and are not used or redistributed here.
