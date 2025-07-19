// frontend/src/components/GoogleMapViewer.tsx
import React, { useEffect, useRef } from 'react';
import {
  APIProvider,
  Map,
  AdvancedMarker,
  Pin,
  useMap,
  type MapMouseEvent as VisGLMapMouseEvent,
} from '@vis.gl/react-google-maps';

// ★ 型定義は types/index.ts からインポートする形に統一
import type { RouteDisplayData, RoutePoint, PointData } from '@/types';

// 親コンポーネント(RouteCreatorPage)と型を合わせる
interface PointDataForMap {
  lat: number;
  lng: number;
  alt?: number | null;
}

// ★★★ props の型定義 ★★★
// onPointDragEnd の引数の型を、より汎用的な形に変更
interface GoogleMapViewerProps {
  apiKey: string;
  initialCenter: { lat: number; lng: number };
  initialZoom: number;
  routes?: RouteDisplayData[];
  onMapClick?: (latLngValue: PointDataForMap) => void;
  onPointDragEnd?: (updatedPoints: RoutePoint[]) => void; // ドラッグ後の全ポイント配列を受け取る
  onPointDelete?: (routeIndex: number, pointIndex: number) => void; // ルートポイント削除用
  isDraggable?: boolean;
  backgroundPolygons?: { points: PointData[], color?: string }[];
  boundsToFit?: google.maps.LatLngBounds | google.maps.LatLngBoundsLiteral | null;
}


// ===================================================================
// ★ 1. ルートとマーカーの描画、およびマーカーのインタラクション専門のコンポーネント
// ===================================================================
interface RouteRendererProps {
  routes: RouteDisplayData[];
  isDraggable: boolean;
  onPointDragEnd?: GoogleMapViewerProps['onPointDragEnd'];
  onMarkerDragStart?: () => void;
  onMarkerDragEndPostProcess?: () => void;
  onPointDelete?: (routeIndex: number, pointIndex: number) => void; // ルートポイント削除用
}

const RouteRenderer: React.FC<RouteRendererProps> = ({ 
  routes, 
  isDraggable, 
  onPointDragEnd,
  onMarkerDragStart,
  onMarkerDragEndPostProcess,
  onPointDelete,
}) => {
  const map = useMap();
  const polylinesRef = useRef<google.maps.Polyline[]>([]);

  // Polyline描画のuseEffect
  useEffect(() => {
    if (!map) return;
    polylinesRef.current.forEach(p => p.setMap(null));
    polylinesRef.current = [];

    routes.forEach(route => {
      if (route.points.length > 1) {
        console.log("Drawing route type:", route.routeType);
        const path = route.points.map((p: RoutePoint) => ({ lat: p.lat, lng: p.lng }));
        // ★ 閉じる処理を追加
        if (route.routeType === 'place_list_ring') {
          path.push(path[0]);
        }

        const newPolyline = new google.maps.Polyline({
          // ★★★ 加工済みの `path` 変数をここで使う ★★★
          path: path,
          
          strokeColor: route.color || '#FF0000',
          strokeOpacity: 0.8,
          strokeWeight: 4,
        });

        newPolyline.setMap(map);
        polylinesRef.current.push(newPolyline);
      }
    });
  }, [map, routes]);

  // ★ マーカードラッグ終了時の処理
  const handleMarkerDragEnd = (event: google.maps.MapMouseEvent, routeIndex: number, pointIndex: number) => {
    if (!onPointDragEnd) return;

    // ドラッグ後の新しい座標
    const newPosition = {
      lat: event.latLng!.lat(),
      lng: event.latLng!.lng(),
    };

    // ルートが1つしかない前提で、そのルートのポイント配列を更新する
    // (RouteCreatorPageでのみドラッグが有効なため)
    const targetRoute = routes[routeIndex];
    if (targetRoute) {
      const updatedPoints = targetRoute.points.map((point: RoutePoint, index: number) => {
        if (index === pointIndex) {
          // ドラッグされたポイントの座標を更新
          return { ...point, lat: newPosition.lat, lng: newPosition.lng };
        }
        return point;
      });
      // 親コンポーネント(RouteCreatorPage)に更新後のポイント配列を通知
      onPointDragEnd(updatedPoints);
    }
    
    // ドラッグ終了後の後処理を親に依頼
    if (onMarkerDragEndPostProcess) {
      onMarkerDragEndPostProcess();
    }
  };

  const handleMarkerClick = (event: google.maps.MapMouseEvent, routeIndex: number, pointIndex: number) => {
    // event.domEvent から元のブラウザイベントを取得できる
    const domEvent = event.domEvent as MouseEvent;

    // MacのCommandキー、またはWindows/LinuxのCtrlキーが押されているかチェック
    if (domEvent.metaKey || domEvent.ctrlKey) {
      if (onPointDelete) {
        // 親に削除を通知
        onPointDelete(routeIndex, pointIndex);
      }
    }
    // 通常のクリックでは何もしない（将来的に情報表示などに使える）
  };

  return (
    <>
      {routes.map((route, routeIndex) =>
        route.points.map((point: RoutePoint, pointIndex: number) => (
          <AdvancedMarker
            key={`route-${route.id}-point-${point.sequence_number}`}
            position={{ lat: point.lat, lng: point.lng }}
            title={`R${route.id}-P${point.sequence_number}`}
            draggable={isDraggable}
            onDragStart={onMarkerDragStart}
            onDragEnd={(e) => handleMarkerDragEnd(e, routeIndex, pointIndex)}
            onClick={(e) => handleMarkerClick(e, routeIndex, pointIndex)}
          >
            <Pin
              background={route.color || '#FF0000'} // Polylineと同じ色を指定
              borderColor={'#FFFFFF'}                 // 枠線は白で見やすく
              glyphColor={'#FFFFFF'}                   // 数字の色も白
            >
              {point.sequence_number?.toString() ?? ''}
            </Pin>
          </AdvancedMarker>
        ))
      )}
    </>
  );
};

interface BackgroundPolygonRendererProps {
  polygons: {
    points: PointData[];
    color?: string;
  }[];
}

const BackgroundPolygonRenderer: React.FC<BackgroundPolygonRendererProps> = ({ polygons }) => {
  const map = useMap();
  const polygonRefs = useRef<google.maps.Polygon[]>([]);

  useEffect(() => {
    if (!map) return;
    // 既存のポリゴンを削除
    polygonRefs.current.forEach(p => p.setMap(null));
    polygonRefs.current = [];

    polygons.forEach(polygonData => {
      if (polygonData.points.length > 2) { // ポリゴンは3点以上必要
        const newPolygon = new google.maps.Polygon({
          paths: polygonData.points,
          fillColor: polygonData.color || '#A9D0F5',
          fillOpacity: 0.3,
          strokeColor: polygonData.color || '#A9D0F5',
          strokeOpacity: 0.7,
          strokeWeight: 2,
          clickable: false,
        });
        newPolygon.setMap(map);
        polygonRefs.current.push(newPolygon);
      }
    });

  }, [map, polygons]);

  return null; // このコンポーネントはポリゴンを描画するだけなので、何も返さない
}


// ===================================================================
// ★ 2. 地図本体と、全体のインタラクションを管理するコンポーネント
// ===================================================================
const InnerMap: React.FC<Omit<GoogleMapViewerProps, 'apiKey'>> = ({
  initialCenter,
  initialZoom,
  routes = [],
  onMapClick,
  onPointDragEnd,
  onPointDelete,
  backgroundPolygons = [],
  boundsToFit,
  isDraggable = false,
}) => {
  console.log("GoogleMapViewer received routes:", routes);
  console.log("%c2. InnerMap received props:", "color: green; font-weight: bold;", {
    routes: routes,
    backgroundPolygons: backgroundPolygons,
  });

  const map = useMap();

  useEffect(() => {
    if (!map || !boundsToFit) return;
    
    console.log("Fitting map to new bounds:", boundsToFit);
    map.fitBounds(boundsToFit);

  }, [map, boundsToFit]); // mapとboundsToFitが変わったら実行

  // ドラッグ状態の管理は InnerMap で行う
  const isDraggingMarkerRef = useRef(false);

  const handleMapClick = (event: VisGLMapMouseEvent) => {
    if (isDraggingMarkerRef.current) return;
    
    if (onMapClick && event.detail.latLng) {
      onMapClick({
        lat: event.detail.latLng.lat,
        lng: event.detail.latLng.lng,
        alt: null,
      });
    }
  };

  // ドラッグ開始/終了時に isDraggingMarkerRef を更新する関数
  const handleMarkerDragStart = () => {
    isDraggingMarkerRef.current = true;
  };

  const handleMarkerDragEndPostProcess = () => {
    setTimeout(() => {
      isDraggingMarkerRef.current = false;
    }, 0);
  };

  return (
    <Map
      defaultCenter={initialCenter}
      defaultZoom={initialZoom}
      gestureHandling={'greedy'}
      disableDefaultUI={false}
      mapId={'unifiedMap'}
      onClick={handleMapClick}
    >
      <BackgroundPolygonRenderer polygons={backgroundPolygons} />
      <RouteRenderer 
        routes={routes}
        isDraggable={isDraggable}
        onPointDragEnd={onPointDragEnd}
        onMarkerDragStart={handleMarkerDragStart}
        onMarkerDragEndPostProcess={handleMarkerDragEndPostProcess}
        onPointDelete={onPointDelete} // ルートポイント削除用
      />
    </Map>
  );
};


// ===================================================================
// ★ 3. APIProviderでラップする親コンポーネント (変更なし)
// ===================================================================
const GoogleMapViewer: React.FC<GoogleMapViewerProps> = (props) => {
  const { apiKey, ...innerMapProps } = props;

  if (!apiKey) {
    return <div style={{padding: '20px', color: 'red', textAlign: 'center'}}>Error: Google Maps API key is not provided.</div>;
  }

  return (
    <APIProvider apiKey={apiKey}>
      <InnerMap {...innerMapProps} />
    </APIProvider>
  );
};

export default GoogleMapViewer;