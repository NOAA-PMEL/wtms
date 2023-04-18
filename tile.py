import math
import shapely.geometry

class Tile:
    def __init__(self, zoom, x, y):
        self.zoom = int(zoom)
        self.x = int(x)
        self.y = int(y)
        tile_count = 2**int(self.zoom)
        if int(self.x) > (tile_count - 1) or int(self.y) > (tile_count - 1):
            print("Tile at "+str(x)+","+str(y)+"does not exist at zoom level "+str(zoom))

        self.lon_width = 360.0 / tile_count
        self.lon = -180.0 + self.x * self.lon_width
        self.lat_height = -2.0 / tile_count
        self.lat = 1.0 + self.y * self.lat_height

        # convert self.lat and lat_height to degrees in a transverse mercator projection
        # note that in fact the coordinates go from about -85 to +85 not -90 to 90!
        self.lat_height = self.lat_height + self.lat;
        self.lat_height = (2.0 * math.atan(math.exp(math.pi * self.lat_height))) - (math.pi / 2.0)
        self.lat_height = self.lat_height * (180.0 / math.pi)

        self.lat = (2.0 * math.atan(math.exp(math.pi * self.lat))) - (math.pi / 2.0)
        self.lat *= (180.0 / math.pi)

        self.lat_height = self.lat_height - self.lat

        if self.lon_width < 0.0:
            self.lon = self.lon + self.lon_width
            self.lon_width = -self.lon_width

        if self.lat_height < 0.0:
            self.lat = self.lat + self.lat_height
            self.lat_height = -self.lat_height

        self.box = shapely.geometry.box(self.lon, self.lat, self.lon+self.lon_width, self.lat+self.lat_height)

    



