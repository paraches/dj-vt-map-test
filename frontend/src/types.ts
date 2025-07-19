export interface PointData {
  lat: number;
  lng: number;
  alt?: number | null;
  sequence_number?: number;
}

export interface RoutePoint extends PointData {
  // 追加のプロパティがあればここに
}

export interface RouteDisplayData {
  id: number | string;
  points: RoutePoint[];
  color?: string;
  routeType?: string;
}