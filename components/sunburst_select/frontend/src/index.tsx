import React from "react"
import { createRoot } from "react-dom/client"
import SunburstSelect from "./SunburstSelect"

const root = document.getElementById("root")
if (root) {
  createRoot(root).render(
    <React.StrictMode>
      <SunburstSelect />
    </React.StrictMode>
  )
}
