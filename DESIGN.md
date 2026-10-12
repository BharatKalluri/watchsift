---
name: WatchSift
description: A compact cinema control panel for IMDb context on Netflix.
colors:
  gold: "#f2cc61"
  gold-hover: "#ffdf87"
  gold-active: "#d6b143"
  charcoal-green: "#1b1e1c"
  field-green: "#272d27"
  divider: "#3a4039"
  muted-green: "#697367"
  text: "#f3efe5"
  label: "#d8dfd1"
  muted-text: "#b8c2b4"
  badge-text: "#171611"
  badge-hover: "#ffe095"
typography:
  wordmark:
    fontFamily: "Georgia, serif"
    fontSize: "25px"
    fontWeight: 500
    letterSpacing: "-0.025em"
  body:
    fontFamily: "Segoe UI, sans-serif"
    fontSize: "13px"
    lineHeight: 1.6
  title:
    fontFamily: "Segoe UI, sans-serif"
    fontSize: "14px"
    fontWeight: 600
  secondary-label:
    fontFamily: "Segoe UI, sans-serif"
    fontSize: "12px"
  hint:
    fontFamily: "Segoe UI, sans-serif"
    fontSize: "11px"
    lineHeight: 1.6
  helper:
    fontFamily: "Segoe UI, sans-serif"
    fontSize: "10px"
  threshold:
    fontSize: "23px"
  badge:
    fontFamily: "Arial, sans-serif"
    fontSize: "12px"
    fontWeight: 700
    lineHeight: 1.4
rounded:
  badge: "4px"
  control: "6px"
  switch: "20px"
spacing:
  small: "8px"
  row: "16px"
  inset: "22px"
components:
  button-primary:
    backgroundColor: "{colors.gold}"
    textColor: "{colors.charcoal-green}"
    rounded: "{rounded.control}"
    padding: "10px 12px"
    width: "100%"
  button-primary-hover:
    backgroundColor: "{colors.gold-hover}"
  button-primary-active:
    backgroundColor: "{colors.gold-active}"
  threshold-input:
    backgroundColor: "{colors.field-green}"
    textColor: "{colors.text}"
    rounded: "{rounded.control}"
    padding: "9px 10px"
    typography: "{typography.threshold}"
  switch:
    backgroundColor: "{colors.muted-green}"
    rounded: "{rounded.switch}"
    width: "34px"
    height: "20px"
  switch-on:
    backgroundColor: "{colors.gold}"
  rating-badge:
    backgroundColor: "{colors.gold}"
    textColor: "{colors.badge-text}"
    rounded: "{rounded.badge}"
    padding: "4px 7px"
    typography: "{typography.badge}"
---

# Design System: WatchSift

## Overview

**Creative North Star: "Compact cinema control panel"**

The implemented extension uses a charcoal-green surface, warm gold controls and an editorial serif wordmark. Plain labels and measured numerals keep the small popup readable. The same gold identifies IMDb badges on Netflix cards.

This captures the code-first direction confirmed in `.impeccable/popup.surface.md`. Source: `extension/popup.html`, `extension/src/popup/popup.css` and `extension/src/content/content.css`; visual evidence: `.impeccable/review/popup.png`, `consent.png` and `cards.png`. Card evidence comes from a synthetic fixture, not live Netflix.

## Colors

Primary: gold marks enabled switches, the save action, AND, links and badges. Hover and pressed buttons use their corresponding gold variants; badges have a separate hover variant.

Neutral: charcoal-green is the popup canvas; field-green separates number fields. Divider lines separate major groups. Muted-green supplies inactive switches, field borders and disabled buttons. Text, label and muted-text form the reading hierarchy.

**The Shared Accent Rule.** Carry the popup's active-state gold through to on-card rating badges.

## Typography

Georgia is reserved for the wordmark. Segoe UI supplies popup text; labels and section titles use the title role. Secondary labels are smaller (12px), hints and consent descriptions smaller again (11px), and footer/helper text smallest (10px).

Threshold values and badge numbers use tabular numerals. Badges use Arial to keep their styling independent of the host page.

## Layout

The Chrome popup has a fixed width (360px), with the inset spacing token around the main controls. Header and footer span its width. Control rows place labels and supporting copy on the left and switches on the right.

The threshold grid uses `1fr 30px 1.35fr`: rating, AND, then the wider vote-count field. The save button spans the grid. Major sections use top borders and generous vertical separation (25px margin, 22px padding). Expanded consent increases document height and scrolls; diagnostic metadata wraps anywhere when needed.

**The Visible AND Rule.** Keep the conjunction between both threshold fields and the explanatory sentence below the save action.

## Elevation & Depth

The extension uses flat tonal separation and thin borders, with no shadows, gradients or backdrop blur. Rating badges sit above host cards at a small inset (6px from left and bottom); they do not redefine card layout.

## Shapes

Fields and buttons share gently rounded control corners. Badges use the smaller badge radius. Switches are pill-shaped with circular thumbs. Dividers remain straight and thin (1px).

## Components

- Save action: full-width gold button; brighter on hover, darker while pressed, muted-green while disabled.
- Number fields: dark green fill, muted-green border, large tabular values and native number validation. Popup keyboard focus uses a gold outline (2px, 4px offset).
- Switches: muted-green off, gold on, charcoal thumb. Hover adds a light outline. The thumb moves over 120ms with ease-out only when reduced motion is not requested; disabled inputs fade to 0.6 opacity.
- Consent disclosure: native summary marker and text. Collapsed initially; the two consent switches remain independent, with their own descriptions. Report details use a nested disclosure.
- Rating badge: compact gold link anchored to the card's lower-left corner, with dark ink protected from host link styles, a brighter hover and white keyboard-focus outline (2px, 3px offset). Below-minimum card content dims to 0.4 opacity while the badge remains fully opaque; content returns to full opacity on hover or focus within. Unknown titles remain visible.

**Passive detail rating.** The existing gold IMDb badge appears in normal flow beneath the main metadata of a user-opened Netflix dialog. Background matching leaves scrolling, navigation and focus untouched; there is no loading overlay or automatic dialog navigation.

## Do's and Don'ts

- **Do** keep visible labels, keyboard-focus outlines and reduced-motion behavior.
- **Do** retain tabular numerals for thresholds and ratings.
- **Do** keep optional sharing in its disclosure and preserve readable, wrapping details.
- **Don't** replace the explicit AND relationship with an ambiguous combined field.
- **Don't** change host-card layout or obstruct its interaction when adding badges.
- **Don't** treat synthetic card screenshots as evidence of live-site reliability.

