export interface FootballTopology {
  vertices: [number, number, number][];
  pentagons: number[][];
  hexagons: number[][];
}

export interface FootballMeshGroup {
  positions: Float32Array;
  uvs: Float32Array;
  colors: Float32Array;
  seam: Float32Array;
  indices: Uint32Array;
}

export interface FootballMeshData {
  black: FootballMeshGroup;
  white: FootballMeshGroup;
  stats: {
    pentagons: number;
    hexagons: number;
    vertices: number;
    triangles: number;
    params: { radius: number; grooveDepth: number; pillow: number };
  };
}

export interface FootballMeshOptions {
  radius?: number;
  subdivisions?: number;
  edgeBias?: number;
  grooveDepth?: number;
  grooveWidth?: number;
  pillow?: number;
  aoWidth?: number;
  aoStrength?: number;
  uvScale?: number;
}

export interface FlatProjectionPanel {
  color: "black" | "white";
  depth: number;
  points: [number, number][];
}

export function buildTruncatedIcosahedron(): FootballTopology;
export function buildFootballMeshData(options?: FootballMeshOptions): FootballMeshData;
export function buildFootballStitchData(options?: {
  radius?: number;
  spacing?: number;
  stitchLength?: number;
  lift?: number;
}): Float32Array;
export function buildFlatProjection(options?: {
  size?: number;
  yaw?: number;
  pitch?: number;
  samples?: number;
}): FlatProjectionPanel[];
