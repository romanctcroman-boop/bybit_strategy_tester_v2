/**
 * Type declarations for plotly.js-basic-dist-min
 *
 * Минимальная типизация для динамического импорта Plotly.
 * Полная типизация доступна через @types/plotly.js если нужно расширение.
 */

declare module 'plotly.js-basic-dist-min' {
  export interface PlotlyHTMLElement extends HTMLElement {
    on(event: string, callback: (data: any) => void): void;
    removeAllListeners(event: string): void;
  }

  export interface Layout {
    [key: string]: any;
  }

  export interface Config {
    [key: string]: any;
  }

  export interface Data {
    [key: string]: any;
  }

  export function newPlot(
    root: HTMLElement,
    data: Data[],
    layout?: Partial<Layout>,
    config?: Partial<Config>
  ): Promise<PlotlyHTMLElement>;

  export function react(
    root: HTMLElement,
    data: Data[],
    layout?: Partial<Layout>,
    config?: Partial<Config>
  ): Promise<PlotlyHTMLElement>;

  export function purge(root: HTMLElement): void;
}
