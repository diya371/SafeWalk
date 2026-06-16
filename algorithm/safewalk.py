import osmnx as ox
import networkx as nx
import numpy as np
import pandas as pd
from math import radians, sin, cos, sqrt, atan2
import os
import pickle

# Load crime data from CSV
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
safety_data = pd.read_csv(os.path.join(BASE_DIR, "final_dataset.csv"))
CACHE_FILE = os.path.join(BASE_DIR, "delhi_graph_cache.pkl")


def get_crime_score(lat, lon):
    """Find nearest area and return its crime score"""
    min_dist = float('inf')
    nearest_crime = 5.0  # default if nothing found

    for _, row in safety_data.iterrows():
        # Calculate distance between road and area center
        dlat = radians(lat - row['lat'])
        dlon = radians(lon - row['lon'])
        a = sin(dlat/2)**2 + cos(radians(lat)) * cos(radians(row['lat'])) * sin(dlon/2)**2
        dist = 6371 * 2 * atan2(sqrt(a), sqrt(1-a))  # distance in km

        if dist < min_dist:
            min_dist = dist
            nearest_crime = row['crime_rate']

    return round(nearest_crime / 10.0, 4)  # normalize to 0-1


def get_crowd_score():
    """More people = safer. Based on time of day."""
    hour = pd.Timestamp.now().hour

    if 8 <= hour <= 11 or 17 <= hour <= 21:
        return 0.2   # rush hours - lots of people - safer
    elif 12 <= hour <= 16:
        return 0.5   # afternoon - medium
    else:
        return 0.8   # night - less people - unsafe


def load_graph(city="Delhi, India"):
    """Load only the queried area (lighter memory footprint)"""
    global CACHE_FILE
    
    # Try loading from cache first
    if os.path.exists(CACHE_FILE):
        print("Loading cached graph...")
        with open(CACHE_FILE, 'rb') as f:
            G = pickle.load(f)
        print("Graph loaded from cache! ✅")
        return G
    
    # If no cache, download a SMALLER area to save memory
    print(f"Loading {city} map (optimized for memory)...")
    
    try:
        # Try full city first
        G = ox.graph_from_place(city, network_type="walk")
    except Exception as e:
        print(f"Full city too large, using bounding box: {e}")
        # Fallback: use smaller area (Delhi center)
        north, south, east, west = 28.75, 28.45, 77.35, 77.05
        G = ox.graph_from_bbox(north, south, east, west, network_type="walk")

    for u, v, data in G.edges(data=True):
        # Get middle point of this road
        lat = (G.nodes[u]['y'] + G.nodes[v]['y']) / 2
        lon = (G.nodes[u]['x'] + G.nodes[v]['x']) / 2

        # Get all 3 scores
        crime_score = get_crime_score(lat, lon)
        crowd_score = get_crowd_score()

        # Lighting from OpenStreetMap
        lit = data.get('lit', 'no')
        if lit == 'yes':
            lighting_score = 1.0
        elif lit == 'limited':
            lighting_score = 0.5
        else:
            lighting_score = 0.0

        # Final safety weight — lower = safer
        # Safety weight formula: crime dominates at 0.6 weight (real govt data)
    # Lighting from OSM tags, crowd from time-of-day, length as tiebreaker

        data['safety_weight'] = round(
            (0.6 * crime_score) +
            (0.2 * (1 - lighting_score)) +
            (0.1 * crowd_score) +
            (0.1 * min(data.get('length', 100) / 500, 1.0)),
            4
        )

    # Save to cache for future runs
    try:
        with open(CACHE_FILE, 'wb') as f:
            pickle.dump(G, f)
        print(f"Graph cached ✅")
    except Exception as e:
        print(f"Warning: Could not save cache: {e}")

    print("Map ready! ✅")
    return G


def get_safest_route(start_lat, start_lon, end_lat, end_lon, G):
    """Given start and end coordinates, return the safest walking route"""

    start_node = ox.nearest_nodes(G, start_lon, start_lat)
    end_node = ox.nearest_nodes(G, end_lon, end_lat)

    safest_path = nx.dijkstra_path(G, start_node, end_node, weight='safety_weight')

    # Calculate average safety score of the route
    total_safety = 0
    total_distance = 0  # in meters
    
    for i in range(len(safest_path) - 1):
        u = safest_path[i]
        v = safest_path[i + 1]
        edge_data = G.get_edge_data(u, v)
        if edge_data:
            total_safety += edge_data[0].get('safety_weight', 0.5)
            total_distance += edge_data[0].get('length', 0)  # length in meters

    avg_safety = total_safety / max(len(safest_path) - 1, 1)

    # Convert to score out of 10 (lower weight = safer = higher score)
    safety_score = round((1 - avg_safety) * 10, 1)

    # Calculate time (average walking speed: 1.4 m/s = 5 km/h)
    walking_speed = 1.4  # meters per second
    time_minutes = round(total_distance / walking_speed / 60, 1)

    # Convert node IDs to coordinates
    coordinates = []
    for node in safest_path:
        coordinates.append({
            "lat": G.nodes[node]['y'],
            "lon": G.nodes[node]['x']
        })

    return {
        "start": {"lat": start_lat, "lon": start_lon},
        "end": {"lat": end_lat, "lon": end_lon},
        "total_stops": len(coordinates),
        "safety_score": safety_score,
        "distance_m": round(total_distance, 1),  # distance in meters
        "distance_km": round(total_distance / 1000, 2),  # distance in kilometers
        "time_minutes": time_minutes,
        "route": coordinates
    }


# Test
if __name__ == "__main__":
    G = load_graph()

    result = get_safest_route(
        start_lat=28.5447, start_lon=77.1642,  # JNU
        end_lat=28.6139, end_lon=77.2090,       # Connaught Place
        G=G
    )

    print("\nRoute Found! ✅")
    print("Total stops:", result['total_stops'])
    print("Safety Score:", result['safety_score'], "/ 10")
    print("First 3 coordinates:", result['route'][:3])
