// One-page, single-column resume. All content arrives as JSON in
// sys.inputs.data (see app/render.py); strings are inserted as plain text,
// so nothing in the warehouse is ever parsed as Typst markup.

#let data = json(bytes(sys.inputs.data))
#let st = data.style
#let accent = rgb(st.accent)
#let muted = rgb("#555555")
#let tight = st.theme == "compact"

#set document(title: data.name + " — Resume", author: data.name)
#set page(paper: data.at("paper", default: "us-letter"), margin: (x: st.margin_x * 1in, y: st.margin_y * 1in))
#set text(font: st.font, size: data.font_size * 1pt, hyphenate: false)
#set par(justify: false, leading: st.leading * 1em, spacing: if tight { 0.45em } else { 0.55em })
#set list(indent: 0.5em, body-indent: 0.45em, spacing: if tight { 0.3em } else { 0.32em }, marker: text(fill: muted)[•])
#show link: set text(fill: accent)

#let section(title) = {
  v(if tight { 0.3em } else { 0.45em })
  if st.heading == "caps" {
    text(size: 0.95em, weight: "bold", fill: accent, tracking: 0.12em, upper(title))
  } else if st.heading == "bold" {
    text(size: 1.05em, weight: "bold", fill: accent, title)
  } else {
    text(size: 1.12em, weight: "bold", fill: accent, smallcaps(title))
  }
  v(-0.45em)
  line(length: 100%, stroke: (if st.heading == "caps" { 0.4pt } else { 0.6pt }) + accent)
  v(-0.15em)
}

#let row(start, end) = grid(
  columns: (1fr, auto),
  column-gutter: 1em,
  start, align(right, end),
)

#let maybe(value) = if value == none { "" } else { value }

// Header
#align(center)[
  #text(size: 2.1em, weight: "bold", fill: if st.theme == "modern" { accent } else { black })[#data.name]
  #v(-0.35em)
  #text(size: 0.95em, data.contact.map(c => if c.url == none { c.text } else { link(c.url, c.text) }).join(h(0.35em) + text(fill: muted)[|] + h(0.35em)))
]

#for sec in data.sections {
  if sec.kind == "education" and sec.entries.len() > 0 {
    section("Education")
    for e in sec.entries {
      row(strong(e.school), maybe(e.dates))
      if e.degree != none { v(-0.3em); emph(e.degree) }
      for d in e.details { v(-0.3em); text(size: 0.95em, d) }
    }
  } else if sec.kind == "items" and sec.entries.len() > 0 {
    section(sec.title)
    for (i, e) in sec.entries.enumerate() {
      if i > 0 { v(0.15em) }
      let head = if e.tech.len() > 0 {
        strong(e.title) + text(fill: muted)[ | ] + emph(e.tech.join(", "))
      } else { strong(e.title) }
      row(head, maybe(e.dates))
      if e.org != none or e.location != none {
        v(if tight { -0.2em } else { -0.3em })
        row(emph(maybe(e.org)), emph(maybe(e.location)))
      }
      v(-0.2em)
      list(..e.bullets.map(b => [#b]))
    }
  } else if sec.kind == "skills" and sec.entries.len() > 0 {
    section("Skills")
    [#strong[Technical:] #sec.entries.join(", ")]
  }
}
