import heapq
from typing import Dict, List, Tuple, Optional
import math

class RoadGraph:
    '''Simplified UK road network graph for shortest path calculation'''
    
    def __init__(self):
        # In production, load from OSM data or road network API
        # This is a simplified grid-based approach
        self.nodes = {}
        self.edges = {}
    
    def add_node(self, node_id: str, lat: float, lng: float):
        self.nodes[node_id] = (lat, lng)
    
    def add_edge(self, from_node: str, to_node: str, weight: float):
        if from_node not in self.edges:
            self.edges[from_node] = []
        self.edges[from_node].append((to_node, weight))
    
    def get_nearest_node(self, lat: float, lng: float) -> Optional[str]:
        '''Find nearest graph node to given coordinates'''
        if not self.nodes:
            return None
        
        min_dist = float('inf')
        nearest = None
        
        for node_id, (node_lat, node_lng) in self.nodes.items():
            dist = self._haversine_distance(lat, lng, node_lat, node_lng)
            if dist < min_dist:
                min_dist = dist
                nearest = node_id
        
        return nearest
    
    def _haversine_distance(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        '''Calculate distance in km between two coordinates'''
        R = 6371  # Earth radius in km
        
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        
        a = (math.sin(dlat / 2) ** 2 + 
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * 
             math.sin(dlng / 2) ** 2)
        c = 2 * math.asin(math.sqrt(a))
        
        return R * c
    
    def dijkstra(self, start_node: str, end_node: str) -> Tuple[float, List[str]]:
        '''
        Run Dijkstra's algorithm to find shortest path
        Returns: (total_distance, path)
        '''
        if start_node not in self.edges:
            # Direct distance if no path exists
            if start_node in self.nodes and end_node in self.nodes:
                dist = self._haversine_distance(
                    *self.nodes[start_node],
                    *self.nodes[end_node]
                )
                return (dist, [start_node, end_node])
            return (float('inf'), [])
        
        distances = {node: float('inf') for node in self.nodes}
        distances[start_node] = 0
        previous = {node: None for node in self.nodes}
        
        pq = [(0, start_node)]
        visited = set()
        
        while pq:
            current_dist, current_node = heapq.heappop(pq)
            
            if current_node in visited:
                continue
            
            visited.add(current_node)
            
            if current_node == end_node:
                break
            
            if current_node not in self.edges:
                continue
            
            for neighbor, weight in self.edges[current_node]:
                distance = current_dist + weight
                
                if distance < distances[neighbor]:
                    distances[neighbor] = distance
                    previous[neighbor] = current_node
                    heapq.heappush(pq, (distance, neighbor))
        
        # Reconstruct path
        path = []
        current = end_node
        while current is not None:
            path.append(current)
            current = previous[current]
        path.reverse()
        
        return (distances[end_node], path)

# Simplified graph for demonstration
# In production, use real road network data
def create_uk_road_graph() -> RoadGraph:
    '''Create a simplified UK road network graph'''
    graph = RoadGraph()
    
    # Major UK cities as nodes (simplified)
    cities = {
        "london": (51.5074, -0.1278),
        "birmingham": (52.4862, -1.8904),
        "manchester": (53.4808, -2.2426),
        "leeds": (53.8008, -1.5491),
        "glasgow": (55.8642, -4.2518),
        "liverpool": (53.4084, -2.9916),
        "bristol": (51.4545, -2.5879),
        "sheffield": (53.3811, -1.4701),
        "edinburgh": (55.9533, -3.1883),
        "cardiff": (51.4816, -3.1791)
    }
    
    for city, (lat, lng) in cities.items():
        graph.add_node(city, lat, lng)
    
    # Add edges with approximate distances
    edges = [
        ("london", "birmingham", 160),
        ("london", "bristol", 172),
        ("birmingham", "manchester", 134),
        ("birmingham", "bristol", 145),
        ("manchester", "leeds", 67),
        ("manchester", "liverpool", 56),
        ("leeds", "sheffield", 58),
        ("glasgow", "edinburgh", 75),
        ("manchester", "glasgow", 346),
    ]
    
    for from_city, to_city, distance in edges:
        graph.add_edge(from_city, to_city, distance)
        graph.add_edge(to_city, from_city, distance)
    
    return graph

def calculate_travel_distance(start_lat: float, start_lng: float, 
                              end_lat: float, end_lng: float) -> float:
    '''
    Calculate approximate road distance between two points
    In production, use Google Maps Distance Matrix API or similar
    '''
    graph = create_uk_road_graph()
    
    start_node = graph.get_nearest_node(start_lat, start_lng)
    end_node = graph.get_nearest_node(end_lat, end_lng)
    
    if start_node and end_node:
        distance, _ = graph.dijkstra(start_node, end_node)
        return distance
    
    # Fallback to haversine if graph fails
    R = 6371
    dlat = math.radians(end_lat - start_lat)
    dlng = math.radians(end_lng - start_lng)
    a = (math.sin(dlat / 2) ** 2 + 
         math.cos(math.radians(start_lat)) * math.cos(math.radians(end_lat)) * 
         math.sin(dlng / 2) ** 2)
    c = 2 * math.asin(math.sqrt(a))
    return R * c * 1.3  # Apply road factor