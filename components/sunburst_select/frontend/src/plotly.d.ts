declare module "plotly.js-dist-min" {
  const Plotly: {
    newPlot: (
      el: HTMLElement,
      data: unknown[],
      layout?: object,
      config?: object
    ) => Promise<{ on: (event: string, fn: (d: unknown) => boolean | void) => void }>
    purge: (el: HTMLElement) => void
  }
  export default Plotly
}
