from django.db import models
from django.contrib.gis.db import models as gis_models
from django.contrib.gis.geos import Point, LineString
from django.contrib.gis.measure import D, Distance
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

class MinimalGeoModel(models.Model):
    name = models.CharField(max_length=100)
    location = gis_models.PointField(srid=4326, dim=3, null=True, blank=True)

    def __str__(self):
        return self.name

# 場所
class Place(models.Model):
    PLACE_TYPE_CHOICES = [
        ('airport', _('Airport')),
        ('golf_course', _('Golf course')),
        ('farm', _('Farm')),
        ('other', _('Other')),
    ]
    name = models.CharField(_("Place Name"), max_length=200)
    place_type = models.CharField(_("Place Type"), max_length=20, choices=PLACE_TYPE_CHOICES, default='other')
    center_lat = models.DecimalField(_("Center Latitude"), max_digits=10, decimal_places=8)
    center_lng = models.DecimalField(_("Center Longitude"), max_digits=11, decimal_places=8)
    initial_zoom = models.IntegerField(_("Initial Zoom Level"), default=15)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Place")
        verbose_name_plural = _("Places")
        ordering = ['name']

    def __str__(self):
        return self.name
    
    def get_place_type_display(self):
        """Returns a human-readable representation of the place type."""
        return dict(self.PLACE_TYPE_CHOICES).get(self.place_type, '')

# 車種
class CarType(models.Model):
    MOVE_TYPE_CHOICES = [
        ('wheels', _('Wheels')),
        ('crawler', _('Crawler')),
        ('other', _('Other')),
    ]
    type_name = models.CharField(_("Type Name"), max_length=100, unique=True)
    description = models.TextField(_("Description"), blank=True)
    # ルート計算やシミュレーションに必要な可能性のあるパラメータ
    width = models.DecimalField(_("Width (m)"), max_digits=5, decimal_places=2, null=True, blank=True)
    height = models.DecimalField(_("Height (m)"), max_digits=5, decimal_places=2, null=True, blank=True)
    length = models.DecimalField(_("Length (m)"), max_digits=5, decimal_places=2, null=True, blank=True)
    move_type = models.CharField(_("Move Type"), max_length=20, choices=MOVE_TYPE_CHOICES, default='wheels')
    cutting_width = models.DecimalField(_("Cutting Width (m)"), max_digits=5, decimal_places=2, null=True, blank=True)
    # curvature (曲率) や旋回半径 (turning radius) などのパラメータ
    curvature = models.DecimalField(_("Curvature (1/m)"), max_digits=5, decimal_places=4, null=True, blank=True)
    # 旋回半径 (turn
    turning_radius = models.DecimalField(_("Turning Radius (m)"), max_digits=5, decimal_places=2, null=True, blank=True)
    # 他の関連パラメータ...
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Car Type")
        verbose_name_plural = _("Car Types")
        ordering = ['type_name']

    def __str__(self):
        return self.type_name

# ルート
class Route(models.Model):
    ROUTE_TYPE_CHOICES = [
        ('automatic', _('Automatic Calculation')), # もし自動作成も保存するなら
        ('place_list', _('Place List (Line)')),
        ('place_list_ring', _('Place List (Ring)')),
    ]

    place = models.ForeignKey(Place, on_delete=models.CASCADE, related_name='routes', verbose_name=_("Place"))
    name = models.CharField(_("Route Name"), max_length=200)
    description = models.TextField(_("Description"), blank=True, null=True) # ★ description を追加

    # このルートが対象とする車種
    car_type = models.ForeignKey(CarType, on_delete=models.PROTECT, related_name='routes', verbose_name=_("Target Car Type"))

    # ルートの種類
    route_type = models.CharField(
        _("Route Type"),
        max_length=20,
        choices=ROUTE_TYPE_CHOICES,
        default='place_list'
    )

    source_area = models.ForeignKey(
        'RouteArea',
        on_delete=models.SET_NULL, # エリアが削除されてもルートは残す
        null=True,
        blank=True,
        related_name='generated_routes',
        verbose_name=_("Source Area"),
        help_text=_("The area definition from which this route was generated.")
    )
    
    # 2. source_data_nameのようなテキスト情報も残しておくと、
    #    PCアプリからのインポート時に便利かもしれない (オプション)
    source_info_text = models.CharField(
        _("Source Info Text"), 
        max_length=255, 
        blank=True,
        help_text=_("Information from the PC app, e.g., source data name or version.")
    )

    calculated_at = models.DateTimeField(_("Calculated At")) # ルート計算が完了した日時
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)
    # 必要であれば、ルートの総距離や推定所要時間なども追加
    # total_distance = models.DecimalField(...)
    # estimated_duration = models.DurationField(...)

    class Meta:
        verbose_name = _("Route")
        verbose_name_plural = _("Routes")
        ordering = ['-calculated_at']

    def __str__(self):
        return f"{self.name} ({self.place.name} for {self.car_type.type_name})"

    @property
    def is_in_use(self) -> bool:
        """
        このルートが現在、1台の車に割り当てられているかどうかを返す。
        Carモデルには 'assigned_route' というFKがあるため、OneToOneの逆参照と同じようにアクセスできる。
        """
        # related_nameは 'assigned_cars' (複数形) だが、
        # Car側にFKがあるので、このルートが割り当てられているCarは最大1台。
        # has-a 関係 (Car -> Route) の逆を調べる。
        # self.assigned_car というOneToOneの逆参照があればシンプルだが、
        # Car側にFKがあるので、Car.objects.filterで調べるのが確実。
        return Car.objects.filter(assigned_route=self).exists()

    @property
    def assigned_car(self):
        """

        このルートを割り当てられているCarオブジェクトを返す。なければNone。
        """
        # .first() を使うことで、該当がなければNone、あればそのオブジェクトを返す
        return Car.objects.filter(assigned_route=self).first()
   
# ルート経路点
class RoutePoint(models.Model):
    route = models.ForeignKey('Route', on_delete=models.CASCADE, related_name='points', verbose_name=_("Route"))
    sequence_number = models.PositiveIntegerField(_("Sequence Number"))
    
    # 緯度・経度・高度をまとめて格納する PointField
    # srid=4326 は WGS84 (GPSなどで使われる標準的な緯度経度)
    # dim=3 で3次元の点を指定 (X, Y, Z)
    location = gis_models.PointField(
        _("Location (Longitude, Latitude, Altitude)"),
        srid=4326,
        dim=3, # 3次元を指定 (経度, 緯度, 高度)
        null=True, # 高度情報がない場合も考慮するなら True
        blank=True # フォームでの入力を任意にする場合
    )

    # 追加フィールド
    aux_wp = models.BooleanField(_("Auxiliary Waypoint"), default=False, help_text=_("Is this an auxiliary waypoint?"))
    heading = models.IntegerField(_("Heading (degrees)"), null=True, blank=True, help_text=_("Vehicle heading at this point, if specified (0-359 degrees)."))
    is_direct_path = models.BooleanField(_("Direct Path to Next"), default=True, help_text=_("Should the path to the next point be a direct line?")) # "Direct"が予約語の可能性があるので変更
    blade_active = models.BooleanField(_("Blade Active"), default=False, help_text=_("Is the blade/tool active at this point?")) # "Blade"が予約語の可能性があるので変更

    # target_speed = models.DecimalField(...) # 必要であれば
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)

    class Meta:
        verbose_name = _("Route Point")
        verbose_name_plural = _("Route Points")
        unique_together = ('route', 'sequence_number')
        ordering = ['route', 'sequence_number']

    def __str__(self):
        location_str = "N/A"
        if self.location:
            lat = self.location.y
            lng = self.location.x
            alt_str = f", Alt: {self.location.z:.2f}m" if self.location.hasz and self.location.z is not None else ""
            location_str = f"Lat: {lat:.6f}, Lng: {lng:.6f}{alt_str}"
        return f"Point {self.sequence_number} for Route {self.route_id} ({location_str})"

    # (オプション) 緯度、経度、高度に個別にアクセスするためのプロパティ
    @property
    def latitude(self) -> float | None:
        return self.location.y if self.location else None

    @property
    def longitude(self) -> float | None:
        return self.location.x if self.location else None

    @property
    def altitude(self) -> float | None:
        return self.location.z if self.location and self.location.hasz else None

    # (オプション) 緯度、経度、高度をまとめて設定するメソッド
    def set_coordinates(self, longitude: float, latitude: float, altitude: float | None = None):
        if altitude is not None:
            self.location = Point(longitude, latitude, altitude, srid=4326)
        else:
            self.location = Point(longitude, latitude, srid=4326) # 高度なしの場合は2Dポイント

# 車両
class Car(models.Model):
    name = models.CharField(_("Car Name"), max_length=100, unique=True)

    # 車種
    car_type = models.ForeignKey(
        CarType,
        on_delete=models.PROTECT, # 車種が削除されても車は残るが、車種不明になる
        null=True,
        blank=True, # 車種が未設定の車も存在可能
        related_name='cars',
        verbose_name=_("Car Type")
    )

    # 所属基地 (Place)
    base_place = models.ForeignKey(
        Place,
        on_delete=models.SET_NULL, # 基地が削除されても車は残るが、所属不明になる
        null=True,
        blank=True,
        related_name='based_cars',
        verbose_name=_("Base Place")
    )

    # 割り当てられたルート (1台の車に1つのルート)
    assigned_route = models.ForeignKey(
        'Route',
        on_delete=models.SET_NULL, # ルートが削除されても車は残す
        null=True,                 # ルートが割り当てられていない車も存在OK
        blank=True,                # 管理画面やフォームで空欄を許可
        related_name='assigned_cars',
        verbose_name=_("Assigned Route")
    )

    # 割り当て状態 (CarRouteAssignmentから移動)
    ASSIGNMENT_STATUS_CHOICES = [
        ('none', _('None')),            # 未割り当て
        ('assigned', _('Assigned')),    # 割り当て済み (待機中)
        ('in_progress', _('In Progress')),# 実行中
        ('completed', _('Completed')),  # 完了
        ('failed', _('Failed')),        # 失敗
    ]
    assignment_status = models.CharField(
        _("Assignment Status"),
        max_length=20,
        choices=ASSIGNMENT_STATUS_CHOICES,
        default='none'
    )
    
    # 割り当てられた日時
    assigned_at = models.DateTimeField(_("Assigned At"), null=True, blank=True)
    # 実行開始日時
    started_at = models.DateTimeField(_("Started At"), null=True, blank=True)
    # 完了日時
    completed_at = models.DateTimeField(_("Completed At"), null=True, blank=True)

    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Car")
        verbose_name_plural = _("Cars")
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.car_type.type_name})"


# ===================================================================
# ★ 1. ルート生成エリアの定義 (新設)
# ===================================================================
class RouteArea(models.Model):
    """
    PCアプリでルートを生成するための作業エリアを定義するモデル。
    このエリア情報がJSONとしてエクスポートされる。
    """
    AREA_STATUS_CHOICES = [
        ('draft', _('Draft')),          # 作成中
        ('defined', _('Defined')),      # 定義完了・エクスポート可能
        ('archived', _('Archived')),    # 使用しない（アーカイブ済み）
    ]

    # --- 基本情報 ---
    name = models.CharField(
        _("Area Name"), 
        max_length=200,
        help_text=_("A unique name for this work area.")
    )
    description = models.TextField(
        _("Description"), 
        blank=True,
        help_text=_("Optional description of the area's purpose or characteristics.")
    )
    place = models.ForeignKey(
        'Place', 
        on_delete=models.CASCADE, 
        related_name='route_areas',
        verbose_name=_("Place"),
        help_text=_("The place this area belongs to.")
    )

    # --- 状態とバージョン管理 ---
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=AREA_STATUS_CHOICES,
        default='draft',
        help_text=_("The current status of this area definition.")
    )
    version = models.PositiveIntegerField(
        _("Version"),
        default=1,
        help_text=_("Version number, incremented on major changes.")
    )

    # --- PCアプリに渡すためのパラメータ ---
    # どのSourceDataセットをPCアプリで参照すべきかの情報（文字列として）
    # ForeignKeyではなく、あくまで情報として持たせる
    source_data_hint = models.CharField(
        _("Source Data Hint"),
        max_length=255,
        blank=True,
        help_text=_("Hint for the PC application, e.g., the name of the source data set to use (e.g., '2024-Q2 LiDAR').")
    )
    # PCアプリ側で考慮すべきパラメータなど
    generation_parameters = models.JSONField(
        _("Generation Parameters"),
        null=True, blank=True,
        help_text=_("Parameters for the PC route generation app, in JSON format (e.g., {'offset': 0.5, 'smoothing': 'medium'}).")
    )

    # --- タイムスタンプ ---
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)


    class Meta:
        verbose_name = _("Route Area")
        verbose_name_plural = _("Route Areas")
        ordering = ['place', '-updated_at']
        # 同じ場所で同じ名前のエリアは存在しないようにする制約
        unique_together = ('place', 'name')

    def __str__(self):
        return f"{self.name} (Place: {self.place.name})"

    def to_geojson_feature(self):
        """
        このエリアをGeoJSONのFeature形式に変換するヘルパーメソッド。
        エクスポート機能で利用する。
        """
        points = self.points.order_by('sequence_number').all()
        if not points:
            return None
        
        # Polygonの座標リストを作成 (最初の点を最後にも追加して閉じる)
        coordinates = [[p.location.x, p.location.y] for p in points]
        if len(coordinates) > 2:
            coordinates.append(coordinates[0])

        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [coordinates] # GeoJSON Polygonは三重の配列
            },
            "properties": {
                "area_id": self.id,
                "area_name": self.name,
                "place_name": self.place.name,
                "description": self.description,
                "version": self.version,
                "source_data_hint": self.source_data_hint,
                "generation_parameters": self.generation_parameters,
                # 既存ルートを上書きするためのヒントも追加可能
                # "target_route_id": self.target_route.id if hasattr(self, 'target_route') else None
            }
        }
        return feature

# ===================================================================
# ★ 2. エリアの頂点 (新設)
# ===================================================================
class AreaPoint(models.Model):
    """
    RouteAreaを構成する頂点を表すモデル。
    """
    area = models.ForeignKey(
        RouteArea, 
        on_delete=models.CASCADE, 
        related_name='points',
        verbose_name=_("Area")
    )
    # To avoid error, use dim=3 with alt==0
    location = gis_models.PointField(
        _("Location (Longitude, Latitude)"),
        srid=4326,
        dim=3,
        help_text=_("A vertex point of the area polygon.")
    )
    sequence_number = models.PositiveIntegerField(
        _("Sequence Number"),
        help_text=_("The order of the vertex in the polygon.")
    )

    class Meta:
        verbose_name = _("Area Point")
        verbose_name_plural = _("Area Points")
        # 1つのエリア内で同じシーケンス番号は存在しない
        unique_together = ('area', 'sequence_number')
        ordering = ['area', 'sequence_number']

    def __str__(self):
        return f"Point {self.sequence_number} for Area {self.area.name}"
