// d3-force-3d (a force-graph dependency) ships no types; the explorer graph uses forceCollide.
declare module "d3-force-3d" {
  export function forceCollide<N>(radius: (node: N) => number): {
    (alpha: number): void;
    initialize?: (nodes: N[], ...args: any[]) => void;
    [key: string]: any;
  };
}
