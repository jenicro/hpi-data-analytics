import React, { useEffect, useRef } from "react"
import { Streamlit, withStreamlitConnection, ComponentProps } from "streamlit-component-lib"
import Plotly from "plotly.js-dist-min"

function SunburstSelect({ args }: ComponentProps): React.ReactElement {
  const containerRef = useRef<HTMLDivElement>(null)
  const height = (args.height as number) || 380
  const lastPlotObjRef = useRef<string | null>(null)
  // Monotonic counter so Python can tell a genuine new click from a stale rerun value.
  const clickSeqRef = useRef(0)
  // Whether we've done the initial newPlot (so updates can use react() instead).
  const initializedRef = useRef(false)

  // Purge only on unmount — not on every update — so Plotly.react() can animate.
  useEffect(() => {
    return () => {
      if (containerRef.current) Plotly.purge(containerRef.current)
    }
  }, [])

  useEffect(() => {
    const el = containerRef.current
    const plotObj = args.plot_obj as string | undefined
    if (!el || !plotObj) return
    // Skip redraw when the figure is unchanged (avoids flicker and speed hit on reruns)
    if (lastPlotObjRef.current === plotObj) return
    lastPlotObjRef.current = plotObj

    let fig: { data?: unknown[]; layout?: Record<string, unknown> }
    try {
      fig = JSON.parse(plotObj)
    } catch {
      return
    }
    const data = fig.data || []
    const layout: Record<string, unknown> = {
      ...(fig.layout || {}),
      margin: { t: 30, b: 30, l: 30, r: 30 },
      height,
    }
    const config = {
      scrollZoom: true,
      displayModeBar: true,
      modeBarButtonsToAdd: ["zoomIn2d" as const, "zoomOut2d" as const, "resetScale2d" as const],
    }

    if (!initializedRef.current) {
      // First render: full newPlot + attach event listener
      Plotly.newPlot(el, data, layout, config).then((gd) => {
        gd.on("plotly_sunburstclick", (d: unknown) => {
          const eventData = d as { points?: Array<{ id?: string; label?: string; customdata?: unknown }> }
          const pt = eventData.points?.[0]
          if (pt) {
            const rawId = pt.id ?? pt.customdata
            const id = rawId != null
              ? (Array.isArray(rawId) ? rawId[0] : rawId)
              : pt.label
            if (id != null) {
              clickSeqRef.current += 1
              Streamlit.setComponentValue(JSON.stringify({ id: String(id), seq: clickSeqRef.current }))
            }
          }
          // Let Plotly's default zoom/drill animation run.
        })
      })
      initializedRef.current = true
    } else {
      // Subsequent renders: in-place update that preserves chart state & animations.
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      ;(Plotly as any).react(el, data, layout)
    }
  }, [args.plot_obj, height])

  useEffect(() => {
    Streamlit.setFrameHeight(height + 20)
  }, [height])

  return <div ref={containerRef} style={{ width: "100%", cursor: "pointer" }} />
}

export default withStreamlitConnection(SunburstSelect)
