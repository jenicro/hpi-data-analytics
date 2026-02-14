import React, { useEffect, useRef } from "react"
import { Streamlit, withStreamlitConnection, ComponentProps } from "streamlit-component-lib"
import Plotly from "plotly.js-dist-min"

function SunburstSelect({ args }: ComponentProps): React.ReactElement {
  const containerRef = useRef<HTMLDivElement>(null)
  const height = (args.height as number) || 380
  const lastPlotObjRef = useRef<string | null>(null)

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

    Plotly.newPlot(el, data, layout, {
      scrollZoom: true,
      displayModeBar: true,
      modeBarButtonsToAdd: ["zoomIn2d", "zoomOut2d", "resetScale2d"],
    }).then((gd) => {
      gd.on("plotly_sunburstclick", (d: unknown) => {
        const eventData = d as { points?: Array<{ id?: string; label?: string }> }
        const pt = eventData.points?.[0]
        if (pt) {
          const id = pt.id !== undefined ? pt.id : pt.label
          if (id != null) {
            Streamlit.setComponentValue(JSON.stringify({ id: String(id) }))
          }
        }
        // Do not return false — let the default zoom/drill animation run
      })
    })

    return () => {
      if (el) Plotly.purge(el)
    }
  }, [args.plot_obj, height])

  useEffect(() => {
    Streamlit.setFrameHeight(height + 20)
  }, [height])

  return <div ref={containerRef} style={{ width: "100%" }} />
}

export default withStreamlitConnection(SunburstSelect)
